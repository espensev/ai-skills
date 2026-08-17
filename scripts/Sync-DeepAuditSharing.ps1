[CmdletBinding()]
param (
    [Parameter(Mandatory=$false)]
    [string]$SharedRoot = (Join-Path $env:OneDrive "Common\common_development\common_dev"),

    [Parameter(Mandatory=$false)]
    [string]$MachineAgentsSkillsRoot = (Join-Path ([Environment]::GetFolderPath("UserProfile")) ".agents\skills"),

    [Parameter(Mandatory=$false)]
    [string]$MachineCodexSkillsRoot = (Join-Path ([Environment]::GetFolderPath("UserProfile")) ".codex\skills"),

    [Parameter(Mandatory=$false)]
    [string]$MachineCodexAgentsFile = (Join-Path ([Environment]::GetFolderPath("UserProfile")) ".codex\AGENTS.md"),

    [Parameter(Mandatory=$false)]
    [string]$MachineCodexConfig = (Join-Path ([Environment]::GetFolderPath("UserProfile")) ".codex\config.toml"),

    [Parameter(Mandatory=$false)]
    [switch]$Apply
)

$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptRoot
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$Results = New-Object System.Collections.Generic.List[object]

function Add-Result {
    param (
        [string]$Surface,
        [string]$Path,
        [string]$Status
    )

    $Results.Add([pscustomobject]@{
        Surface = $Surface
        Path = $Path
        Status = $Status
    }) | Out-Null
}

function Set-ManagedBlock {
    param (
        [string]$Text,
        [string]$BlockId,
        [string]$Body
    )

    $Start = "<!-- ai-skills:${BlockId}:start -->"
    $End = "<!-- ai-skills:${BlockId}:end -->"
    $Block = "$Start`r`n$Body`r`n$End"
    $Pattern = "(?s)" + [regex]::Escape($Start) + ".*?" + [regex]::Escape($End)

    if ([regex]::IsMatch($Text, $Pattern)) {
        return [regex]::Replace(
            $Text,
            $Pattern,
            [System.Text.RegularExpressions.MatchEvaluator]{ param($Match) $Block },
            1
        )
    }

    $LegacyMarker = "<!-- ai-skills: -->"
    $LegacyPattern = "(?s)" + [regex]::Escape($LegacyMarker) + ".*?" + [regex]::Escape($LegacyMarker)
    if ([regex]::IsMatch($Text, $LegacyPattern)) {
        return [regex]::Replace(
            $Text,
            $LegacyPattern,
            [System.Text.RegularExpressions.MatchEvaluator]{ param($Match) $Block },
            1
        )
    }

    $Trimmed = $Text.TrimEnd("`r", "`n")
    if ([string]::IsNullOrWhiteSpace($Trimmed)) {
        return $Block + "`r`n"
    }
    return $Trimmed + "`r`n`r`n" + $Block + "`r`n"
}

function Set-TextFile {
    param (
        [string]$Surface,
        [string]$Path,
        [string]$Text
    )

    $Current = if (Test-Path -LiteralPath $Path) {
        [System.IO.File]::ReadAllText($Path)
    } else {
        ""
    }

    if ($Current -ceq $Text) {
        Add-Result -Surface $Surface -Path $Path -Status "current"
        return
    }
    if (-not $Apply) {
        Add-Result -Surface $Surface -Path $Path -Status "would-update"
        return
    }

    $Parent = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $Parent)) {
        New-Item -ItemType Directory -Path $Parent -Force | Out-Null
    }
    [System.IO.File]::WriteAllText($Path, $Text, $Utf8NoBom)
    Add-Result -Surface $Surface -Path $Path -Status "updated"
}

function Add-DeepAuditTableRow {
    param (
        [string]$Text,
        [string]$Purpose
    )

    if ($Text -match '(?m)^\| `/deep-audit` \|') {
        return $Text
    }

    $Row = '| `/deep-audit` | ' + $Purpose + ' |' + "`r`n"
    $Pattern = '(?m)^(\| `/manager` .*\|\r?\n)'
    if (-not [regex]::IsMatch($Text, $Pattern)) {
        throw "Shared skill table has no /manager row to anchor /deep-audit"
    }
    return [regex]::Replace($Text, $Pattern, ('$1' + $Row), 1)
}

