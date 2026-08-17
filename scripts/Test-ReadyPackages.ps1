param (
    [Parameter(Mandatory=$false)]
    [string]$ExportSmokeDir,

    [Parameter(Mandatory=$false)]
    [switch]$SkipExportSmoke,

    [Parameter(Mandatory=$false)]
    [switch]$StrictSkillManifest,

    [Parameter(Mandatory=$false)]
    [string]$InstallerSmokeDir,

    [Parameter(Mandatory=$false)]
    [switch]$SkipInstallerSmoke
)

$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptRoot
$ReleaseManifestPath = Join-Path $RepoRoot "release-manifest.json"

if (-not $ExportSmokeDir) {
    $ExportSmokeDir = Join-Path ([System.IO.Path]::GetTempPath()) "ai-skills-ready-packages-smoke"
}
if (-not $InstallerSmokeDir) {
    $InstallerSmokeDir = Join-Path ([System.IO.Path]::GetTempPath()) "ai-skills-installer-smoke"
}
$Failures = New-Object System.Collections.Generic.List[string]
$Warnings = New-Object System.Collections.Generic.List[string]
$Rows = New-Object System.Collections.Generic.List[object]

function Add-Failure {
    param ([string]$Message)
    $Failures.Add($Message) | Out-Null
}

function Add-WarningMessage {
    param ([string]$Message)
    $Warnings.Add($Message) | Out-Null
}

function Test-RequiredPath {
    param (
        [string]$BasePath,
        [string]$RelativePath,
        [string]$Label
    )

    $FullPath = Join-Path $BasePath ($RelativePath -replace "/", [System.IO.Path]::DirectorySeparatorChar)
    if (-not (Test-Path $FullPath)) {
        Add-Failure "$Label missing: $RelativePath"
        return $false
    }

    return $true
}

function Get-SkillDescription {
    param ([string]$SkillPath)

    $SkillText = Get-Content -Raw $SkillPath
    $FrontmatterMatch = [regex]::Match($SkillText, "(?s)^---\s*(.*?)\s*---")
    if (-not $FrontmatterMatch.Success) {
        return $null
    }

    foreach ($Line in ($FrontmatterMatch.Groups[1].Value -split "\r?\n")) {
        if ($Line -match "^\s*description:\s*(.+?)\s*$") {
            return $Matches[1].Trim().Trim('"').Trim("'")
        }
    }

    return $null
}

function Get-SkillName {
    param ([string]$SkillPath)

    $SkillText = Get-Content -Raw $SkillPath
    $FrontmatterMatch = [regex]::Match($SkillText, "(?s)^---\s*(.*?)\s*---")
    if (-not $FrontmatterMatch.Success) {
        return $null
    }

    foreach ($Line in ($FrontmatterMatch.Groups[1].Value -split "\r?\n")) {
        if ($Line -match "^\s*name:\s*(.+?)\s*$") {
            return $Matches[1].Trim().Trim('"').Trim("'")
        }
    }

    return $null
}

function Test-SkillDescription {
    param (
        [string]$PackageName,
        [string]$SkillName,
        [string]$SkillPath
    )

    $DeclaredName = Get-SkillName $SkillPath
    if ($DeclaredName -ne $SkillName) {
        Add-Failure "$PackageName skill frontmatter name does not match folder: $SkillName (declares '$DeclaredName')"
    }
    if ($SkillName -notmatch '^[a-z0-9]+(?:-[a-z0-9]+)*$') {
        Add-Failure "$PackageName skill folder is not kebab-case: $SkillName"
    }

    $Description = Get-SkillDescription $SkillPath
    if ([string]::IsNullOrWhiteSpace($Description)) {
        Add-Failure "$PackageName skill frontmatter missing description: $SkillName"
        return
    }

    if ($Description -notmatch "(?i)\bUse\s+(when|for|after|before)\b") {
        Add-Failure "$PackageName skill description lacks discovery trigger: $SkillName"
    }
}

