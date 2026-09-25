param (
    [Parameter(Mandatory=$false)]
    [ValidateSet("Both", "Codex", "Claude")]
    [string]$Provider = "Both",

    [Parameter(Mandatory=$false)]
    [string[]]$CodexTargets,

    [Parameter(Mandatory=$false)]
    [string[]]$ClaudeTargets,

    [Parameter(Mandatory=$false)]
    [ValidateNotNullOrEmpty()]
    [string[]]$SkillNames,

    [Parameter(Mandatory=$false)]
    [ValidateSet("None", "DevHomeLifecycle")]
    [string]$CodexLocalPlugin = "None",

    [Parameter(Mandatory=$false)]
    [switch]$Force,

    [Parameter(Mandatory=$false)]
    [switch]$DryRun,

    [Parameter(Mandatory=$false)]
    [switch]$Check
)

$ErrorActionPreference = "Stop"

if ($Check -and ($Force -or $DryRun)) {
    throw "Check cannot be combined with Force or DryRun; it is already read-only"
}
if ($SkillNames -and $Provider -eq "Both") {
    throw "SkillNames requires a single provider: Codex or Claude"
}
if ($SkillNames -and $CodexLocalPlugin -ne "None") {
    throw "Synchronize the local plugin in a separate invocation from selected skills"
}

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

function Get-PackageFiles {
    param ([string]$SourcePath)

    $SourcePrefix = [System.IO.Path]::GetFullPath($SourcePath).TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    ) + [System.IO.Path]::DirectorySeparatorChar
    return @(Get-ChildItem -LiteralPath $SourcePath -Recurse -File -Force |
        Where-Object { -not (Test-GeneratedPackageArtifact $_.FullName) } |
        ForEach-Object { $_.FullName.Substring($SourcePrefix.Length) })
}

function Test-SameFileContent {
    param (
        [string]$SourceFile,
        [string]$TargetFile
    )

    # ISO-8859-1 (Latin-1) maps each byte to one char, so these strings are the raw bytes. Text
    # compares with CRLF folded to LF, because a line-ending flip is not drift; a
    # NUL byte marks a binary file, which compares raw.
    $SourceBytes = [System.IO.File]::ReadAllBytes($SourceFile)
    $TargetBytes = [System.IO.File]::ReadAllBytes($TargetFile)
    $SourceText = [System.Text.Encoding]::GetEncoding(28591).GetString($SourceBytes)
    $TargetText = [System.Text.Encoding]::GetEncoding(28591).GetString($TargetBytes)
    if ([Array]::IndexOf($SourceBytes, [byte]0) -lt 0 -and [Array]::IndexOf($TargetBytes, [byte]0) -lt 0) {
        $SourceText = $SourceText.Replace("`r`n", "`n")
        $TargetText = $TargetText.Replace("`r`n", "`n")
    }
    return [string]::Equals($SourceText, $TargetText, [System.StringComparison]::Ordinal)
}