function Update-SharedClaudeRules {
    param (
        [string]$Path,
        [int]$ClaudeSkillCount,
        [int]$CodexSkillCount
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Missing shared Claude rules: $Path"
    }

    $Text = [System.IO.File]::ReadAllText($Path)
    $Text = Add-DeepAuditTableRow -Text $Text -Purpose 'Evidence-backed, read-only runtime efficiency and scalability audits'

    $ProviderPattern = '(?s)(Provider targets \(status per the repo''s `release-manifest\.json`\):\r?\n)(?:- .*?\r?\n)+(\r?\nShared architecture:)'
    $ProviderBlock = @'
- `claude-skills/` — {0} install-ready skills for Claude Code
- `codex-skills/` — {1} install-ready skills for OpenAI Codex
'@ -f $ClaudeSkillCount, $CodexSkillCount -replace "`n", "`r`n"
    if ([regex]::IsMatch($Text, $ProviderPattern)) {
        $Text = [regex]::Replace($Text, $ProviderPattern, ('$1' + $ProviderBlock.TrimEnd() + '$2'), 1)
    }

    $Body = @'
## Deep Audit Routing

- Use `/deep-audit discover <scope>` for a new multi-pass runtime efficiency or
  scalability audit; use `resume` only for unambiguous saved audit state.
- The skill is read-only toward product code by default and requires explicit
  authority for risky profiling, load, fault, restart, privileged, production,
  or paid activity.
- Route ordinary diff review, one known regression with a requested fix,
  bounded feasibility research, tests/coverage, and security assessment to
  their narrower workflows. Route parallel remediation, approval gates, and
  implementation ownership to `/manager` or another orchestration workflow.
'@ -replace "`n", "`r`n"
    $Text = Set-ManagedBlock -Text $Text -BlockId "deep-audit" -Body $Body.Trim()
    Set-TextFile -Surface "shared-claude-rules" -Path $Path -Text $Text
}

function Update-SharedCodexRules {
    param (
        [string]$Path,
        [int]$ClaudeSkillCount,
        [int]$CodexSkillCount
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Missing shared Codex rules: $Path"
    }

    $Text = [System.IO.File]::ReadAllText($Path)
    $Text = Add-DeepAuditTableRow -Text $Text -Purpose 'Evidence-backed, read-only runtime efficiency and scalability audits'
    $SharedSkillsText = @'
Skills in `.agents/skills/` here are the cross-machine shared source.
Each machine synchronizes selected skills into its plugin-managed `~/.agents/skills/` root without replacing that entire tree.
'@ -replace "`n", "`r`n"
    $Text = [regex]::Replace(
        $Text,
        '(?m)^Skills in `\.Codex/skills/` here are the shared set available on all machines\.\r?\nEach machine symlinks `~/\.Codex/skills/` → this OneDrive location\.\r?\n',
        $SharedSkillsText,
        1
    )

    $ProviderPattern = '(?s)(?:Three provider targets|Provider targets):\r?\n(?:- .*?\r?\n)+(\r?\nShared architecture:)'
    $ProviderBlock = @'
- `claude-skills/` — {0} install-ready skills for Claude Code
- `codex-skills/` — {1} install-ready skills for OpenAI Codex
'@ -f $ClaudeSkillCount, $CodexSkillCount -replace "`n", "`r`n"
    if ([regex]::IsMatch($Text, $ProviderPattern)) {
        $Text = [regex]::Replace($Text, $ProviderPattern, ("Provider targets:`r`n" + $ProviderBlock.TrimEnd() + '$1'), 1)
    }

    $Body = @'
## Deep Audit Routing

- Use `deep-audit` for multi-pass runtime efficiency or scalability audits that
  reconstruct real execution paths and quantify operational multipliers.
- The skill is read-only toward product code by default and requires explicit
  authority for risky profiling, load, fault, restart, privileged, production,
  or paid activity.
- Route ordinary diff review, one known regression with a requested fix,
  bounded feasibility research, tests/coverage, and security assessment to
  their narrower workflows. Route parallel remediation, approval gates, and
  implementation ownership to `manager` or another orchestration workflow.
'@ -replace "`n", "`r`n"
    $Text = Set-ManagedBlock -Text $Text -BlockId "deep-audit" -Body $Body.Trim()
    Set-TextFile -Surface "shared-codex-rules" -Path $Path -Text $Text
}

