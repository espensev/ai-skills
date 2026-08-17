param (
    [Parameter(Mandatory=$false)]
    [switch]$Check
)

$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptRoot
$SourceRoot = Join-Path $RepoRoot "skills-src"
$ManifestPath = Join-Path $SourceRoot "manifest.json"

if (-not (Test-Path $ManifestPath)) {
    throw "Missing single-source manifest: $ManifestPath"
}

# Token vocabulary substituted into generated SKILL.md files.
# Each token maps to @(claude value, codex value). Values use [char] codes for
# non-ASCII glyphs so the vocabulary stays visible in ASCII-only diffs.
$TokenValues = [ordered]@{
    "{{cmd}}"            = @("/", "$")
    "{{ctx}}"            = @("CLAUDE.md", "AGENTS.md")
    "{{ctx-other}}"      = @("AGENTS.md", "CLAUDE.md")
    "{{Provider}}"       = @("Claude", "Codex")
    "{{Provider-other}}" = @("Codex", "Claude")
    "{{provider-lc}}"    = @("claude", "codex")
    "{{wt}}"             = @(".claude/worktrees", ".worktrees")
    "{{dash}}"           = @(([string][char]0x2014), "-")
    "{{arrow}}"          = @(([string][char]0x2192), "->")
    "{{bidir}}"          = @(([string][char]0x2194), "<->")
    "{{Model-low}}"      = @("Haiku", "Mini")
    "{{Model-mid}}"      = @("Sonnet", "Standard")
    "{{Model-high}}"     = @("Opus", "Max")
    "{{model-low-lc}}"   = @("haiku", "mini")
    "{{model-mid-lc}}"   = @("sonnet", "standard")
    "{{model-high-lc}}"  = @("opus", "max")
}

function Expand-SkillSource {
    param (
        [string]$SkillName,
        [string]$SourceText,
        [string]$ProviderName,
        [int]$ProviderIndex
    )

    # Pass 1: resolve {{#claude}} / {{#codex}} line-scoped conditional blocks.
    $OutputLines = New-Object System.Collections.Generic.List[string]
    $OpenBlock = $null
    foreach ($Line in $SourceText.Split("`n")) {
        if ($Line -match '^\{\{#(claude|codex)\}\}$') {
            if ($null -ne $OpenBlock) {
                throw "$SkillName`: nested conditional block is not supported"
            }
            $OpenBlock = $Matches[1]
            continue
        }
        if ($Line -match '^\{\{/(claude|codex)\}\}$') {
            if ($OpenBlock -ne $Matches[1]) {
                throw "$SkillName`: unbalanced conditional block close: $Line"
            }
            $OpenBlock = $null
            continue
        }
        if ($null -eq $OpenBlock -or $OpenBlock -eq $ProviderName) {
            $OutputLines.Add($Line)
        }
    }
    if ($null -ne $OpenBlock) {
        throw "$SkillName`: unterminated conditional block: {{#$OpenBlock}}"
    }

    # Pass 2: ordinal, case-sensitive token substitution.
    $Text = $OutputLines -join "`n"
    foreach ($Token in $TokenValues.Keys) {
        $Text = $Text.Replace($Token, $TokenValues[$Token][$ProviderIndex])
    }
    if ($Text.Contains("{{") -or $Text.Contains("}}")) {
        throw "$SkillName`: unexpanded token remains in generated $ProviderName output"
    }

    return $Text
}

function Test-BytesEqual {
    param (
        [byte[]]$Expected,
        [string]$TargetPath
    )

    if (-not (Test-Path $TargetPath)) {
        return $false
    }
    $Actual = [System.IO.File]::ReadAllBytes($TargetPath)
    if ($Actual.Length -ne $Expected.Length) {
        return $false
    }
    return [Convert]::ToBase64String($Actual) -eq [Convert]::ToBase64String($Expected)
}