function Copy-CleanDirectory {
    param (
        [string]$SourcePath,
        [string]$TargetPath
    )

    New-Item -ItemType Directory -Path $TargetPath -Force | Out-Null
    foreach ($RelativeFile in Get-PackageFiles $SourcePath) {
        $TargetFile = Join-Path $TargetPath $RelativeFile
        New-Item -ItemType Directory -Path (Split-Path -Parent $TargetFile) -Force | Out-Null
        Copy-Item -LiteralPath (Join-Path $SourcePath $RelativeFile) -Destination $TargetFile -Force
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

function Repair-MissingFiles {
    param (
        [string]$ProviderName,
        [string]$Kind,
        [string]$Name,
        [string]$SourcePath,
        [string]$TargetPath
    )

    # Without -Force an existing directory is only topped up: copy the source
    # files it lacks and never overwrite one that is there, so local edits survive.
    $Missing = @(Get-PackageFiles $SourcePath | Where-Object {
        -not (Test-Path -LiteralPath (Join-Path $TargetPath $_) -PathType Leaf)
    })
    if ($Missing.Count -eq 0) {
        return "skipped"
    }

    $Action = "repaired"
    if ($DryRun) {
        $Action = "would-repair"
    } else {
        foreach ($RelativeFile in $Missing) {
            $TargetFile = Join-Path $TargetPath $RelativeFile
            New-Item -ItemType Directory -Path (Split-Path -Parent $TargetFile) -Force | Out-Null
            Copy-Item -LiteralPath (Join-Path $SourcePath $RelativeFile) -Destination $TargetFile -Force
        }
    }

    $MissingList = ($Missing -replace "\\", "/") -join ", "
    Write-Host "$Kind $Action [$ProviderName]: $Name ($($Missing.Count) missing: $MissingList) -> $TargetPath"
    return $Action
}

function Copy-SkillDirectory {
    param (
        [string]$ProviderName,
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
        return Repair-MissingFiles -ProviderName $ProviderName -Kind "Skill" -Name $SkillName -SourcePath $SourcePath -TargetPath $TargetPath
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
        [string]$ProviderName,
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
        return Repair-MissingFiles -ProviderName $ProviderName -Kind "Directory" -Name $RelativePath -SourcePath $SourcePath -TargetPath $TargetPath
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

function Get-ProviderSelection {
    param (
        [string]$ProviderName,
        [string]$PackageDirectory
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
    if ($SkillNames) {
        foreach ($Name in $SkillNames) {
            if ($Name -notmatch '^[a-z0-9]+(?:-[a-z0-9]+)*$' -or $Name -notin $Skills) {
                throw "Invalid selected skill '$Name' for $ProviderName"
            }
            if (-not (Test-Path -LiteralPath (Join-Path $PackageRoot "skills\$Name\SKILL.md") -PathType Leaf)) {
                throw "Invalid selected skill '$Name': source SKILL.md missing"
            }
        }
        $Skills = @($SkillNames | Select-Object -Unique)
        $SupportFiles = @()
        $SupportDirectories = @()
    }

    return [pscustomobject]@{
        PackageRoot = $PackageRoot
        Skills = @($Skills)
        SupportFiles = @($SupportFiles)
        SupportDirectories = @($SupportDirectories)
    }
}

function Get-InstallFindings {
    param (
        [string]$ProviderName,
        [string]$TargetRoot,
        [object]$Selection,
        [switch]$IncludeDrift
    )

    # One entry per selected source file; skills install at the target root, not
    # under skills\, so each entry carries both of its paths.
    $Entries = @()
    foreach ($File in $Selection.SupportFiles) {
        $NativeFile = $File -replace "/", [System.IO.Path]::DirectorySeparatorChar
        $Entries += [pscustomobject]@{
            Kind = "File"
            Path = $File
            Source = Join-Path $Selection.PackageRoot $NativeFile
            Target = Join-Path $TargetRoot $NativeFile
        }
    }
    $Groups = @(
        foreach ($Directory in $Selection.SupportDirectories) {
            $NativeDirectory = $Directory -replace "/", [System.IO.Path]::DirectorySeparatorChar
            @{ Kind = "Directory"; Name = $Directory; Source = Join-Path $Selection.PackageRoot $NativeDirectory; Target = Join-Path $TargetRoot $NativeDirectory }
        }
        foreach ($Skill in $Selection.Skills) {
            @{ Kind = "Skill"; Name = $Skill; Source = Join-Path $Selection.PackageRoot "skills\$Skill"; Target = Join-Path $TargetRoot $Skill }
        }
    )
    foreach ($Group in $Groups) {
        foreach ($RelativeFile in Get-PackageFiles $Group.Source) {
            $Entries += [pscustomobject]@{
                Kind = $Group.Kind
                Path = "$($Group.Name)/$($RelativeFile -replace "\\", "/")"
                Source = Join-Path $Group.Source $RelativeFile
                Target = Join-Path $Group.Target $RelativeFile
            }
        }
    }

    foreach ($Entry in $Entries) {
        if (-not (Test-Path -LiteralPath $Entry.Source -PathType Leaf)) {
            throw "Manifest references missing file: $($Entry.Source)"
        }

        $Status = $null
        if (-not (Test-Path -LiteralPath $Entry.Target -PathType Leaf)) {
            $Status = "Missing"
        } elseif ($IncludeDrift -and -not (Test-SameFileContent -SourceFile $Entry.Source -TargetFile $Entry.Target)) {
            $Status = "Drifted"
        }
        if ($Status) {
            [pscustomobject]@{
                Provider = $ProviderName
                Target = $TargetRoot
                Kind = $Entry.Kind
                Path = $Entry.Path
                Status = $Status
            }
        }
    }
}

function Test-ProviderPackage {
    param (
        [string]$ProviderName,
        [string]$PackageDirectory,
        [string[]]$TargetRoots
    )

    $Selection = Get-ProviderSelection -ProviderName $ProviderName -PackageDirectory $PackageDirectory
    $Targets = Get-UniquePaths $TargetRoots
    if ($Targets.Count -eq 0) {
        throw "$ProviderName has no target skill roots"
    }

    foreach ($TargetRoot in $Targets) {
        Write-Host "Check [$ProviderName]: $TargetRoot ($($Selection.Skills.Count) skills, $($Selection.SupportFiles.Count) files, $($Selection.SupportDirectories.Count) directories) against $($Selection.PackageRoot)"
        Get-InstallFindings -ProviderName $ProviderName -TargetRoot $TargetRoot -Selection $Selection -IncludeDrift
    }
}

function Sync-ProviderPackage {
    param (
        [string]$ProviderName,
        [string]$PackageDirectory,
        [string[]]$TargetRoots
    )

    $Selection = Get-ProviderSelection -ProviderName $ProviderName -PackageDirectory $PackageDirectory
    $PackageRoot = $Selection.PackageRoot
    $Skills = $Selection.Skills
    $SupportFiles = $Selection.SupportFiles
    $SupportDirectories = $Selection.SupportDirectories
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
        $DirectoriesRepaired = 0
        $DirectoriesSkipped = 0
        $SkillsCopied = 0
        $SkillsRepaired = 0
        $SkillsSkipped = 0
        $RetiredSkillsPruned = @(
            if (-not $SkillNames) {
                Remove-RetiredSkillDirectories `
                    -ProviderName $ProviderName `
                    -TargetRoot $TargetRoot `
                    -RetiredSkills $RetiredSkillRecords
            }
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
            $Result = Copy-ManifestDirectory -ProviderName $ProviderName -SourceRoot $PackageRoot -TargetRoot $TargetRoot -RelativePath $Directory
            if ($Result -eq "skipped") {
                $DirectoriesSkipped += 1
            } elseif ($Result -in @("repaired", "would-repair")) {
                $DirectoriesRepaired += 1
            } else {
                $DirectoriesCopied += 1
            }
        }

        foreach ($Skill in $Skills) {
            $Result = Copy-SkillDirectory -ProviderName $ProviderName -SourceRoot $PackageRoot -TargetRoot $TargetRoot -SkillName $Skill
            if ($Result -eq "skipped") {
                $SkillsSkipped += 1
            } elseif ($Result -in @("repaired", "would-repair")) {
                $SkillsRepaired += 1
            } else {
                $SkillsCopied += 1
            }
        }

        if (-not $DryRun) {
            # A copy that returned is not proof it landed: every selected source
            # file, each skill's SKILL.md included, must now exist in the target.
            $Missing = @(Get-InstallFindings -ProviderName $ProviderName -TargetRoot $TargetRoot -Selection $Selection)
            if ($Missing.Count -gt 0) {
                throw "Post-install verification failed [$ProviderName] ${TargetRoot}: $($Missing.Count) missing: $(($Missing | ForEach-Object { $_.Path }) -join ', ')"
            }
        }

        $Rows += [pscustomobject]@{
            Provider = $ProviderName
            Target = $TargetRoot
            Skills = $Skills.Count
            SkillsCopied = $SkillsCopied
            SkillsRepaired = $SkillsRepaired
            SkillsSkipped = $SkillsSkipped
            FilesCopied = $FilesCopied
            FilesSkipped = $FilesSkipped
            DirectoriesCopied = $DirectoriesCopied
            DirectoriesRepaired = $DirectoriesRepaired
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
$CheckRows = @()
$LocalPluginResult = $null
$LocalPluginCheckFailed = $false

if ($Provider -eq "Both" -or $Provider -eq "Codex") {
    if ($Check) {
        $CheckRows += @(Test-ProviderPackage -ProviderName "Codex" -PackageDirectory "codex-skills" -TargetRoots $CodexTargets)
    } else {
        foreach ($Row in Sync-ProviderPackage -ProviderName "Codex" -PackageDirectory "codex-skills" -TargetRoots $CodexTargets) {
            $AllRows += $Row
        }
    }

    if ($CodexLocalPlugin -eq "DevHomeLifecycle") {
        $PluginSyncPath = Join-Path $RepoRoot "codex-skills\local-hooks\devhome-lifecycle\Sync-DevHomeLifecyclePlugin.ps1"
        if (-not (Test-Path -LiteralPath $PluginSyncPath -PathType Leaf)) {
            throw "DevHome lifecycle plugin synchronizer is missing: $PluginSyncPath"
        }

        $PluginSyncParameters = @{
            CodexHome = "D:\DevHome\state\codex"
        }
        if ($DryRun -or $Check) {
            $PluginSyncParameters.Check = $true
        }
        elseif ($Force) {
            $PluginSyncParameters.Force = $true
        }
        $LocalPluginResult = & $PluginSyncPath @PluginSyncParameters
        # The synchronizer's -Check carries its verdict in the exit code.
        $LocalPluginCheckFailed = $Check -and $LASTEXITCODE -ne 0
    }
}

if ($Provider -eq "Both" -or $Provider -eq "Claude") {
    if ($Check) {
        $CheckRows += @(Test-ProviderPackage -ProviderName "Claude" -PackageDirectory "claude-skills" -TargetRoots $ClaudeTargets)
    } else {
        foreach ($Row in Sync-ProviderPackage -ProviderName "Claude" -PackageDirectory "claude-skills" -TargetRoots $ClaudeTargets) {
            $AllRows += $Row
        }
    }
}

if ($Check) {
    Write-Output ""
    Write-Output "Local Agent Skill Check (read-only)"
    Write-Output ""
    $SortedCheckRows = @($CheckRows | Sort-Object Provider, Target, Status, Kind, Path)
    if ($SortedCheckRows.Count -gt 0) {
        $SortedCheckRows | Format-Table -AutoSize
        # Format-Table truncates to the host width; these lines are the
        # untruncated surface that callers and tests match on.
        foreach ($Row in $SortedCheckRows) {
            Write-Output "FINDING $($Row.Status) [$($Row.Provider)] $($Row.Kind) $($Row.Path) <- $($Row.Target)"
        }
    }

    if ($null -ne $LocalPluginResult) {
        Write-Output ""
        Write-Output "Local Codex Plugin Check"
        $LocalPluginResult | Format-List
    }

    if ($SortedCheckRows.Count -gt 0 -or $LocalPluginCheckFailed) {
        $MissingCount = @($SortedCheckRows | Where-Object { $_.Status -eq "Missing" }).Count
        $DriftedCount = @($SortedCheckRows | Where-Object { $_.Status -eq "Drifted" }).Count
        $PluginNote = if ($LocalPluginCheckFailed) { "; local Codex plugin is not current" } else { "" }
        throw "Install check failed: $MissingCount missing, $DriftedCount drifted$PluginNote. Re-run without -Check to restore missing files, or add -Force to overwrite drifted ones."
    }

    Write-Output "PASS - installed entries match source"
    return
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