function Test-SkillSupportReferences {
    param (
        [string]$PackageName,
        [string]$SkillName,
        [string]$SkillPath
    )

    $SkillRoot = Split-Path -Parent $SkillPath
    $SkillText = (Get-Content -Raw $SkillPath) -replace "\\", "/"
    foreach ($SupportDirName in @("references", "examples", "assets", "scripts")) {
        $SupportDir = Join-Path $SkillRoot $SupportDirName
        if (-not (Test-Path $SupportDir)) {
            continue
        }

        $Prefix = [System.IO.Path]::GetFullPath($SkillRoot).TrimEnd(
            [System.IO.Path]::DirectorySeparatorChar,
            [System.IO.Path]::AltDirectorySeparatorChar
        ) + [System.IO.Path]::DirectorySeparatorChar
        foreach ($SupportFile in @(Get-ChildItem -LiteralPath $SupportDir -Recurse -File -Force)) {
            $RelativePath = $SupportFile.FullName.Substring($Prefix.Length) -replace "\\", "/"
            if ($SkillText -notmatch [regex]::Escape($RelativePath)) {
                Add-Failure "$PackageName skill support file is not referenced by SKILL.md: $SkillName/$RelativePath"
            }
        }
    }
}

function Test-SkillScriptReferences {
    param (
        [string]$PackageName,
        [string]$PackageRoot,
        [string]$SkillName,
        [string]$SkillPath,
        [string[]]$RuntimeFiles,
        [string[]]$RuntimeDirectories
    )

    $SkillText = Get-Content -Raw $SkillPath
    $BundledFiles = @($RuntimeFiles | ForEach-Object { ($_ -replace "\\", "/").TrimEnd("/") })
    $BundledDirs = @($RuntimeDirectories | ForEach-Object { ($_ -replace "\\", "/").TrimEnd("/") })
    $Matches = [regex]::Matches($SkillText, "scripts/[A-Za-z0-9_./-]+")

    foreach ($Match in $Matches) {
        $Reference = ($Match.Value -replace "\\", "/").TrimEnd(".", ",", ")", "]", "}", ":", ";", "'", '"')
        if ([string]::IsNullOrWhiteSpace($Reference)) {
            continue
        }

        $IsBundled = ($Reference -in $BundledFiles)
        if (-not $IsBundled) {
            foreach ($Directory in $BundledDirs) {
                if ($Reference -eq $Directory -or $Reference.StartsWith($Directory + "/")) {
                    $IsBundled = $true
                    break
                }
            }
        }

        if (-not $IsBundled) {
            Add-Failure "$PackageName skill references unbundled script path: $SkillName -> $Reference"
            continue
        }

        $FullPath = Join-Path $PackageRoot ($Reference -replace "/", [System.IO.Path]::DirectorySeparatorChar)
        if (-not (Test-Path $FullPath)) {
            Add-Failure "$PackageName skill references missing script path: $SkillName -> $Reference"
        }
    }
}

function Test-SkillCommandReferences {
    param (
        [string]$PackageName,
        [string]$SkillName,
        [string]$SkillPath,
        [string[]]$SourceOnlySkills
    )

    if (@($SourceOnlySkills).Count -eq 0) {
        return
    }

    $SkillText = Get-Content -Raw $SkillPath
    $Matches = [regex]::Matches($SkillText, "(?<![A-Za-z0-9_.-])[/`$]([A-Za-z][A-Za-z0-9-]+)(?![A-Za-z0-9-])")

    foreach ($Match in $Matches) {
        $CommandName = $Match.Groups[1].Value
        if ($CommandName -in $SourceOnlySkills) {
            Add-Failure "$PackageName skill references source-only skill command: $SkillName -> $($Match.Value)"
        }
    }
}

function Get-ManifestSkillNames {
    param ([object]$InstallManifest)

    return @($InstallManifest.default_skills) + @($InstallManifest.optional_skills)
}

