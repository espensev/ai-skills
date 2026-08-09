param (
    [Parameter(Mandatory=$false)]
    [ValidateSet("Both", "Codex", "Claude")]
    [string]$Provider = "Both",

    [Parameter(Mandatory=$false)]
    [string[]]$CodexTargets,

    [Parameter(Mandatory=$false)]
    [string[]]$ClaudeTargets,

    [Parameter(Mandatory=$false)]
    [switch]$FailOnMissingOrStale,

    [Parameter(Mandatory=$false)]
    [switch]$IncludeExtra
)

$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptRoot
$Rows = New-Object System.Collections.Generic.List[object]

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

function Get-UniquePaths {
    param ([string[]]$Paths)

    $Seen = @{}
    $Result = @()
    foreach ($Path in @($Paths)) {
        if ([string]::IsNullOrWhiteSpace($Path)) {
            continue
        }
        $FullPath = [System.IO.Path]::GetFullPath([Environment]::ExpandEnvironmentVariables($Path))
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
    if (Test-Path "D:\DevHome\state\codex") {
        $Paths += "D:\DevHome\state\codex\skills"
    }
    return Get-UniquePaths @($Paths)
}

function Get-DefaultClaudeTargets {
    $Paths = @()
    if (-not [string]::IsNullOrWhiteSpace($env:CLAUDE_HOME)) {
        $Paths += (Join-Path $env:CLAUDE_HOME "skills")
    }
    $Paths += (Join-Path $HOME ".claude\skills")
    if (Test-Path "D:\DevHome\state\claude") {
        $Paths += "D:\DevHome\state\claude\skills"
    }
    return Get-UniquePaths @($Paths)
}

function Add-Row {
    param (
        [string]$ProviderName,
        [string]$TargetRoot,
        [string]$Kind,
        [string]$Path,
        [string]$Status,
        [string]$Detail = ""
    )

    $Rows.Add([pscustomobject]@{
        Provider = $ProviderName
        Target = $TargetRoot
        Kind = $Kind
        Path = $Path
        Status = $Status
        Detail = $Detail
    }) | Out-Null
}

function Get-PortableRelativePath {
    param (
        [string]$BasePath,
        [string]$TargetPath
    )

    $BaseFull = [System.IO.Path]::GetFullPath($BasePath).TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    )
    $TargetFull = [System.IO.Path]::GetFullPath($TargetPath)

    try {
        $RelativePath = [System.IO.Path]::GetRelativePath($BaseFull, $TargetFull)
    } catch {
        $BaseWithSeparator = $BaseFull + [System.IO.Path]::DirectorySeparatorChar
        if ($TargetFull.Equals($BaseFull, [System.StringComparison]::OrdinalIgnoreCase)) {
            $RelativePath = "."
        } elseif ($TargetFull.StartsWith($BaseWithSeparator, [System.StringComparison]::OrdinalIgnoreCase)) {
            $RelativePath = $TargetFull.Substring($BaseWithSeparator.Length)
        } else {
            $RelativePath = $TargetFull
        }
    }

    return $RelativePath -replace "\\", "/"
}

function Test-FileMatch {
    param (
        [string]$ProviderName,
        [string]$TargetRoot,
        [string]$SourceRoot,
        [string]$RelativePath,
        [string]$Kind
    )

    $NativePath = $RelativePath -replace "/", [System.IO.Path]::DirectorySeparatorChar
    $SourcePath = Join-Path $SourceRoot $NativePath
    $TargetPath = Join-Path $TargetRoot $NativePath

    if (-not (Test-Path $SourcePath)) {
        Add-Row $ProviderName $TargetRoot $Kind $RelativePath "SourceMissing"
        return
    }
    if (-not (Test-Path $TargetPath)) {
        Add-Row $ProviderName $TargetRoot $Kind $RelativePath "Missing"
        return
    }

    $SourceHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $SourcePath).Hash
    $TargetHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $TargetPath).Hash
    if ($SourceHash -ne $TargetHash) {
        Add-Row $ProviderName $TargetRoot $Kind $RelativePath "Stale"
    }
}

