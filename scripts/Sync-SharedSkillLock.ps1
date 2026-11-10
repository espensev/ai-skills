<#
.SYNOPSIS
    Reconciles the shared agents .skill-lock.json against installed skills.
.DESCRIPTION
    Scans installed skill folders containing SKILL.md under the shared agents
    skill root, carries forward provenance metadata from an existing or seed
    .skill-lock.json when available, classifies Ai-Skills and local skills,
    removes uninstalled entries, and writes a deterministic version-3 lock file.
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [string] $SkillsRoot = '',
    [string] $LockPath = '',
    [string] $SeedLockPath = '',
    [string] $AiSkillsRepositoryRoot = '',
    [switch] $Check,
    [switch] $DryRun,
    [string] $VerifierPath = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'AiEnvironment\Private\Common.ps1')

function Resolve-DefaultSharedStateRoot {
    if (-not [string]::IsNullOrWhiteSpace($env:DEVHOME_STATE_ROOT)) {
        return Resolve-AiPath $env:DEVHOME_STATE_ROOT
    }
    if (-not [string]::IsNullOrWhiteSpace($env:MACHINE_CODE_ROOT)) {
        return Resolve-AiPath (Join-Path $env:MACHINE_CODE_ROOT 'DevHome\state')
    }
    return 'D:\DevHome\state'
}

function Get-SkillFolderDigest {
    param([Parameter(Mandatory)][string] $DirectoryPath)

    $resolvedDir = Resolve-AiPath $DirectoryPath
    $files = @(Get-ChildItem -LiteralPath $resolvedDir -Recurse -File -Force | Sort-Object FullName)
    $manifestLines = foreach ($file in $files) {
        $rel = [System.IO.Path]::GetRelativePath($resolvedDir, $file.FullName).Replace('\', '/')
        $fileHash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        "$rel`:$fileHash"
    }
    $bytes = [System.Text.Encoding]::UTF8.GetBytes(($manifestLines -join "`n"))
    $sha256 = [System.Security.Cryptography.SHA256]::Create()
    try {
        $hex = ([System.BitConverter]::ToString($sha256.ComputeHash($bytes))).Replace('-', '').ToLowerInvariant()
    }
    finally {
        $sha256.Dispose()
    }
    return $hex.Substring(0, 40)
}

function ConvertTo-LockTimestampString {
    param(
        [AllowNull()][object] $Value,
        [Parameter(Mandatory)][string] $FallbackUtc
    )

    if ($null -eq $Value) {
        return $FallbackUtc
    }
    if ($Value -is [DateTime]) {
        return $Value.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ss.fffZ')
    }
    if ($Value -is [DateTimeOffset]) {
        return $Value.UtcDateTime.ToString('yyyy-MM-ddTHH:mm:ss.fffZ')
    }
    $text = [string]$Value
    if ([string]::IsNullOrWhiteSpace($text)) {
        return $FallbackUtc
    }
    return $text
}

$stateRoot = Resolve-DefaultSharedStateRoot
if ([string]::IsNullOrWhiteSpace($SkillsRoot)) {
    $SkillsRoot = Join-Path $stateRoot 'agents\skills'
}
if ([string]::IsNullOrWhiteSpace($LockPath)) {
    $LockPath = Join-Path $stateRoot 'agents\.skill-lock.json'
}
if ([string]::IsNullOrWhiteSpace($AiSkillsRepositoryRoot)) {
    $AiSkillsRepositoryRoot = Split-Path -Parent $PSScriptRoot
}

$resolvedSkillsRoot = Resolve-AiPath $SkillsRoot
$resolvedLockPath = Resolve-AiPath $LockPath
$resolvedRepoRoot = Resolve-AiPath $AiSkillsRepositoryRoot

if (-not (Test-Path -LiteralPath $resolvedSkillsRoot -PathType Container)) {
    throw "Shared skills directory missing: $resolvedSkillsRoot"
}

$existingLock = $null
$existingRawJson = $null
if (Test-Path -LiteralPath $resolvedLockPath -PathType Leaf) {
    $existingRawJson = Get-Content -Raw -LiteralPath $resolvedLockPath
    $existingLock = $existingRawJson | ConvertFrom-Json -Depth 100
}

$seedLock = $null
if (-not [string]::IsNullOrWhiteSpace($SeedLockPath)) {
    $resolvedSeedPath = Resolve-AiPath $SeedLockPath
    if (-not (Test-Path -LiteralPath $resolvedSeedPath -PathType Leaf)) {
        throw "Seed skill lock missing: $resolvedSeedPath"
    }
    $seedLock = Get-Content -Raw -LiteralPath $resolvedSeedPath | ConvertFrom-Json -Depth 100
}

$installedDirectories = @(
    Get-ChildItem -LiteralPath $resolvedSkillsRoot -Directory -Force |
        Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'SKILL.md') -PathType Leaf } |
        Sort-Object Name
)

