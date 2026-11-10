<#
.SYNOPSIS
    Audits and prunes stale disabled [[skills.config]] path entries in Codex config.toml.
.DESCRIPTION
    Removes only simple [[skills.config]] blocks whose path no longer exists on disk
    and whose enabled flag is explicitly false. Preserves all valid skill entries,
    name-based skill rules, enabled/complex blocks, comments, and unrelated TOML
    sections. Validates semantic TOML equivalence with Python tomllib and the
    AiEnvironment safe config reader before atomic replacement.
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [string[]] $ConfigPath = @(),
    [switch] $IncludeCompanionAccounts,
    [switch] $Check,
    [switch] $DryRun,
    [string] $BackupDirectory = '',
    [string] $VerifierPath = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'AiEnvironment\Private\Common.ps1')

function Resolve-DefaultCodexStateRoot {
    if (-not [string]::IsNullOrWhiteSpace($env:DEVHOME_STATE_ROOT)) {
        return Resolve-AiPath $env:DEVHOME_STATE_ROOT
    }
    if (-not [string]::IsNullOrWhiteSpace($env:MACHINE_CODE_ROOT)) {
        return Resolve-AiPath (Join-Path $env:MACHINE_CODE_ROOT 'DevHome\state')
    }
    return 'D:\DevHome\state'
}

