param (
    [Parameter(Mandatory=$false)]
    [ValidateSet("Both", "Codex", "Claude")]
    [string]$Provider = "Both",

    [Parameter(Mandatory=$false)]
    [string[]]$CodexTargets,

    [Parameter(Mandatory=$false)]
    [string[]]$ClaudeTargets,

    [Parameter(Mandatory=$false)]
    [ValidateSet("None", "DevHomeLifecycle")]
    [string]$CodexLocalPlugin = "None",

    [Parameter(Mandatory=$false)]
    [switch]$Force,

    [Parameter(Mandatory=$false)]
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptRoot
$RetiredSkillsPath = Join-Path $ScriptRoot "retired-skills.json"

function Get-RetiredSkillRecords {
    if (-not (Test-Path -LiteralPath $RetiredSkillsPath -PathType Leaf)) {
        throw "Retired skill registry missing: $RetiredSkillsPath"
    }

    $Registry = Get-Content -Raw -LiteralPath $RetiredSkillsPath | ConvertFrom-Json
    if ($Registry.schema -ne "ai-skills/retired-skills/v1") {
        throw "Unsupported retired skill registry schema: $($Registry.schema)"
    }

    $Records = @($Registry.retired_skills)
    if ($Records.Count -eq 0) {
        throw "Retired skill registry is empty: $RetiredSkillsPath"
    }

    $Seen = @{}
    foreach ($Record in $Records) {
        $Name = [string]$Record.name
        $Replacement = [string]$Record.replacement
        if ($Name -notmatch '^[a-z0-9]+(?:-[a-z0-9]+)*$') {
            throw "Unsafe retired skill name in registry: $Name"
        }
        if ([string]::IsNullOrWhiteSpace($Replacement)) {
            throw "Retired skill '$Name' has no replacement route"
        }
        if ($Seen.ContainsKey($Name)) {
            throw "Duplicate retired skill in registry: $Name"
        }
        $Seen[$Name] = $true
    }

    return @($Records | Sort-Object name)
}

$RetiredSkillRecords = Get-RetiredSkillRecords

if ($Provider -eq "Claude" -and $CodexLocalPlugin -ne "None") {
    throw "CodexLocalPlugin requires Provider Codex or Both"
}

function Test-GeneratedPackageArtifact {
    param ([string]$Path)

    return ($Path -match '(^|[\\/])__pycache__([\\/]|$)' -or $Path -match '\.py[co]$')
}

function Get-PathIdentity {
    param ([string]$Path)

    $FullPath = [System.IO.Path]::GetFullPath($Path)
    $Item = Get-Item -LiteralPath $FullPath -Force -ErrorAction SilentlyContinue
    if ($Item -and $Item.LinkType -and $Item.Target) {
        return [System.IO.Path]::GetFullPath([string]@($Item.Target)[0])
    }

    $ParentPath = Split-Path -Parent $FullPath
    $ParentItem = Get-Item -LiteralPath $ParentPath -Force -ErrorAction SilentlyContinue
    if ($ParentItem -and $ParentItem.LinkType -and $ParentItem.Target) {
        return Join-Path ([string]@($ParentItem.Target)[0]) (Split-Path -Leaf $FullPath)
    }

    return $FullPath
}

function Copy-CleanDirectory {
    param (
        [string]$SourcePath,
        [string]$TargetPath
    )

    New-Item -ItemType Directory -Path $TargetPath -Force | Out-Null
    $SourcePrefix = [System.IO.Path]::GetFullPath($SourcePath).TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    ) + [System.IO.Path]::DirectorySeparatorChar
    Get-ChildItem -LiteralPath $SourcePath -Recurse -File -Force |
        Where-Object { -not (Test-GeneratedPackageArtifact $_.FullName) } |
        ForEach-Object {
            $RelativeFile = $_.FullName.Substring($SourcePrefix.Length)
            $TargetFile = Join-Path $TargetPath $RelativeFile
            New-Item -ItemType Directory -Path (Split-Path -Parent $TargetFile) -Force | Out-Null
            Copy-Item -LiteralPath $_.FullName -Destination $TargetFile -Force
        }

    Get-ChildItem -LiteralPath $TargetPath -Recurse -File -Force -ErrorAction SilentlyContinue |
        Where-Object { Test-GeneratedPackageArtifact $_.FullName } |
        Remove-Item -Force
    Get-ChildItem -LiteralPath $TargetPath -Recurse -Directory -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -eq "__pycache__" } |
        Sort-Object FullName -Descending |
        Remove-Item -Recurse -Force
}

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
        $Key = (Get-PathIdentity $FullPath).ToLowerInvariant()
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

    Copy-CleanDirectory -SourcePath $SourcePath -TargetPath $TargetPath

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

    Copy-CleanDirectory -SourcePath $SourcePath -TargetPath $TargetPath

    if (Test-Path $TargetPath) {
        return "copied"
    }

    return "missing"
}

