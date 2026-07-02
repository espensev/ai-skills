param (
    [Parameter(Mandatory=$false)]
    [switch]$IncludeLiveRootCompare,

    [Parameter(Mandatory=$false)]
    [switch]$SkipUnitTests,

    [Parameter(Mandatory=$false)]
    [switch]$SkipParityReport
)

$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptRoot

function Invoke-Step {
    param (
        [string]$Name,
        [scriptblock]$Command
    )

    Write-Output ""
    Write-Output "== $Name =="
    & $Command
}

Set-Location $RepoRoot

Invoke-Step "Ready package validation" {
    & (Join-Path $ScriptRoot "Test-ReadyPackages.ps1")
}

Invoke-Step "README manifest counts" {
    & (Join-Path $ScriptRoot "Update-ReadmePackageCounts.ps1") -Check
}

if (-not $SkipUnitTests) {
    Invoke-Step "Codex and Claude package contract tests" {
        python -m unittest codex-skills.tests.test_skill_docs_contract claude-skills.tests.test_skill_docs_contract
        if ($LASTEXITCODE -ne 0) {
            throw "Package contract tests failed"
        }
    }
}

if (-not $SkipParityReport) {
    Invoke-Step "Provider parity report" {
        & (Join-Path $ScriptRoot "Compare-ProviderSkillParity.ps1") -MaxRows 20
    }
}

if ($IncludeLiveRootCompare) {
    Invoke-Step "Live Codex and Claude root comparison" {
        & (Join-Path $ScriptRoot "Compare-AgentSkillRoots.ps1") -FailOnMissingOrStale
    }
}

Invoke-Step "Git diff whitespace check" {
    git diff --check
    if ($LASTEXITCODE -ne 0) {
        throw "git diff --check failed"
    }
}

Invoke-Step "Git staged diff whitespace check" {
    git diff --cached --check
    if ($LASTEXITCODE -ne 0) {
        throw "git diff --cached --check failed"
    }
}

Write-Output ""
Write-Output "PASS - release readiness checks completed"