function Build-CodexSkillConfigPlan {
    param([Parameter(Mandatory)][string] $TargetPath)

    $resolvedPath = Resolve-AiPath $TargetPath
    if (-not (Test-Path -LiteralPath $resolvedPath -PathType Leaf)) {
        throw "Codex config missing: $resolvedPath"
    }

    $beforeBytes = [System.IO.File]::ReadAllBytes($resolvedPath)
    $utf8Strict = [System.Text.UTF8Encoding]::new($false, $true)
    $rawText = $utf8Strict.GetString($beforeBytes)
    if ($rawText.Length -gt 0 -and $rawText[0] -eq [char]0xFEFF) {
        $rawText = $rawText.Substring(1)
    }
    $newline = if ($rawText.Contains("`r`n")) { "`r`n" } else { "`n" }
    $lines = @($rawText -split '\r?\n')

    # Verify the untouched file parses cleanly before planning any edit.
    $null = Read-AiCodexConfig -Path $resolvedPath

    $removeLineFlags = New-Object bool[] $lines.Count
    $removedSkillIndices = [System.Collections.Generic.List[int]]::new()
    $prunedPaths = [System.Collections.Generic.List[string]]::new()
    $totalSkillBlocks = 0
    $byNameBlocks = 0
    $existingPathBlocks = 0
    $retainedMissingBlocks = 0

    $index = 0
    while ($index -lt $lines.Count) {
        $trimmed = $lines[$index].Trim()
        if ($trimmed -cne '[[skills.config]]') {
            $index++
            continue
        }

        $skillBlockOrdinal = $totalSkillBlocks
        $totalSkillBlocks++
        $startIndex = $index
        $scanIndex = $index + 1
        while ($scanIndex -lt $lines.Count) {
            $candidateTrimmed = $lines[$scanIndex].Trim()
            if ($candidateTrimmed.StartsWith('[')) {
                break
            }
            $scanIndex++
        }

        $endIndex = $scanIndex - 1
        # Keep any trailing comment cluster attached to a following non-skill section.
        if ($scanIndex -lt $lines.Count -and $lines[$scanIndex].Trim() -cne '[[skills.config]]') {
            $peel = $endIndex
            $sawTrailingComment = $false
            while ($peel -gt $startIndex) {
                $peelTrimmed = $lines[$peel].Trim()
                if ($peelTrimmed.StartsWith('#')) {
                    $sawTrailingComment = $true
                    $peel--
                    continue
                }
                if ([string]::IsNullOrWhiteSpace($peelTrimmed) -and -not $sawTrailingComment) {
                    $peel--
                    continue
                }
                break
            }
            if ($sawTrailingComment) {
                while ($peel -gt $startIndex -and [string]::IsNullOrWhiteSpace($lines[$peel].Trim())) {
                    $peel--
                }
                $endIndex = $peel
            }
        }

        $blockPath = $null
        $blockEnabled = $null
        $hasComplexContent = $false
        for ($lineIndex = $startIndex + 1; $lineIndex -le $endIndex; $lineIndex++) {
            $entryTrimmed = $lines[$lineIndex].Trim()
            if ([string]::IsNullOrWhiteSpace($entryTrimmed)) {
                continue
            }
            if ($entryTrimmed.StartsWith('#')) {
                $hasComplexContent = $true
                continue
            }
            $commentStripped = Remove-AiTomlInlineComment -Value $entryTrimmed
            if ($commentStripped.Length -ne $entryTrimmed.Length) {
                $hasComplexContent = $true
            }
            if ($entryTrimmed -notmatch '^([A-Za-z0-9_-]+)\s*=\s*(.*)$') {
                $hasComplexContent = $true
                continue
            }
            $keyName = $Matches[1]
            $rawVal = $Matches[2]
            switch ($keyName) {
                'path' {
                    $parsedPath = ConvertFrom-AiTomlScalar $rawVal
                    if ($parsedPath -isnot [string] -or $null -ne $blockPath) {
                        $hasComplexContent = $true
                    }
                    else {
                        $blockPath = $parsedPath
                    }
                }
                'enabled' {
                    $parsedEnabled = ConvertFrom-AiTomlScalar $rawVal
                    if ($parsedEnabled -isnot [bool] -or $null -ne $blockEnabled) {
                        $hasComplexContent = $true
                    }
                    else {
                        $blockEnabled = $parsedEnabled
                    }
                }
                'name' {
                    $parsedName = ConvertFrom-AiTomlScalar $rawVal
                    if ($parsedName -isnot [string]) {
                        $hasComplexContent = $true
                    }
                }
                default {
                    $hasComplexContent = $true
                }
            }
        }

        if ([string]::IsNullOrWhiteSpace($blockPath)) {
            $byNameBlocks++
        }
        else {
            $pathExists = $false
            $resolvedSkillPath = $blockPath
            try {
                $resolvedSkillPath = Resolve-AiPath $blockPath
                $pathExists = Test-Path -LiteralPath $resolvedSkillPath -PathType Leaf
            }
            catch {
                $pathExists = $false
            }

            if ($pathExists) {
                $existingPathBlocks++
            }
            elseif (-not $hasComplexContent -and $blockEnabled -eq $false) {
                for ($mark = $startIndex; $mark -le $endIndex; $mark++) {
                    $removeLineFlags[$mark] = $true
                }
                $removedSkillIndices.Add($skillBlockOrdinal) | Out-Null
                $prunedPaths.Add($resolvedSkillPath) | Out-Null
            }
            else {
                $retainedMissingBlocks++
            }
        }

        $index = $scanIndex
    }

    $afterLines = [System.Collections.Generic.List[string]]::new()
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if (-not $removeLineFlags[$i]) {
            $afterLines.Add($lines[$i]) | Out-Null
        }
    }
    $afterText = $afterLines -join $newline

    if ($removedSkillIndices.Count -gt 0) {
        Assert-CodexTomlPruneEquivalence `
            -BeforeBytes $beforeBytes `
            -AfterText $afterText `
            -RemovedSkillIndices @($removedSkillIndices) `
            -ExpectedRemainingMissingPaths $retainedMissingBlocks
    }

    return [pscustomobject][ordered]@{
        Path = $resolvedPath
        BeforeBytes = $beforeBytes
        AfterText = $afterText
        TotalSkillBlocks = $totalSkillBlocks
        ExistingPathBlocks = $existingPathBlocks
        ByNameBlocks = $byNameBlocks
        PrunedCount = $removedSkillIndices.Count
        RetainedMissingCount = $retainedMissingBlocks
        PrunedPaths = @($prunedPaths)
    }
}

