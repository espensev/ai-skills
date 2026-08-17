param (
    [Parameter(Mandatory=$false)]
    [switch]$ShowAll,

    [Parameter(Mandatory=$false)]
    [int]$MaxRows = 0,

    [Parameter(Mandatory=$false)]
    [switch]$FailOnUndeclaredFork
)

$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptRoot
$ManifestPath = Join-Path $RepoRoot "release-manifest.json"
$SourceManifestPath = Join-Path $RepoRoot "skills-src\manifest.json"

if (-not (Test-Path $ManifestPath)) {
    throw "Missing release manifest: $ManifestPath"
}
if (-not (Test-Path $SourceManifestPath)) {
    throw "Missing single-source manifest: $SourceManifestPath"
}

function Get-DescriptionLines {
    param ([string]$Text)

    # Returns every description: line in the leading frontmatter block, tagged
    # with the conditional scope it sits in (shared / claude / codex). Scope is
    # only ever non-shared in a skills-src canon file.
    $Found = @()
    $Block = "shared"
    $InFrontmatter = $false
    $Lines = @($Text -split "\r?\n")
    for ($Index = 0; $Index -lt $Lines.Count; $Index++) {
        $Line = $Lines[$Index]
        $LineNumber = $Index + 1
        if ($Line -eq "---") {
            if (-not $InFrontmatter) {
                $InFrontmatter = $true
                continue
            }
            break
        }
        if (-not $InFrontmatter) {
            continue
        }
        if ($Line -match '^\{\{#(claude|codex)\}\}$') {
            $Block = $Matches[1]
            continue
        }
        if ($Line -match '^\{\{/(claude|codex)\}\}$') {
            $Block = "shared"
            continue
        }
        if ($Line -match "^\s*description:\s*(.*?)\s*$") {
            $Value = $Matches[1].Trim()
            if ($Value -match '^[>|][+-]?$') {
                $Style = $Value.Substring(0, 1)
                $Body = @()
                $Probe = $Index + 1
                while ($Probe -lt $Lines.Count) {
                    $Next = $Lines[$Probe]
                    if ($Next -match '^\s+(.*)$') {
                        $Body += $Matches[1].Trim()
                        $Probe++
                        continue
                    }
                    if ([string]::IsNullOrWhiteSpace($Next)) {
                        $Body += ""
                        $Probe++
                        continue
                    }
                    break
                }
                $Index = $Probe - 1
                $Value = if ($Style -eq ">") { ($Body -join " ").Trim() } else { ($Body -join "`n").Trim() }
            }
            $Found += [pscustomobject]@{
                Text = $Value.Trim('"').Trim("'")
                Scope = $Block
                Line = $LineNumber
            }
        }
    }
    return $Found
}

function Get-SkillDescription {
    param ([string]$SkillPath)

    $Lines = @(Get-DescriptionLines -Text (Get-Content -Raw $SkillPath))
    if ($Lines.Count -eq 0) {
        return ""
    }
    return $Lines[0].Text
}

