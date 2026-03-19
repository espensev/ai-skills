[CmdletBinding()]
param(
    [string]$RepoRoot = (Get-Location).Path,
    [string]$DefaultModel = "qwen3-coder:30b",
    [string]$OllamaUrl = "http://127.0.0.1:11434",
    [string]$HaikuModel = "",
    [string]$SonnetModel = "",
    [string]$OpusModel = "",
    [double]$Temperature = 0.1,
    [int]$NumCtx = 16384,
    [int]$MaxConventionChars = 12000,
    [int]$MaxFileChars = 24000,
    [int]$MaxIterations = 24,
    [switch]$SkipMerge,
    [switch]$SkipVerification,
    [string]$PlanId = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$bridgePath = Join-Path $PSScriptRoot "ollama-bridge.ps1"
if (-not (Test-Path -LiteralPath $bridgePath)) {
    throw "Base bridge script not found: $bridgePath"
}

$bridgeArgs = @(
    "-File", $bridgePath,
    "-RepoRoot", $RepoRoot,
    "-LaunchMode", "campaign",
    "-OllamaUrl", $OllamaUrl,
    "-DefaultModel", $DefaultModel,
    "-HaikuModel", $HaikuModel,
    "-SonnetModel", $SonnetModel,
    "-OpusModel", $OpusModel,
    "-Temperature", [string]$Temperature,
    "-NumCtx", [string]$NumCtx,
    "-MaxConventionChars", [string]$MaxConventionChars,
    "-MaxFileChars", [string]$MaxFileChars,
    "-MaxIterations", [string]$MaxIterations
)

if ($SkipMerge) { $bridgeArgs += "-SkipMerge" }
if ($SkipVerification) { $bridgeArgs += "-SkipVerification" }
if ($PlanId) { $bridgeArgs += @("-PlanId", $PlanId) }

Write-Host "Running Ollama bridge in campaign mode."
& pwsh @bridgeArgs
exit $LASTEXITCODE

