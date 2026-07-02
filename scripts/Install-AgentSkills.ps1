param (
    [Parameter(Mandatory=$false)]
    [ValidateSet("Both", "Codex", "Claude")]
    [string]$Provider = "Both",

    [Parameter(Mandatory=$false)]
    [string[]]$CodexTargets,

    [Parameter(Mandatory=$false)]
    [string[]]$ClaudeTargets,

    [Parameter(Mandatory=$false)]
    [switch]$Force,

    [Parameter(Mandatory=$false)]
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptRoot

function Get-UniquePaths {
    param ([string[]]$Paths)

    $Seen = @{}
    $Result = @()

    foreach ($Path in @($Paths)) {
        if ([string]::IsNullOrWhiteSpace($Path)) {
            continue
        }

        $Expanded = [Environment]::ExpandEnvironmentVariables($Path)
        $FullPath = [System.IO.Path]::GetFullPath($Expanded)
        $Key = $FullPath.ToLowerInvariant()
        if (-not $Seen.ContainsKey($Key)) {
            $Seen[$Key] = $true
            $Result += $FullPath
        }
    }

    return @($Result)
}

function Get-DefaultCodexTargets {
    $Paths = @()

    if (-not [string]::IsNullOrWhiteSpace($env:CODEX_HOME)) {
        $Paths += (Join-Path $env:CODEX_HOME "skills")
    }

    $Paths += (Join-Path $HOME ".codex\skills")

    $StateRoot = "D:\DevHome\state\codex"
    if (Test-Path $StateRoot) {
        $Paths += (Join-Path $StateRoot "skills")
    }

    return Get-UniquePaths @($Paths)
}

function Get-DefaultClaudeTargets {
    $Paths = @()

    if (-not [string]::IsNullOrWhiteSpace($env:CLAUDE_HOME)) {
        $Paths += (Join-Path $env:CLAUDE_HOME "skills")
    }

    $Paths += (Join-Path $HOME ".claude\skills")

    $StateRoot = "D:\DevHome\state\claude"
    if (Test-Path $StateRoot) {
        $Paths += (Join-Path $StateRoot "skills")
    }

    return Get-UniquePaths @($Paths)
}

function Copy-ManifestFile {
    param (
        [string]$SourceRoot,
        [string]$TargetRoot,
        [string]$RelativePath
    )

    $SourcePath = Join-Path $SourceRoot ($RelativePath -replace "/", [System.IO.Path]::DirectorySeparatorChar)
    $TargetPath = Join-Path $TargetRoot ($RelativePath -replace "/", [System.IO.Path]::DirectorySeparatorChar)

    if (-not (Test-Path $SourcePath)) {
        throw "Manifest references missing file: $SourcePath"
    }

    if ((Test-Path $TargetPath) -and -not $Force) {
        return "skipped"
    }

    if ($DryRun) {
        return "would-copy"
    }

    New-Item -ItemType Directory -Path (Split-Path -Parent $TargetPath) -Force | Out-Null
    Copy-Item -LiteralPath $SourcePath -Destination $TargetPath -Force
    return "copied"
}

function Copy-SkillDirectory {
    param (
        [string]$SourceRoot,
        [string]$TargetRoot,
        [string]$SkillName
    )

    $SourcePath = Join-Path $SourceRoot ("skills\" + $SkillName)
    $TargetPath = Join-Path $TargetRoot $SkillName

    if (-not (Test-Path (Join-Path $SourcePath "SKILL.md"))) {
        throw "Manifest references missing skill: $SourcePath"
    }

    if ((Test-Path $TargetPath) -and -not $Force) {
        return "skipped"
    }

    if ($DryRun) {
        if (Test-Path $TargetPath) {
            return "would-refresh"
        }
        return "would-copy"
    }

    New-Item -ItemType Directory -Path $TargetPath -Force | Out-Null
    Get-ChildItem -LiteralPath $SourcePath -Force | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $TargetPath -Recurse -Force
    }

    if (Test-Path $TargetPath) {
        return "copied"
    }

    return "missing"
}

function Copy-ManifestDirectory {
    param (
        [string]$SourceRoot,
        [string]$TargetRoot,
        [string]$RelativePath
    )

    $SourcePath = Join-Path $SourceRoot ($RelativePath -replace "/", [System.IO.Path]::DirectorySeparatorChar)
    $TargetPath = Join-Path $TargetRoot ($RelativePath -replace "/", [System.IO.Path]::DirectorySeparatorChar)

    if (-not (Test-Path $SourcePath)) {
        throw "Manifest references missing directory: $SourcePath"
    }

    if ((Test-Path $TargetPath) -and -not $Force) {
        return "skipped"
    }

    if ($DryRun) {
        if (Test-Path $TargetPath) {
            return "would-refresh"
        }
        return "would-copy"
    }

    New-Item -ItemType Directory -Path $TargetPath -Force | Out-Null
    Get-ChildItem -LiteralPath $SourcePath -Force | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $TargetPath -Recurse -Force
    }

    if (Test-Path $TargetPath) {
        return "copied"
    }

    return "missing"
}

