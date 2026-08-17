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
    & (Join-Path $ScriptRoot "Test-ReadyPackages.ps1") -StrictSkillManifest
}

Invoke-Step "README manifest counts" {
    & (Join-Path $ScriptRoot "Update-ReadmePackageCounts.ps1") -Check
}

Invoke-Step "Provider skill package generation" {
    & (Join-Path $ScriptRoot "Build-ProviderSkillPackages.ps1") -Check
    if ($LASTEXITCODE -ne 0) {
        throw "Provider skill package check failed"
    }
}

# Deliberately NOT behind -SkipParityReport: the human-readable report below is
# optional, this enforcement is not. Invoke-Step does not propagate child exit
# codes, hence the explicit $LASTEXITCODE guard.
Invoke-Step "Provider parity enforcement" {
    & (Join-Path $ScriptRoot "Compare-ProviderSkillParity.ps1") -FailOnUndeclaredFork
    if ($LASTEXITCODE -ne 0) {
        throw "Provider parity enforcement failed"
    }
}

if (-not $SkipUnitTests) {
    Invoke-Step "Codex, Claude, and local plugin contract tests" {
        python -m unittest codex-skills.tests.test_skill_docs_contract codex-skills.tests.test_local_plugin_contract claude-skills.tests.test_skill_docs_contract
        if ($LASTEXITCODE -ne 0) {
            throw "Package contract tests failed"
        }
    }

    Invoke-Step "DevHome lifecycle source and plugin-cache contracts" {
        $LifecycleTestPaths = @(
            (Join-Path $RepoRoot "codex-skills\local-hooks\devhome-lifecycle\tests\DevHome-Hooks.Tests.ps1"),
            (Join-Path $RepoRoot "codex-skills\local-hooks\devhome-lifecycle\tests\DevHome-PluginSync.Tests.ps1")
        )
        $LifecycleResult = Invoke-Pester -Path $LifecycleTestPaths -Output Normal -PassThru
        if ($LifecycleResult.FailedCount -ne 0) {
            throw "DevHome lifecycle contracts failed: $($LifecycleResult.FailedCount)"
        }
    }

    Invoke-Step "Installer retirement contracts" {
        $InstallerTestPath = Join-Path $RepoRoot "scripts\tests\Install-AgentSkills.Tests.ps1"
        $InstallerResult = Invoke-Pester -Path $InstallerTestPath -Output Normal -PassThru
        if ($InstallerResult.FailedCount -ne 0) {
            throw "Installer retirement contracts failed: $($InstallerResult.FailedCount)"
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