function Get-PortableRelativePath {
    param (
        [string]$BasePath,
        [string]$TargetPath
    )

    $BaseFull = [System.IO.Path]::GetFullPath($BasePath)
    $TargetFull = [System.IO.Path]::GetFullPath($TargetPath)
    return [System.IO.Path]::GetRelativePath($BaseFull, $TargetFull) -replace "\\", "/"
}

$Manifest = Get-Content -Raw $ManifestPath | ConvertFrom-Json
$GeneratedSkills = @($Manifest.generated_skills)
if ($GeneratedSkills.Count -eq 0) {
    throw "Manifest lists no generated skills: $ManifestPath"
}
$Duplicates = @($GeneratedSkills | Group-Object | Where-Object { $_.Count -gt 1 })
if ($Duplicates.Count -gt 0) {
    throw "Manifest lists duplicate generated skills: $(($Duplicates | Select-Object -ExpandProperty Name) -join ', ')"
}
$Overlap = @($GeneratedSkills | Where-Object { @($Manifest.provider_owned_shared_skills) -contains $_ })
if ($Overlap.Count -gt 0) {
    throw "Manifest lists skills as both generated and provider-owned: $($Overlap -join ', ')"
}

$Providers = @(
    [pscustomobject]@{ Name = "claude"; Index = 0; PackageRoot = Join-Path $RepoRoot "claude-skills" },
    [pscustomobject]@{ Name = "codex";  Index = 1; PackageRoot = Join-Path $RepoRoot "codex-skills" }
)
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$StaleFiles = @()
$OrphanFiles = @()
$FileCount = 0