function Get-ContentHash {
    param ([string]$Path)
    return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.Substring(0, 12)
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

$SourceManifest = Get-Content -Raw $SourceManifestPath | ConvertFrom-Json
$GeneratedSkills = @($SourceManifest.generated_skills)
$ProviderOwnedSharedSkills = @($SourceManifest.provider_owned_shared_skills)
$DeclaredForks = @{}
if ($null -ne $SourceManifest.declared_provider_forks) {
    foreach ($Property in $SourceManifest.declared_provider_forks.PSObject.Properties) {
        $DeclaredForks[$Property.Name] = [string]$Property.Value
    }
}

$ReleaseManifest = Get-Content -Raw $ManifestPath | ConvertFrom-Json
$Records = @()

foreach ($Package in $ReleaseManifest.packages) {
    if ($Package.status -ne "ready") {
        continue
    }
    if ($Package.strategy -ne "portable-runtime") {
        continue
    }

    $PackageRoot = Join-Path $RepoRoot $Package.path

    # Enumerate from the filesystem, not the install manifest: a shared pair
    # that ships in both package trees must be parity-governed even when it is
    # held out of the portable release (telemetry-live-ops is machine-local).
    $SkillsRoot = Join-Path $PackageRoot "skills"
    if (-not (Test-Path $SkillsRoot)) {
        continue
    }

    foreach ($Skill in @(Get-ChildItem -LiteralPath $SkillsRoot -Directory | Select-Object -ExpandProperty Name)) {
        $SkillPath = Join-Path $SkillsRoot "$Skill\SKILL.md"
        if (-not (Test-Path $SkillPath)) {
            continue
        }

        $Records += [pscustomobject]@{
            Skill = $Skill
            Package = $Package.name
            Provider = if ($Package.path -like "claude*") { "claude" } else { "codex" }
            Description = Get-SkillDescription $SkillPath
            Hash = Get-ContentHash $SkillPath
            Path = Get-PortableRelativePath -BasePath $RepoRoot -TargetPath $SkillPath
        }
    }
}

# Findings are hard errors: an unenforced fork nobody declared, or a
# description divergence that no conditional block in the canon accounts for.
$Findings = @()
$Rows = @()
$GeneratorEnforced = 0

# Every governed shared skill must exist in both provider trees. Grouping only
# pairs would otherwise make a one-sided deletion disappear from this report.
foreach ($ExpectedPair in @($GeneratedSkills + $ProviderOwnedSharedSkills | Sort-Object -Unique)) {
    $PairRecords = @($Records | Where-Object { $_.Skill -eq $ExpectedPair })
    foreach ($ProviderName in @("claude", "codex")) {
        if ($ProviderName -notin @($PairRecords | Select-Object -ExpandProperty Provider -Unique)) {
            $Findings += "$ExpectedPair`: governed shared skill is missing from the $ProviderName package tree"
        }
    }
}

foreach ($Group in ($Records | Group-Object Skill | Where-Object { $_.Count -gt 1 })) {
    $Skill = $Group.Name
    $DescriptionCount = @($Group.Group | Select-Object -ExpandProperty Description -Unique).Count
    $HashCount = @($Group.Group | Select-Object -ExpandProperty Hash -Unique).Count

    if ($GeneratedSkills -contains $Skill) {
        # Body parity is byte-verified by Build-ProviderSkillPackages.ps1 -Check,
        # so a body difference here is generator-produced by construction and is
        # not drift. What -Check cannot see is a description that diverges
        # without the canon declaring it, so lint that instead.
        $GeneratorEnforced++
        $SrcPath = Join-Path $RepoRoot "skills-src\$Skill\SKILL.src.md"
        if (-not (Test-Path $SrcPath)) {
            $Findings += "$Skill`: listed in generated_skills but has no canon at skills-src/$Skill/SKILL.src.md"
            continue
        }

        $SrcDescriptions = @(Get-DescriptionLines -Text (Get-Content -Raw $SrcPath))
        foreach ($Provider in @("claude", "codex")) {
            $Applicable = @($SrcDescriptions | Where-Object { $_.Scope -eq "shared" -or $_.Scope -eq $Provider })
            if ($Applicable.Count -ne 1) {
                $Findings += "$Skill`: canon defines $($Applicable.Count) description: lines for $Provider (expected exactly 1) in skills-src/$Skill/SKILL.src.md"
            }
        }

        if ($DescriptionCount -gt 1) {
            foreach ($Provider in @("claude", "codex")) {
                $Applicable = @($SrcDescriptions | Where-Object { $_.Scope -eq "shared" -or $_.Scope -eq $Provider })
                if ($Applicable.Count -eq 1 -and $Applicable[0].Scope -ne $Provider) {
                    $Findings += "$Skill`: claude and codex descriptions diverge, but the $Provider description is not declared in a {{#$Provider}} conditional block (skills-src/$Skill/SKILL.src.md line $($Applicable[0].Line)). Undeclared description divergence."
                }
            }
        }
        continue
    }

    $Declared = $DeclaredForks.ContainsKey($Skill)
    $Forked = ($DescriptionCount -gt 1 -or $HashCount -gt 1)
    if ($Forked -and -not $Declared) {
        $Findings += "$Skill`: provider-owned shared pair differs between claude and codex with no entry in skills-src/manifest.json declared_provider_forks. Either single-source it under skills-src or declare the fork with a reason."
    }

    if (-not $ShowAll -and -not $Forked) {
        continue
    }

    $Rows += [pscustomobject]@{
        Skill = $Skill
        Packages = (($Group.Group | Select-Object -ExpandProperty Package) -join ", ")
        DescriptionVariants = $DescriptionCount
        BodyVariants = $HashCount
        Declared = if ($Declared) { "yes" } else { "NO" }
        Paths = (($Group.Group | Select-Object -ExpandProperty Path) -join "; ")
    }
}

if ($FailOnUndeclaredFork) {
    if ($Findings.Count -gt 0) {
        # Plain output + exit 1 (no throw): under ErrorActionPreference Stop a
        # thrown error record would bypass the caller's LASTEXITCODE handling.
        Write-Output "FAIL - undeclared provider fork or description divergence:"
        $Findings | ForEach-Object { Write-Output "  $_" }
        exit 1
    }

    Write-Output "PASS - no undeclared provider forks ($GeneratorEnforced generator-enforced pairs, $($DeclaredForks.Count) declared fork(s))"
    exit 0
}

Write-Output "$GeneratorEnforced shared pairs are generator-enforced (byte-verified by Build-ProviderSkillPackages.ps1 -Check) and are not parity-reported."
if ($Findings.Count -gt 0) {
    Write-Output "Undeclared drift found (run with -FailOnUndeclaredFork to gate on it):"
    $Findings | ForEach-Object { Write-Output "  $_" }
}

if ($Rows.Count -eq 0) {
    Write-Output "PASS - no unenforced shared skill parity drift found"
} else {
    $SortedRows = @($Rows | Sort-Object Skill)
    if ($MaxRows -gt 0 -and $SortedRows.Count -gt $MaxRows) {
        Write-Output "Showing first $MaxRows of $($SortedRows.Count) unenforced shared skill parity rows."
        $SortedRows = @($SortedRows | Select-Object -First $MaxRows)
    }
    $SortedRows | Format-Table -AutoSize
}
