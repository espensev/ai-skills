BeforeAll {
    $script:ReadinessScript = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\Test-ReleaseReadiness.ps1"))

    function New-ReadinessFixture {
        param (
            [Parameter(Mandatory)][string]$Root,
            [switch]$ControllerIsCheckout,
            [switch]$PluginShouldPass
        )

        $repoRoot = Join-Path $Root "repo"
        $lifecycleRoot = Join-Path $repoRoot "codex-skills\local-hooks\devhome-lifecycle"
        $declaredRoot = if ($ControllerIsCheckout) {
            $lifecycleRoot
        }
        else {
            Join-Path $Root "controller\codex-skills\local-hooks\devhome-lifecycle"
        }
        $lifecycleTests = Join-Path $lifecycleRoot "tests"
        $scriptRoot = Join-Path $repoRoot "scripts"
        $binRoot = Join-Path $Root "bin"
        foreach ($path in @($lifecycleTests, (Join-Path $lifecycleRoot "hooks"), $scriptRoot, (Join-Path $scriptRoot "tests"), $binRoot)) {
            New-Item -ItemType Directory -Path $path -Force | Out-Null
        }

        Copy-Item -LiteralPath $script:ReadinessScript -Destination (Join-Path $scriptRoot "Test-ReleaseReadiness.ps1")
        $declaredCommand = 'pwsh -File "${PLUGIN_ROOT}/Sync.ps1" -SourcePackageRoot "' + ($declaredRoot -replace '\\', '/') + '"'
        Set-Content -LiteralPath (Join-Path $lifecycleRoot "hooks\hooks.json") -Encoding utf8 -Value (@{
            hooks = @{ SessionStart = @(@{ hooks = @(@{
                type = "command"
                command = $declaredCommand
                commandWindows = $declaredCommand
            }) }) }
        } | ConvertTo-Json -Depth 8)

        $hooksMarker = Join-Path $Root "hooks-ran.txt"
        Set-Content -LiteralPath (Join-Path $lifecycleTests "DevHome-Hooks.Tests.ps1") -Encoding utf8 -Value @"
Describe "portable hook contracts" {
    It "runs from the checkout" {
        Set-Content -LiteralPath '$($hooksMarker.Replace("'", "''"))' -Value ran
        `$true | Should -BeTrue
    }
}
"@
        $pluginMarker = Join-Path $Root "plugin-ran.txt"
        $pluginExpectation = if ($PluginShouldPass) { '$true' } else { '$false' }
        Set-Content -LiteralPath (Join-Path $lifecycleTests "DevHome-PluginSync.Tests.ps1") -Encoding utf8 -Value @"
Describe "controller-only plugin-cache contracts" {
    It "runs only at the declared controller root" {
        Set-Content -LiteralPath '$($pluginMarker.Replace("'", "''"))' -Value ran
        $pluginExpectation | Should -BeTrue
    }
}
"@

        foreach ($name in @("Test-ReadyPackages.ps1", "Update-ReadmePackageCounts.ps1", "Build-ProviderSkillPackages.ps1", "Compare-ProviderSkillParity.ps1")) {
            Set-Content -LiteralPath (Join-Path $scriptRoot $name) -Encoding utf8 -Value 'param([switch]$StrictSkillManifest, [switch]$Check, [switch]$FailOnUndeclaredFork, [int]$MaxRows)'
        }
        foreach ($name in @("Install-AgentSkills.Tests.ps1", "AiEnvironment.Tests.ps1")) {
            Set-Content -LiteralPath (Join-Path $scriptRoot "tests\$name") -Encoding utf8 -Value 'Describe "portable fixture contract" { It "passes" { $true | Should -BeTrue } }'
        }
        Set-Content -LiteralPath (Join-Path $scriptRoot "tests\ReleaseReadiness.Tests.ps1") -Encoding utf8 -Value 'Describe "fixture readiness contract" { It "passes without recursion" { $true | Should -BeTrue } }'
        Set-Content -LiteralPath (Join-Path $binRoot "python.cmd") -Encoding ascii -Value '@exit /b 0'
        Set-Content -LiteralPath (Join-Path $binRoot "git.cmd") -Encoding ascii -Value '@exit /b 0'

        [pscustomobject]@{
            BinRoot = $binRoot
            HooksMarker = $hooksMarker
            HooksPath = Join-Path $lifecycleRoot "hooks\hooks.json"
            LifecycleRoot = $lifecycleRoot
            Marker = $pluginMarker
            Script = Join-Path $scriptRoot "Test-ReleaseReadiness.ps1"
        }
    }

    function Invoke-ReadinessFixture {
        param ([Parameter(Mandatory)]$Fixture)

        $savedPath = $env:PATH
        try {
            $env:PATH = "$($Fixture.BinRoot);$savedPath"
            $output = (& pwsh -NoProfile -File $Fixture.Script -SkipParityReport 2>&1) | Out-String
            $exitCode = $LASTEXITCODE
        }
        finally {
            $env:PATH = $savedPath
        }
        [pscustomobject]@{ ExitCode = $exitCode; Output = $output }
    }
}

Describe "release readiness lifecycle authority" {
    It "skips the plugin-cache contract outside the declared controller root" {
        $fixture = New-ReadinessFixture -Root (Join-Path $TestDrive "alternate")
        $result = Invoke-ReadinessFixture -Fixture $fixture

        $result.ExitCode | Should -Be 0 -Because $result.Output
        $result.Output | Should -Match "SKIP/N/A.+controller-root-only"
        Test-Path -LiteralPath $fixture.HooksMarker | Should -BeTrue
        Test-Path -LiteralPath $fixture.Marker | Should -BeFalse
        $result.Output | Should -Match "== Installer retirement contracts =="
        $result.Output | Should -Match "== AI environment wanted-state contracts =="
        $result.Output | Should -Match "PASS - release readiness checks completed"

        $hooksManifest = Get-Content -Raw -LiteralPath $fixture.HooksPath | ConvertFrom-Json
        $hooksManifest.hooks.SessionStart[0].hooks[0].command = 'pwsh -File "${PLUGIN_ROOT}/Sync.ps1" -SourcePackageRoot "' + ($fixture.LifecycleRoot -replace '\\', '/') + '"'
        $hooksManifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $fixture.HooksPath -Encoding utf8
        Remove-Item -LiteralPath $fixture.HooksMarker
        $mismatchResult = Invoke-ReadinessFixture -Fixture $fixture

        $mismatchResult.ExitCode | Should -Not -Be 0
        Test-Path -LiteralPath $fixture.HooksMarker | Should -BeTrue
        $mismatchResult.Output | Should -Match "(?s)Expected exactly one lifecycle controller -SourcePackageRoot.+found 2"
    }

    It "runs and enforces the plugin-cache contract at the declared controller root" {
        $fixture = New-ReadinessFixture -Root (Join-Path $TestDrive "controller") -ControllerIsCheckout
        $result = Invoke-ReadinessFixture -Fixture $fixture

        $result.ExitCode | Should -Not -Be 0
        Test-Path -LiteralPath $fixture.Marker | Should -BeTrue
        $result.Output | Should -Match "== DevHome lifecycle controller-only plugin-cache contracts =="
        $result.Output | Should -Match "controller-only plugin-cache contracts failed: 1"
        $result.Output | Should -Not -Match "SKIP/N/A"
    }

    It "runs portable hooks before rejecting either missing command variant" {
        foreach ($variantName in @("command", "commandWindows")) {
            $fixture = New-ReadinessFixture -Root (Join-Path $TestDrive "missing-$variantName")
            $hooksManifest = Get-Content -Raw -LiteralPath $fixture.HooksPath | ConvertFrom-Json
            $hooksManifest.hooks.SessionStart[0].hooks[0].$variantName = ""
            $hooksManifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $fixture.HooksPath -Encoding utf8

            $result = Invoke-ReadinessFixture -Fixture $fixture

            $result.ExitCode | Should -Not -Be 0
            Test-Path -LiteralPath $fixture.HooksMarker | Should -BeTrue
            $result.Output | Should -Match "Lifecycle SessionStart $variantName must be nonblank and declare -SourcePackageRoot"
            Test-Path -LiteralPath $fixture.Marker | Should -BeFalse
        }
    }
}