function Remove-RetiredSkillDirectories {
    param (
        [string]$ProviderName,
        [string]$TargetRoot,
        [object[]]$RetiredSkills
    )

    $TargetFull = [System.IO.Path]::GetFullPath($TargetRoot).TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    )
    $TargetPrefix = $TargetFull + [System.IO.Path]::DirectorySeparatorChar
    $Pruned = @()

    foreach ($Record in @($RetiredSkills)) {
        $Name = [string]$Record.name
        $Replacement = [string]$Record.replacement
        $RetiredPath = [System.IO.Path]::GetFullPath((Join-Path $TargetFull $Name))
        if (-not $RetiredPath.StartsWith($TargetPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing retired skill path outside target root: $RetiredPath"
        }
        if (-not (Test-Path -LiteralPath $RetiredPath)) {
            continue
        }

        $Item = Get-Item -LiteralPath $RetiredPath -Force
        if (-not $Item.PSIsContainer) {
            throw "Retired skill target is not a directory: $RetiredPath"
        }

        $Action = "removed"
        if ($DryRun) {
            $Action = "would-remove"
        } elseif ($Item.LinkType) {
            Remove-Item -LiteralPath $RetiredPath -Force
        } else {
            Remove-Item -LiteralPath $RetiredPath -Recurse -Force
        }

        Write-Host "Retired skill $Action [$ProviderName]: $Name -> $Replacement ($RetiredPath)"
        $Pruned += $Name
    }

    return @($Pruned)
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
        $RetiredSkillsPruned = @(
            Remove-RetiredSkillDirectories `
                -ProviderName $ProviderName `
                -TargetRoot $TargetRoot `
                -RetiredSkills $RetiredSkillRecords
        )

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
            RetiredSkillsPruned = $RetiredSkillsPruned.Count
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
$LocalPluginResult = $null

if ($Provider -eq "Both" -or $Provider -eq "Codex") {
    foreach ($Row in Sync-ProviderPackage -ProviderName "Codex" -PackageDirectory "codex-skills" -TargetRoots $CodexTargets) {
        $AllRows += $Row
    }

    if ($CodexLocalPlugin -eq "DevHomeLifecycle") {
        $PluginSyncPath = Join-Path $RepoRoot "codex-skills\local-hooks\devhome-lifecycle\Sync-DevHomeLifecyclePlugin.ps1"
        if (-not (Test-Path -LiteralPath $PluginSyncPath -PathType Leaf)) {
            throw "DevHome lifecycle plugin synchronizer is missing: $PluginSyncPath"
        }

        $PluginSyncParameters = @{
            CodexHome = "D:\DevHome\state\codex"
        }
        if ($DryRun) {
            $PluginSyncParameters.Check = $true
        }
        elseif ($Force) {
            $PluginSyncParameters.Force = $true
        }
        $LocalPluginResult = & $PluginSyncPath @PluginSyncParameters
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

if ($null -ne $LocalPluginResult) {
    Write-Output ""
    Write-Output "Local Codex Plugin Sync"
    $LocalPluginResult | Format-List
}

if ($DryRun) {
    Write-Output ""
    Write-Output "Dry run only. Re-run without -DryRun to copy missing entries, or add -Force to refresh existing manifest-listed entries."
}
