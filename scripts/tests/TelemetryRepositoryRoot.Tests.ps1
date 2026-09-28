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
}
