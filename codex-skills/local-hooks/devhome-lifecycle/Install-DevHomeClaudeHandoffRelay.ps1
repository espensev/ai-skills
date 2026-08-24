[CmdletBinding(SupportsShouldProcess)]
[Diagnostics.CodeAnalysis.SuppressMessageAttribute(
    'PSReviewUnusedParameter',
    '',
    Justification = 'Script parameters are consumed by script-scoped helper functions.'
)]
param(
    [Parameter(Mandatory = $false)]
    [string] $TargetRoot = 'D:\DevHome\state\claude',

    [Parameter(Mandatory = $false)]
    [switch] $AllowTestOnlyTargetRootOverride,

    [Parameter(Mandatory = $false)]
    [switch] $Check,

    [Parameter(Mandatory = $false)]
    [string] $VerifierPath = $(
        Join-Path `
            ([Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData)) `
            'common_dev\v2\Test-LocalMachineIdentity.ps1'
    ),

    [Parameter(Mandatory = $false)]
    [string] $ExpectedMachineId = 'snd-desk',

    [Parameter(Mandatory = $false)]
    [string] $ExpectedInstallationId = 'ca96d510-7d87-4cec-8e1a-bd8fc3866903'
)

$ErrorActionPreference = 'Stop'

$PackageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$SourceHookPath = Join-Path $PackageRoot 'hooks\Invoke-HandoffRelay.ps1'
$DefaultRuntimeRoot = 'D:\DevHome\state\claude'
$HookRelativePath = 'hooks\Invoke-HandoffRelay.ps1'
$StatusMessage = 'Handoff Relay: preparing next-session context'

