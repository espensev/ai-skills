param (
    [Parameter(Mandatory=$false)]
    [string]$ReadmePath,

    [Parameter(Mandatory=$false)]
    [switch]$Check
)

$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptRoot
$ManifestPath = Join-Path $RepoRoot "release-manifest.json"

if (-not $ReadmePath) {
    $ReadmePath = Join-Path $RepoRoot "README.md"
}

if (-not (Test-Path $ManifestPath)) {
    throw "Missing release manifest: $ManifestPath"
}
if (-not (Test-Path $ReadmePath)) {
    throw "Missing README: $ReadmePath"
}

$ReleaseManifest = Get-Content -Raw $ManifestPath | ConvertFrom-Json
$Counts = [ordered]@{}
$Total = 0

foreach ($Package in $ReleaseManifest.packages) {
    if ($Package.status -ne "ready") {
        continue
    }

    $PackageRoot = Join-Path $RepoRoot $Package.path
    $InstallManifestPath = Join-Path $PackageRoot "package\install-manifest.json"
    if (-not (Test-Path $InstallManifestPath)) {
        throw "$($Package.name) install manifest missing: package/install-manifest.json"
    }

    $InstallManifest = Get-Content -Raw $InstallManifestPath | ConvertFrom-Json
    switch ($Package.strategy) {
        "portable-runtime" {
            $SkillCount = @($InstallManifest.default_skills).Count + @($InstallManifest.optional_skills).Count
        }
        "gemini-adapter" {
            $SkillCount = @($InstallManifest.skills).Count
        }
        "antigravity-adapter" {
            $SkillCount = @($InstallManifest.skills).Count
        }
        default {
            throw "$($Package.name) uses unsupported count strategy: $($Package.strategy)"
        }
    }

    $Counts[$Package.name] = $SkillCount
    $Total += $SkillCount
}

$Original = Get-Content -Raw $ReadmePath
$TotalPattern = "\d+\s+install-ready skills"
if (([regex]::Matches($Original, $TotalPattern)).Count -ne 1) {
    throw "README total install-ready skill count phrase missing or ambiguous"
}

$Updated = [regex]::Replace($Original, $TotalPattern, "$Total install-ready skills", 1)

foreach ($PackageName in $Counts.Keys) {
    $Pattern = "(\|\s*\*\*$([regex]::Escape($PackageName))\*\*\s*\|\s*)\d+(\s*\|)"
    if (([regex]::Matches($Updated, $Pattern)).Count -ne 1) {
        throw "README package count row missing or ambiguous: $PackageName"
    }
    $Replacement = "`${1}$($Counts[$PackageName])`${2}"
    $Updated = [regex]::Replace($Updated, $Pattern, $Replacement, 1)
}

if ($Check) {
    if ($Updated -ne $Original) {
        Write-Error "README package counts are stale. Run scripts/Update-ReadmePackageCounts.ps1."
        exit 1
    }

    Write-Output "PASS - README package counts match manifests"
    exit 0
}

if ($Updated -ne $Original) {
    Set-Content -Path $ReadmePath -Value $Updated -NoNewline
    Write-Output "Updated README package counts from manifests"
} else {
    Write-Output "README package counts already match manifests"
}
