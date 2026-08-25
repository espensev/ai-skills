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
    # Steps below gate on $LASTEXITCODE, which is unset in a fresh shell that has
    # not yet run a native command - an unset value fails the -ne 0 test and
    # reports a false failure. Seed it per step so each check reads its own call.
    $global:LASTEXITCODE = 0
    & $Command
}

function Get-LifecycleControllerSourceRoot {
    param (
        [Parameter(Mandatory)]
        [string]$LifecyclePackageRoot
    )

    $hooksPath = Join-Path $LifecyclePackageRoot "hooks\hooks.json"
    $hooksManifest = Get-Content -Raw -LiteralPath $hooksPath | ConvertFrom-Json
    $sessionStartCommands = @(
        $hooksManifest.hooks.SessionStart |
            ForEach-Object { $_.hooks } |
            Where-Object { $_.type -ceq "command" }
    )
    if ($sessionStartCommands.Count -ne 1) {
        throw "Lifecycle hooks must declare exactly one SessionStart command reconciler in $hooksPath."
    }

    $commandVariants = [ordered]@{
        command = [string]$sessionStartCommands[0].command
        commandWindows = [string]$sessionStartCommands[0].commandWindows
    }
    $declaredRoots = @(
        foreach ($variant in $commandVariants.GetEnumerator()) {
            if ([string]::IsNullOrWhiteSpace($variant.Value)) {
                throw "Lifecycle SessionStart $($variant.Key) must be nonblank and declare -SourcePackageRoot in $hooksPath."
            }
            if ($variant.Value -notmatch '(?i)(?:^|\s)-SourcePackageRoot\s+(?:"(?<double>[^"]+)"|''(?<single>[^'']+)''|(?<bare>\S+))') {
                throw "Lifecycle SessionStart $($variant.Key) must declare -SourcePackageRoot in $hooksPath."
            }
            $declaredRoot = @($Matches.double, $Matches.single, $Matches.bare) |
                Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
                Select-Object -First 1
            Resolve-ReadinessPath -Path $declaredRoot
        }
    )
    $rootMap = [System.Collections.Generic.Dictionary[string, string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($declaredRoot in $declaredRoots) {
        if (-not $rootMap.ContainsKey($declaredRoot)) {
            $rootMap.Add($declaredRoot, $declaredRoot)
        }
    }
    $uniqueRoots = @($rootMap.Values)
    if ($uniqueRoots.Count -ne 1) {
        throw "Expected exactly one lifecycle controller -SourcePackageRoot in $hooksPath; found $($uniqueRoots.Count)."
    }
    return $uniqueRoots[0]
}

function Resolve-ReadinessPath {
    param ([Parameter(Mandatory)][string]$Path)

    $expanded = [Environment]::ExpandEnvironmentVariables($Path)
    if ($expanded.StartsWith('\\?\UNC\', [System.StringComparison]::OrdinalIgnoreCase)) {
        $expanded = '\\' + $expanded.Substring(8)
    }
    elseif ($expanded.StartsWith('\\?\', [System.StringComparison]::OrdinalIgnoreCase)) {
        $expanded = $expanded.Substring(4)
    }
    $fullPath = [System.IO.Path]::GetFullPath($expanded)
    $pathRoot = [System.IO.Path]::GetPathRoot($fullPath)
    if ([string]::Equals($fullPath, $pathRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $pathRoot
    }
    return $fullPath.TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
}

function Test-SamePath {
    param (
        [Parameter(Mandatory)][string]$Left,
        [Parameter(Mandatory)][string]$Right
    )

    $leftPath = Resolve-ReadinessPath -Path $Left
    $rightPath = Resolve-ReadinessPath -Path $Right
    return [string]::Equals($leftPath, $rightPath, [System.StringComparison]::OrdinalIgnoreCase)
}

Set-Location $RepoRoot

Invoke-Step "Ready package validation" {
    & (Join-Path $ScriptRoot "Test-ReadyPackages.ps1") -StrictSkillManifest
    if ($LASTEXITCODE -ne 0) {
        throw "Ready package validation failed"
    }
}

Invoke-Step "README manifest counts" {
    & (Join-Path $ScriptRoot "Update-ReadmePackageCounts.ps1") -Check
    if ($LASTEXITCODE -ne 0) {
        throw "README manifest count check failed"
    }
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

    Invoke-Step "Release readiness orchestration contracts" {
        $ReadinessTestPath = Join-Path $RepoRoot "scripts\tests\ReleaseReadiness.Tests.ps1"
        $ReadinessResult = Invoke-Pester -Path $ReadinessTestPath -Output Normal -PassThru
        if ($ReadinessResult.FailedCount -ne 0) {
            throw "Release readiness orchestration contracts failed: $($ReadinessResult.FailedCount)"
        }
    }

    $LifecyclePackageRoot = Join-Path $RepoRoot "codex-skills\local-hooks\devhome-lifecycle"
    Invoke-Step "DevHome lifecycle portable source contracts" {
        $LifecycleHooksTestPath = Join-Path $LifecyclePackageRoot "tests\DevHome-Hooks.Tests.ps1"
        $LifecycleHooksResult = Invoke-Pester -Path $LifecycleHooksTestPath -Output Normal -PassThru
        if ($LifecycleHooksResult.FailedCount -ne 0) {
            throw "DevHome lifecycle portable source contracts failed: $($LifecycleHooksResult.FailedCount)"
        }
    }

    $LifecycleControllerSourceRoot = Get-LifecycleControllerSourceRoot -LifecyclePackageRoot $LifecyclePackageRoot
    $IsLifecycleControllerRoot = Test-SamePath -Left $LifecyclePackageRoot -Right $LifecycleControllerSourceRoot

    if ($IsLifecycleControllerRoot) {
        Invoke-Step "DevHome lifecycle controller-only plugin-cache contracts" {
            $PluginSyncTestPath = Join-Path $LifecyclePackageRoot "tests\DevHome-PluginSync.Tests.ps1"
            $PluginSyncResult = Invoke-Pester -Path $PluginSyncTestPath -Output Normal -PassThru
            if ($PluginSyncResult.FailedCount -ne 0) {
                throw "DevHome lifecycle controller-only plugin-cache contracts failed: $($PluginSyncResult.FailedCount)"
            }
        }
    }
    else {
        Invoke-Step "DevHome lifecycle controller-only plugin-cache contracts" {
            Write-Output "SKIP/N/A - controller-root-only lane; checkout package root is $LifecyclePackageRoot; declared controller source root is $LifecycleControllerSourceRoot"
        }
    }

    Invoke-Step "Installer retirement contracts" {
        $InstallerTestPath = Join-Path $RepoRoot "scripts\tests\Install-AgentSkills.Tests.ps1"
        $InstallerResult = Invoke-Pester -Path $InstallerTestPath -Output Normal -PassThru
        if ($InstallerResult.FailedCount -ne 0) {
            throw "Installer retirement contracts failed: $($InstallerResult.FailedCount)"
        }
    }

    Invoke-Step "AI environment wanted-state contracts" {
        $AiEnvironmentTestPath = Join-Path $RepoRoot "scripts\tests\AiEnvironment.Tests.ps1"
        $AiEnvironmentResult = Invoke-Pester -Path $AiEnvironmentTestPath -Output Normal -PassThru
        if ($AiEnvironmentResult.FailedCount -ne 0) {
            throw "AI environment wanted-state contracts failed: $($AiEnvironmentResult.FailedCount)"
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