function Resolve-NormalizedPath {
    param([Parameter(Mandatory)][string] $Path)

    $expanded = [Environment]::ExpandEnvironmentVariables($Path)
    if ($expanded.StartsWith('\\?\UNC\', [System.StringComparison]::OrdinalIgnoreCase)) {
        $expanded = '\\' + $expanded.Substring(8)
    }
    elseif ($expanded.StartsWith('\\?\', [System.StringComparison]::OrdinalIgnoreCase)) {
        $expanded = $expanded.Substring(4)
    }

    return [System.IO.Path]::GetFullPath($expanded).TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    )
}

function Get-ExpectedCommand {
    param([Parameter(Mandatory)][string] $ResolvedTargetRoot)

    $hookPath = (Join-Path $ResolvedTargetRoot $HookRelativePath) -replace '\\', '/'
    return "pwsh -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$hookPath`" -Provider Claude"
}

function Get-LegacyOwnedCommand {
    param([Parameter(Mandatory)][string] $ResolvedTargetRoot)

    $hookPath = (Join-Path $ResolvedTargetRoot $HookRelativePath) -replace '\\', '/'
    return @(
        "pwsh -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$hookPath`""
    )
}

function ConvertTo-NormalizedCommand {
    param([Parameter(Mandatory)][string] $Command)

    return (($Command.Trim() -replace '\\', '/') -replace '\s+', ' ')
}

function Test-OwnedHandler {
    param(
        [object] $Handler,
        [Parameter(Mandatory)][string[]] $OwnedCommands
    )

    if ($null -eq $Handler -or [string]::IsNullOrWhiteSpace([string] $Handler.command)) {
        return $false
    }

    $candidate = ConvertTo-NormalizedCommand -Command ([string] $Handler.command)
    foreach ($ownedCommand in $OwnedCommands) {
        if ([string]::Equals(
            $candidate,
            (ConvertTo-NormalizedCommand -Command $ownedCommand),
            [System.StringComparison]::OrdinalIgnoreCase
        )) {
            return $true
        }
    }

    return $false
}

function Read-HookConfiguration {
    param([Parameter(Mandatory)][string] $SettingsPath)

    if (-not (Test-Path -LiteralPath $SettingsPath -PathType Leaf)) {
        return [pscustomobject] ([ordered]@{})
    }

    return Get-Content -Raw -LiteralPath $SettingsPath |
        ConvertFrom-Json -Depth 100 -ErrorAction Stop
}

function Get-RegistrationDrift {
    param(
        [Parameter(Mandatory)][object] $Settings,
        [Parameter(Mandatory)][string] $ExpectedCommand,
        [Parameter(Mandatory)][string[]] $OwnedCommands
    )

    $stopGroups = if (
        $null -ne $Settings.PSObject.Properties['hooks'] -and
        $null -ne $Settings.hooks.PSObject.Properties['Stop']
    ) {
        @($Settings.hooks.Stop)
    }
    else {
        @()
    }
    $ownedHandlers = @(
        foreach ($group in @($stopGroups | Where-Object { $null -ne $_ })) {
            foreach ($handler in @($group.hooks)) {
                if (Test-OwnedHandler -Handler $handler -OwnedCommands $OwnedCommands) {
                    $handler
                }
            }
        }
    )
    if ($ownedHandlers.Count -ne 1) {
        return "expected one Handoff Relay registration, found $($ownedHandlers.Count)"
    }

    $handler = $ownedHandlers[0]
    $drift = [System.Collections.Generic.List[string]]::new()
    if ([string] $handler.type -cne 'command') {
        $drift.Add('handler type differs')
    }
    if ([string] $handler.command -cne $ExpectedCommand) {
        $drift.Add('handler command differs')
    }
    if ([int] $handler.timeout -ne 5) {
        $drift.Add('handler timeout differs')
    }
    if ([string] $handler.statusMessage -cne $StatusMessage) {
        $drift.Add('handler status message differs')
    }
    if ($handler.async -eq $true) {
        $drift.Add('handler must be synchronous')
    }

    return @($drift)
}

function Get-HookDrift {
    param([Parameter(Mandatory)][string] $ResolvedTargetRoot)

    $drift = [System.Collections.Generic.List[string]]::new()
    $targetHookPath = Join-Path $ResolvedTargetRoot $HookRelativePath
    $settingsPath = Join-Path $ResolvedTargetRoot 'settings.json'

    if (-not (Test-Path -LiteralPath $targetHookPath -PathType Leaf)) {
        $drift.Add("$HookRelativePath missing")
    }
    else {
        $sourceHash = (Get-FileHash -LiteralPath $SourceHookPath -Algorithm SHA256).Hash
        $targetHash = (Get-FileHash -LiteralPath $targetHookPath -Algorithm SHA256).Hash
        if ($sourceHash -cne $targetHash) {
            $drift.Add("$HookRelativePath differs")
        }
    }

    try {
        $settings = Read-HookConfiguration -SettingsPath $settingsPath
        foreach ($registrationDrift in @(
            Get-RegistrationDrift `
                -Settings $settings `
                -ExpectedCommand (Get-ExpectedCommand -ResolvedTargetRoot $ResolvedTargetRoot) `
                -OwnedCommands @(
                    Get-ExpectedCommand -ResolvedTargetRoot $ResolvedTargetRoot
                    Get-LegacyOwnedCommand -ResolvedTargetRoot $ResolvedTargetRoot
                )
        )) {
            $drift.Add("settings.json $registrationDrift")
        }
    }
    catch {
        $drift.Add('settings.json is not valid JSON')
    }

    return @($drift)
}

function ConvertTo-HandoffRelayRegistration {
    param(
        [Parameter(Mandatory)][object] $Settings,
        [Parameter(Mandatory)][string] $ExpectedCommand,
        [Parameter(Mandatory)][string[]] $OwnedCommands
    )

    if ($null -eq $Settings.PSObject.Properties['hooks']) {
        $Settings | Add-Member -MemberType NoteProperty -Name hooks -Value ([pscustomobject] ([ordered]@{}))
    }

    $preservedGroups = [System.Collections.Generic.List[object]]::new()
    $stopGroups = if ($null -ne $Settings.hooks.PSObject.Properties['Stop']) {
        @($Settings.hooks.Stop)
    }
    else {
        @()
    }
    foreach ($group in @($stopGroups | Where-Object { $null -ne $_ })) {
        $remainingHandlers = @(
            foreach ($handler in @($group.hooks)) {
                if (-not (Test-OwnedHandler -Handler $handler -OwnedCommands $OwnedCommands)) {
                    $handler
                }
            }
        )
        if ($remainingHandlers.Count -eq 0) {
            continue
        }

        $group.hooks = [object[]] $remainingHandlers
        $preservedGroups.Add($group)
    }

    $ownedGroup = [pscustomobject] ([ordered]@{
        hooks = [object[]] @(
            [pscustomobject] ([ordered]@{
                type = 'command'
                command = $ExpectedCommand
                timeout = 5
                statusMessage = $StatusMessage
            })
        )
    })
    $preservedGroups.Add($ownedGroup)

    if ($null -eq $Settings.hooks.PSObject.Properties['Stop']) {
        $Settings.hooks | Add-Member `
            -MemberType NoteProperty `
            -Name Stop `
            -Value ([object[]] $preservedGroups.ToArray())
    }
    else {
        $Settings.hooks.Stop = [object[]] $preservedGroups.ToArray()
    }

    return $Settings
}

function Assert-VerifiedMachine {
    if (-not (Test-Path -LiteralPath $VerifierPath -PathType Leaf)) {
        throw "Machine verifier is missing: $VerifierPath"
    }

    $identity = @(& $VerifierPath)[-1]
    if (
        $null -eq $identity -or
        $identity.status -cne 'VERIFIED' -or
        $identity.machineId -cne $ExpectedMachineId -or
        $identity.instanceId -cne $ExpectedInstallationId
    ) {
        throw "Machine identity mismatch. Expected VERIFIED $ExpectedMachineId/$ExpectedInstallationId."
    }

    return $identity
}

if (-not (Test-Path -LiteralPath $SourceHookPath -PathType Leaf)) {
    throw "Handoff Relay source hook is missing: $SourceHookPath"
}

$ResolvedTargetRoot = Resolve-NormalizedPath -Path $TargetRoot
$targetPathRoot = [System.IO.Path]::GetPathRoot($ResolvedTargetRoot).TrimEnd(
    [System.IO.Path]::DirectorySeparatorChar,
    [System.IO.Path]::AltDirectorySeparatorChar
)
if ($ResolvedTargetRoot -ceq $targetPathRoot) {
    throw "Refusing to use a filesystem root as the Claude target: $ResolvedTargetRoot"
}
$resolvedDefaultRuntimeRoot = Resolve-NormalizedPath -Path $DefaultRuntimeRoot
if (
    -not [string]::Equals(
        $ResolvedTargetRoot,
        $resolvedDefaultRuntimeRoot,
        [System.StringComparison]::OrdinalIgnoreCase
    ) -and
    -not $AllowTestOnlyTargetRootOverride
) {
    throw "Refusing alternate hook target '$ResolvedTargetRoot'; Handoff Relay is pinned to the physical DevHome Claude root '$resolvedDefaultRuntimeRoot'. Use the test-only override only for isolated tests."
}

$InitialDrift = @(Get-HookDrift -ResolvedTargetRoot $ResolvedTargetRoot)
if ($Check) {
    if ($InitialDrift.Count -gt 0) {
        throw "Installed Claude Handoff Relay drift: $($InitialDrift -join '; ')"
    }

    [pscustomobject]@{
        Status = 'CURRENT'
        Source = $PackageRoot
        Target = $ResolvedTargetRoot
        Files = 2
    }
    return
}

$identity = Assert-VerifiedMachine
if ($InitialDrift.Count -eq 0) {
    [pscustomobject]@{
        Status = 'UNCHANGED'
        MachineId = $identity.machineId
        Source = $PackageRoot
        Target = $ResolvedTargetRoot
        Backup = $null
        Files = 2
    }
    return
}

if (-not $PSCmdlet.ShouldProcess($ResolvedTargetRoot, 'Install Claude Handoff Relay')) {
    return
}

$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
$backupRoot = Join-Path (Join-Path $ResolvedTargetRoot 'hook-backups\handoff-relay') $timestamp
$settingsPath = Join-Path $ResolvedTargetRoot 'settings.json'
$targetHookPath = Join-Path $ResolvedTargetRoot $HookRelativePath
$backupCreated = $false
foreach ($existingPath in @($settingsPath, $targetHookPath)) {
    if (-not (Test-Path -LiteralPath $existingPath -PathType Leaf)) {
        continue
    }

    $relativePath = [System.IO.Path]::GetRelativePath($ResolvedTargetRoot, $existingPath)
    $backupPath = Join-Path $backupRoot $relativePath
    $null = New-Item -ItemType Directory -Path (Split-Path -Parent $backupPath) -Force
    Copy-Item -LiteralPath $existingPath -Destination $backupPath -Force
    $backupCreated = $true
}

$null = New-Item -ItemType Directory -Path $ResolvedTargetRoot,(Split-Path -Parent $targetHookPath) -Force
Copy-Item -LiteralPath $SourceHookPath -Destination $targetHookPath -Force

$settings = Read-HookConfiguration -SettingsPath $settingsPath
$settings = ConvertTo-HandoffRelayRegistration `
    -Settings $settings `
    -ExpectedCommand (Get-ExpectedCommand -ResolvedTargetRoot $ResolvedTargetRoot) `
    -OwnedCommands @(
        Get-ExpectedCommand -ResolvedTargetRoot $ResolvedTargetRoot
        Get-LegacyOwnedCommand -ResolvedTargetRoot $ResolvedTargetRoot
    )
$renderedSettings = ($settings | ConvertTo-Json -Depth 100) + [Environment]::NewLine
$tempSettingsPath = Join-Path $ResolvedTargetRoot ('.settings.handoff-relay.{0}.{1}.tmp' -f $PID, [guid]::NewGuid().ToString('N'))
$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
try {
    [System.IO.File]::WriteAllText($tempSettingsPath, $renderedSettings, $utf8NoBom)
    $null = Get-Content -Raw -LiteralPath $tempSettingsPath |
        ConvertFrom-Json -Depth 100 -ErrorAction Stop
    Move-Item -LiteralPath $tempSettingsPath -Destination $settingsPath -Force
}
finally {
    if (Test-Path -LiteralPath $tempSettingsPath -PathType Leaf) {
        Remove-Item -LiteralPath $tempSettingsPath -Force
    }
}

$RemainingDrift = @(Get-HookDrift -ResolvedTargetRoot $ResolvedTargetRoot)
if ($RemainingDrift.Count -gt 0) {
    throw "Claude Handoff Relay installation did not converge: $($RemainingDrift -join '; ')"
}

[pscustomobject]@{
    Status = 'INSTALLED'
    MachineId = $identity.machineId
    Source = $PackageRoot
    Target = $ResolvedTargetRoot
    Backup = if ($backupCreated) { $backupRoot } else { $null }
    Files = 2
    NewSessionRequired = $true
}