function Test-ReadmePackageCounts {
    param ([object]$ReleaseManifest)

    $ReadmePath = Join-Path $RepoRoot "README.md"
    if (-not (Test-Path $ReadmePath)) {
        Add-Failure "Missing README.md"
        return
    }

    $ReadmeText = Get-Content -Raw $ReadmePath
    $ExpectedTotal = 0

    foreach ($Package in $ReleaseManifest.packages) {
        if ($Package.status -ne "ready") {
            continue
        }

        $PackageRoot = Join-Path $RepoRoot $Package.path
        $InstallManifestPath = Join-Path $PackageRoot "package\install-manifest.json"
        if (-not (Test-Path $InstallManifestPath)) {
            continue
        }

        $InstallManifest = Get-Content -Raw $InstallManifestPath | ConvertFrom-Json
        $SkillCount = @(Get-ManifestSkillNames -InstallManifest $InstallManifest).Count
        $ExpectedTotal += $SkillCount

        $PackageRowPattern = "\|\s*\*\*$([regex]::Escape($Package.name))\*\*\s*\|\s*(\d+)\s*\|"
        $PackageRowMatch = [regex]::Match($ReadmeText, $PackageRowPattern)
        if (-not $PackageRowMatch.Success) {
            Add-Failure "README package count row missing: $($Package.name)"
        } elseif ([int]$PackageRowMatch.Groups[1].Value -ne $SkillCount) {
            Add-Failure "README package count mismatch for $($Package.name): README=$($PackageRowMatch.Groups[1].Value), manifest=$SkillCount"
        }
    }

    $TotalMatch = [regex]::Match($ReadmeText, "(\d+)\s+install-ready skills")
    if (-not $TotalMatch.Success) {
        Add-Failure "README total install-ready skill count missing"
    } elseif ([int]$TotalMatch.Groups[1].Value -ne $ExpectedTotal) {
        Add-Failure "README total install-ready skill count mismatch: README=$($TotalMatch.Groups[1].Value), manifests=$ExpectedTotal"
    }
}