function Sync-ProviderPackage {
    param (
        [string]$ProviderName,
        [string]$PackageDirectory,
        [string[]]$TargetRoots
    )

    $PackageRoot = Join-Path $RepoRoot $PackageDirectory
    $ManifestPath = Join-Path $PackageRoot "package\install-manifest.json"

    if (-not (Test-Path $ManifestPath)) {
        throw "$ProviderName package manifest missing: $ManifestPath"
    }

    $Manifest = Get-Content -Raw $ManifestPath | ConvertFrom-Json
    $Skills = @($Manifest.default_skills) + @($Manifest.optional_skills)
    $SupportFiles = @($Manifest.contract_files) + @($Manifest.optional_contract_files) + @($Manifest.runtime_files)
    $SupportDirectories = @($Manifest.runtime_directories)
    $Targets = Get-UniquePaths $TargetRoots

    if ($Targets.Count -eq 0) {
        throw "$ProviderName has no target skill roots"
    }

    $Rows = @()

    foreach ($TargetRoot in $Targets) {
        if (-not $DryRun) {
            New-Item -ItemType Directory -Path $TargetRoot -Force | Out-Null
        }

        $FilesCopied = 0
        $FilesSkipped = 0
        $DirectoriesCopied = 0
        $DirectoriesSkipped = 0
        $SkillsCopied = 0
        $SkillsSkipped = 0

        foreach ($File in $SupportFiles) {
            $Result = Copy-ManifestFile -SourceRoot $PackageRoot -TargetRoot $TargetRoot -RelativePath $File
            if ($Result -eq "skipped") {
                $FilesSkipped += 1
            } else {
                $FilesCopied += 1
            }
        }

        foreach ($Directory in $SupportDirectories) {
            $Result = Copy-ManifestDirectory -SourceRoot $PackageRoot -TargetRoot $TargetRoot -RelativePath $Directory
            if ($Result -eq "skipped") {
                $DirectoriesSkipped += 1
            } else {
                $DirectoriesCopied += 1
            }
        }

        foreach ($Skill in $Skills) {
            $Result = Copy-SkillDirectory -SourceRoot $PackageRoot -TargetRoot $TargetRoot -SkillName $Skill
            if ($Result -eq "skipped") {
                $SkillsSkipped += 1
            } else {
                $SkillsCopied += 1
            }
        }

        $Rows += [pscustomobject]@{
            Provider = $ProviderName
            Target = $TargetRoot
            Skills = $Skills.Count
            SkillsCopied = $SkillsCopied
            SkillsSkipped = $SkillsSkipped
            FilesCopied = $FilesCopied
            FilesSkipped = $FilesSkipped
            DirectoriesCopied = $DirectoriesCopied
            DirectoriesSkipped = $DirectoriesSkipped
            DryRun = [bool]$DryRun
            Force = [bool]$Force
        }
    }

    return @($Rows)
}

if (-not $CodexTargets) {
    $CodexTargets = Get-DefaultCodexTargets
}
if (-not $ClaudeTargets) {
    $ClaudeTargets = Get-DefaultClaudeTargets
}

$AllRows = @()

if ($Provider -eq "Both" -or $Provider -eq "Codex") {
    foreach ($Row in Sync-ProviderPackage -ProviderName "Codex" -PackageDirectory "codex-skills" -TargetRoots $CodexTargets) {
        $AllRows += $Row
    }
}

if ($Provider -eq "Both" -or $Provider -eq "Claude") {
    foreach ($Row in Sync-ProviderPackage -ProviderName "Claude" -PackageDirectory "claude-skills" -TargetRoots $ClaudeTargets) {
        $AllRows += $Row
    }
}

Write-Output "Local Agent Skill Sync"
Write-Output ""
$AllRows | Format-Table -AutoSize

if ($DryRun) {
    Write-Output ""
    Write-Output "Dry run only. Re-run without -DryRun to copy missing entries, or add -Force to refresh existing manifest-listed entries."
}