function Update-MachineCodexRules {
    param (
        [string]$Path,
        [string]$SharedRulesPath
    )

    $Text = if (Test-Path -LiteralPath $Path) {
        [System.IO.File]::ReadAllText($Path)
    } else {
        ""
    }
    $Body = @'
## Shared Context And Deep Audit

- Read the shared machine context at {0} before relying on machine
  inventory or cross-machine conventions.
- Use `deep-audit` for evidence-backed, multi-pass runtime efficiency and
  scalability audits. It is read-only toward product code by default.
- Do not use it as the primary workflow for ordinary diff review, one known
  regression with a requested fix, bounded feasibility research, QA, or
  security assessment, or for parallel remediation and implementation gates.
'@ -f $SharedRulesPath -replace "`n", "`r`n"
    $Text = Set-ManagedBlock -Text $Text -BlockId "deep-audit" -Body $Body.Trim()
    Set-TextFile -Surface "machine-codex-rules" -Path $Path -Text $Text
}

function Resolve-LinkAwareSkillPath {
    param (
        [string]$SkillsRoot,
        [string]$SkillName
    )

    $PhysicalRoot = $SkillsRoot
    $RootItem = Get-Item -LiteralPath $SkillsRoot -ErrorAction SilentlyContinue
    if ($RootItem -and $RootItem.LinkType -and $RootItem.Target) {
        $PhysicalRoot = [string]@($RootItem.Target)[0]
    } else {
        $ParentPath = Split-Path -Parent $SkillsRoot
        $ParentItem = Get-Item -LiteralPath $ParentPath -ErrorAction SilentlyContinue
        if ($ParentItem -and $ParentItem.LinkType -and $ParentItem.Target) {
            $PhysicalRoot = Join-Path ([string]@($ParentItem.Target)[0]) (Split-Path -Leaf $SkillsRoot)
        }
    }

    return Join-Path (Join-Path $PhysicalRoot $SkillName) "SKILL.md"
}