function Test-DirectoryMatch {
    param (
        [string]$ProviderName,
        [string]$TargetRoot,
        [string]$SourceRoot,
        [string]$RelativePath,
        [string]$Kind
    )

    $NativePath = $RelativePath -replace "/", [System.IO.Path]::DirectorySeparatorChar
    $SourceDir = Join-Path $SourceRoot $NativePath
    $TargetDir = Join-Path $TargetRoot $NativePath

    if (-not (Test-Path $SourceDir)) {
        Add-Row $ProviderName $TargetRoot $Kind $RelativePath "SourceMissing"
        return
    }
    if (-not (Test-Path $TargetDir)) {
        Add-Row $ProviderName $TargetRoot $Kind $RelativePath "Missing"
        return
    }

    $SourceFiles = @(Get-ChildItem -LiteralPath $SourceDir -Recurse -File -Force |
        Where-Object { -not (Test-GeneratedPackageArtifact $_.FullName) })
    foreach ($SourceFile in $SourceFiles) {
        $RelativeFile = Get-PortableRelativePath -BasePath $SourceRoot -TargetPath $SourceFile.FullName
        Test-FileMatch -ProviderName $ProviderName -TargetRoot $TargetRoot -SourceRoot $SourceRoot -RelativePath $RelativeFile -Kind $Kind
    }

    $TargetFiles = @(Get-ChildItem -LiteralPath $TargetDir -Recurse -File -Force |
        Where-Object { -not (Test-GeneratedPackageArtifact $_.FullName) })
    foreach ($TargetFile in $TargetFiles) {
        $RelativeFile = Get-PortableRelativePath -BasePath $TargetRoot -TargetPath $TargetFile.FullName
        $SourcePath = Join-Path $SourceRoot ($RelativeFile -replace "/", [System.IO.Path]::DirectorySeparatorChar)
        if (-not (Test-Path $SourcePath)) {
            Add-Row $ProviderName $TargetRoot $Kind $RelativeFile "ExtraFile"
        }
    }
}

function Compare-ProviderPackage {
    param (
        [string]$ProviderName,
        [string]$PackageDirectory,
        [string[]]$TargetRoots
    )

    $PackageRoot = Join-Path $RepoRoot $PackageDirectory
    $InstallManifestPath = Join-Path $PackageRoot "package\install-manifest.json"
    if (-not (Test-Path $InstallManifestPath)) {
        throw "$ProviderName install manifest missing: $InstallManifestPath"
    }

    $Manifest = Get-Content -Raw $InstallManifestPath | ConvertFrom-Json
    $Skills = @($Manifest.default_skills) + @($Manifest.optional_skills)
    $SourceOnlySkills = @($Manifest.source_only_skills)
    $Files = @($Manifest.contract_files) + @($Manifest.optional_contract_files) + @($Manifest.runtime_files)
    $Directories = @($Manifest.runtime_directories)

    foreach ($TargetRoot in @(Get-UniquePaths $TargetRoots)) {
        if (-not (Test-Path $TargetRoot)) {
            Add-Row $ProviderName $TargetRoot "Root" "." "Missing"
            continue
        }

        foreach ($File in $Files) {
            Test-FileMatch -ProviderName $ProviderName -TargetRoot $TargetRoot -SourceRoot $PackageRoot -RelativePath $File -Kind "File"
        }
        foreach ($Directory in $Directories) {
            Test-DirectoryMatch -ProviderName $ProviderName -TargetRoot $TargetRoot -SourceRoot $PackageRoot -RelativePath $Directory -Kind "Directory"
        }
        foreach ($Skill in $Skills) {
            Test-DirectoryMatch -ProviderName $ProviderName -TargetRoot $TargetRoot -SourceRoot (Join-Path $PackageRoot "skills") -RelativePath $Skill -Kind "Skill"
        }

        if ($IncludeExtra) {
            $RootSkillDirs = @(Get-ChildItem -LiteralPath $TargetRoot -Directory -Force | Where-Object {
                Test-Path (Join-Path $_.FullName "SKILL.md")
            } | ForEach-Object { $_.Name })
            foreach ($SourceOnly in @($RootSkillDirs | Where-Object { $_ -in $SourceOnlySkills })) {
                Add-Row $ProviderName $TargetRoot "Skill" $SourceOnly "SourceOnlyInstalled" "Listed in source_only_skills; not managed by installer"
            }
            foreach ($Extra in @($RootSkillDirs | Where-Object { $_ -notin $Skills -and $_ -notin $SourceOnlySkills })) {
                Add-Row $ProviderName $TargetRoot "Skill" $Extra "Extra"
            }
        }
    }
}

if (-not $CodexTargets) {
    $CodexTargets = Get-DefaultCodexTargets
}
if (-not $ClaudeTargets) {
    $ClaudeTargets = Get-DefaultClaudeTargets
}

if ($Provider -eq "Both" -or $Provider -eq "Codex") {
    Compare-ProviderPackage -ProviderName "Codex" -PackageDirectory "codex-skills" -TargetRoots $CodexTargets
}
if ($Provider -eq "Both" -or $Provider -eq "Claude") {
    Compare-ProviderPackage -ProviderName "Claude" -PackageDirectory "claude-skills" -TargetRoots $ClaudeTargets
}

if ($Rows.Count -eq 0) {
    Write-Output "PASS - local agent skill roots match manifest-listed files"
    exit 0
}

$Rows | Sort-Object Provider, Target, Status, Kind, Path | Format-Table -AutoSize

$Blocking = @($Rows | Where-Object { $_.Status -in @("Missing", "Stale", "SourceMissing") })
if ($FailOnMissingOrStale -and $Blocking.Count -gt 0) {
    throw "Local agent skill roots have $($Blocking.Count) missing or stale manifest-listed entries"
}
