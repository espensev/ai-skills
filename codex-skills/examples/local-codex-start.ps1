[CmdletBinding()]
param(
    [string]$RepoRoot = (Get-Location).Path,
    [string]$CodexCommand = "codex",
    [string]$Prompt = "",
    [switch]$SkipObserverContext
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-OptionalFileText {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [int]$MaxChars = 4000
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return ""
    }

    $text = Get-Content -LiteralPath $Path -Raw
    if ($text.Length -le $MaxChars) {
        return $text.Trim()
    }

    return ($text.Substring(0, $MaxChars) + "`n`n[TRUNCATED]").Trim()
}

$resolvedRepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
Set-Location -LiteralPath $resolvedRepoRoot

$agentsPath = Join-Path $resolvedRepoRoot "AGENTS.md"
$intelligencePath = Join-Path $resolvedRepoRoot "docs\observer\project-intelligence.md"
$observationsPath = Join-Path $resolvedRepoRoot "data\observations.jsonl"

$sections = New-Object System.Collections.Generic.List[string]
$sections.Add("Read AGENTS.md first and follow the repo conventions.")

if (-not $SkipObserverContext) {
    if (Test-Path -LiteralPath $intelligencePath) {
        $intelligence = Get-OptionalFileText -Path $intelligencePath -MaxChars 6000
        if ($intelligence) {
            $sections.Add("Observer synthesis:")
            $sections.Add($intelligence)
        }
    }

    if (Test-Path -LiteralPath $observationsPath) {
        $recent = Get-Content -LiteralPath $observationsPath -Tail 20
        if ($recent) {
            $sections.Add("Recent observer entries (JSONL tail):")
            $sections.Add(($recent -join "`n"))
        }
    }
}

if ($Prompt) {
    $sections.Add("Immediate task:")
    $sections.Add($Prompt.Trim())
}
else {
    $sections.Add("Immediate task:")
    $sections.Add("Summarize the current repo state, then start with the highest-signal open issue.")
}

$bootstrapPrompt = $sections -join "`n`n"

Write-Host "Starting Codex in $resolvedRepoRoot"
& $CodexCommand $bootstrapPrompt
