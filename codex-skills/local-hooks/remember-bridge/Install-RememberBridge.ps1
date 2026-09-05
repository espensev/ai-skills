[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory = $false)]
    [string] $TargetRoot = 'D:\DevHome\state\remember\bridge',

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

# Installs the Grok/Kimi Remember bridge into the DevHome Remember state root.
# Hook commands in Grok (~/.grok/hooks/remember.json) and Kimi
# (~/.kimi-code/config.toml [[hooks]]) point at the installed copy under
# <TargetRoot>\bin, never at this repository checkout. Bare invocation installs
# (or reports UNCHANGED); -Check only compares.

$ErrorActionPreference = 'Stop'

$PackageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$DefaultTargetRoot = 'D:\DevHome\state\remember\bridge'
$OwnedFiles = @('Invoke-RememberBridge.py')

function Assert-VerifiedMachine {
    if (-not (Test-Path -LiteralPath $VerifierPath -PathType Leaf)) {
        throw "Machine verifier is missing: $VerifierPath"
    }

    $identity = & $VerifierPath
    if ($null -eq $identity) {
        throw 'Machine verifier returned no identity.'
    }
    $identity = @($identity)[-1]
    if (
        $identity.status -cne 'VERIFIED' -or
        $identity.machineId -cne $ExpectedMachineId -or
        $identity.instanceId -cne $ExpectedInstallationId
    ) {
        throw "Machine identity mismatch. Expected VERIFIED $ExpectedMachineId/$ExpectedInstallationId."
    }

    return $identity
}

function Get-BridgeDrift {
    param([Parameter(Mandatory)][string] $BinRoot)

    $drift = New-Object System.Collections.Generic.List[string]
    foreach ($fileName in $OwnedFiles) {
        $sourcePath = Join-Path $PackageRoot $fileName
        $targetPath = Join-Path $BinRoot $fileName
        if (-not (Test-Path -LiteralPath $targetPath -PathType Leaf)) {
            $drift.Add("missing: $targetPath")
            continue
        }
        $sourceHash = (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash
        $targetHash = (Get-FileHash -LiteralPath $targetPath -Algorithm SHA256).Hash
        if ($sourceHash -cne $targetHash) {
            $drift.Add("hash mismatch: $targetPath")
        }
    }
    return $drift
}

function Invoke-BridgeProbe {
    param([Parameter(Mandatory)][string] $ScriptPath)

    $launcher = Get-Command -Name 'py' -ErrorAction SilentlyContinue
    if ($null -eq $launcher) {
        return @('probe skipped: the py launcher is not on PATH (hook commands use `py -3`)')
    }
    try {
        $output = & $launcher.Source -3 $ScriptPath 2>&1
        return @($output | ForEach-Object { [string] $_ })
    } catch {
        return @("probe failed: $($_.Exception.Message)")
    }
}

foreach ($fileName in $OwnedFiles) {
    $sourcePath = Join-Path $PackageRoot $fileName
    if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
        throw "Source bridge file is missing: $sourcePath"
    }
}

$ResolvedTargetRoot = [System.IO.Path]::GetFullPath(
    [Environment]::ExpandEnvironmentVariables($TargetRoot)
).TrimEnd(
    [System.IO.Path]::DirectorySeparatorChar,
    [System.IO.Path]::AltDirectorySeparatorChar
)
$targetPathRoot = [System.IO.Path]::GetPathRoot($ResolvedTargetRoot).TrimEnd(
    [System.IO.Path]::DirectorySeparatorChar,
    [System.IO.Path]::AltDirectorySeparatorChar
)
if ($ResolvedTargetRoot -ceq $targetPathRoot) {
    throw "Refusing to use a filesystem root as the bridge target: $ResolvedTargetRoot"
}
$resolvedDefaultTargetRoot = [System.IO.Path]::GetFullPath($DefaultTargetRoot).TrimEnd(
    [System.IO.Path]::DirectorySeparatorChar,
    [System.IO.Path]::AltDirectorySeparatorChar
)
if (
    -not [string]::Equals(
        $ResolvedTargetRoot,
        $resolvedDefaultTargetRoot,
        [System.StringComparison]::OrdinalIgnoreCase
    ) -and
    -not $AllowTestOnlyTargetRootOverride
) {
    throw "Refusing alternate bridge target '$ResolvedTargetRoot'; the bridge is pinned to the DevHome Remember root '$resolvedDefaultTargetRoot'. Use the test-only override switch for disposable targets."
}

$BinRoot = Join-Path $ResolvedTargetRoot 'bin'
$InitialDrift = @(Get-BridgeDrift -BinRoot $BinRoot)

if ($Check) {
    if ($InitialDrift.Count -gt 0) {
        throw "Installed Remember bridge drift: $($InitialDrift -join '; ')"
    }

    [pscustomobject]@{
        Status = 'CURRENT'
        Source = $PackageRoot
        Target = $BinRoot
        Files = $OwnedFiles.Count
    }
    return
}

$identity = Assert-VerifiedMachine
if ($InitialDrift.Count -eq 0) {
    [pscustomobject]@{
        Status = 'UNCHANGED'
        MachineId = $identity.machineId
        Source = $PackageRoot
        Target = $BinRoot
        Backup = $null
        Files = $OwnedFiles.Count
        Probe = Invoke-BridgeProbe -ScriptPath (Join-Path $BinRoot $OwnedFiles[0])
    }
    return
}

if (-not $PSCmdlet.ShouldProcess($BinRoot, 'Install the Grok/Kimi Remember bridge')) {
    return
}

$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
$backupRoot = Join-Path (Join-Path $ResolvedTargetRoot 'bin-backups') $timestamp
$backedUp = $false
foreach ($fileName in $OwnedFiles) {
    $existingPath = Join-Path $BinRoot $fileName
    if (Test-Path -LiteralPath $existingPath -PathType Leaf) {
        New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
        Copy-Item -LiteralPath $existingPath -Destination (Join-Path $backupRoot $fileName) -Force
        $backedUp = $true
    }
}

New-Item -ItemType Directory -Path $BinRoot -Force | Out-Null
foreach ($fileName in $OwnedFiles) {
    Copy-Item -LiteralPath (Join-Path $PackageRoot $fileName) -Destination (Join-Path $BinRoot $fileName) -Force
}

$FinalDrift = @(Get-BridgeDrift -BinRoot $BinRoot)
if ($FinalDrift.Count -gt 0) {
    throw "Remember bridge install left drift: $($FinalDrift -join '; ')"
}

[pscustomobject]@{
    Status = 'INSTALLED'
    MachineId = $identity.machineId
    Source = $PackageRoot
    Target = $BinRoot
    Backup = $(if ($backedUp) { $backupRoot } else { $null })
    Files = $OwnedFiles.Count
    Probe = Invoke-BridgeProbe -ScriptPath (Join-Path $BinRoot $OwnedFiles[0])
}
