<#
.SYNOPSIS
    Projects the canonical grand-sweep skill package into a ZCode user-scope
    skills root (default ~\.zcode\skills\grand-sweep, reached through the
    .zcode junction to D:\DevHome\state\zcode).

.DESCRIPTION
    Check mode (default) compares every source file against the target and
    reports drift (missing, changed, extra); exits 1 when drifted, 0 when in
    sync. -Apply copies every canonical file over the target and removes only
    the extra files the comparison found; it never deletes recursively.
    Unrelated sibling directories are preserved. Refuses unsafe skill names, a
    source without SKILL.md, targets that resolve inside the canonical package,
    and a target that is a file or a reparse point. Never touches any other
    path under the target root.

.PARAMETER SkillName
    Name of the packaged skill to project. Must match ^[a-z][a-z0-9-]*$ and
    exist under codex-skills\skills with a SKILL.md.

.PARAMETER TargetSkillRoot
    The projected skill directory (not the skills root). Defaults to the
    user's ZCode skills root for the named skill.

.PARAMETER Apply
    Copy the canonical package over the target. Without it, check only.

.EXAMPLE
    pwsh scripts/Sync-GrandSweepZCode.ps1              # check, exit 1 on drift
    pwsh scripts/Sync-GrandSweepZCode.ps1 -Apply       # project
#>
[CmdletBinding()]
param (
    [Parameter(Mandatory=$false)]
    [ValidatePattern('\A[a-z][a-z0-9-]*\z')]
    [string]$SkillName = "grand-sweep",

    [Parameter(Mandatory=$false)]
    [string]$TargetSkillRoot,

    [Parameter(Mandatory=$false)]
    [switch]$Apply
)

$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptRoot
$SourcePackage = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot "codex-skills\skills\$SkillName"))

if (-not (Test-Path -LiteralPath (Join-Path $SourcePackage "SKILL.md") -PathType Leaf)) {
    throw "Invalid skill name '$SkillName': not a packaged skill with SKILL.md under codex-skills\skills"
}

if ($SkillName -ne "grand-sweep") {
    throw "Invalid skill name '$SkillName': this sync owns exactly one skill, grand-sweep"
}

if ([string]::IsNullOrWhiteSpace($TargetSkillRoot)) {
    $UserProfile = [Environment]::GetFolderPath("UserProfile")
    $TargetSkillRoot = Join-Path $UserProfile ".zcode\skills\$SkillName"
}
$TargetSkillRoot = [System.IO.Path]::GetFullPath($TargetSkillRoot)

if ($TargetSkillRoot -eq $SourcePackage -or $TargetSkillRoot.StartsWith($SourcePackage + [System.IO.Path]::DirectorySeparatorChar)) {
    throw "Refusing target '$TargetSkillRoot': it resolves inside the canonical package"
}

function Get-RelativeInventory {
    param ([string]$Directory)

    $inventory = @{}
    if (-not (Test-Path -LiteralPath $Directory)) { return $inventory }
    Get-ChildItem -LiteralPath $Directory -Recurse -File | ForEach-Object {
        $relative = $_.FullName.Substring($Directory.Length).TrimStart('\', '/') -replace '\\', '/'
        $inventory[$relative] = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
    }
    return $inventory
}

$sourceInventory = Get-RelativeInventory -Directory $SourcePackage
$targetInventory = Get-RelativeInventory -Directory $TargetSkillRoot

$missing = @($sourceInventory.Keys | Where-Object { -not $targetInventory.ContainsKey($_) } | Sort-Object)
$changed = @($sourceInventory.Keys | Where-Object { $targetInventory.ContainsKey($_) -and $targetInventory[$_] -ne $sourceInventory[$_] } | Sort-Object)
$extra = @($targetInventory.Keys | Where-Object { -not $sourceInventory.ContainsKey($_) } | Sort-Object)

if (-not $Apply) {
    if ($missing.Count -eq 0 -and $changed.Count -eq 0 -and $extra.Count -eq 0) {
        Write-Output "in-sync: $SkillName projected at '$TargetSkillRoot' matches the canonical package"
        exit 0
    }
    foreach ($item in $missing) { Write-Output "missing: $item" }
    foreach ($item in $changed) { Write-Output "changed: $item" }
    foreach ($item in $extra) { Write-Output "extra: $item" }
    Write-Output ("drift: {0} missing, {1} changed, {2} extra in '{3}'" -f `
        $missing.Count, $changed.Count, $extra.Count, $TargetSkillRoot)
    exit 1
}

if (Test-Path -LiteralPath $TargetSkillRoot) {
    $targetItem = Get-Item -LiteralPath $TargetSkillRoot -Force
    if (-not $targetItem.PSIsContainer) {
        throw "Refusing target '$TargetSkillRoot': it is not a skill directory"
    }
    if (($targetItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Refusing target '$TargetSkillRoot': it is a reparse point (junction or link); project into its real directory instead"
    }
}

# No recursive delete: copy every canonical file over the target, then remove
# only the extras the comparison above found, then drop directories left empty.
Get-ChildItem -LiteralPath $SourcePackage -Recurse -File | ForEach-Object {
    $relative = $_.FullName.Substring($SourcePackage.Length).TrimStart('\', '/')
    $destination = Join-Path $TargetSkillRoot $relative
    $destinationParent = Split-Path -Parent $destination
    if (-not (Test-Path -LiteralPath $destinationParent)) {
        New-Item -ItemType Directory -Path $destinationParent -Force | Out-Null
    }
    Copy-Item -LiteralPath $_.FullName -Destination $destination -Force
}
foreach ($item in $extra) {
    $stale = Join-Path $TargetSkillRoot ($item -replace '/', '\')
    if (Test-Path -LiteralPath $stale -PathType Leaf) {
        Remove-Item -LiteralPath $stale -Force
    }
}
Get-ChildItem -LiteralPath $TargetSkillRoot -Recurse -Directory |
    Sort-Object -Property { $_.FullName.Length } -Descending |
    ForEach-Object {
        if ($null -eq (Get-ChildItem -LiteralPath $_.FullName -Force | Select-Object -First 1)) {
            Remove-Item -LiteralPath $_.FullName -Force
        }
    }

Write-Output ("applied: projected '{0}' -> '{1}' ({2} files)" -f `
    $SourcePackage, $TargetSkillRoot, $sourceInventory.Count)
exit 0
