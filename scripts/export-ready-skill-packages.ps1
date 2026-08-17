param (
    [Parameter(Mandatory=$false)]
    [string]$TargetDir,

    [Parameter(Mandatory=$false)]
    [switch]$Force
)

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptRoot
$ManifestPath = Join-Path $RepoRoot "release-manifest.json"

function Test-GeneratedPackageArtifact {
    param ([string]$Path)

    return ($Path -match '(^|[\\/])__pycache__([\\/]|$)' -or $Path -match '\.py[co]$')
}

function Copy-CleanDirectory {
    param (
        [string]$SourcePath,
        [string]$TargetPath
    )

    New-Item -ItemType Directory -Path $TargetPath -Force | Out-Null
    $SourcePrefix = [System.IO.Path]::GetFullPath($SourcePath).TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    ) + [System.IO.Path]::DirectorySeparatorChar
    Get-ChildItem -LiteralPath $SourcePath -Recurse -File -Force |
        Where-Object { -not (Test-GeneratedPackageArtifact $_.FullName) } |
        ForEach-Object {
            $RelativeFile = $_.FullName.Substring($SourcePrefix.Length)
            $TargetFile = Join-Path $TargetPath $RelativeFile
            New-Item -ItemType Directory -Path (Split-Path -Parent $TargetFile) -Force | Out-Null
            Copy-Item -LiteralPath $_.FullName -Destination $TargetFile -Force
        }
}

if (-Not (Test-Path $ManifestPath)) {
    throw "Missing release manifest: $ManifestPath"
}

$Manifest = Get-Content -Raw $ManifestPath | ConvertFrom-Json

if (-Not $TargetDir) {
    $TargetDir = Join-Path $HOME ("OneDrive\Common\common_development\" + $Manifest.export_name)
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
                Copy-CleanDirectory `
                    -SourcePath (Join-Path $SourceRoot $RuntimeDir) `
                    -TargetPath (Join-Path $PackageDest $RuntimeDir)
            }

            foreach ($Skill in @($InstallManifest.default_skills) + @($InstallManifest.optional_skills)) {
                Copy-CleanDirectory `
                    -SourcePath (Join-Path $SourceRoot ("skills\" + $Skill)) `
                    -TargetPath (Join-Path $PackageDest ("skills\" + $Skill))
            }
        }

        default {
            throw "Unsupported package strategy: $($Package.strategy)"
        }
    }
}

Write-Output $TargetDir