function Assert-CodexTomlPruneEquivalence {
    param(
        [Parameter(Mandatory)][byte[]] $BeforeBytes,
        [Parameter(Mandatory)][string] $AfterText,
        [Parameter(Mandatory)][int[]] $RemovedSkillIndices,
        [Parameter(Mandatory)][int] $ExpectedRemainingMissingPaths
    )

    $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("codex-skill-prune-verify-$PID-" + [guid]::NewGuid().ToString('N'))
    $beforeTmp = "$tempRoot.before.toml"
    $afterTmp = "$tempRoot.after.toml"
    $indicesJson = ($RemovedSkillIndices | ConvertTo-Json -Compress)
    if ($RemovedSkillIndices.Count -eq 1) {
        $indicesJson = "[$indicesJson]"
    }

    $verifyPy = @'
import json
import pathlib
import sys
import tomllib

before_path = pathlib.Path(sys.argv[1])
after_path = pathlib.Path(sys.argv[2])
removed = set(json.loads(sys.argv[3]))

before = tomllib.loads(before_path.read_text(encoding="utf-8-sig"))
after = tomllib.loads(after_path.read_text(encoding="utf-8-sig"))

before_other = {k: v for k, v in before.items() if k != "skills"}
after_other = {k: v for k, v in after.items() if k != "skills"}
if before_other != after_other:
    sys.exit(11)

before_skills = dict(before.get("skills", {}))
after_skills = dict(after.get("skills", {}))
before_cfg = before_skills.pop("config", [])
after_cfg = after_skills.pop("config", [])
if before_skills != after_skills:
    sys.exit(12)

expected_cfg = [entry for idx, entry in enumerate(before_cfg) if idx not in removed]
if after_cfg != expected_cfg:
    sys.exit(13)
'@

    try {
        [System.IO.File]::WriteAllBytes($beforeTmp, $BeforeBytes)
        [System.IO.File]::WriteAllText($afterTmp, $AfterText, [System.Text.UTF8Encoding]::new($false))

        $python = (Get-Command python -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
        $null = & $python -B -c $verifyPy $beforeTmp $afterTmp $indicesJson
        if ($LASTEXITCODE -ne 0) {
            throw "Semantic TOML equivalence verification failed (code=$LASTEXITCODE)."
        }

        $parsedAfter = Read-AiCodexConfig -Path $afterTmp
        $afterMissing = 0
        foreach ($entry in @($parsedAfter.Skills)) {
            $entryPath = [string](Get-AiProperty $entry 'Path')
            if ([string]::IsNullOrWhiteSpace($entryPath)) { continue }
            if (-not (Test-Path -LiteralPath (Resolve-AiPath $entryPath) -PathType Leaf)) {
                $afterMissing++
            }
        }
        if ($afterMissing -ne $ExpectedRemainingMissingPaths) {
            throw "Post-prune missing skill path count ($afterMissing) did not match expected ($ExpectedRemainingMissingPaths)."
        }
    }
    finally {
        foreach ($tmp in @($beforeTmp, $afterTmp)) {
            if (Test-Path -LiteralPath $tmp -PathType Leaf) {
                Remove-Item -LiteralPath $tmp -Force
            }
        }
    }
}

$targets = [System.Collections.Generic.List[string]]::new()
if ($ConfigPath.Count -gt 0) {
    foreach ($candidate in $ConfigPath) {
        $targets.Add((Resolve-AiPath $candidate)) | Out-Null
    }
}
else {
    $stateRoot = Resolve-DefaultCodexStateRoot
    $primaryHome = if (-not [string]::IsNullOrWhiteSpace($env:CODEX_HOME)) {
        Resolve-AiPath $env:CODEX_HOME
    }
    else {
        Join-Path $stateRoot 'codex'
    }
    $targets.Add((Resolve-AiPath (Join-Path $primaryHome 'config.toml'))) | Out-Null

    if ($IncludeCompanionAccounts) {
        foreach ($accountName in @('alt', 'account3', 'account4')) {
            $companionConfig = Join-Path $stateRoot "codex-accounts\$accountName\config.toml"
            if (Test-Path -LiteralPath $companionConfig -PathType Leaf) {
                $targets.Add((Resolve-AiPath $companionConfig)) | Out-Null
            }
        }
    }
}

$uniqueTargets = [System.Collections.Generic.List[string]]::new()
$seenTargets = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
foreach ($target in $targets) {
    if ($seenTargets.Add($target)) {
        $uniqueTargets.Add($target) | Out-Null
    }
}

$plans = @(foreach ($target in $uniqueTargets) {
    Build-CodexSkillConfigPlan -TargetPath $target
})

$mutatingPlans = @($plans | Where-Object { $_.PrunedCount -gt 0 })
if (-not $Check -and -not $DryRun -and -not $WhatIfPreference -and $mutatingPlans.Count -gt 0) {
    foreach ($plan in $mutatingPlans) {
        Assert-AiControllerIdentity -TargetPath $plan.Path -VerifierPath $VerifierPath
    }
}

$results = [System.Collections.Generic.List[object]]::new()
$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
$stamp = [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-fff')

foreach ($plan in $plans) {
    $status = 'Current'
    $backupPath = $null

    if ($Check) {
        $status = if ($plan.PrunedCount -gt 0 -or $plan.RetainedMissingCount -gt 0) { 'Drift' } else { 'Current' }
    }
    elseif ($DryRun) {
        $status = if ($plan.PrunedCount -gt 0) { 'DryRun' } else { 'Current' }
    }
    elseif ($plan.PrunedCount -gt 0) {
        $status = 'Planned'
        if ($PSCmdlet.ShouldProcess($plan.Path, "Prune $($plan.PrunedCount) stale disabled [[skills.config]] block(s)")) {
            $currentBytes = [System.IO.File]::ReadAllBytes($plan.Path)
            if (-not [System.Linq.Enumerable]::SequenceEqual([byte[]]$currentBytes, [byte[]]$plan.BeforeBytes)) {
                throw "Concurrent modification detected before replacing Codex config: $($plan.Path)"
            }

            $effectiveBackupDir = if (-not [string]::IsNullOrWhiteSpace($BackupDirectory)) {
                Resolve-AiPath $BackupDirectory
            }
            else {
                Join-Path ([System.IO.Path]::GetDirectoryName($plan.Path)) 'hook-backups'
            }
            [void][System.IO.Directory]::CreateDirectory($effectiveBackupDir)
            $backupPath = Join-Path $effectiveBackupDir "config.toml.$stamp.bak"
            [System.IO.File]::WriteAllBytes($backupPath, $plan.BeforeBytes)

            $tempWritePath = "$($plan.Path).$PID.$([guid]::NewGuid().ToString('N')).tmp"
            try {
                [System.IO.File]::WriteAllText($tempWritePath, $plan.AfterText, $utf8NoBom)
                [System.IO.File]::Replace($tempWritePath, $plan.Path, [NullString]::Value)
            }
            finally {
                if (Test-Path -LiteralPath $tempWritePath -PathType Leaf) {
                    Remove-Item -LiteralPath $tempWritePath -Force
                }
            }
            $status = 'Updated'
        }
    }

    $results.Add([pscustomobject][ordered]@{
        Status = $status
        Path = $plan.Path
        BackupPath = $backupPath
        TotalSkillBlocks = $plan.TotalSkillBlocks
        RemainingSkillBlocks = $plan.TotalSkillBlocks - $plan.PrunedCount
        ExistingPathBlocks = $plan.ExistingPathBlocks
        ByNameBlocks = $plan.ByNameBlocks
        PrunedCount = $plan.PrunedCount
        RetainedMissingCount = $plan.RetainedMissingCount
    }) | Out-Null
}

$output = @($results)
$output
if ($Check -and @($output | Where-Object { $_.Status -cne 'Current' }).Count -gt 0) {
    exit 1
}
$global:LASTEXITCODE = 0
exit 0
