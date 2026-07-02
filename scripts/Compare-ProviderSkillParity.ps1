param (
    [Parameter(Mandatory=$false)]
    [switch]$IncludeLegacy,

    [Parameter(Mandatory=$false)]
    [switch]$ShowAll,

    [Parameter(Mandatory=$false)]
    [int]$MaxRows = 0
)

$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptRoot
$ManifestPath = Join-Path $RepoRoot "release-manifest.json"

if (-not (Test-Path $ManifestPath)) {
    throw "Missing release manifest: $ManifestPath"
}

function Get-ManifestSkillNames {
    param (
        [object]$Package,
        [object]$InstallManifest
    )

    switch ($Package.strategy) {
        "portable-runtime" { return @($InstallManifest.default_skills) + @($InstallManifest.optional_skills) }
        "gemini-adapter" { return @($InstallManifest.skills) }
        "antigravity-adapter" { return @($InstallManifest.skills) }
        default { return @() }
    }
}

function Get-SkillDescription {
    param ([string]$SkillPath)

    $Text = Get-Content -Raw $SkillPath
    $Frontmatter = [regex]::Match($Text, "(?s)^---\s*(.*?)\s*---")
    if (-not $Frontmatter.Success) {
        return ""
    }

    foreach ($Line in ($Frontmatter.Groups[1].Value -split "\r?\n")) {
        if ($Line -match "^\s*description:\s*(.+?)\s*$") {
            return $Matches[1].Trim().Trim('"').Trim("'")
        }
    }

    return ""
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

$ReleaseManifest = Get-Content -Raw $ManifestPath | ConvertFrom-Json
$Records = @()

foreach ($Package in $ReleaseManifest.packages) {
    if ($Package.status -ne "ready" -and -not $IncludeLegacy) {
        continue
    }
    if ($Package.strategy -notin @("portable-runtime", "gemini-adapter", "antigravity-adapter")) {
        continue
    }

    $PackageRoot = Join-Path $RepoRoot $Package.path
    $InstallManifestPath = Join-Path $PackageRoot "package\install-manifest.json"
    if (-not (Test-Path $InstallManifestPath)) {
        continue
    }

    $InstallManifest = Get-Content -Raw $InstallManifestPath | ConvertFrom-Json
    foreach ($Skill in @(Get-ManifestSkillNames -Package $Package -InstallManifest $InstallManifest)) {
        $SkillPath = Join-Path $PackageRoot "skills\$Skill\SKILL.md"
        if (-not (Test-Path $SkillPath)) {
            continue
        }

        $Records += [pscustomobject]@{
            Skill = $Skill
            Package = $Package.name
            Description = Get-SkillDescription $SkillPath
            Hash = Get-ContentHash $SkillPath
            Path = Get-PortableRelativePath -BasePath $RepoRoot -TargetPath $SkillPath
        }
    }
}

$Rows = @()
foreach ($Group in ($Records | Group-Object Skill | Where-Object { $_.Count -gt 1 })) {
    $DescriptionCount = @($Group.Group | Select-Object -ExpandProperty Description -Unique).Count
    $HashCount = @($Group.Group | Select-Object -ExpandProperty Hash -Unique).Count
    if (-not $ShowAll -and $DescriptionCount -eq 1 -and $HashCount -eq 1) {
        continue
    }

    $Rows += [pscustomobject]@{
        Skill = $Group.Name
        Packages = (($Group.Group | Select-Object -ExpandProperty Package) -join ", ")
        DescriptionVariants = $DescriptionCount
        BodyVariants = $HashCount
        Paths = (($Group.Group | Select-Object -ExpandProperty Path) -join "; ")
    }
}

if ($Rows.Count -eq 0) {
    Write-Output "PASS - no shared skill parity drift found"
} else {
    $SortedRows = @($Rows | Sort-Object Skill)
    if ($MaxRows -gt 0 -and $SortedRows.Count -gt $MaxRows) {
        Write-Output "Showing first $MaxRows of $($SortedRows.Count) shared skill parity rows."
        $SortedRows = @($SortedRows | Select-Object -First $MaxRows)
    }
    $SortedRows | Format-Table -AutoSize
}
