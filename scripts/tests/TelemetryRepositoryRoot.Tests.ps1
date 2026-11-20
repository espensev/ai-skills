BeforeDiscovery {
    $cases = foreach ($provider in @('codex-skills', 'claude-skills')) {
        foreach ($scriptName in @('telemetry-live-start.ps1', 'telemetry-live-verify.ps1')) {
            @{ Provider = $provider; ScriptName = $scriptName }
        }
    }
}

Describe 'Telemetry repository resolution in <Provider>/<ScriptName>' -ForEach $cases {
    BeforeAll {
        $repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
        $path = Join-Path $repoRoot "$Provider\skills\telemetry-live-ops\scripts\$ScriptName"
        $tokens = $null
        $parseErrors = $null
        $ast = [System.Management.Automation.Language.Parser]::ParseFile($path, [ref]$tokens, [ref]$parseErrors)
        if ($parseErrors.Count -ne 0) { throw "Telemetry script has parse errors: $path" }

        # Load only pure resolution helpers. Never execute the script's live tail.
        foreach ($name in @('Get-EnvironmentValue', 'Resolve-TelemetryRepositoryRoot')) {
            $functionAst = $ast.Find({
                param($node)
                $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name
            }, $false)
            if ($null -eq $functionAst) { throw "Missing resolution helper: $name" }
            . ([scriptblock]::Create($functionAst.Extent.Text))
        }
    }

    BeforeEach {
        $script:ResolutionEnvironment = @{}
        Mock Get-EnvironmentValue {
            param($Names)
            foreach ($name in $Names) {
                if ($script:ResolutionEnvironment.ContainsKey($name)) {
                    return $script:ResolutionEnvironment[$name]
                }
            }
            return $null
        }
    }

    It 'preserves an explicit repository without reading environment defaults' {
        $explicit = Join-Path $TestDrive 'explicit-repository'
        Resolve-TelemetryRepositoryRoot -CurrentValue $explicit | Should -BeExactly $explicit
        Should -Invoke Get-EnvironmentValue -Times 0 -Exactly
    }

    It 'uses the telemetry override without requiring a machine code role' {
        $override = Join-Path $TestDrive 'override-repository'
        $script:ResolutionEnvironment['OLLAMA_TELEMETRY_REPO'] = $override
        Resolve-TelemetryRepositoryRoot -CurrentValue '' | Should -BeExactly $override
        Should -Invoke Get-EnvironmentValue -Times 0 -Exactly -ParameterFilter { 'MACHINE_CODE_ROOT' -in $Names }
    }

    It 'derives the default from the configured code role' {
        $script:ResolutionEnvironment['MACHINE_CODE_ROOT'] = $TestDrive
        Resolve-TelemetryRepositoryRoot -CurrentValue '' |
            Should -BeExactly (Join-Path $TestDrive 'AI4000\observability\ollama-telemetry')
    }

    It 'fails before live work when neither override nor code role exists' {
        { Resolve-TelemetryRepositoryRoot -CurrentValue '' } | Should -Throw '*Set MACHINE_CODE_ROOT*'
    }

    Context 'forwarding the remote API to the telemetry repository' {
        BeforeAll {
            # Use the mocked environment resolver so persisted workstation overrides
            # cannot hide a stale default. Both entry points dispatch only to TestDrive.
            $resolver = $ast.Find({
                param($node)
                $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Get-EnvironmentValue'
            }, $false).Extent
            $wrapper = [scriptblock]::Create($ast.Extent.Text.Remove($resolver.StartOffset, $resolver.EndOffset - $resolver.StartOffset))
            $scripts = New-Item -ItemType Directory -Force -Path (Join-Path $TestDrive 'native/scripts')
            $isStart = $ScriptName -eq 'telemetry-live-start.ps1'
            $entry = if ($isStart) { 'start-remote-host-stack.ps1' } else { 'verify-live-deployment.ps1' }
            Set-Content -LiteralPath (Join-Path $scripts $entry) -Value @'
param([string]$ApiHost, [int]$ApiPort, [string]$RemoteBaseUrl)
$PSBoundParameters
'@
        }

        It 'leaves the remote endpoint to the repository when no override is configured' {
            $received = & $wrapper -RepoRoot $TestDrive
            $received.ContainsKey('RemoteBaseUrl') | Should -BeFalse
            $received.ContainsKey('ApiHost') | Should -BeFalse
            $received.ContainsKey('ApiPort') | Should -BeFalse
        }

        It 'forwards the <Source> remote endpoint' -ForEach @(
            @{ Source = 'environment'; ExpectedHost = 'environment.invalid'; ExpectedPort = 43210 }
            @{ Source = 'explicit'; ExpectedHost = 'explicit.invalid'; ExpectedPort = 43211 }
        ) {
            $script:ResolutionEnvironment['OLLAMA_TELEMETRY_REMOTE_URL'] = 'http://environment.invalid:43210'
            $options = @{ RepoRoot = $TestDrive }
            $expectedUrl = "http://${ExpectedHost}:$ExpectedPort"
            if ($Source -eq 'explicit') { $options.RemoteBaseUrl = $expectedUrl }
            $received = & $wrapper @options
            if ($isStart) {
                $received.ApiHost | Should -BeExactly $ExpectedHost
                $received.ApiPort | Should -Be $ExpectedPort
            } else {
                $received.RemoteBaseUrl | Should -BeExactly $expectedUrl
            }
        }
    }
}
