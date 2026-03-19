param (
    [Parameter(Mandatory=$false)]
    [string]$TargetDir,

    [Parameter(Mandatory=$false)]
    [switch]$Force
)

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptRoot
$ManifestPath = Join-Path $RepoRoot "release-manifest.json"

if (-Not (Test-Path $ManifestPath)) {
    throw "Missing release manifest: $ManifestPath"
}

$Manifest = Get-Content -Raw $ManifestPath | ConvertFrom-Json

if (-Not $TargetDir) {
    $TargetDir = Join-Path $HOME ("OneDrive\Common\" + $Manifest.export_name)
}

if (Test-Path $TargetDir) {
    if (-Not $Force) {
        throw "Target already exists. Re-run with -Force to replace it: $TargetDir"
    }

    Remove-Item -Recurse -Force $TargetDir
}

New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null
Copy-Item -Path $ManifestPath -Destination (Join-Path $TargetDir "release-manifest.json") -Force

foreach ($Package in $Manifest.packages) {
    if ($Package.status -ne "ready") {
        continue
    }

    $SourceRoot = Join-Path $RepoRoot $Package.path
    $PackageDest = Join-Path $TargetDir $Package.name

    if (-Not (Test-Path $SourceRoot)) {
        throw "Missing package source: $SourceRoot"
    }

    switch ($Package.strategy) {
        "portable-runtime" {
            $ManifestFile = Join-Path $SourceRoot "package\install-manifest.json"
            if (-Not (Test-Path $ManifestFile)) {
                throw "Missing install manifest: $ManifestFile"
            }

            $InstallManifest = Get-Content -Raw $ManifestFile | ConvertFrom-Json

            New-Item -ItemType Directory -Path $PackageDest -Force | Out-Null
            New-Item -ItemType Directory -Path (Join-Path $PackageDest "skills") -Force | Out-Null
            New-Item -ItemType Directory -Path (Join-Path $PackageDest "scripts") -Force | Out-Null
            New-Item -ItemType Directory -Path (Join-Path $PackageDest "docs") -Force | Out-Null
            New-Item -ItemType Directory -Path (Join-Path $PackageDest "package") -Force | Out-Null

            foreach ($File in @("README.md") + $InstallManifest.contract_files + $InstallManifest.optional_contract_files) {
                $SourceFile = Join-Path $SourceRoot $File
                if (Test-Path $SourceFile) {
                    Copy-Item -Path $SourceFile -Destination (Join-Path $PackageDest $File) -Force
                }
            }

            Copy-Item -Path $ManifestFile -Destination (Join-Path $PackageDest "package\install-manifest.json") -Force
            Copy-Item -Path (Join-Path $SourceRoot "docs\skill-portability-notes.md") -Destination (Join-Path $PackageDest "docs\skill-portability-notes.md") -Force

            foreach ($RuntimeFile in $InstallManifest.runtime_files) {
                $FileName = Split-Path $RuntimeFile -Leaf
                Copy-Item -Path (Join-Path $SourceRoot $RuntimeFile) -Destination (Join-Path $PackageDest "scripts\$FileName") -Force
            }

            foreach ($RuntimeDir in $InstallManifest.runtime_directories) {
                Copy-Item -Path (Join-Path $SourceRoot $RuntimeDir) -Destination (Join-Path $PackageDest "scripts") -Recurse -Force
            }

            foreach ($Skill in @($InstallManifest.default_skills) + @($InstallManifest.optional_skills)) {
                Copy-Item -Path (Join-Path $SourceRoot ("skills\" + $Skill)) -Destination (Join-Path $PackageDest "skills") -Recurse -Force
            }
        }

        "gemini-adapter" {
            $GeminiManifestFile = Join-Path $SourceRoot "package\install-manifest.json"

            New-Item -ItemType Directory -Path $PackageDest -Force | Out-Null
            New-Item -ItemType Directory -Path (Join-Path $PackageDest "skills") -Force | Out-Null
            New-Item -ItemType Directory -Path (Join-Path $PackageDest ".gemini") -Force | Out-Null
            New-Item -ItemType Directory -Path (Join-Path $PackageDest "scripts") -Force | Out-Null
            New-Item -ItemType Directory -Path (Join-Path $PackageDest "docs") -Force | Out-Null
            New-Item -ItemType Directory -Path (Join-Path $PackageDest "package") -Force | Out-Null

            foreach ($File in @("README.md", "GEMINI.md")) {
                Copy-Item -Path (Join-Path $SourceRoot $File) -Destination (Join-Path $PackageDest $File) -Force
            }

            Copy-Item -Path (Join-Path $SourceRoot "scripts\bootstrap.ps1") -Destination (Join-Path $PackageDest "scripts\bootstrap.ps1") -Force
            Copy-Item -Path (Join-Path $SourceRoot "docs\skill-portability-notes.md") -Destination (Join-Path $PackageDest "docs\skill-portability-notes.md") -Force
            Copy-Item -Path (Join-Path $SourceRoot "skills") -Destination $PackageDest -Recurse -Force
            Copy-Item -Path (Join-Path $SourceRoot ".gemini\commands") -Destination (Join-Path $PackageDest ".gemini") -Recurse -Force

            if (Test-Path $GeminiManifestFile) {
                Copy-Item -Path $GeminiManifestFile -Destination (Join-Path $PackageDest "package\install-manifest.json") -Force
            }
        }

        default {
            throw "Unsupported package strategy: $($Package.strategy)"
        }
    }
}

Write-Output $TargetDir
