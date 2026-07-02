param (
    [Parameter(Mandatory=$false)]
    [string]$ExportSmokeDir,

    [Parameter(Mandatory=$false)]
    [switch]$SkipExportSmoke,

    [Parameter(Mandatory=$false)]
    [switch]$StrictWrapperManifest,

    [Parameter(Mandatory=$false)]
    [switch]$StrictWorkflowManifest,

    [Parameter(Mandatory=$false)]
    [switch]$StrictSkillManifest
)

$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptRoot
$ReleaseManifestPath = Join-Path $RepoRoot "release-manifest.json"

if (-not $ExportSmokeDir) {
    $ExportSmokeDir = Join-Path ([System.IO.Path]::GetTempPath()) "ai-skills-ready-packages-smoke"
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

function Resolve-RelativeInclude {
    param (
        [string]$FromFile,
        [string]$IncludePath
    )

    $FromDir = Split-Path -Parent $FromFile
    $NativeInclude = $IncludePath -replace "/", [System.IO.Path]::DirectorySeparatorChar
    return [System.IO.Path]::GetFullPath((Join-Path $FromDir $NativeInclude))
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

function Test-SkillDescription {
    param (
        [string]$PackageName,
        [string]$SkillName,
        [string]$SkillPath
    )

    $Description = Get-SkillDescription $SkillPath
    if ([string]::IsNullOrWhiteSpace($Description)) {
        Add-Failure "$PackageName skill frontmatter missing description: $SkillName"
        return
    }

    if ($Description -notmatch "(?i)\bUse\s+(when|for|after|before)\b") {
        Add-Failure "$PackageName skill description lacks discovery trigger: $SkillName"
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
        $WrapperCount = $null
        $ExtraWrapperCount = $null
        $WorkflowCount = $null
        $ExtraWorkflowCount = $null
        $ExtraSkillCount = $null

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
                $SkillCount = $Skills.Count
                foreach ($Skill in $Skills) {
                    $SkillPath = Join-Path $PackageRoot ("skills\" + $Skill + "\SKILL.md")
                    if (Test-RequiredPath $PackageRoot "skills/$Skill/SKILL.md" "$($Package.name) skill") {
                        Test-SkillDescription $Package.name $Skill $SkillPath
                        Test-SkillScriptReferences `
                            -PackageName $Package.name `
                            -PackageRoot $PackageRoot `
                            -SkillName $Skill `
                            -SkillPath $SkillPath `
                            -RuntimeFiles @($InstallManifest.runtime_files) `
                            -RuntimeDirectories @($InstallManifest.runtime_directories)
                    }
                }

                if ($Skills -contains "telemetry-live-ops") {
                    Add-Failure "$($Package.name) exports source-only telemetry-live-ops"
                }

                $SkillDir = Join-Path $PackageRoot "skills"
                $DiskSkills = @()
                if (Test-Path $SkillDir) {
                    $DiskSkills = @(Get-ChildItem $SkillDir -Directory | ForEach-Object { $_.Name })
                }
                $ExtraSkills = @($DiskSkills | Where-Object { $_ -notin $Skills })
                $ExtraSkillCount = $ExtraSkills.Count
                if ($ExtraSkills.Count -gt 0) {
                    $Message = "$($Package.name) has skill directories not listed in package/install-manifest.json: $($ExtraSkills -join ', ')"
                    if ($StrictSkillManifest) {
                        Add-Failure $Message
                    } else {
                        Add-WarningMessage $Message
                    }
                }
            }

            "gemini-adapter" {
                foreach ($RootFile in @($InstallManifest.root_files)) {
                    Test-RequiredPath $PackageRoot $RootFile "$($Package.name) root file" | Out-Null
                }

                foreach ($DocsFile in @($InstallManifest.docs_files)) {
                    Test-RequiredPath $PackageRoot $DocsFile "$($Package.name) docs file" | Out-Null
                }

                foreach ($ScriptFile in @($InstallManifest.script_files)) {
                    Test-RequiredPath $PackageRoot $ScriptFile "$($Package.name) script file" | Out-Null
                }

                $Skills = @($InstallManifest.skills)
                $Wrappers = @($InstallManifest.command_wrappers)
                $SkillCount = $Skills.Count
                $WrapperCount = $Wrappers.Count

                foreach ($Skill in $Skills) {
                    $SkillPath = Join-Path $PackageRoot ("skills\" + $Skill + "\SKILL.md")
                    if (Test-RequiredPath $PackageRoot "skills/$Skill/SKILL.md" "$($Package.name) skill") {
                        Test-SkillDescription $Package.name $Skill $SkillPath
                    }
                }

                foreach ($Wrapper in $Wrappers) {
                    $WrapperPath = Join-Path $PackageRoot ".gemini\commands\$Wrapper"
                    if (-not (Test-Path $WrapperPath)) {
                        Add-Failure "$($Package.name) command wrapper missing: $Wrapper"
                        continue
                    }

                    $WrapperText = Get-Content -Raw $WrapperPath
                    $IncludeMatches = [regex]::Matches($WrapperText, "@\{([^}]+)\}")
                    if ($IncludeMatches.Count -eq 0) {
                        Add-WarningMessage "$($Package.name) command wrapper has no include: $Wrapper"
                        continue
                    }

                    foreach ($Match in $IncludeMatches) {
                        $ResolvedInclude = Resolve-RelativeInclude $WrapperPath $Match.Groups[1].Value
                        if (-not (Test-Path $ResolvedInclude)) {
                            Add-Failure "$($Package.name) command wrapper include missing: $Wrapper -> $($Match.Groups[1].Value)"
                        }
                    }
                }

                $WrapperDir = Join-Path $PackageRoot ".gemini\commands"
                $DiskWrappers = @()
                if (Test-Path $WrapperDir) {
                    $DiskWrappers = @(Get-ChildItem $WrapperDir -Filter "*.toml" | ForEach-Object { $_.Name })
                }
                $ExtraWrappers = @($DiskWrappers | Where-Object { $_ -notin $Wrappers })
                $ExtraWrapperCount = $ExtraWrappers.Count
                if ($ExtraWrappers.Count -gt 0) {
                    $Message = "$($Package.name) has command wrappers not listed in package/install-manifest.json: $($ExtraWrappers -join ', ')"
                    if ($StrictWrapperManifest) {
                        Add-Failure $Message
                    } else {
                        Add-WarningMessage $Message
                    }
                }

                if ($Skills -contains "telemetry-live-ops") {
                    Add-Failure "$($Package.name) exports source-only telemetry-live-ops"
                }
                if ($Wrappers -contains "telemetry-live-ops.toml") {
                    Add-Failure "$($Package.name) exports source-only telemetry-live-ops wrapper"
                }
            }

            "antigravity-adapter" {
                foreach ($RootFile in @($InstallManifest.root_files)) {
                    Test-RequiredPath $PackageRoot $RootFile "$($Package.name) root file" | Out-Null
                }

                foreach ($DocsFile in @($InstallManifest.docs_files)) {
                    Test-RequiredPath $PackageRoot $DocsFile "$($Package.name) docs file" | Out-Null
                }

                foreach ($ScriptFile in @($InstallManifest.script_files)) {
                    Test-RequiredPath $PackageRoot $ScriptFile "$($Package.name) script file" | Out-Null
                }

                $Skills = @($InstallManifest.skills)
                $Workflows = @($InstallManifest.workflows)
                $SkillCount = $Skills.Count
                $WorkflowCount = $Workflows.Count

                foreach ($Skill in $Skills) {
                    $SkillPath = Join-Path $PackageRoot ("skills\" + $Skill + "\SKILL.md")
                    if (Test-RequiredPath $PackageRoot "skills/$Skill/SKILL.md" "$($Package.name) skill") {
                        Test-SkillDescription $Package.name $Skill $SkillPath
                    }
                }

                foreach ($Workflow in $Workflows) {
                    $WorkflowPath = Join-Path $PackageRoot ".agent\workflows\$Workflow"
                    if (-not (Test-Path $WorkflowPath)) {
                        Add-Failure "$($Package.name) workflow missing: $Workflow"
                        continue
                    }

                    $SkillName = [System.IO.Path]::GetFileNameWithoutExtension($Workflow)
                    if ($SkillName -notin $Skills) {
                        Add-Failure "$($Package.name) workflow has no matching skill: $Workflow"
                    }

                    $WorkflowText = Get-Content -Raw $WorkflowPath
                    if ($WorkflowText -notmatch [regex]::Escape(".agents/skills/$SkillName/SKILL.md")) {
                        Add-WarningMessage "$($Package.name) workflow does not reference its installed skill path: $Workflow"
                    }
                }

                $WorkflowDir = Join-Path $PackageRoot ".agent\workflows"
                $DiskWorkflows = @()
                if (Test-Path $WorkflowDir) {
                    $DiskWorkflows = @(Get-ChildItem $WorkflowDir -Filter "*.md" | ForEach-Object { $_.Name })
                }
                $ExtraWorkflows = @($DiskWorkflows | Where-Object { $_ -notin $Workflows })
                $ExtraWorkflowCount = $ExtraWorkflows.Count
                if ($ExtraWorkflows.Count -gt 0) {
                    $Message = "$($Package.name) has workflows not listed in package/install-manifest.json: $($ExtraWorkflows -join ', ')"
                    if ($StrictWorkflowManifest) {
                        Add-Failure $Message
                    } else {
                        Add-WarningMessage $Message
                    }
                }

                if ($Skills -contains "telemetry-live-ops") {
                    Add-Failure "$($Package.name) exports source-only telemetry-live-ops"
                }
                if ($Workflows -contains "telemetry-live-ops.md") {
                    Add-Failure "$($Package.name) exports source-only telemetry-live-ops workflow"
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
            Wrappers = $WrapperCount
            ExtraWrappers = $ExtraWrapperCount
            Workflows = $WorkflowCount
            ExtraWorkflows = $ExtraWorkflowCount
            ExtraSkills = $ExtraSkillCount
        }) | Out-Null
    }
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
