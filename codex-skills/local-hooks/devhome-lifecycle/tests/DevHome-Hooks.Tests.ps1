Describe 'DevHome Codex lifecycle hooks' {
    BeforeAll {
        $script:PackageRoot = Split-Path -Parent $PSScriptRoot
        $script:HookScript = Join-Path $script:PackageRoot 'hooks\Invoke-DevHomeHook.ps1'
        $script:HooksConfig = Join-Path $script:PackageRoot 'hooks.json'
        $script:Installer = Join-Path $script:PackageRoot 'Install-DevHomeCodexHooks.ps1'
        $script:Synchronizer = Join-Path $script:PackageRoot 'Sync-DevHomeCodexHooks.ps1'
        $script:PluginManifest = Join-Path $script:PackageRoot '.codex-plugin\plugin.json'
        $script:PluginHooksConfig = Join-Path $script:PackageRoot 'hooks\hooks.json'
        $script:PluginSkill = Join-Path $script:PackageRoot 'skills\devhome-lifecycle\SKILL.md'
        $script:RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $script:PackageRoot '..\..\..'))
        $script:AgentSkillInstaller = Join-Path $script:RepoRoot 'scripts\Install-AgentSkills.ps1'
        $script:PhysicalCodexHome = 'D:\DevHome\state\codex'

        function New-CapturingInstallerPackage {
            $root = Join-Path $TestDrive ([guid]::NewGuid().ToString('N'))
            $null = New-Item -ItemType Directory -Path $root -Force
            @'
[CmdletBinding()]
param(
    [string] $TargetRoot,
    [switch] $Check,
    [string] $VerifierPath,
    [string] $ExpectedMachineId,
    [string] $ExpectedInstallationId
)
Add-Content -LiteralPath $env:FAKE_RUNTIME_TARGET_MARKER -Value $TargetRoot
[pscustomobject]@{ Status = if ($Check) { 'CURRENT' } else { 'UNCHANGED' } }
'@ | Set-Content -LiteralPath (Join-Path $root 'Install-DevHomeCodexHooks.ps1') -Encoding utf8NoBOM
            return $root
        }

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

        It 'keeps the direct installer default on physical DevHome despite ambient CODEX_HOME' {
            $tokens = $null
            $parseErrors = $null
            $ast = [System.Management.Automation.Language.Parser]::ParseFile(
                $script:Installer,
                [ref]$tokens,
                [ref]$parseErrors
            )
            $parseErrors | Should -HaveCount 0
            $targetParameter = @(
                $ast.ParamBlock.Parameters |
                    Where-Object { $_.Name.VariablePath.UserPath -ceq 'TargetRoot' }
            )
            $targetParameter | Should -HaveCount 1

            $hadCodexHome = Test-Path Env:CODEX_HOME
            $previousCodexHome = $env:CODEX_HOME
            try {
                $env:CODEX_HOME = Join-Path $TestDrive 'AppData\Local\Codex'
                $defaultTarget = & ([scriptblock]::Create(
                    $targetParameter[0].DefaultValue.Extent.Text
                ))
            }
            finally {
                if ($hadCodexHome) {
                    $env:CODEX_HOME = $previousCodexHome
                }
                else {
                    Remove-Item Env:CODEX_HOME -ErrorAction SilentlyContinue
                }
            }

            $defaultTarget | Should -BeExactly $script:PhysicalCodexHome
        }

        It 'rejects an AppData direct-installer target before verifier drift or writes' {
            $alternateRoot = Join-Path $TestDrive 'AppData\Local\Codex'
            $null = New-Item -ItemType Directory -Path $alternateRoot -Force
            $sentinel = Join-Path $alternateRoot 'sentinel.txt'
            Set-Content -LiteralPath $sentinel -Value 'unchanged' -Encoding ascii
            $verifierMarker = Join-Path $TestDrive 'direct-installer-verifier-called.txt'
            $verifier = Join-Path $TestDrive 'direct-installer-verifier.ps1'
            @"
Set-Content -LiteralPath '$verifierMarker' -Value 'called' -Encoding ascii
[pscustomobject]@{
    status = 'VERIFIED'
    machineId = 'snd-desk'
    instanceId = 'ca96d510-7d87-4cec-8e1a-bd8fc3866903'
}
"@ | Set-Content -LiteralPath $verifier -Encoding utf8NoBOM

            {
                & $script:Installer `
                    -TargetRoot $alternateRoot `
                    -VerifierPath $verifier `
                    -Check
            } | Should -Throw '*physical DevHome Codex root*test-only*'

            Test-Path -LiteralPath $verifierMarker | Should -BeFalse
            (Get-Content -Raw -LiteralPath $sentinel).Trim() | Should -BeExactly 'unchanged'
            Test-Path -LiteralPath (Join-Path $alternateRoot 'hooks.json') | Should -BeFalse
            Test-Path -LiteralPath (Join-Path $alternateRoot 'hooks') | Should -BeFalse
        }

        It 'pins ambient AppData CODEX_HOME to the physical startup runtime target' {
            $fakePackage = New-CapturingInstallerPackage
            $marker = Join-Path $TestDrive 'captured-runtime-target.txt'
            $ambientCodexHome = Join-Path $TestDrive 'AppData\Local\Codex'
            $hadCodexHome = Test-Path Env:CODEX_HOME
            $previousCodexHome = $env:CODEX_HOME
            $env:FAKE_RUNTIME_TARGET_MARKER = $marker
            try {
                $env:CODEX_HOME = $ambientCodexHome
                @(
                    & $script:Synchronizer `
                        -SourcePackageRoot $fakePackage `
                        -Check `
                        -Quiet
                ).Count | Should -Be 0
            }
            finally {
                Remove-Item Env:FAKE_RUNTIME_TARGET_MARKER -ErrorAction SilentlyContinue
                if ($hadCodexHome) {
                    $env:CODEX_HOME = $previousCodexHome
                }
                else {
                    Remove-Item Env:CODEX_HOME -ErrorAction SilentlyContinue
                }
            }

            (Get-Content -LiteralPath $marker -Tail 1) | Should -BeExactly $script:PhysicalCodexHome
        }

        It 'rejects an alternate runtime target before invoking the source installer' {
            $fakePackage = New-CapturingInstallerPackage
            $marker = Join-Path $TestDrive 'rejected-runtime-target.txt'
            $env:FAKE_RUNTIME_TARGET_MARKER = $marker
            try {
                {
                    & $script:Synchronizer `
                        -SourcePackageRoot $fakePackage `
                        -TargetRoot (Join-Path $TestDrive 'alternate-codex-home') `
                        -Check `
                        -Quiet
                } | Should -Throw '*physical DevHome Codex root*test-only*'
            }
            finally {
                Remove-Item Env:FAKE_RUNTIME_TARGET_MARKER -ErrorAction SilentlyContinue
            }

            Test-Path -LiteralPath $marker | Should -BeFalse
        }

        It 'makes Install-AgentSkills pass the physical Codex root explicitly' {
            $installerText = Get-Content -Raw -LiteralPath $script:AgentSkillInstaller

            $installerText | Should -Match '(?s)\$PluginSyncParameters\s*=\s*@\{.*CodexHome\s*=\s*"D:\\DevHome\\state\\codex"'
        }

        It 'installs the closed hook set and proves it has no drift' {
            Test-Path -LiteralPath $script:Installer -PathType Leaf | Should -BeTrue
            $targetRoot = Join-Path $TestDrive 'codex-home'

            & $script:Installer `
                -TargetRoot $targetRoot `
                -AllowTestOnlyTargetRootOverride |
                Out-Null
            {
                & $script:Installer `
                    -TargetRoot $targetRoot `
                    -AllowTestOnlyTargetRootOverride `
                    -Check
            } | Should -Not -Throw

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
            & $script:Installer `
                -TargetRoot $targetRoot `
                -AllowTestOnlyTargetRootOverride |
                Out-Null
            $driftedPath = Join-Path $targetRoot 'hooks\Invoke-DevHomeHook.ps1'
            Add-Content -LiteralPath $driftedPath -Value '# drift probe'

            {
                & $script:Installer `
                    -TargetRoot $targetRoot `
                    -AllowTestOnlyTargetRootOverride `
                    -Check
            } | Should -Throw '*drift*'
            (Get-Content -LiteralPath $driftedPath -Tail 1) | Should -BeExactly '# drift probe'
        }

        It 'quietly repairs runtime drift through the plugin synchronizer' {
            Test-Path -LiteralPath $script:Synchronizer -PathType Leaf | Should -BeTrue
            $targetRoot = Join-Path $TestDrive 'synchronized-codex-home'

            @(
                & $script:Synchronizer `
                    -TargetRoot $targetRoot `
                    -AllowTestOnlyTargetRootOverride `
                    -Quiet
            ).Count | Should -Be 0
            {
                & $script:Synchronizer `
                    -TargetRoot $targetRoot `
                    -AllowTestOnlyTargetRootOverride `
                    -Check `
                    -Quiet
            } | Should -Not -Throw

            $driftedPath = Join-Path $targetRoot 'hooks\Invoke-DevHomeHook.ps1'
            Add-Content -LiteralPath $driftedPath -Value '# synchronizer drift probe'

            @(
                & $script:Synchronizer `
                    -TargetRoot $targetRoot `
                    -AllowTestOnlyTargetRootOverride `
                    -Quiet
            ).Count | Should -Be 0
            {
                & $script:Installer `
                    -TargetRoot $targetRoot `
                    -AllowTestOnlyTargetRootOverride `
                    -Check
            } | Should -Not -Throw
            (Get-Content -LiteralPath $driftedPath -Tail 1) | Should -Not -BeExactly '# synchronizer drift probe'
        }

        It 'uses the canonical source package when invoked from a stale plugin cache' {
            $cachedRoot = Join-Path $TestDrive 'stale-plugin-cache'
            New-Item -ItemType Directory -Path $cachedRoot -Force | Out-Null
            Copy-Item -LiteralPath $script:Synchronizer -Destination $cachedRoot
            $cachedSynchronizer = Join-Path $cachedRoot 'Sync-DevHomeCodexHooks.ps1'
            $targetRoot = Join-Path $TestDrive 'source-delegated-codex-home'

            {
                & $cachedSynchronizer `
                    -SourcePackageRoot $script:PackageRoot `
                    -TargetRoot $targetRoot `
                    -AllowTestOnlyTargetRootOverride `
                    -Quiet
            } | Should -Not -Throw
            {
                & $script:Installer `
                    -TargetRoot $targetRoot `
                    -AllowTestOnlyTargetRootOverride `
                    -Check
            } | Should -Not -Throw
        }
    }

    Context 'Ai-Skills plugin package' {
        It 'declares the lifecycle plugin and bundled operator skill' {
            $manifest = Get-Content -Raw -LiteralPath $script:PluginManifest | ConvertFrom-Json

            $manifest.name | Should -BeExactly 'devhome-lifecycle'
            $manifest.version | Should -Match '^\d+\.\d+\.\d+$'
            $manifest.hooks | Should -BeExactly './hooks/hooks.json'
            $manifest.skills | Should -BeExactly './skills/'
            Test-Path -LiteralPath $script:PluginSkill -PathType Leaf | Should -BeTrue
            (Get-Content -Raw -LiteralPath $script:PluginSkill) | Should -Match '(?m)^name: devhome-lifecycle$'
        }

        It 'registers one reconciliation hook without duplicating behavior hooks' {
            $pluginHooks = Get-Content -Raw -LiteralPath $script:PluginHooksConfig | ConvertFrom-Json
            $eventNames = @($pluginHooks.hooks.PSObject.Properties.Name)

            $eventNames | Should -HaveCount 1
            $eventNames[0] | Should -BeExactly 'SessionStart'
            $definitions = @($pluginHooks.hooks.SessionStart)
            $definitions | Should -HaveCount 1
            $definitions[0].matcher | Should -BeExactly 'startup|resume'

            $commands = @($definitions[0].hooks)
            $commands | Should -HaveCount 1
            $commands[0].command | Should -Match '\$\{PLUGIN_ROOT\}/Sync-DevHomeCodexHooks\.ps1'
            $commands[0].command | Should -Match '-SourcePackageRoot.+Ai-Skills/codex-skills/local-hooks/devhome-lifecycle'
            $commands[0].commandWindows | Should -BeExactly $commands[0].command
            $commands[0].command | Should -Not -Match 'Invoke-RememberAdapter|Invoke-DevHomeHook'
            $commands[0].command | Should -Not -Match 'AllowTestOnly'
        }
    }
}