$existingSkillsObj = Get-AiProperty $existingLock 'skills'
$seedSkillsObj = Get-AiProperty $seedLock 'skills'
$existingNames = @(
    if ($null -ne $existingSkillsObj) {
        $existingSkillsObj.PSObject.Properties | ForEach-Object { [string]$_.Name } | Sort-Object -Unique
    }
)

$nowUtc = [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ss.fffZ')
$skillsMap = [ordered]@{}
$carriedFromExisting = 0
$carriedFromSeed = 0
$classifiedAiSkills = 0
$classifiedLocal = 0

foreach ($dir in $installedDirectories) {
    $name = [string]$dir.Name
    $folderHash = Get-SkillFolderDigest -DirectoryPath $dir.FullName

    $existingEntry = if ($null -ne $existingSkillsObj -and $null -ne $existingSkillsObj.PSObject.Properties[$name]) {
        $existingSkillsObj.PSObject.Properties[$name].Value
    }
    else {
        $null
    }
    $seedEntry = if ($null -ne $seedSkillsObj -and $null -ne $seedSkillsObj.PSObject.Properties[$name]) {
        $seedSkillsObj.PSObject.Properties[$name].Value
    }
    else {
        $null
    }

    $prior = if ($null -ne $existingEntry) {
        $carriedFromExisting++
        $existingEntry
    }
    elseif ($null -ne $seedEntry) {
        $carriedFromSeed++
        $seedEntry
    }
    else {
        $null
    }

    if ($null -ne $prior) {
        $priorHash = [string](Get-AiProperty $prior 'skillFolderHash')
        $installedAt = ConvertTo-LockTimestampString -Value (Get-AiProperty $prior 'installedAt') -FallbackUtc $nowUtc
        $updatedAt = if ($null -ne $existingEntry -and $priorHash -ceq $folderHash) {
            ConvertTo-LockTimestampString -Value (Get-AiProperty $existingEntry 'updatedAt') -FallbackUtc $installedAt
        }
        else {
            $nowUtc
        }

        $entryOrdered = [ordered]@{
            source = [string](Get-AiProperty $prior 'source' 'local/agents-skills')
            sourceType = [string](Get-AiProperty $prior 'sourceType' 'local')
        }
        $sourceUrl = [string](Get-AiProperty $prior 'sourceUrl')
        if (-not [string]::IsNullOrWhiteSpace($sourceUrl)) {
            $entryOrdered.sourceUrl = $sourceUrl
        }
        $skillPath = [string](Get-AiProperty $prior 'skillPath')
        if (-not [string]::IsNullOrWhiteSpace($skillPath)) {
            $entryOrdered.skillPath = $skillPath
        }
        $entryOrdered.skillFolderHash = $folderHash
        $entryOrdered.installedAt = $installedAt
        $entryOrdered.updatedAt = $updatedAt
        $skillsMap[$name] = $entryOrdered
    }
    else {
        $aiSkillCandidate = Join-Path $resolvedRepoRoot "codex-skills\skills\$name\SKILL.md"
        if (Test-Path -LiteralPath $aiSkillCandidate -PathType Leaf) {
            $classifiedAiSkills++
            $skillsMap[$name] = [ordered]@{
                source = 'espensev/ai-skills'
                sourceType = 'local'
                sourceUrl = 'https://github.com/espensev/ai-skills.git'
                skillPath = "codex-skills/skills/$name/SKILL.md"
                skillFolderHash = $folderHash
                installedAt = $nowUtc
                updatedAt = $nowUtc
            }
        }
        else {
            $classifiedLocal++
            $skillsMap[$name] = [ordered]@{
                source = 'local/agents-skills'
                sourceType = 'local'
                skillPath = "skills/$name/SKILL.md"
                skillFolderHash = $folderHash
                installedAt = $nowUtc
                updatedAt = $nowUtc
            }
        }
    }
}

$dismissedObj = [ordered]@{}
$priorDismissed = if ($null -ne $existingLock) {
    Get-AiProperty $existingLock 'dismissed'
}
elseif ($null -ne $seedLock) {
    Get-AiProperty $seedLock 'dismissed'
}
else {
    $null
}
if ($null -ne $priorDismissed -and $priorDismissed -is [System.Management.Automation.PSCustomObject]) {
    foreach ($prop in @($priorDismissed.PSObject.Properties | Sort-Object Name)) {
        $dismissedObj[[string]$prop.Name] = $prop.Value
    }
}

$lockDocument = [ordered]@{
    version = 3
    skills = $skillsMap
    dismissed = $dismissedObj
}

$desiredJson = (($lockDocument | ConvertTo-Json -Depth 100) -replace "`r`n", "`n").TrimEnd("`n") + "`n"
$normalizedExistingJson = if ($null -eq $existingRawJson) {
    $null
}
else {
    ($existingRawJson -replace "`r`n", "`n").TrimEnd("`n") + "`n"
}
$changed = $normalizedExistingJson -cne $desiredJson

$installedNames = @($installedDirectories | Select-Object -ExpandProperty Name)
$prunedNames = @($existingNames | Where-Object { $_ -notin $installedNames })
$unrecordedExistingCount = @($installedNames | Where-Object { $_ -notin $existingNames }).Count
$existingComplete = ($null -ne $existingLock) -and ($prunedNames.Count -eq 0) -and ($unrecordedExistingCount -eq 0)

$status = 'Current'
if ($Check) {
    $status = if (-not $existingComplete -or $changed) { 'Drift' } else { 'Current' }
}
elseif ($DryRun) {
    $status = if ($changed) { 'DryRun' } else { 'Current' }
}
elseif ($changed) {
    $status = 'Planned'
    if ($PSCmdlet.ShouldProcess($resolvedLockPath, "Synchronize shared skill lock ($($installedNames.Count) skills)")) {
        Assert-AiControllerIdentity -TargetPath $resolvedLockPath -VerifierPath $VerifierPath
        Write-AiJsonFileAtomic -Path $resolvedLockPath -Value $lockDocument
        $status = 'Updated'
    }
}

$result = [pscustomobject][ordered]@{
    Status = $status
    LockPath = $resolvedLockPath
    SkillsRoot = $resolvedSkillsRoot
    InstalledCount = $installedNames.Count
    RecordedCount = $skillsMap.Count
    CarriedFromExisting = $carriedFromExisting
    CarriedFromSeed = $carriedFromSeed
    ClassifiedAiSkills = $classifiedAiSkills
    ClassifiedLocal = $classifiedLocal
    RemovedStaleCount = $prunedNames.Count
    Changed = $changed
}

$result
if ($Check -and $result.Status -cne 'Current') {
    exit 1
}
$global:LASTEXITCODE = 0
exit 0
