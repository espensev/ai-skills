[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory = $false)]
    [string] $TargetRoot = $(
        if ([string]::IsNullOrWhiteSpace($env:CODEX_HOME)) {
            'D:\DevHome\state\codex'
        }
        else {
            $env:CODEX_HOME
        }
    ),

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
$SourceHooksRoot = Join-Path $PackageRoot 'hooks'
$SourceConfigPath = Join-Path $PackageRoot 'hooks.json'
$DefaultRuntimeRoot = 'D:\DevHome\state\codex'
$OwnedHookFiles = @(
    'Invoke-DevHomeHook.ps1',
    'Invoke-RememberAdapter.cmd',
    'Invoke-RememberAdapter.py',
    'Invoke-RememberClaude.cmd'
)

function ConvertTo-JsonPathText {
    param([Parameter(Mandatory)][string] $Path)

    return (($Path | ConvertTo-Json -Compress).Trim('"'))
}

function Get-ExpectedHooksConfig {
    param([Parameter(Mandatory)][string] $ResolvedTargetRoot)

    $sourceText = [System.IO.File]::ReadAllText($SourceConfigPath)
    $sourceRootText = ConvertTo-JsonPathText -Path $DefaultRuntimeRoot
    $targetRootText = ConvertTo-JsonPathText -Path $ResolvedTargetRoot
    $rendered = $sourceText.Replace($sourceRootText, $targetRootText)

    $null = $rendered | ConvertFrom-Json -ErrorAction Stop
    return $rendered
}

function Get-HookDrift {
    param(
        [Parameter(Mandatory)][string] $ResolvedTargetRoot,
        [Parameter(Mandatory)][string] $ExpectedConfig
    )

    $drift = [System.Collections.Generic.List[string]]::new()
    $targetConfigPath = Join-Path $ResolvedTargetRoot 'hooks.json'
    if (-not (Test-Path -LiteralPath $targetConfigPath -PathType Leaf)) {
        $drift.Add('hooks.json missing')
    }
    elseif ([System.IO.File]::ReadAllText($targetConfigPath) -cne $ExpectedConfig) {
        $drift.Add('hooks.json differs')
    }

    foreach ($fileName in $OwnedHookFiles) {
        $sourcePath = Join-Path $SourceHooksRoot $fileName
        $targetPath = Join-Path (Join-Path $ResolvedTargetRoot 'hooks') $fileName
        if (-not (Test-Path -LiteralPath $targetPath -PathType Leaf)) {
            $drift.Add("hooks/$fileName missing")
            continue
        }

        $sourceHash = (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash
        $targetHash = (Get-FileHash -LiteralPath $targetPath -Algorithm SHA256).Hash
        if ($sourceHash -cne $targetHash) {
            $drift.Add("hooks/$fileName differs")
        }
    }

    return @($drift)
}

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

if (-not (Test-Path -LiteralPath $SourceConfigPath -PathType Leaf)) {
    throw "Source hook configuration is missing: $SourceConfigPath"
}
foreach ($fileName in $OwnedHookFiles) {
    $sourcePath = Join-Path $SourceHooksRoot $fileName
    if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
        throw "Source hook file is missing: $sourcePath"
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
    throw "Refusing to use a filesystem root as the Codex target: $ResolvedTargetRoot"
}

$ExpectedConfig = Get-ExpectedHooksConfig -ResolvedTargetRoot $ResolvedTargetRoot
$InitialDrift = @(Get-HookDrift -ResolvedTargetRoot $ResolvedTargetRoot -ExpectedConfig $ExpectedConfig)

if ($Check) {
    if ($InitialDrift.Count -gt 0) {
        throw "Installed Codex hook drift: $($InitialDrift -join '; ')"
    }

    [pscustomobject]@{
        Status = 'CURRENT'
        Source = $PackageRoot
        Target = $ResolvedTargetRoot
        Files = $OwnedHookFiles.Count + 1
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
        Files = $OwnedHookFiles.Count + 1
    }
    return
}

if (-not $PSCmdlet.ShouldProcess($ResolvedTargetRoot, 'Install DevHome Codex lifecycle hooks')) {
    return
}

$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
$backupRoot = Join-Path (Join-Path $ResolvedTargetRoot 'hook-backups') $timestamp
$targetConfigPath = Join-Path $ResolvedTargetRoot 'hooks.json'
$targetHooksRoot = Join-Path $ResolvedTargetRoot 'hooks'
$backupCreated = $false

foreach ($relativePath in @('hooks.json') + @($OwnedHookFiles | ForEach-Object { "hooks\$_" })) {
    $existingPath = Join-Path $ResolvedTargetRoot $relativePath
    if (-not (Test-Path -LiteralPath $existingPath -PathType Leaf)) {
        continue
    }

    $backupPath = Join-Path $backupRoot $relativePath
    New-Item -ItemType Directory -Path (Split-Path -Parent $backupPath) -Force | Out-Null
    Copy-Item -LiteralPath $existingPath -Destination $backupPath -Force
    $backupCreated = $true
}

New-Item -ItemType Directory -Path $ResolvedTargetRoot,$targetHooksRoot -Force | Out-Null
$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
[System.IO.File]::WriteAllText($targetConfigPath, $ExpectedConfig, $utf8NoBom)
foreach ($fileName in $OwnedHookFiles) {
    Copy-Item -LiteralPath (Join-Path $SourceHooksRoot $fileName) `
        -Destination (Join-Path $targetHooksRoot $fileName) `
        -Force
}

$RemainingDrift = @(Get-HookDrift -ResolvedTargetRoot $ResolvedTargetRoot -ExpectedConfig $ExpectedConfig)
if ($RemainingDrift.Count -gt 0) {
    throw "Codex hook installation did not converge: $($RemainingDrift -join '; ')"
}

[pscustomobject]@{
    Status = 'INSTALLED'
    MachineId = $identity.machineId
    Source = $PackageRoot
    Target = $ResolvedTargetRoot
    Backup = if ($backupCreated) { $backupRoot } else { $null }
    Files = $OwnedHookFiles.Count + 1
    TrustReviewRequired = $true
}