function New-SmokeRunDirectory {
    param ([string]$BaseDir)

    New-Item -ItemType Directory -Path $BaseDir -Force | Out-Null
    $RunDir = Join-Path $BaseDir ([guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $RunDir -Force | Out-Null
    return $RunDir
}

function Test-InstalledPortablePackage {
    param (
        [object]$Package,
        [object]$InstallManifest,
        [string]$TargetRoot
    )

    foreach ($File in @($InstallManifest.contract_files) + @($InstallManifest.optional_contract_files) + @($InstallManifest.runtime_files)) {
        $TargetPath = Join-Path $TargetRoot ($File -replace "/", [System.IO.Path]::DirectorySeparatorChar)
        if (-not (Test-Path $TargetPath)) {
            Add-Failure "$($Package.name) installer smoke missing file: $File"
        }
    }

    foreach ($Directory in @($InstallManifest.runtime_directories)) {
        $TargetPath = Join-Path $TargetRoot ($Directory -replace "/", [System.IO.Path]::DirectorySeparatorChar)
        if (-not (Test-Path $TargetPath)) {
            Add-Failure "$($Package.name) installer smoke missing directory: $Directory"
        }
    }

    foreach ($Skill in @(Get-ManifestSkillNames -InstallManifest $InstallManifest)) {
        $TargetPath = Join-Path $TargetRoot "$Skill\SKILL.md"
        if (-not (Test-Path $TargetPath)) {
            Add-Failure "$($Package.name) installer smoke missing skill: $Skill"
        }
    }
}

function Test-InstallerSmoke {
    param ([object]$ReleaseManifest)

    $InstallScript = Join-Path $ScriptRoot "Install-AgentSkills.ps1"
    if (-not (Test-Path $InstallScript)) {
        Add-Failure "Missing installer script: scripts/Install-AgentSkills.ps1"
        return
    }

    $RunDir = New-SmokeRunDirectory $InstallerSmokeDir
    $CodexTarget = Join-Path $RunDir "codex-skills"
    $ClaudeTarget = Join-Path $RunDir "claude-skills"

    try {
        & $InstallScript -Provider Both -CodexTargets $CodexTarget -ClaudeTargets $ClaudeTarget -Force | Out-Null

        foreach ($Package in $ReleaseManifest.packages) {
            if ($Package.status -ne "ready" -or $Package.strategy -ne "portable-runtime") {
                continue
            }

            $PackageRoot = Join-Path $RepoRoot $Package.path
            $InstallManifestPath = Join-Path $PackageRoot "package\install-manifest.json"
            $InstallManifest = Get-Content -Raw $InstallManifestPath | ConvertFrom-Json

            if ($Package.name -eq "codex-skills") {
                Test-InstalledPortablePackage -Package $Package -InstallManifest $InstallManifest -TargetRoot $CodexTarget
            } elseif ($Package.name -eq "claude-skills") {
                Test-InstalledPortablePackage -Package $Package -InstallManifest $InstallManifest -TargetRoot $ClaudeTarget
            } else {
                Add-WarningMessage "$($Package.name) portable installer smoke has no default temp target mapping"
            }
        }
    } catch {
        Add-Failure "Installer smoke failed: $($_.Exception.Message)"
    }
}

if (-not (Test-Path $ReleaseManifestPath)) {
    Add-Failure "Missing release manifest: release-manifest.json"
} else {
    $ReleaseManifest = Get-Content -Raw $ReleaseManifestPath | ConvertFrom-Json

    foreach ($Package in $ReleaseManifest.packages) {
        if ($Package.status -ne "ready") {
            continue
        }

        $PackageRoot = Join-Path $RepoRoot $Package.path
        $InstallManifestPath = Join-Path $PackageRoot "package\install-manifest.json"
        $SkillCount = 0
        $SourceOnlySkillCount = $null

        if (-not (Test-Path $PackageRoot)) {
            Add-Failure "$($Package.name) source root missing: $($Package.path)"
            continue
        }

        if (-not (Test-Path $InstallManifestPath)) {
            Add-Failure "$($Package.name) install manifest missing: package/install-manifest.json"
            continue
        }

        $InstallManifest = Get-Content -Raw $InstallManifestPath | ConvertFrom-Json

        switch ($Package.strategy) {
            "portable-runtime" {
                foreach ($ContractFile in @($InstallManifest.contract_files)) {
                    Test-RequiredPath $PackageRoot $ContractFile "$($Package.name) contract" | Out-Null
                }

                foreach ($OptionalContractFile in @($InstallManifest.optional_contract_files)) {
                    $OptionalFullPath = Join-Path $PackageRoot ($OptionalContractFile -replace "/", [System.IO.Path]::DirectorySeparatorChar)
                    if (-not (Test-Path $OptionalFullPath)) {
                        Add-WarningMessage "$($Package.name) optional contract missing: $OptionalContractFile"
                    }
                }

                foreach ($RuntimeFile in @($InstallManifest.runtime_files)) {
                    Test-RequiredPath $PackageRoot $RuntimeFile "$($Package.name) runtime file" | Out-Null
                }

                foreach ($RuntimeDir in @($InstallManifest.runtime_directories)) {
                    Test-RequiredPath $PackageRoot $RuntimeDir "$($Package.name) runtime directory" | Out-Null
                }

                $Skills = @($InstallManifest.default_skills) + @($InstallManifest.optional_skills)
                $SourceOnlySkills = @($InstallManifest.source_only_skills)
                $SkillCount = $Skills.Count
                $SourceOnlySkillCount = $SourceOnlySkills.Count
                $ExportedSourceOnlySkills = @($Skills | Where-Object { $_ -in $SourceOnlySkills })
                if ($ExportedSourceOnlySkills.Count -gt 0) {
                    Add-Failure "$($Package.name) exports source-only skills: $($ExportedSourceOnlySkills -join ', ')"
                }

                foreach ($Skill in $Skills) {
                    $SkillPath = Join-Path $PackageRoot ("skills\" + $Skill + "\SKILL.md")
                    if (Test-RequiredPath $PackageRoot "skills/$Skill/SKILL.md" "$($Package.name) skill") {
                        Test-SkillDescription $Package.name $Skill $SkillPath
                        Test-SkillSupportReferences $Package.name $Skill $SkillPath
                        Test-SkillScriptReferences `
                            -PackageName $Package.name `
                            -PackageRoot $PackageRoot `
                            -SkillName $Skill `
                            -SkillPath $SkillPath `
                            -RuntimeFiles @($InstallManifest.runtime_files) `
                            -RuntimeDirectories @($InstallManifest.runtime_directories)
                        Test-SkillCommandReferences `
                            -PackageName $Package.name `
                            -SkillName $Skill `
                            -SkillPath $SkillPath `
                            -SourceOnlySkills $SourceOnlySkills
                    }
                }

                $SkillDir = Join-Path $PackageRoot "skills"
                $DiskSkills = @()
                if (Test-Path $SkillDir) {
                    $DiskSkills = @(Get-ChildItem $SkillDir -Directory | ForEach-Object { $_.Name })
                }
                $ExtraSkills = @($DiskSkills | Where-Object { $_ -notin $Skills })
                $UnexpectedExtraSkills = @($ExtraSkills | Where-Object { $_ -notin $SourceOnlySkills })
                $MissingSourceOnlySkills = @($SourceOnlySkills | Where-Object { $_ -notin $DiskSkills })
                if ($UnexpectedExtraSkills.Count -gt 0) {
                    $Message = "$($Package.name) has unexpected skill directories not listed in package/install-manifest.json: $($UnexpectedExtraSkills -join ', ')"
                    if ($StrictSkillManifest) {
                        Add-Failure $Message
                    } else {
                        Add-WarningMessage $Message
                    }
                }
                if ($MissingSourceOnlySkills.Count -gt 0) {
                    Add-Failure "$($Package.name) source_only_skills references missing directories: $($MissingSourceOnlySkills -join ', ')"
                }
            }

            default {
                Add-Failure "$($Package.name) uses unsupported strategy: $($Package.strategy)"
            }
        }

        $Rows.Add([pscustomobject]@{
            Package = $Package.name
            Strategy = $Package.strategy
            Skills = $SkillCount
            SourceOnlySkills = $SourceOnlySkillCount
        }) | Out-Null
    }

    Test-ReadmePackageCounts -ReleaseManifest $ReleaseManifest
}

if (-not $SkipExportSmoke -and $Failures.Count -eq 0) {
    $ExportScript = Join-Path $ScriptRoot "export-ready-skill-packages.ps1"
    if (-not (Test-Path $ExportScript)) {
        Add-Failure "Missing export script: scripts/export-ready-skill-packages.ps1"
    } else {
        try {
            & $ExportScript -TargetDir $ExportSmokeDir -Force | Out-Null
            $ExpectedPackages = @($ReleaseManifest.packages | Where-Object { $_.status -eq "ready" } | ForEach-Object { $_.name })
            foreach ($PackageName in $ExpectedPackages) {
                if (-not (Test-Path (Join-Path $ExportSmokeDir $PackageName))) {
                    Add-Failure "Export smoke missing package: $PackageName"
                }
            }
        } catch {
            Add-Failure "Export smoke failed: $($_.Exception.Message)"
        }
    }
}

if (-not $SkipInstallerSmoke -and $Failures.Count -eq 0) {
    Test-InstallerSmoke -ReleaseManifest $ReleaseManifest
}

Write-Output "Ready Package Validation"
Write-Output ""
$Rows | Format-Table -AutoSize

if ($Warnings.Count -gt 0) {
    Write-Output ""
    Write-Output "Warnings:"
    foreach ($Warning in $Warnings) {
        Write-Output "  WARN - $Warning"
    }
}

if ($Failures.Count -gt 0) {
    Write-Output ""
    Write-Output "Failures:"
    foreach ($Failure in $Failures) {
        Write-Output "  FAIL - $Failure"
    }
    exit 1
}

Write-Output ""
Write-Output "PASS - ready package validation completed"
if (-not $SkipExportSmoke) {
    Write-Output "Export smoke target: $ExportSmokeDir"
}
if (-not $SkipInstallerSmoke) {
    Write-Output "Installer smoke target root: $InstallerSmokeDir"
}
