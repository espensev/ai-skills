Describe 'DevHome Codex lifecycle hooks' {
    BeforeAll {
        $script:PackageRoot = Split-Path -Parent $PSScriptRoot
        $script:HookScript = Join-Path $script:PackageRoot 'hooks\Invoke-DevHomeHook.ps1'
        $script:HooksConfig = Join-Path $script:PackageRoot 'hooks.json'
        $script:Installer = Join-Path $script:PackageRoot 'Install-DevHomeCodexHooks.ps1'

        function Invoke-HookProcess {
            param(
                [Parameter(Mandatory)]
                [ValidateSet('PreToolUse', 'UserPromptSubmit')]
                [string] $Event,

                [Parameter(Mandatory)]
                [hashtable] $Payload
            )

            $inputPath = Join-Path $TestDrive 'hook-input.json'
            $outputPath = Join-Path $TestDrive 'hook-output.json'
            $errorPath = Join-Path $TestDrive 'hook-error.txt'
            $Payload | ConvertTo-Json -Depth 12 -Compress | Set-Content -LiteralPath $inputPath -Encoding utf8NoBOM

            $process = Start-Process -FilePath (Get-Command pwsh).Source `
                -ArgumentList @('-NoProfile', '-File', $script:HookScript, '-Event', $Event) `
                -RedirectStandardInput $inputPath `
                -RedirectStandardOutput $outputPath `
                -RedirectStandardError $errorPath `
                -Wait `
                -PassThru

            [pscustomobject]@{
                ExitCode = $process.ExitCode
                Output = Get-Content -Raw -LiteralPath $outputPath
                Error = Get-Content -Raw -LiteralPath $errorPath
            }
        }

        function Get-TomlHookStateBody {
            param(
                [Parameter(Mandatory)]
                [string] $ConfigToml,

                [Parameter(Mandatory)]
                [string] $StateKey
            )

            $escapedKey = [regex]::Escape($StateKey)
            $headerPattern = '(?m)^\[hooks\.state\."' + $escapedKey + '"\]\r?$'
            $headerMatch = [regex]::Match($ConfigToml, $headerPattern)
            if (-not $headerMatch.Success) {
                return $null
            }

            $remaining = $ConfigToml.Substring($headerMatch.Index + $headerMatch.Length) -replace '^\r?\n', ''
            $nextHeader = [regex]::Match($remaining, '(?m)^\[')
            if ($nextHeader.Success) {
                return $remaining.Substring(0, $nextHeader.Index)
            }

            $remaining
        }

        function Invoke-RegisteredHookShell {
            param(
                [Parameter(Mandatory)]
                [ValidateSet('PowerShell', 'Cmd')]
                [string] $Shell,

                [Parameter(Mandatory)]
                [string] $Command
            )

            $label = $Shell.ToLowerInvariant()
            $inputPath = Join-Path $TestDrive "$label-hook-input.json"
            $outputPath = Join-Path $TestDrive "$label-hook-output.json"
            $errorPath = Join-Path $TestDrive "$label-hook-error.txt"
            $codexHome = Join-Path $TestDrive "$label-codex-home"
            '{}' | Set-Content -LiteralPath $inputPath -Encoding utf8NoBOM

            if ($Shell -eq 'PowerShell') {
                $filePath = (Get-Command pwsh).Source
                $arguments = @('-NoProfile', '-Command', $Command)
            }
            else {
                $filePath = $env:ComSpec
                $arguments = @('/d', '/c', $Command)
            }

            $process = Start-Process -FilePath $filePath `
                -ArgumentList $arguments `
                -Environment @{ CODEX_HOME = $codexHome } `
                -RedirectStandardInput $inputPath `
                -RedirectStandardOutput $outputPath `
                -RedirectStandardError $errorPath `
                -PassThru

            if (-not $process.WaitForExit(10000)) {
                $process.Kill($true)
                $process.WaitForExit()
                throw "$Shell hook command exceeded the 10-second test bound."
            }
            $process.WaitForExit()

            [pscustomobject]@{
                ExitCode = $process.ExitCode
                Output = Get-Content -Raw -LiteralPath $outputPath
                Error = Get-Content -Raw -LiteralPath $errorPath
            }
        }
    }

    Context 'PreToolUse safety guard' {
        It 'allows an ordinary read-only shell command' {
            $result = Invoke-HookProcess -Event PreToolUse -Payload @{
                hook_event_name = 'PreToolUse'
                cwd = 'D:\DevHome'
                tool_name = 'Bash'
                tool_input = @{ command = "Get-Content -Raw 'D:\DevHome\AGENTS.md'" }
            }

            $result.ExitCode | Should -Be 0
            $result.Output.Trim() | Should -Be '{}'
        }

        It 'blocks recursive deletion of the DevHome root' {
            $result = Invoke-HookProcess -Event PreToolUse -Payload @{
                hook_event_name = 'PreToolUse'
                cwd = 'D:\DevHome'
                tool_name = 'Bash'
                tool_input = @{ command = "Remove-Item -LiteralPath 'D:\DevHome' -Recurse -Force" }
            }

            $result.ExitCode | Should -Be 0
            $output = $result.Output | ConvertFrom-Json
            $output.hookSpecificOutput.permissionDecision | Should -Be 'deny'
            $output.hookSpecificOutput.permissionDecisionReason | Should -Match 'broad recursive delete'
        }

        It 'blocks apply_patch edits to generated native memory' {
            $result = Invoke-HookProcess -Event PreToolUse -Payload @{
                hook_event_name = 'PreToolUse'
                cwd = 'D:\DevHome'
                tool_name = 'apply_patch'
                tool_input = @{ command = "*** Update File: memories\memory_summary.md" }
            }

            $output = $result.Output | ConvertFrom-Json
            $output.hookSpecificOutput.permissionDecision | Should -Be 'deny'
            $output.hookSpecificOutput.permissionDecisionReason | Should -Match 'generated memory'
        }

        It 'blocks shell mutations of the ACL-protected Sevnet runtime' {
            $result = Invoke-HookProcess -Event PreToolUse -Payload @{
                hook_event_name = 'PreToolUse'
                cwd = 'D:\DevHome'
                tool_name = 'Bash'
                tool_input = @{ command = "Set-Content -LiteralPath 'C:\Users\Sev\AppData\Local\Sevnet\config.json' -Value '{}'" }
            }

            $output = $result.Output | ConvertFrom-Json
            $output.hookSpecificOutput.permissionDecision | Should -Be 'deny'
            $output.hookSpecificOutput.permissionDecisionReason | Should -Match 'Sevnet runtime'
        }
    }

    Context 'UserPromptSubmit secret detector' {
        It 'allows ordinary prompts' {
            $result = Invoke-HookProcess -Event UserPromptSubmit -Payload @{
                hook_event_name = 'UserPromptSubmit'
                cwd = 'D:\DevHome'
                prompt = 'Please update the parser and run its focused tests.'
            }

            $result.ExitCode | Should -Be 0
            $result.Output.Trim() | Should -Be '{}'
        }

        It 'blocks PEM private keys without echoing the prompt' {
            $secret = '-----BEGIN PRIVATE KEY-----'
            $result = Invoke-HookProcess -Event UserPromptSubmit -Payload @{
                hook_event_name = 'UserPromptSubmit'
                cwd = 'D:\DevHome'
                prompt = "Please inspect $secret and diagnose it."
            }

            $output = $result.Output | ConvertFrom-Json
            $output.decision | Should -Be 'block'
            $output.reason | Should -Match 'secret'
            $result.Output | Should -Not -Match ([regex]::Escape($secret))
        }

        It 'blocks a high-confidence OpenAI API key pattern' {
            $result = Invoke-HookProcess -Event UserPromptSubmit -Payload @{
                hook_event_name = 'UserPromptSubmit'
                cwd = 'D:\DevHome'
                prompt = 'Use sk-proj-abcdefghijklmnopqrstuvwxyz123456 for this request.'
            }

            ($result.Output | ConvertFrom-Json).decision | Should -Be 'block'
        }
    }

    Context 'Codex hook configuration' {
        It 'runs the registered SessionStart command through PowerShell and cmd' {
            $config = Get-Content -Raw -LiteralPath $script:HooksConfig | ConvertFrom-Json
            $command = $config.hooks.SessionStart[0].hooks[0].command

            $results = foreach ($shell in @('PowerShell', 'Cmd')) {
                [pscustomobject]@{
                    Shell = $shell
                    Result = Invoke-RegisteredHookShell -Shell $shell -Command $command
                }
            }

            foreach ($invocation in $results) {
                $invocation.Result.ExitCode | Should -Be 0 -Because "$($invocation.Shell) must execute the registered hook command successfully"
                $invocation.Result.Output.Trim() | Should -BeExactly '{}'
                { $invocation.Result.Output | ConvertFrom-Json -ErrorAction Stop } | Should -Not -Throw
            }
        }

        It 'registers the approved Windows-native safety and Remember adapter hooks' {
            $config = Get-Content -Raw -LiteralPath $script:HooksConfig | ConvertFrom-Json

            $eventNames = @($config.hooks.PSObject.Properties.Name)
            $eventNames | Should -Contain 'PreToolUse'
            $eventNames | Should -Contain 'SessionStart'
            $eventNames | Should -Contain 'UserPromptSubmit'
            $eventNames | Should -Contain 'PostToolUse'
            $eventNames | Should -Contain 'Stop'
            $config.hooks.PreToolUse[0].matcher | Should -Be '^(?:Bash|apply_patch|Edit|Write)$'
            @($config.hooks.UserPromptSubmit).Count | Should -Be 1 -Because 'prompt blockers and prompt consumers run concurrently, so Remember must consume only the accepted transcript'
            $registrations = @(
                @{
                    Hook = $config.hooks.PreToolUse[0].hooks[0]
                    Command = 'pwsh -NoProfile -File "D:\DevHome\state\codex\hooks\Invoke-DevHomeHook.ps1" -Event PreToolUse'
                },
                @{
                    Hook = $config.hooks.UserPromptSubmit[0].hooks[0]
                    Command = 'pwsh -NoProfile -File "D:\DevHome\state\codex\hooks\Invoke-DevHomeHook.ps1" -Event UserPromptSubmit'
                },
                @{
                    Hook = $config.hooks.SessionStart[0].hooks[0]
                    Command = 'D:\DevHome\state\codex\hooks\Invoke-RememberAdapter.cmd --event SessionStart'
                },
                @{
                    Hook = $config.hooks.PostToolUse[0].hooks[0]
                    Command = 'D:\DevHome\state\codex\hooks\Invoke-RememberAdapter.cmd --event PostToolUse'
                },
                @{
                    Hook = $config.hooks.Stop[0].hooks[0]
                    Command = 'D:\DevHome\state\codex\hooks\Invoke-RememberAdapter.cmd --event Stop'
                }
            )
            foreach ($registration in $registrations) {
                $registration.Hook.command | Should -BeExactly $registration.Command
                $registration.Hook.commandWindows | Should -BeExactly $registration.Command
            }
            $config.hooks.SessionStart[0].hooks[0].timeout | Should -Be 20
            $config.hooks.SessionStart[0].hooks[0].statusMessage | Should -Be 'Loading Remember context through Codex adapter'
            $config.hooks.PostToolUse[0].hooks[0].timeout | Should -Be 5
            $config.hooks.PostToolUse[0].hooks[0].async | Should -BeTrue -Because 'Remember capture is informational and must not add Git Bash latency to every tool call'
            $config.hooks.PostToolUse[0].hooks[0].statusMessage | Should -Be 'Capturing Codex session for Remember'
            @($config.hooks.Stop).Count | Should -Be 1
            $config.hooks.Stop[0].PSObject.Properties.Name | Should -Not -Contain 'matcher'
            $config.hooks.Stop[0].hooks[0].timeout | Should -Be 5
            $config.hooks.Stop[0].hooks[0].statusMessage | Should -Be 'Finalizing Remember transcript capture'
            ($config | ConvertTo-Json -Depth 20) | Should -Not -Match 'bash \\"'
            ($config | ConvertTo-Json -Depth 20) | Should -Not -Match 'remember\\[0-9]+\.[0-9]+\.[0-9]+'
        }

        It 'does not register the raw Remember plugin hooks' {
            $codexHome = if ([string]::IsNullOrWhiteSpace($env:CODEX_HOME)) {
                'D:\DevHome\state\codex'
            }
            else {
                $env:CODEX_HOME
            }
            $configTomlPath = Join-Path $codexHome 'config.toml'
            $configToml = Get-Content -Raw -LiteralPath $configTomlPath
            $configToml | Should -Not -Match 'remember@claude-plugins-official:hooks/hooks\.json'
        }

        It 'does not borrow disabled state from a later TOML section' {
            $configToml = @'
[hooks.state."remember@claude-plugins-official:hooks/hooks.json:session_start:0:0"]
trusted_hash = "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

[hooks.state."unrelated:hooks/hooks.json:session_start:0:0"]
enabled = false
'@

            $stateKey = 'remember@claude-plugins-official:hooks/hooks.json:session_start:0:0'
            $sectionBody = Get-TomlHookStateBody -ConfigToml $configToml -StateKey $stateKey
            $disabledLines = @($sectionBody -split '\r?\n' | Where-Object { $_ -ceq 'enabled = false' })

            $disabledLines.Count | Should -Be 0
        }
    }

    Context 'Source-controlled installation' {
        It 'uses the installed DevMesh v2 verifier as its default mutation gate' {
            $installerText = Get-Content -Raw -LiteralPath $script:Installer

            $installerText | Should -Match 'common_dev\\v2\\Test-LocalMachineIdentity\.ps1'
            $installerText | Should -Not -Match 'common_development\\common_dev\\Get-VerifiedMachineIdentity\.ps1'
        }

        It 'installs the closed hook set and proves it has no drift' {
            Test-Path -LiteralPath $script:Installer -PathType Leaf | Should -BeTrue
            $targetRoot = Join-Path $TestDrive 'codex-home'

            & $script:Installer -TargetRoot $targetRoot | Out-Null
            { & $script:Installer -TargetRoot $targetRoot -Check } | Should -Not -Throw

            $expectedFiles = @(
                'hooks.json',
                'hooks\Invoke-DevHomeHook.ps1',
                'hooks\Invoke-RememberAdapter.cmd',
                'hooks\Invoke-RememberAdapter.py',
                'hooks\Invoke-RememberClaude.cmd'
            )
            foreach ($relativePath in $expectedFiles) {
                Test-Path -LiteralPath (Join-Path $targetRoot $relativePath) -PathType Leaf | Should -BeTrue
            }

            $installedConfig = Get-Content -Raw -LiteralPath (Join-Path $targetRoot 'hooks.json')
            $installedConfig | Should -Not -Match 'D:\\DevHome\\state\\codex'
            { $installedConfig | ConvertFrom-Json -ErrorAction Stop } | Should -Not -Throw
            $parsedConfig = $installedConfig | ConvertFrom-Json
            $parsedConfig.hooks.PreToolUse[0].hooks[0].command | Should -Match ([regex]::Escape($targetRoot))
        }

        It 'detects installed hook drift without repairing it in check mode' {
            $targetRoot = Join-Path $TestDrive 'drifted-codex-home'
            & $script:Installer -TargetRoot $targetRoot | Out-Null
            $driftedPath = Join-Path $targetRoot 'hooks\Invoke-DevHomeHook.ps1'
            Add-Content -LiteralPath $driftedPath -Value '# drift probe'

            { & $script:Installer -TargetRoot $targetRoot -Check } | Should -Throw '*drift*'
            (Get-Content -LiteralPath $driftedPath -Tail 1) | Should -BeExactly '# drift probe'
        }
    }
}