foreach ($Skill in $GeneratedSkills) {
    $SkillSourceDir = Join-Path $SourceRoot $Skill
    $SourcePath = Join-Path $SkillSourceDir "SKILL.src.md"
    if (-not (Test-Path $SourcePath)) {
        throw "Missing canonical source for generated skill: $SourcePath"
    }
    $SourceText = [System.IO.File]::ReadAllText($SourcePath, $Utf8NoBom)
    if ($SourceText.Contains("`r")) {
        throw "CRLF line endings detected in canonical source: $SourcePath. Src files must be LF-only; CR would corrupt conditional-block markers."
    }

    # Planned outputs: expanded SKILL.md per provider plus verbatim support files.
    $PlannedFiles = @()
    foreach ($Provider in $Providers) {
        $TargetDir = Join-Path $Provider.PackageRoot "skills\$Skill"
        if (-not (Test-Path $TargetDir)) {
            throw "Generated skill has no $($Provider.Name) package directory: $TargetDir"
        }
        $Expanded = Expand-SkillSource -SkillName $Skill -SourceText $SourceText `
            -ProviderName $Provider.Name -ProviderIndex $Provider.Index
        $PlannedFiles += [pscustomobject]@{
            TargetPath = Join-Path $TargetDir "SKILL.md"
            Bytes = $Utf8NoBom.GetBytes($Expanded)
        }
    }

    # files/ ships verbatim to both providers; files-claude/ and files-codex/
    # ship verbatim to that provider only (a support file one provider has no
    # runtime for, e.g. a Claude-only tool reference).
    $FilesDir = Join-Path $SkillSourceDir "files"
    if (Test-Path $FilesDir) {
        foreach ($SupportFile in @(Get-ChildItem -LiteralPath $FilesDir -Recurse -File)) {
            $Relative = Get-PortableRelativePath -BasePath $FilesDir -TargetPath $SupportFile.FullName
            $Bytes = [System.IO.File]::ReadAllBytes($SupportFile.FullName)
            foreach ($Provider in $Providers) {
                $PlannedFiles += [pscustomobject]@{
                    TargetPath = Join-Path $Provider.PackageRoot "skills\$Skill\$($Relative -replace '/', '\')"
                    Bytes = $Bytes
                }
            }
        }
    }

    foreach ($Provider in $Providers) {
        $ProviderFilesDir = Join-Path $SkillSourceDir "files-$($Provider.Name)"
        if (-not (Test-Path $ProviderFilesDir)) {
            continue
        }
        foreach ($SupportFile in @(Get-ChildItem -LiteralPath $ProviderFilesDir -Recurse -File)) {
            $Relative = Get-PortableRelativePath -BasePath $ProviderFilesDir -TargetPath $SupportFile.FullName
            $PlannedFiles += [pscustomobject]@{
                TargetPath = Join-Path $Provider.PackageRoot "skills\$Skill\$($Relative -replace '/', '\')"
                Bytes = [System.IO.File]::ReadAllBytes($SupportFile.FullName)
            }
        }
    }

    # Orphan detection: any .md file in a generated skill's package dir that the
    # build does not plan is drift (e.g. a hand-added doc the generator would
    # never produce or clean up).
    $PlannedPaths = @($PlannedFiles | ForEach-Object { [System.IO.Path]::GetFullPath($_.TargetPath) })
    foreach ($Provider in $Providers) {
        $TargetDir = Join-Path $Provider.PackageRoot "skills\$Skill"
        foreach ($ExistingMd in @(Get-ChildItem -LiteralPath $TargetDir -Recurse -File -Filter *.md)) {
            if ($PlannedPaths -notcontains [System.IO.Path]::GetFullPath($ExistingMd.FullName)) {
                $OrphanFiles += Get-PortableRelativePath -BasePath $RepoRoot -TargetPath $ExistingMd.FullName
            }
        }
    }

    foreach ($Planned in $PlannedFiles) {
        $FileCount++
        if (Test-BytesEqual -Expected $Planned.Bytes -TargetPath $Planned.TargetPath) {
            continue
        }
        if ($Check) {
            $StaleFiles += Get-PortableRelativePath -BasePath $RepoRoot -TargetPath $Planned.TargetPath
        } else {
            $TargetParent = Split-Path -Parent $Planned.TargetPath
            if (-not (Test-Path $TargetParent)) {
                New-Item -ItemType Directory -Path $TargetParent -Force | Out-Null
            }
            [System.IO.File]::WriteAllBytes($Planned.TargetPath, $Planned.Bytes)
            $StaleFiles += Get-PortableRelativePath -BasePath $RepoRoot -TargetPath $Planned.TargetPath
        }
    }
}

if ($Check) {
    $Problems = @()
    if ($StaleFiles.Count -gt 0) {
        $Problems += "Provider skill packages are stale relative to skills-src. Run scripts/Build-ProviderSkillPackages.ps1. Differing files:`n" + ($StaleFiles -join "`n")
    }
    if ($OrphanFiles.Count -gt 0) {
        $Problems += "Unplanned .md files found inside generated skill package directories (remove them or move their content into skills-src):`n" + ($OrphanFiles -join "`n")
    }
    if ($Problems.Count -gt 0) {
        # Plain output + exit 1 (no Write-Error): under ErrorActionPreference
        # Stop a thrown error record would bypass the caller's LASTEXITCODE
        # handling and double-report. This yields one clear failure in both
        # standalone -File runs and gate-step invocations.
        Write-Output ("FAIL - " + ($Problems -join "`n"))
        exit 1
    }

    Write-Output "PASS - provider skill packages match skills-src ($FileCount files across $($GeneratedSkills.Count) skills)"
    exit 0
}

if ($OrphanFiles.Count -gt 0) {
    Write-Output "WARNING - unplanned .md files inside generated skill package directories (not touched by the build):"
    $OrphanFiles | ForEach-Object { Write-Output "  $_" }
}

if ($StaleFiles.Count -gt 0) {
    Write-Output "Regenerated $($StaleFiles.Count) of $FileCount package files from skills-src:"
    $StaleFiles | ForEach-Object { Write-Output "  $_" }
} else {
    Write-Output "Provider skill packages already match skills-src ($FileCount files across $($GeneratedSkills.Count) skills)"
}