function Update-MachineCodexSkillTrim {
    param (
        [string]$Path,
        [string]$AgentsSkillsRoot
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Missing machine Codex config: $Path"
    }

    $SkillPath = Resolve-LinkAwareSkillPath -SkillsRoot $AgentsSkillsRoot -SkillName "deep-audit"
    $Text = [System.IO.File]::ReadAllText($Path)
    $PathPattern = [regex]::Escape($SkillPath)
    $BlockPattern = "(?ms)^\[\[skills\.config\]\]\r?\npath\s*=\s*'${PathPattern}'\r?\nenabled\s*=\s*(?:true|false)\s*\r?\n?"
    $Block = @"
[[skills.config]]
path = '$SkillPath'
enabled = false

"@ -replace "`n", "`r`n"
    $Block += "`r`n"

    if ([regex]::IsMatch($Text, $BlockPattern)) {
        $Text = [regex]::Replace($Text, $BlockPattern, $Block, 1)
    } else {
        $AnchorPattern = '(?m)^(# keep the agents root copies installed for non-Codex consumers\.\r?\n)'
        if ([regex]::IsMatch($Text, $AnchorPattern)) {
            $Text = [regex]::Replace($Text, $AnchorPattern, ('$1' + $Block), 1)
        } else {
            $Text = $Text.TrimEnd("`r", "`n") + "`r`n`r`n" + $Block
        }
    }

    Set-TextFile -Surface "machine-codex-skill-trim" -Path $Path -Text $Text
}

function Sync-SkillDirectory {
    param (
        [string]$ProviderName,
        [string]$SourcePath,
        [string]$TargetRoot
    )

    if (-not (Test-Path -LiteralPath (Join-Path $SourcePath "SKILL.md"))) {
        throw "Missing canonical $ProviderName Deep Audit skill: $SourcePath"
    }

    $TargetPath = Join-Path $TargetRoot "deep-audit"
    $SourceFiles = @(Get-ChildItem -LiteralPath $SourcePath -File -Recurse -Force)
    $Matches = (Test-Path -LiteralPath $TargetPath)
    if ($Matches) {
        foreach ($SourceFile in $SourceFiles) {
            $Relative = [System.IO.Path]::GetRelativePath($SourcePath, $SourceFile.FullName)
            $TargetFile = Join-Path $TargetPath $Relative
            if (-not (Test-Path -LiteralPath $TargetFile) -or
                (Get-FileHash -LiteralPath $SourceFile.FullName -Algorithm SHA256).Hash -ne
                (Get-FileHash -LiteralPath $TargetFile -Algorithm SHA256).Hash) {
                $Matches = $false
                break
            }
        }
    }

    if ($Matches) {
        Add-Result -Surface "$ProviderName-skill" -Path $TargetPath -Status "current"
        return
    }
    if (-not $Apply) {
        Add-Result -Surface "$ProviderName-skill" -Path $TargetPath -Status "would-sync"
        return
    }

    New-Item -ItemType Directory -Path $TargetPath -Force | Out-Null
    foreach ($SourceFile in $SourceFiles) {
        $Relative = [System.IO.Path]::GetRelativePath($SourcePath, $SourceFile.FullName)
        $TargetFile = Join-Path $TargetPath $Relative
        New-Item -ItemType Directory -Path (Split-Path -Parent $TargetFile) -Force | Out-Null
        Copy-Item -LiteralPath $SourceFile.FullName -Destination $TargetFile -Force
    }
    Add-Result -Surface "$ProviderName-skill" -Path $TargetPath -Status "synced"
}

$SharedClaudeRules = Join-Path $SharedRoot "CLAUDE.md"
$SharedCodexRules = Join-Path $SharedRoot "AGENTS.md"
$ClaudeSource = Join-Path $RepoRoot "claude-skills\skills\deep-audit"
$CodexSource = Join-Path $RepoRoot "codex-skills\skills\deep-audit"
$ClaudeManifest = Get-Content -Raw (Join-Path $RepoRoot "claude-skills\package\install-manifest.json") | ConvertFrom-Json
$CodexManifest = Get-Content -Raw (Join-Path $RepoRoot "codex-skills\package\install-manifest.json") | ConvertFrom-Json
$ClaudeSkillCount = @($ClaudeManifest.default_skills).Count + @($ClaudeManifest.optional_skills).Count
$CodexSkillCount = @($CodexManifest.default_skills).Count + @($CodexManifest.optional_skills).Count

Update-SharedClaudeRules -Path $SharedClaudeRules -ClaudeSkillCount $ClaudeSkillCount -CodexSkillCount $CodexSkillCount
Update-SharedCodexRules -Path $SharedCodexRules -ClaudeSkillCount $ClaudeSkillCount -CodexSkillCount $CodexSkillCount
Update-MachineCodexRules -Path $MachineCodexAgentsFile -SharedRulesPath $SharedCodexRules
Update-MachineCodexSkillTrim -Path $MachineCodexConfig -AgentsSkillsRoot $MachineAgentsSkillsRoot

Sync-SkillDirectory -ProviderName "claude-shared" -SourcePath $ClaudeSource -TargetRoot (Join-Path $SharedRoot ".claude\skills")
Sync-SkillDirectory -ProviderName "codex-package" -SourcePath $CodexSource -TargetRoot $MachineCodexSkillsRoot
Sync-SkillDirectory -ProviderName "codex-machine" -SourcePath $CodexSource -TargetRoot $MachineAgentsSkillsRoot
Sync-SkillDirectory -ProviderName "codex-shared" -SourcePath $CodexSource -TargetRoot (Join-Path $SharedRoot ".agents\skills")

Write-Output "Deep Audit Sharing Sync"
Write-Output ""
$Results | Format-Table -AutoSize
if (-not $Apply) {
    Write-Output ""
    Write-Output "Dry run only. Re-run with -Apply to update rule files and synchronize Deep Audit."
}
