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
$RetiredSkillsPath = Join-Path $ScriptRoot "retired-skills.json"

if (-not (Test-Path -LiteralPath $RetiredSkillsPath -PathType Leaf)) {
    throw "Retired skill registry missing: $RetiredSkillsPath"
}
$RetiredRegistry = Get-Content -Raw -LiteralPath $RetiredSkillsPath | ConvertFrom-Json
if ($RetiredRegistry.schema -ne "ai-skills/retired-skills/v1") {
    throw "Unsupported retired skill registry schema: $($RetiredRegistry.schema)"
}
$RetiredSkills = @($RetiredRegistry.retired_skills)

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
    $BaseWithSeparator = $BaseFull + [System.IO.Path]::DirectorySeparatorChar

    # Callers pass enumerated FullName paths, which are already absolute.
    # GetFullPath rewrites a stray file named like a DOS device (skill\NUL) to
    # \\.\NUL and loses the owning skill, so plain prefix math goes first.
    if ($TargetPath.StartsWith($BaseWithSeparator, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $TargetPath.Substring($BaseWithSeparator.Length) -replace "\\", "/"
    }

    $TargetFull = [System.IO.Path]::GetFullPath($TargetPath)

    try {
        $RelativePath = [System.IO.Path]::GetRelativePath($BaseFull, $TargetFull)
    } catch {
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

# Text files compare with CRLF folded to LF so a checkout's line endings do not
# read as drift; these binary types stay byte-exact.
$BinaryExtensions = @(".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp", ".zip", ".gz", ".exe", ".dll", ".pdf")

function Get-ComparableContent {
    param ([string]$Path)

    # Latin-1 maps every byte to one char, so the fold is byte-exact and no
    # text encoding is guessed.
    $Content = [System.Text.Encoding]::GetEncoding(28591).GetString([System.IO.File]::ReadAllBytes($Path))
    # A NUL byte also marks a binary file, matching Install-AgentSkills.ps1 -Check.
    if ([System.IO.Path]::GetExtension($Path) -notin $BinaryExtensions -and $Content.IndexOf([char]0) -lt 0) {
        $Content = $Content.Replace("`r`n", "`n")
    }
    return $Content
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

    if (-not (Test-Path -LiteralPath $SourcePath)) {
        Add-Row $ProviderName $TargetRoot $Kind $RelativePath "SourceMissing"
        return
    }
    if (-not (Test-Path -LiteralPath $TargetPath)) {
        Add-Row $ProviderName $TargetRoot $Kind $RelativePath "Missing"
        return
    }

    $SourceContent = Get-ComparableContent $SourcePath
    $TargetContent = Get-ComparableContent $TargetPath
    if (-not [string]::Equals($SourceContent, $TargetContent, [System.StringComparison]::Ordinal)) {
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

    if (-not (Test-Path -LiteralPath $SourceDir)) {
        Add-Row $ProviderName $TargetRoot $Kind $RelativePath "SourceMissing"
        return
    }
    if (-not (Test-Path -LiteralPath $TargetDir)) {
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
        if (-not (Test-Path -LiteralPath $SourcePath)) {
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

        foreach ($Retired in $RetiredSkills) {
            $RetiredName = [string]$Retired.name
            if ($RetiredName -notmatch '^[a-z0-9]+(?:-[a-z0-9]+)*$') {
                throw "Unsafe retired skill name in registry: $RetiredName"
            }
            $RetiredPath = Join-Path $TargetRoot $RetiredName
            if (Test-Path -LiteralPath $RetiredPath) {
                Add-Row `
                    $ProviderName `
                    $TargetRoot `
                    "RetiredSkill" `
                    $RetiredName `
                    "RetiredInstalled" `
                    "Replace with $([string]$Retired.replacement); rerun Install-AgentSkills.ps1"
            }
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
        # Source-only skills are never walked above, so a copy that lost its
        # SKILL.md would otherwise produce no row. Absence is not demanded.
        foreach ($SourceOnly in $SourceOnlySkills) {
            $SkillDir = Join-Path $TargetRoot $SourceOnly
            if ((Test-Path -LiteralPath $SkillDir -PathType Container) -and
                -not (Test-Path -LiteralPath (Join-Path $SkillDir "SKILL.md") -PathType Leaf)) {
                Add-Row $ProviderName $TargetRoot "Skill" "$SourceOnly/SKILL.md" "Missing" "Source-only skill directory has no SKILL.md"
            }
        }

        if ($IncludeExtra) {
            # Every directory counts, so an orphan without SKILL.md is reported.
            # Dot directories are host-owned (Codex .system) and top-level
            # directories of manifest files (scripts/) belong to the package.
            $OwnedDirs = @(@($Files | Where-Object { $_ -match '/' }) + @($Directories) | ForEach-Object { ($_ -split '/')[0] })
            $RootDirs = @(Get-ChildItem -LiteralPath $TargetRoot -Directory -Force | Where-Object {
                -not $_.Name.StartsWith(".") -and $_.Name -notin $OwnedDirs
            })
            foreach ($SourceOnly in @($RootDirs | Where-Object { $_.Name -in $SourceOnlySkills })) {
                Add-Row $ProviderName $TargetRoot "Skill" $SourceOnly.Name "SourceOnlyInstalled" "Listed in source_only_skills; not managed by installer"
            }
            foreach ($Extra in @($RootDirs | Where-Object { $_.Name -notin $Skills -and $_.Name -notin $SourceOnlySkills })) {
                $Detail = if (Test-Path -LiteralPath (Join-Path $Extra.FullName "SKILL.md") -PathType Leaf) { "" } else { "No SKILL.md" }
                Add-Row $ProviderName $TargetRoot "Skill" $Extra.Name "Extra" $Detail
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

# Format-Table truncates columns to the host width, so the table above is for
# humans only. Emit one untruncated line per finding as the machine-readable
# surface that callers and tests match on.
foreach ($Row in ($Rows | Sort-Object Provider, Target, Status, Kind, Path)) {
    Write-Output "FINDING $($Row.Status) [$($Row.Provider)] $($Row.Kind) $($Row.Path) <- $($Row.Target)"
}

$Blocking = @($Rows | Where-Object { $_.Status -in @("Missing", "Stale", "SourceMissing", "RetiredInstalled") })
if ($FailOnMissingOrStale -and $Blocking.Count -gt 0) {
    throw "Local agent skill roots have $($Blocking.Count) missing, stale, or retired entries"
}
