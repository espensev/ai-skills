Describe 'DevHome Codex lifecycle hooks' {
    BeforeAll {
        $script:PackageRoot = Split-Path -Parent $PSScriptRoot
        $script:HookScript = Join-Path $script:PackageRoot 'hooks\Invoke-DevHomeHook.ps1'
        $script:HandoffRelayScript = Join-Path $script:PackageRoot 'hooks\Invoke-HandoffRelay.ps1'
        $script:HooksConfig = Join-Path $script:PackageRoot 'hooks.json'
        $script:Installer = Join-Path $script:PackageRoot 'Install-DevHomeCodexHooks.ps1'
        $script:ClaudeHandoffInstaller = Join-Path $script:PackageRoot 'Install-DevHomeClaudeHandoffRelay.ps1'
        $script:Synchronizer = Join-Path $script:PackageRoot 'Sync-DevHomeCodexHooks.ps1'
        $script:PluginManifest = Join-Path $script:PackageRoot '.codex-plugin\plugin.json'
        $script:PluginHooksConfig = Join-Path $script:PackageRoot 'hooks\hooks.json'
        $script:PluginSkill = Join-Path $script:PackageRoot 'skills\devhome-lifecycle\SKILL.md'
        $script:RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $script:PackageRoot '..\..\..'))
        $script:AgentSkillInstaller = Join-Path $script:RepoRoot 'scripts\Install-AgentSkills.ps1'
        $script:PhysicalCodexHome = 'D:\DevHome\state\codex'
        $script:PhysicalClaudeHome = 'D:\DevHome\state\claude'

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

        function Invoke-HandoffRelayProcess {
            param(
                [Parameter(Mandatory = $false)]
                [AllowNull()]
                [hashtable] $Payload,

                [Parameter(Mandatory = $false)]
                [string] $RawInput,

                [Parameter(Mandatory)]
                [string] $RememberProjectsRoot,

                [Parameter(Mandatory = $false)]
                [ValidateSet('Codex', 'Claude')]
                [string] $Provider = 'Codex',

                [Parameter(Mandatory = $false)]
                [string] $VerifierPath,

                [Parameter(Mandatory = $false)]
                [hashtable] $HookParameters = @{}
            )

            if ([string]::IsNullOrWhiteSpace($VerifierPath)) {
                $VerifierPath = New-TestMachineVerifier
            }

            $inputPath = Join-Path $TestDrive 'handoff-relay-input.json'
            $outputPath = Join-Path $TestDrive 'handoff-relay-output.json'
            $errorPath = Join-Path $TestDrive 'handoff-relay-error.txt'
            $renderedInput = if ($PSBoundParameters.ContainsKey('RawInput')) {
                $RawInput
            }
            elseif ($null -ne $Payload) {
                $Payload | ConvertTo-Json -Depth 20 -Compress
            }
            else {
                throw 'Payload or RawInput is required.'
            }
            Set-Content -LiteralPath $inputPath -Value $renderedInput -Encoding utf8NoBOM -NoNewline

            $argumentList = [System.Collections.Generic.List[string]]::new()
            foreach ($argument in @(
                '-NoLogo',
                '-NoProfile',
                '-NonInteractive',
                '-File',
                $script:HandoffRelayScript,
                '-RememberProjectsRoot',
                $RememberProjectsRoot,
                '-Provider',
                $Provider,
                '-VerifierPath',
                $VerifierPath
            )) {
                $argumentList.Add([string] $argument)
            }
            foreach ($name in @($HookParameters.Keys | Sort-Object)) {
                $argumentList.Add("-$name")
                $argumentList.Add([string] $HookParameters[$name])
            }

            $process = Start-Process -FilePath (Get-Command pwsh).Source `
                -ArgumentList $argumentList `
                -RedirectStandardInput $inputPath `
                -RedirectStandardOutput $outputPath `
                -RedirectStandardError $errorPath `
                -Wait `
                -PassThru

            [pscustomobject]@{
                ExitCode = $process.ExitCode
                Output = if (Test-Path -LiteralPath $outputPath) {
                    Get-Content -Raw -LiteralPath $outputPath
                }
                else {
                    ''
                }
                Error = if (Test-Path -LiteralPath $errorPath) {
                    Get-Content -Raw -LiteralPath $errorPath
                }
                else {
                    ''
                }
            }
        }

        function Write-HandoffRelayTranscript {
            param(
                [Parameter(Mandatory)]
                [object[]] $Records
            )

            $path = Join-Path $TestDrive ("handoff-transcript-{0}.jsonl" -f [guid]::NewGuid().ToString('N'))
            $Records |
                ForEach-Object { $_ | ConvertTo-Json -Depth 20 -Compress } |
                Set-Content -LiteralPath $path -Encoding utf8NoBOM
            return $path
        }

        function Get-HandoffRelayInstruction {
            param([Parameter(Mandatory)][string] $Output)

            $parsed = $Output | ConvertFrom-Json -Depth 20
            if (-not [string]::IsNullOrWhiteSpace([string] $parsed.reason)) {
                return [string] $parsed.reason
            }

            return [string] $parsed.hookSpecificOutput.additionalContext
        }

        function Get-HandoffRelayDraftPath {
            param([Parameter(Mandatory)][string] $Output)

            $instruction = Get-HandoffRelayInstruction -Output $Output
            $match = [regex]::Match($instruction, '(?m)^Draft:\s*(?<path>.+?)\s*$')
            if (-not $match.Success) {
                throw "Handoff Relay instruction did not declare a draft path: $instruction"
            }

            return $match.Groups['path'].Value
        }

        function New-TestHandoffDraft {
            param(
                [Parameter(Mandatory)]
                [string] $Marker,

                [Parameter(Mandatory = $false)]
                [switch] $IncludeNoise
            )

            $noise = if ($IncludeNoise) {
                @'
This introductory paragraph is superfluous and must not be published.

## Notes the relay does not know

- Probably everything is perfect now.

'@
            }
            else {
                ''
            }

            @"
$noise## Summary

- $Marker completed the bounded Handoff Relay change.
- $Marker completed the bounded Handoff Relay change.
- Maybe the runtime is flawless now.

## Outcome

- Added deterministic draft validation and publication.
- This deliberately overlong outcome bullet contains many unnecessary words so the deterministic cleaner must shorten it automatically while retaining a bounded useful prefix instead of allowing verbose filler to expand the final handoff document without limit.

This paragraph is intentionally ignored.

## Verified state

- [unverified] The remote is definitely current.
- [verified] $Marker is the active test marker. Evidence: the isolated fixture supplied it.

## Changed source/runtime/remote surfaces

- Source fixture changed; runtime and remote fixtures stayed unchanged.

## Verification evidence

- PASS: the isolated Handoff Relay fixture reached its second Stop pass.

## Open risks

- [risk] A fresh-session smoke is still required. Basis: this fixture is process-level only.
- It might all fail for an unknown reason.

## Next actionable gate

1. Run one attended fresh-session smoke.
"@
        }

        function Get-ContractHandoffDraft {
            param(
                [Parameter(Mandatory)]
                [string[]] $SummaryItems,

                [Parameter(Mandatory = $false)]
                [string[]] $OutcomeItems = @('Completed the bounded relay fixture.'),

                [Parameter(Mandatory = $false)]
                [string[]] $VerifiedItems = @(
                    '[verified] The fixture marker is present. Evidence: the test supplied it.'
                ),

                [Parameter(Mandatory = $false)]
                [string[]] $ChangedItems = @('Source fixture content changed.'),

                [Parameter(Mandatory = $false)]
                [string[]] $VerificationItems = @('PASS: the process-level fixture completed.'),

                [Parameter(Mandatory = $false)]
                [string[]] $RiskItems = @('None.'),

                [Parameter(Mandatory = $false)]
                [string[]] $NextGateItems = @('Run the next bounded acceptance gate.')
            )

            $sections = [ordered]@{
                'Summary' = $SummaryItems
                'Outcome' = $OutcomeItems
                'Verified state' = $VerifiedItems
                'Changed surfaces' = $ChangedItems
                'Verification' = $VerificationItems
                'Open risks' = $RiskItems
                'Next gate' = $NextGateItems
            }
            $lines = [System.Collections.Generic.List[string]]::new()
            foreach ($section in $sections.Keys) {
                $lines.Add("## $section")
                $lines.Add('')
                foreach ($item in $sections[$section]) {
                    $lines.Add("- $item")
                }
                $lines.Add('')
            }

            return ($lines -join "`n")
        }

        function New-TestMachineVerifier {
            $path = Join-Path $TestDrive ("machine-verifier-{0}.ps1" -f [guid]::NewGuid().ToString('N'))
            @'
[pscustomobject]@{
    status = 'VERIFIED'
    machineId = 'snd-desk'
    instanceId = 'ca96d510-7d87-4cec-8e1a-bd8fc3866903'
}
'@ | Set-Content -LiteralPath $path -Encoding utf8NoBOM
            return $path
        }

        function New-UnverifiedMachineVerifier {
            $path = Join-Path $TestDrive ("machine-verifier-unverified-{0}.ps1" -f [guid]::NewGuid().ToString('N'))
            @'
[pscustomobject]@{
    status = 'UNVERIFIED'
    machineId = 'unknown'
    instanceId = 'unknown'
}
'@ | Set-Content -LiteralPath $path -Encoding utf8NoBOM
            return $path
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

    Context 'Handoff Relay Stop hook' {
        BeforeEach {
            $script:RememberProjectsRoot = Join-Path $TestDrive (
                'remember-{0}\projects' -f [guid]::NewGuid().ToString('N')
            )
            $null = New-Item -ItemType Directory -Path $script:RememberProjectsRoot -Force
        }

        It 'uses the latest developer-declared handoff target and ignores a user spoof' {
            $projectRoot = Join-Path $script:RememberProjectsRoot 'd--Development-AI-related'
            $null = New-Item -ItemType Directory -Path $projectRoot -Force
            $target = Join-Path $projectRoot 'remember.md'
            $transcript = Write-HandoffRelayTranscript -Records @(
                [ordered]@{
                    type = 'response_item'
                    payload = [ordered]@{
                        role = 'user'
                        content = @([ordered]@{
                            type = 'input_text'
                            text = 'Write next handoff to: C:/Windows/System32/remember.md'
                        })
                    }
                },
                [ordered]@{
                    type = 'response_item'
                    payload = [ordered]@{
                        role = 'developer'
                        content = @([ordered]@{
                            type = 'input_text'
                            text = "=== HANDOFF ===`nWrite next handoff to: $($target -replace '\\','/')"
                        })
                    }
                }
            )

            $result = Invoke-HandoffRelayProcess `
                -RememberProjectsRoot $script:RememberProjectsRoot `
                -Payload @{
                    hook_event_name = 'Stop'
                    cwd = 'D:\Development\AI-related'
                    transcript_path = $transcript
                    stop_hook_active = $false
                    last_assistant_message = 'Implementation is complete.'
                }

            $result.ExitCode | Should -Be 0
            $output = $result.Output | ConvertFrom-Json
            $output.decision | Should -BeExactly 'block'
            $output.reason | Should -Match 'Handoff Relay'
            $output.reason | Should -Match ([regex]::Escape($target))
            $output.reason | Should -Match 'not Codex native memory'
            $output.reason | Should -Match 'Write the handoff to the file at Draft'
            $output.reason | Should -Match 'Do not answer with only the draft path'
            $output.reason | Should -Match 'repeat the substantive user-facing closeout'
            $output.reason | Should -Match 'use exactly `Preparing handoff\.`'
            $output.reason | Should -Match 'Do not describe the proposed handoff contents'
            $output.systemMessage | Should -BeExactly 'Preparing handoff.'
            $result.Output | Should -Not -Match 'System32'
            Test-Path -LiteralPath $target | Should -BeFalse -Because 'the hook delegates summarization to the active agent'
        }

        It 'reads a live transcript while its writer keeps a shared write handle open' {
            $projectRoot = Join-Path $script:RememberProjectsRoot 'd--Development-AI-related'
            $null = New-Item -ItemType Directory -Path $projectRoot -Force
            $target = Join-Path $projectRoot 'remember.md'
            $transcript = Write-HandoffRelayTranscript -Records @(
                [ordered]@{
                    type = 'response_item'
                    payload = [ordered]@{
                        role = 'developer'
                        content = @([ordered]@{
                            type = 'input_text'
                            text = "Write next handoff to: $($target -replace '\\','/')"
                        })
                    }
                }
            )
            $writer = [System.IO.FileStream]::new(
                $transcript,
                [System.IO.FileMode]::Open,
                [System.IO.FileAccess]::Write,
                [System.IO.FileShare]::ReadWrite
            )
            try {
                $result = Invoke-HandoffRelayProcess `
                    -RememberProjectsRoot $script:RememberProjectsRoot `
                    -Payload @{
                        hook_event_name = 'Stop'
                        cwd = 'D:\Development\AI-related'
                        transcript_path = $transcript
                        stop_hook_active = $false
                    }
            }
            finally {
                $writer.Dispose()
            }

            ($result.Output | ConvertFrom-Json).decision | Should -BeExactly 'block'
            ($result.Output | ConvertFrom-Json).reason | Should -Match ([regex]::Escape($target))
        }

        It 'derives the existing Remember project from cwd when no declaration is present' {
            $projectRoot = Join-Path $script:RememberProjectsRoot 'd--Development-AI-related'
            $null = New-Item -ItemType Directory -Path $projectRoot -Force

            $result = Invoke-HandoffRelayProcess `
                -RememberProjectsRoot $script:RememberProjectsRoot `
                -Payload @{
                    hook_event_name = 'Stop'
                    session_id = 'derived-project-session'
                    turn_id = 'derived-project-turn'
                    cwd = 'D:\Development\AI-related'
                    stop_hook_active = $false
                }

            $output = $result.Output | ConvertFrom-Json
            $output.decision | Should -BeExactly 'block'
            $output.reason | Should -Match ([regex]::Escape((Join-Path $projectRoot 'remember.md')))
        }

        It 'selects the nearest enrolled ancestor for a nested cwd' {
            $projectRoot = Join-Path $script:RememberProjectsRoot 'd--Development-AI-related'
            $null = New-Item -ItemType Directory -Path $projectRoot -Force

            $result = Invoke-HandoffRelayProcess `
                -RememberProjectsRoot $script:RememberProjectsRoot `
                -Payload @{
                    hook_event_name = 'Stop'
                    session_id = 'nested-project-session'
                    turn_id = 'nested-project-turn'
                    cwd = 'D:\Development\AI-related\Ai-Skills\codex-skills'
                    stop_hook_active = $false
                }

            $instruction = Get-HandoffRelayInstruction -Output $result.Output
            $instruction | Should -Match ([regex]::Escape((Join-Path $projectRoot 'remember.md')))
            $instruction | Should -Match 'Workspace: D:\\Development\\AI-related'
        }

        It 'rejects an enrolled project junction that escapes the Remember projects root' {
            $outsideProject = Join-Path $TestDrive 'outside-remember-project'
            $null = New-Item -ItemType Directory -Path $outsideProject -Force
            $projectRoot = Join-Path $script:RememberProjectsRoot 'd--Development-AI-related'
            try {
                $null = New-Item `
                    -ItemType Junction `
                    -Path $projectRoot `
                    -Target $outsideProject `
                    -ErrorAction Stop
            }
            catch {
                Set-ItResult -Skipped -Because "Junction fixture creation is unavailable: $($_.Exception.Message)"
                return
            }

            $result = Invoke-HandoffRelayProcess `
                -RememberProjectsRoot $script:RememberProjectsRoot `
                -Payload @{
                    hook_event_name = 'Stop'
                    session_id = 'junction-escape-session'
                    turn_id = 'junction-escape-turn'
                    cwd = 'D:\Development\AI-related'
                    stop_hook_active = $false
                }

            $result.Output.Trim() | Should -BeExactly '{}'
            Test-Path -LiteralPath (Join-Path $outsideProject 'remember.md') | Should -BeFalse
            Test-Path -LiteralPath (Join-Path $outsideProject 'tmp\handoff-relay') | Should -BeFalse
        }

        It 'uses non-error additional context for Claude and the strict block shape for Codex' {
            $projectRoot = Join-Path $script:RememberProjectsRoot 'd--Development-AI-related'
            $null = New-Item -ItemType Directory -Path $projectRoot -Force

            $claude = Invoke-HandoffRelayProcess `
                -RememberProjectsRoot $script:RememberProjectsRoot `
                -Provider Claude `
                -Payload @{
                    hook_event_name = 'Stop'
                    session_id = 'claude-output-session'
                    cwd = 'D:\Development\AI-related'
                    stop_hook_active = $false
                }
            $claudeOutput = $claude.Output | ConvertFrom-Json -Depth 20
            $claudeOutput.PSObject.Properties.Name | Should -Not -Contain 'decision'
            $claudeOutput.hookSpecificOutput.hookEventName | Should -BeExactly 'Stop'
            $claudeOutput.hookSpecificOutput.additionalContext | Should -Match 'Draft:'
            $claudeOutput.systemMessage | Should -Match 'preparing'

            $codex = Invoke-HandoffRelayProcess `
                -RememberProjectsRoot $script:RememberProjectsRoot `
                -Provider Codex `
                -Payload @{
                    hook_event_name = 'Stop'
                    session_id = 'codex-output-session'
                    turn_id = 'codex-output-turn'
                    cwd = 'D:\Development\AI-related'
                    stop_hook_active = $false
                }
            $codexOutput = $codex.Output | ConvertFrom-Json -Depth 20
            $codexOutput.decision | Should -BeExactly 'block'
            $codexOutput.reason | Should -Match 'Draft:'
            $codexOutput.systemMessage | Should -Match 'preparing'
            $codexOutput.PSObject.Properties.Name | Should -Not -Contain 'hookSpecificOutput'
        }

        It 'quarantines a loose stale draft before preparing the current attempt' {
            $projectRoot = Join-Path $script:RememberProjectsRoot 'd--Development-AI-related'
            $relayRoot = Join-Path $projectRoot 'tmp\handoff-relay'
            $null = New-Item -ItemType Directory -Path $relayRoot -Force
            $staleKey = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
            $staleDraft = Join-Path $relayRoot "$staleKey.draft.md"
            'stale draft retained from an old continuation prompt' |
                Set-Content -LiteralPath $staleDraft -Encoding utf8NoBOM

            $result = Invoke-HandoffRelayProcess `
                -RememberProjectsRoot $script:RememberProjectsRoot `
                -Payload @{
                    hook_event_name = 'Stop'
                    session_id = 'stale-sweep-session'
                    turn_id = 'stale-sweep-turn'
                    cwd = 'D:\Development\AI-related'
                    stop_hook_active = $false
                }

            $output = $result.Output | ConvertFrom-Json
            $output.decision | Should -BeExactly 'block'
            $output.systemMessage | Should -Match 'quarantined 1 stale draft'
            Test-Path -LiteralPath $staleDraft | Should -BeFalse
            $archives = @(
                Get-ChildItem -LiteralPath $relayRoot -Filter "$staleKey.orphaned.*.draft.md"
            )
            $archives.Count | Should -BeExactly 1
            (Get-Content -Raw -LiteralPath $archives[0].FullName).Trim() |
                Should -BeExactly 'stale draft retained from an old continuation prompt'

            $healthPath = Join-Path (
                Split-Path -Parent $script:RememberProjectsRoot
            ) 'handoff-relay\latest-status.json'
            $health = Get-Content -Raw -LiteralPath $healthPath | ConvertFrom-Json
            $health.status | Should -BeExactly 'PREPARED'
            $health.details.quarantinedDrafts | Should -BeExactly '1'
        }

        It 'serializes concurrent initializers before they inspect or create attempt files' {
            $projectRoot = Join-Path $script:RememberProjectsRoot 'd--Development-AI-related'
            $relayRoot = Join-Path $projectRoot 'tmp\handoff-relay'
            $null = New-Item -ItemType Directory -Path $relayRoot -Force
            $looseKey = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
            $looseDraft = Join-Path $relayRoot "$looseKey.draft.md"
            'loose draft visible before either initializer enters the lock' |
                Set-Content -LiteralPath $looseDraft -Encoding utf8NoBOM
            $verifierPath = New-TestMachineVerifier
            $publishLock = [System.IO.FileStream]::new(
                (Join-Path $relayRoot 'publish.lock'),
                [System.IO.FileMode]::OpenOrCreate,
                [System.IO.FileAccess]::ReadWrite,
                [System.IO.FileShare]::None
            )
            $invocations = @()
            try {
                foreach ($suffix in @('a', 'b')) {
                    $inputPath = Join-Path $TestDrive "concurrent-init-$suffix-input.json"
                    $outputPath = Join-Path $TestDrive "concurrent-init-$suffix-output.json"
                    $errorPath = Join-Path $TestDrive "concurrent-init-$suffix-error.txt"
                    @{
                        hook_event_name = 'Stop'
                        session_id = "concurrent-init-session-$suffix"
                        turn_id = "concurrent-init-turn-$suffix"
                        cwd = 'D:\Development\AI-related'
                        stop_hook_active = $false
                    } | ConvertTo-Json -Depth 20 -Compress |
                        Set-Content -LiteralPath $inputPath -Encoding utf8NoBOM -NoNewline
                    $process = Start-Process `
                        -FilePath (Get-Command pwsh).Source `
                        -ArgumentList @(
                            '-NoLogo',
                            '-NoProfile',
                            '-NonInteractive',
                            '-File',
                            $script:HandoffRelayScript,
                            '-RememberProjectsRoot',
                            $script:RememberProjectsRoot,
                            '-Provider',
                            'Codex',
                            '-VerifierPath',
                            $verifierPath,
                            '-PublishLockAttempts',
                            '120'
                        ) `
                        -RedirectStandardInput $inputPath `
                        -RedirectStandardOutput $outputPath `
                        -RedirectStandardError $errorPath `
                        -PassThru
                    $invocations += [pscustomobject]@{
                        Process = $process
                        OutputPath = $outputPath
                        ErrorPath = $errorPath
                    }
                }

                Start-Sleep -Milliseconds 1000
                $exitedWhileLocked = @(
                    $invocations | Where-Object { $_.Process.HasExited }
                ).Count
                $statesWhileLocked = @(
                    Get-ChildItem -LiteralPath $relayRoot -Filter '*.state.json'
                ).Count
                $looseDraftPresentWhileLocked = Test-Path `
                    -LiteralPath $looseDraft `
                    -PathType Leaf
            }
            finally {
                $publishLock.Dispose()
            }

            foreach ($invocation in $invocations) {
                $invocation.Process.WaitForExit(10000) | Should -BeTrue
            }
            $exitedWhileLocked | Should -BeExactly 0
            $statesWhileLocked | Should -BeExactly 0
            $looseDraftPresentWhileLocked | Should -BeTrue

            $outputs = @(
                foreach ($invocation in $invocations) {
                    (Get-Content -Raw -LiteralPath $invocation.OutputPath) |
                        ConvertFrom-Json
                }
            )
            @($outputs | Where-Object decision -EQ 'block') | Should -HaveCount 2
            Test-Path -LiteralPath $looseDraft | Should -BeFalse
            @(
                Get-ChildItem `
                    -LiteralPath $relayRoot `
                    -Filter "$looseKey.orphaned.*.draft.md"
            ) | Should -HaveCount 1
            $firstDraft = Get-HandoffRelayDraftPath -Output (
                Get-Content -Raw -LiteralPath $invocations[0].OutputPath
            )
            'active draft written after its initializer released the project lock' |
                Set-Content -LiteralPath $firstDraft -Encoding utf8NoBOM
            $firstState = $firstDraft -replace '\.draft\.md$', '.state.json'
            Test-Path -LiteralPath $firstState -PathType Leaf | Should -BeTrue
            Test-Path -LiteralPath $firstDraft -PathType Leaf | Should -BeTrue
            @(
                Get-ChildItem -LiteralPath $relayRoot -Filter '*.orphaned.*.draft.md'
            ) | Should -HaveCount 1
        }

        It 'reports a preparation lock timeout without starting or publishing an attempt' {
            $projectRoot = Join-Path $script:RememberProjectsRoot 'd--Development-AI-related'
            $relayRoot = Join-Path $projectRoot 'tmp\handoff-relay'
            $null = New-Item -ItemType Directory -Path $relayRoot -Force
            $target = Join-Path $projectRoot 'remember.md'
            '# stable handoff' | Set-Content -LiteralPath $target -Encoding utf8NoBOM
            $publishLock = [System.IO.FileStream]::new(
                (Join-Path $relayRoot 'publish.lock'),
                [System.IO.FileMode]::OpenOrCreate,
                [System.IO.FileAccess]::ReadWrite,
                [System.IO.FileShare]::None
            )
            try {
                $result = Invoke-HandoffRelayProcess `
                    -RememberProjectsRoot $script:RememberProjectsRoot `
                    -Payload @{
                        hook_event_name = 'Stop'
                        session_id = 'preparation-timeout-session'
                        turn_id = 'preparation-timeout-turn'
                        cwd = 'D:\Development\AI-related'
                        stop_hook_active = $false
                    }
            }
            finally {
                $publishLock.Dispose()
            }

            $output = $result.Output | ConvertFrom-Json
            $output.systemMessage | Should -BeExactly (
                'Handoff Relay: automatic context refresh needs another try.'
            )
            $output.PSObject.Properties.Name | Should -Not -Contain 'decision'
            $output.PSObject.Properties.Name | Should -Not -Contain 'reason'
            $output.PSObject.Properties.Name | Should -Not -Contain 'hookSpecificOutput'
            @(
                Get-ChildItem -LiteralPath $relayRoot -Filter '*.state.json'
            ) | Should -HaveCount 0
            @(
                Get-ChildItem -LiteralPath $relayRoot -Filter '*.draft.md'
            ) | Should -HaveCount 0
            (Get-Content -Raw -LiteralPath $target).Trim() |
                Should -BeExactly '# stable handoff'

            $healthPath = Join-Path (
                Split-Path -Parent $script:RememberProjectsRoot
            ) 'handoff-relay\latest-status.json'
            $health = Get-Content -Raw -LiteralPath $healthPath | ConvertFrom-Json
            $health.status | Should -BeExactly 'FAILED'
            $health.code | Should -BeExactly 'unexpected-error'
            $health.details.stage | Should -BeExactly 'prepare'
        }

        It 'reports an unexpected completion error without changing the canonical handoff' {
            $projectRoot = Join-Path $script:RememberProjectsRoot 'd--Development-AI-related'
            $null = New-Item -ItemType Directory -Path $projectRoot -Force
            $target = Join-Path $projectRoot 'remember.md'
            '# stable handoff' | Set-Content -LiteralPath $target -Encoding utf8NoBOM
            $payload = @{
                hook_event_name = 'Stop'
                session_id = 'unexpected-completion-session'
                turn_id = 'unexpected-completion-turn'
                cwd = 'D:\Development\AI-related'
                stop_hook_active = $false
            }

            $first = Invoke-HandoffRelayProcess `
                -RememberProjectsRoot $script:RememberProjectsRoot `
                -Payload $payload
            $draftPath = Get-HandoffRelayDraftPath -Output $first.Output
            New-TestHandoffDraft -Marker 'MUST-NOT-PUBLISH' |
                Set-Content -LiteralPath $draftPath -Encoding utf8NoBOM
            $lockPath = Join-Path (Split-Path -Parent $draftPath) 'publish.lock'
            $publishLock = [System.IO.FileStream]::new(
                $lockPath,
                [System.IO.FileMode]::OpenOrCreate,
                [System.IO.FileAccess]::ReadWrite,
                [System.IO.FileShare]::None
            )
            try {
                $payload.stop_hook_active = $true
                $second = Invoke-HandoffRelayProcess `
                    -RememberProjectsRoot $script:RememberProjectsRoot `
                    -Payload $payload
            }
            finally {
                $publishLock.Dispose()
            }

            $output = $second.Output | ConvertFrom-Json
            $output.systemMessage | Should -BeExactly (
                'Handoff Relay: automatic context refresh needs another try.'
            )
            (Get-Content -Raw -LiteralPath $target).Trim() |
                Should -BeExactly '# stable handoff'

            $healthPath = Join-Path (
                Split-Path -Parent $script:RememberProjectsRoot
            ) 'handoff-relay\latest-status.json'
            $health = Get-Content -Raw -LiteralPath $healthPath | ConvertFrom-Json
            $health.status | Should -BeExactly 'FAILED'
            $health.code | Should -BeExactly 'unexpected-error'
            $health.details.stage | Should -BeExactly 'complete'
        }

        It 'preserves active and archived attempts when draft archival cannot start' {
            $projectRoot = Join-Path $script:RememberProjectsRoot 'd--Development-AI-related'
            $null = New-Item -ItemType Directory -Path $projectRoot -Force
            $target = Join-Path $projectRoot 'remember.md'
            '# stable handoff' | Set-Content -LiteralPath $target -Encoding utf8NoBOM
            $firstPayload = @{
                hook_event_name = 'Stop'
                session_id = 'archive-race-session'
                turn_id = 'archive-race-turn'
                cwd = 'D:\Development\AI-related'
                stop_hook_active = $false
            }

            $first = Invoke-HandoffRelayProcess `
                -RememberProjectsRoot $script:RememberProjectsRoot `
                -Payload $firstPayload
            $draftPath = Get-HandoffRelayDraftPath -Output $first.Output
            $statePath = $draftPath -replace '\.draft\.md$', '.state.json'
            '# invalid draft held across archival' |
                Set-Content -LiteralPath $draftPath -Encoding utf8NoBOM
            $relayRoot = Split-Path -Parent $draftPath
            $failedDraft = Join-Path $relayRoot (
                'dddddddddddddddddddddddddddddddd.failed.20260825T010203004Z.draft.md'
            )
            $conflictState = Join-Path $relayRoot (
                'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee.conflict.20260825T010203004Z.state.json'
            )
            $nonRawDraft = Join-Path $relayRoot 'not-a-session-key.draft.md'
            $looseKey = 'cccccccccccccccccccccccccccccccc'
            $looseDraft = Join-Path $relayRoot "$looseKey.draft.md"
            'failed archive' | Set-Content -LiteralPath $failedDraft -Encoding utf8NoBOM
            '{"archive":"conflict"}' |
                Set-Content -LiteralPath $conflictState -Encoding utf8NoBOM
            'not an exact raw name' |
                Set-Content -LiteralPath $nonRawDraft -Encoding utf8NoBOM
            'truly loose draft' | Set-Content -LiteralPath $looseDraft -Encoding utf8NoBOM

            $draftLock = [System.IO.FileStream]::new(
                $draftPath,
                [System.IO.FileMode]::Open,
                [System.IO.FileAccess]::Read,
                [System.IO.FileShare]::Read
            )
            try {
                $firstPayload.stop_hook_active = $true
                $failedCompletion = Invoke-HandoffRelayProcess `
                    -RememberProjectsRoot $script:RememberProjectsRoot `
                    -Payload $firstPayload
            }
            finally {
                $draftLock.Dispose()
            }

            $secondPreparation = Invoke-HandoffRelayProcess `
                -RememberProjectsRoot $script:RememberProjectsRoot `
                -Payload @{
                    hook_event_name = 'Stop'
                    session_id = 'concurrent-preparation-session'
                    turn_id = 'concurrent-preparation-turn'
                    cwd = 'D:\Development\AI-related'
                    stop_hook_active = $false
                }

            ($failedCompletion.Output | ConvertFrom-Json).systemMessage |
                Should -BeExactly 'Handoff Relay: automatic context refresh needs another try.'
            ($secondPreparation.Output | ConvertFrom-Json).decision |
                Should -BeExactly 'block'
            Test-Path -LiteralPath $statePath -PathType Leaf | Should -BeTrue
            Test-Path -LiteralPath $draftPath -PathType Leaf | Should -BeTrue
            (Get-Content -Raw -LiteralPath $draftPath).Trim() |
                Should -BeExactly '# invalid draft held across archival'
            @(Get-ChildItem -LiteralPath $relayRoot -Filter '*.orphaned.*.draft.md' |
                Where-Object Name -Like "$(Split-Path -LeafBase $draftPath).orphaned.*") |
                Should -HaveCount 0
            Test-Path -LiteralPath $looseDraft | Should -BeFalse
            @(Get-ChildItem -LiteralPath $relayRoot -Filter "$looseKey.orphaned.*.draft.md") |
                Should -HaveCount 1
            (Get-Content -Raw -LiteralPath $failedDraft).Trim() |
                Should -BeExactly 'failed archive'
            (Get-Content -Raw -LiteralPath $conflictState).Trim() |
                Should -BeExactly '{"archive":"conflict"}'
            (Get-Content -Raw -LiteralPath $nonRawDraft).Trim() |
                Should -BeExactly 'not an exact raw name'
            (Get-Content -Raw -LiteralPath $target).Trim() |
                Should -BeExactly '# stable handoff'
        }

        It 'cleans a noisy draft and atomically publishes the compact fixed schema on the second Stop' {
            $projectRoot = Join-Path $script:RememberProjectsRoot 'd--Development-AI-related'
            $null = New-Item -ItemType Directory -Path $projectRoot -Force
            $target = Join-Path $projectRoot 'remember.md'
            '# old handoff' | Set-Content -LiteralPath $target -Encoding utf8NoBOM
            $payload = @{
                hook_event_name = 'Stop'
                session_id = 'publish-session'
                turn_id = 'publish-turn'
                cwd = 'D:\Development\AI-related\Ai-Skills'
                stop_hook_active = $false
            }

            $first = Invoke-HandoffRelayProcess `
                -RememberProjectsRoot $script:RememberProjectsRoot `
                -Payload $payload
            $draftPath = Get-HandoffRelayDraftPath -Output $first.Output
            New-TestHandoffDraft -Marker 'PUBLISH-MARKER' -IncludeNoise |
                Set-Content -LiteralPath $draftPath -Encoding utf8NoBOM

            $payload.stop_hook_active = $true
            $second = Invoke-HandoffRelayProcess `
                -RememberProjectsRoot $script:RememberProjectsRoot `
                -Payload $payload

            $secondOutput = $second.Output | ConvertFrom-Json
            $secondOutput.PSObject.Properties.Name | Should -Not -Contain 'decision'
            $secondOutput.systemMessage | Should -BeExactly (
                'Handoff Relay: next-session context refreshed.'
            )
            $published = Get-Content -Raw -LiteralPath $target
            $published | Should -Match '^# Handoff'
            $published | Should -Match 'handoff-relay:v1'
            $published | Should -Match '(?m)^## Summary\r?$'
            $published | Should -Match '(?m)^## Changed surfaces\r?$'
            $published | Should -Match '(?m)^## Verification\r?$'
            $published | Should -Match '(?m)^## Next gate\r?$'
            $published | Should -Match 'PUBLISH-MARKER'
            $published | Should -Not -Match 'superfluous'
            $published | Should -Not -Match '(?i)maybe|probably|unverified|might all fail'
            @($published -split '\s+' | Where-Object { $_ }).Count | Should -BeLessOrEqual 450
            Test-Path -LiteralPath $draftPath | Should -BeFalse

            $healthPath = Join-Path (Split-Path -Parent $script:RememberProjectsRoot) 'handoff-relay\latest-status.json'
            $health = Get-Content -Raw -LiteralPath $healthPath | ConvertFrom-Json
            $health.status | Should -BeExactly 'PUBLISHED'
            $health.code | Should -BeExactly 'published'
            $health.cleaning.droppedItems | Should -BeGreaterThan 0
            $health.cleaning.truncatedItems | Should -BeGreaterThan 0
            $health.cleaning.ignoredLines | Should -BeGreaterThan 0
        }

        It 'accepts exact section names without Markdown prefixes and publishes the handoff' {
            $projectRoot = Join-Path $script:RememberProjectsRoot 'd--Development-AI-related'
            $null = New-Item -ItemType Directory -Path $projectRoot -Force
            $target = Join-Path $projectRoot 'remember.md'
            '# old handoff' | Set-Content -LiteralPath $target -Encoding utf8NoBOM
            $payload = @{
                hook_event_name = 'Stop'
                session_id = 'plain-heading-session'
                turn_id = 'plain-heading-turn'
                cwd = 'D:\Development\AI-related'
                stop_hook_active = $false
            }

            $first = Invoke-HandoffRelayProcess `
                -RememberProjectsRoot $script:RememberProjectsRoot `
                -Payload $payload
            $draftPath = Get-HandoffRelayDraftPath -Output $first.Output
            @'
Summary
- Plain headings came from the exact failed runtime shape.
Outcome
- The completed work remains available for the next session.
Verified state
- [verified] The regression fixture is complete. Evidence: every required section is present.
Changed surfaces
- Source and test fixtures changed.
Verification
- The isolated relay process reached its publication pass.
Open risks
- None.
Next gate
- Run the full lifecycle suite.
'@ | Set-Content -LiteralPath $draftPath -Encoding utf8NoBOM

            $payload.stop_hook_active = $true
            $second = Invoke-HandoffRelayProcess `
                -RememberProjectsRoot $script:RememberProjectsRoot `
                -Payload $payload

            $secondOutput = $second.Output | ConvertFrom-Json
            $secondOutput.systemMessage | Should -BeExactly (
                'Handoff Relay: next-session context refreshed.'
            )
            $published = Get-Content -Raw -LiteralPath $target
            $published | Should -Match '(?m)^## Summary\r?$'
            $published | Should -Match 'Plain headings came from the exact failed runtime shape.'
        }

        It 'quarantines and reports a current draft whose transaction state disappeared' {
            $projectRoot = Join-Path $script:RememberProjectsRoot 'd--Development-AI-related'
            $null = New-Item -ItemType Directory -Path $projectRoot -Force
            $target = Join-Path $projectRoot 'remember.md'
            '# stable handoff' | Set-Content -LiteralPath $target -Encoding utf8NoBOM
            $payload = @{
                hook_event_name = 'Stop'
                session_id = 'missing-state-session'
                turn_id = 'missing-state-turn'
                cwd = 'D:\Development\AI-related'
                stop_hook_active = $false
            }

            $first = Invoke-HandoffRelayProcess `
                -RememberProjectsRoot $script:RememberProjectsRoot `
                -Payload $payload
            $draftPath = Get-HandoffRelayDraftPath -Output $first.Output
            New-TestHandoffDraft -Marker 'MISSING-STATE-MARKER' |
                Set-Content -LiteralPath $draftPath -Encoding utf8NoBOM
            $statePath = $draftPath -replace '\.draft\.md$', '.state.json'
            Remove-Item -LiteralPath $statePath -Force

            $payload.stop_hook_active = $true
            $second = Invoke-HandoffRelayProcess `
                -RememberProjectsRoot $script:RememberProjectsRoot `
                -Payload $payload

            $secondOutput = $second.Output | ConvertFrom-Json
            $secondOutput.systemMessage | Should -BeExactly (
                'Handoff Relay: automatic context refresh needs another try.'
            )
            (Get-Content -Raw -LiteralPath $target).Trim() | Should -BeExactly '# stable handoff'
            Test-Path -LiteralPath $draftPath | Should -BeFalse
            @(
                Get-ChildItem `
                    -LiteralPath (Split-Path -Parent $draftPath) `
                    -Filter '*.orphaned.*.draft.md'
            ).Count | Should -BeExactly 1

            $healthPath = Join-Path (
                Split-Path -Parent $script:RememberProjectsRoot
            ) 'handoff-relay\latest-status.json'
            $health = Get-Content -Raw -LiteralPath $healthPath | ConvertFrom-Json
            $health.status | Should -BeExactly 'FAILED'
            $health.code | Should -BeExactly 'state-missing'
            $health.details.draftQuarantined | Should -BeExactly 'True'
        }

        It 'drops explicit speculation from factual sections without rejecting a contract-valid risk' {
            $projectRoot = Join-Path $script:RememberProjectsRoot 'd--Development-AI-related'
            $null = New-Item -ItemType Directory -Path $projectRoot -Force
            $target = Join-Path $projectRoot 'remember.md'
            '# baseline' | Set-Content -LiteralPath $target -Encoding utf8NoBOM
            $payload = @{
                hook_event_name = 'Stop'
                session_id = 'speculation-filter-session'
                turn_id = 'speculation-filter-turn'
                cwd = 'D:\Development\AI-related'
                stop_hook_active = $false
            }

            $first = Invoke-HandoffRelayProcess `
                -RememberProjectsRoot $script:RememberProjectsRoot `
                -Payload $payload
            $draftPath = Get-HandoffRelayDraftPath -Output $first.Output
            Get-ContractHandoffDraft `
                -SummaryItems @(
                    'Stable summary evidence is retained.',
                    'FACT-SUMMARY could fail after publication.'
                ) `
                -OutcomeItems @(
                    'Stable outcome evidence is retained.',
                    'FACT-OUTCOME might produce a different result.',
                    'FACT-MAY may contain stale state.'
                ) `
                -VerifiedItems @(
                    '[verified] Stable state is present. Evidence: the fixture supplied it.',
                    '[verified] FACT-ALLEGED is allegedly complete. Evidence: a rumor supplied it.'
                ) `
                -ChangedItems @(
                    'Stable source fixture content changed.',
                    'FACT-APPEARS appears current.'
                ) `
                -VerificationItems @(
                    'PASS: stable verification completed.',
                    'FACT-EXPECTED is expected to pass.'
                ) `
                -RiskItems @(
                    '[risk] RISK-MODAL could fail after publication. Basis: the attended smoke is pending.'
                ) |
                Set-Content -LiteralPath $draftPath -Encoding utf8NoBOM

            $payload.stop_hook_active = $true
            Invoke-HandoffRelayProcess `
                -RememberProjectsRoot $script:RememberProjectsRoot `
                -Payload $payload |
                Out-Null

            $published = Get-Content -Raw -LiteralPath $target
            $published | Should -Match 'Stable summary evidence is retained'
            $published | Should -Match 'RISK-MODAL could fail'
            foreach ($marker in @(
                'FACT-SUMMARY',
                'FACT-OUTCOME',
                'FACT-MAY',
                'FACT-ALLEGED',
                'FACT-APPEARS',
                'FACT-EXPECTED'
            )) {
                $published | Should -Not -Match $marker
            }
        }

        It 'enforces inclusive per-item character and UTF-8 boundaries on giant tokens' {
            $projectRoot = Join-Path $script:RememberProjectsRoot 'd--Development-AI-related'
            $null = New-Item -ItemType Directory -Path $projectRoot -Force
            $target = Join-Path $projectRoot 'remember.md'
            '# baseline' | Set-Content -LiteralPath $target -Encoding utf8NoBOM

            $characterPayload = @{
                hook_event_name = 'Stop'
                session_id = 'character-boundary-session'
                turn_id = 'character-boundary-turn'
                cwd = 'D:\Development\AI-related'
                stop_hook_active = $false
            }
            $characterParameters = @{
                MaxItemCharacters = 64
                MaxItemUtf8Bytes = 128
            }
            $characterLimit = 'A' * 64
            $characterOver = 'B' * 65
            $first = Invoke-HandoffRelayProcess `
                -RememberProjectsRoot $script:RememberProjectsRoot `
                -Payload $characterPayload `
                -HookParameters $characterParameters
            $draftPath = Get-HandoffRelayDraftPath -Output $first.Output
            Get-ContractHandoffDraft -SummaryItems @($characterLimit, $characterOver) |
                Set-Content -LiteralPath $draftPath -Encoding utf8NoBOM
            $characterPayload.stop_hook_active = $true
            Invoke-HandoffRelayProcess `
                -RememberProjectsRoot $script:RememberProjectsRoot `
                -Payload $characterPayload `
                -HookParameters $characterParameters |
                Out-Null

            $characterLines = @(Get-Content -LiteralPath $target)
            $characterLines | Should -Contain "- $characterLimit"
            $characterLines | Should -Contain ("- {0} ..." -f ('B' * 60))
            $characterLines | Should -Not -Contain "- $characterOver"

            $utf8Payload = @{
                hook_event_name = 'Stop'
                session_id = 'utf8-boundary-session'
                turn_id = 'utf8-boundary-turn'
                cwd = 'D:\Development\AI-related'
                stop_hook_active = $false
            }
            $utf8Parameters = @{
                MaxItemCharacters = 256
                MaxItemUtf8Bytes = 128
            }
            $utf8Limit = ([string] [char] 0x00E9) * 64
            $utf8Over = ([string] [char] 0x00F8) * 65
            $first = Invoke-HandoffRelayProcess `
                -RememberProjectsRoot $script:RememberProjectsRoot `
                -Payload $utf8Payload `
                -HookParameters $utf8Parameters
            $draftPath = Get-HandoffRelayDraftPath -Output $first.Output
            Get-ContractHandoffDraft -SummaryItems @($utf8Limit, $utf8Over) |
                Set-Content -LiteralPath $draftPath -Encoding utf8NoBOM
            $utf8Payload.stop_hook_active = $true
            Invoke-HandoffRelayProcess `
                -RememberProjectsRoot $script:RememberProjectsRoot `
                -Payload $utf8Payload `
                -HookParameters $utf8Parameters |
                Out-Null

            $utf8Lines = @(Get-Content -LiteralPath $target)
            $utf8Lines | Should -Contain "- $utf8Limit"
            $utf8Lines | Should -Contain ("- {0} ..." -f (([string] [char] 0x00F8) * 62))
            $utf8Lines | Should -Not -Contain "- $utf8Over"
        }

        It 'accepts an exact final-document UTF-8 cap and rejects one byte below it' {
            function Invoke-DocumentCapCase {
                param(
                    [Parameter(Mandatory)][string] $Root,
                    [Parameter(Mandatory = $false)][int] $MaximumBytes = 0
                )

                $projectsRoot = Join-Path $Root 'projects'
                $projectRoot = Join-Path $projectsRoot 'd--Development-AI-related'
                $null = New-Item -ItemType Directory -Path $projectRoot -Force
                $target = Join-Path $projectRoot 'remember.md'
                '# baseline' | Set-Content -LiteralPath $target -Encoding utf8NoBOM
                $payload = @{
                    hook_event_name = 'Stop'
                    session_id = 'document-boundary-session'
                    turn_id = 'document-boundary-turn'
                    cwd = 'D:\Development\AI-related'
                    stop_hook_active = $false
                }
                $parameters = @{}
                if ($MaximumBytes -gt 0) {
                    $parameters.MaxPublishedBytes = $MaximumBytes
                }

                $first = Invoke-HandoffRelayProcess `
                    -RememberProjectsRoot $projectsRoot `
                    -Payload $payload `
                    -HookParameters $parameters
                $draftPath = Get-HandoffRelayDraftPath -Output $first.Output
                Get-ContractHandoffDraft -SummaryItems @('Stable document-cap fixture summary.') |
                    Set-Content -LiteralPath $draftPath -Encoding utf8NoBOM
                $payload.stop_hook_active = $true
                $second = Invoke-HandoffRelayProcess `
                    -RememberProjectsRoot $projectsRoot `
                    -Payload $payload `
                    -HookParameters $parameters

                return [pscustomobject]@{
                    Target = $target
                    HealthPath = Join-Path $Root 'handoff-relay\latest-status.json'
                    Second = $second
                }
            }

            $reference = Invoke-DocumentCapCase -Root (Join-Path $TestDrive 'document-cap-reference')
            $referenceDocument = Get-Content -Raw -LiteralPath $reference.Target
            $actualBytes = [System.Text.UTF8Encoding]::new($false).GetByteCount($referenceDocument)

            $exact = Invoke-DocumentCapCase `
                -Root (Join-Path $TestDrive 'document-cap-exact') `
                -MaximumBytes $actualBytes
            $exactDocument = Get-Content -Raw -LiteralPath $exact.Target
            [System.Text.UTF8Encoding]::new($false).GetByteCount($exactDocument) |
                Should -BeExactly $actualBytes

            $below = Invoke-DocumentCapCase `
                -Root (Join-Path $TestDrive 'document-cap-below') `
                -MaximumBytes ($actualBytes - 1)
            (Get-Content -Raw -LiteralPath $below.Target).Trim() | Should -BeExactly '# baseline'
            $belowHealth = Get-Content -Raw -LiteralPath $below.HealthPath | ConvertFrom-Json
            $belowHealth.status | Should -BeExactly 'FAILED'
            $belowHealth.code | Should -BeExactly 'document-too-large'
            $belowHealth.details.maximumBytes | Should -BeExactly ([string] ($actualBytes - 1))
            $belowHealth.details.actualBytes | Should -BeExactly ([string] $actualBytes)
        }

        It 'rejects a draft that loses a required section during cleaning and records a bounded failure' {
            $projectRoot = Join-Path $script:RememberProjectsRoot 'd--Development-AI-related'
            $null = New-Item -ItemType Directory -Path $projectRoot -Force
            $target = Join-Path $projectRoot 'remember.md'
            '# preserved handoff' | Set-Content -LiteralPath $target -Encoding utf8NoBOM
            $payload = @{
                hook_event_name = 'Stop'
                session_id = 'invalid-draft-session'
                turn_id = 'invalid-draft-turn'
                cwd = 'D:\Development\AI-related'
                stop_hook_active = $false
            }

            $first = Invoke-HandoffRelayProcess `
                -RememberProjectsRoot $script:RememberProjectsRoot `
                -Payload $payload
            $draftPath = Get-HandoffRelayDraftPath -Output $first.Output
            @'
## Summary
- Invalid draft.
## Outcome
- It omits most required sections.
'@ | Set-Content -LiteralPath $draftPath -Encoding utf8NoBOM

            $payload.stop_hook_active = $true
            $second = Invoke-HandoffRelayProcess `
                -RememberProjectsRoot $script:RememberProjectsRoot `
                -Payload $payload

            $failureMessage = ($second.Output | ConvertFrom-Json).systemMessage
            $failureMessage | Should -BeExactly (
                'Handoff Relay: automatic context refresh needs another try.'
            )
            $failureMessage | Should -Not -Match 'draft-invalid|canonical|not published'
            (Get-Content -Raw -LiteralPath $target).Trim() | Should -BeExactly '# preserved handoff'
            $healthPath = Join-Path (Split-Path -Parent $script:RememberProjectsRoot) 'handoff-relay\latest-status.json'
            $health = Get-Content -Raw -LiteralPath $healthPath | ConvertFrom-Json
            $health.status | Should -BeExactly 'FAILED'
            $health.code | Should -BeExactly 'draft-invalid'
            @(Get-ChildItem -LiteralPath (Split-Path -Parent $draftPath) -Filter '*.failed.*.draft.md') |
                Should -HaveCount 1
        }

        It 'creates the canonical remember file on first successful publication for an enrolled project' {
            $projectRoot = Join-Path $script:RememberProjectsRoot 'd--Development-AI-related'
            $null = New-Item -ItemType Directory -Path $projectRoot -Force
            $target = Join-Path $projectRoot 'remember.md'
            $payload = @{
                hook_event_name = 'Stop'
                session_id = 'first-publication-session'
                turn_id = 'first-publication-turn'
                cwd = 'D:\Development\AI-related'
                stop_hook_active = $false
            }

            $first = Invoke-HandoffRelayProcess `
                -RememberProjectsRoot $script:RememberProjectsRoot `
                -Payload $payload
            $draftPath = Get-HandoffRelayDraftPath -Output $first.Output
            New-TestHandoffDraft -Marker 'FIRST-PUBLICATION' |
                Set-Content -LiteralPath $draftPath -Encoding utf8NoBOM

            $payload.stop_hook_active = $true
            Invoke-HandoffRelayProcess `
                -RememberProjectsRoot $script:RememberProjectsRoot `
                -Payload $payload |
                Out-Null

            Test-Path -LiteralPath $target -PathType Leaf | Should -BeTrue
            $published = Get-Content -Raw -LiteralPath $target
            $published | Should -Match 'FIRST-PUBLICATION'
            $published | Should -Match 'baseline_sha256: <absent>'
        }

        It 'preserves the later draft as a conflict when another session changed the canonical handoff' {
            $projectRoot = Join-Path $script:RememberProjectsRoot 'd--Development-AI-related'
            $null = New-Item -ItemType Directory -Path $projectRoot -Force
            $target = Join-Path $projectRoot 'remember.md'
            '# baseline handoff' | Set-Content -LiteralPath $target -Encoding utf8NoBOM
            $firstPayload = @{
                hook_event_name = 'Stop'
                session_id = 'concurrent-session-a'
                turn_id = 'concurrent-turn-a'
                cwd = 'D:\Development\AI-related'
                stop_hook_active = $false
            }
            $secondPayload = @{
                hook_event_name = 'Stop'
                session_id = 'concurrent-session-b'
                turn_id = 'concurrent-turn-b'
                cwd = 'D:\Development\AI-related'
                stop_hook_active = $false
            }

            $firstStart = Invoke-HandoffRelayProcess `
                -RememberProjectsRoot $script:RememberProjectsRoot `
                -Payload $firstPayload
            $secondStart = Invoke-HandoffRelayProcess `
                -RememberProjectsRoot $script:RememberProjectsRoot `
                -Payload $secondPayload
            $firstDraft = Get-HandoffRelayDraftPath -Output $firstStart.Output
            $secondDraft = Get-HandoffRelayDraftPath -Output $secondStart.Output
            New-TestHandoffDraft -Marker 'SESSION-A' | Set-Content -LiteralPath $firstDraft -Encoding utf8NoBOM
            New-TestHandoffDraft -Marker 'SESSION-B' | Set-Content -LiteralPath $secondDraft -Encoding utf8NoBOM

            $firstPayload.stop_hook_active = $true
            Invoke-HandoffRelayProcess `
                -RememberProjectsRoot $script:RememberProjectsRoot `
                -Payload $firstPayload |
                Out-Null
            $secondPayload.stop_hook_active = $true
            Invoke-HandoffRelayProcess `
                -RememberProjectsRoot $script:RememberProjectsRoot `
                -Payload $secondPayload |
                Out-Null

            $published = Get-Content -Raw -LiteralPath $target
            $published | Should -Match 'SESSION-A'
            $published | Should -Not -Match 'SESSION-B'
            $healthPath = Join-Path (Split-Path -Parent $script:RememberProjectsRoot) 'handoff-relay\latest-status.json'
            $health = Get-Content -Raw -LiteralPath $healthPath | ConvertFrom-Json
            $health.status | Should -BeExactly 'CONFLICT'
            $health.code | Should -BeExactly 'canonical-changed'
            @(Get-ChildItem -LiteralPath (Split-Path -Parent $secondDraft) -Filter '*.conflict.*.draft.md') |
                Should -HaveCount 1
        }

        It 'allows the second Stop pass without creating a continuation loop' {
            $projectRoot = Join-Path $script:RememberProjectsRoot 'd--Development-AI-related'
            $null = New-Item -ItemType Directory -Path $projectRoot -Force

            $result = Invoke-HandoffRelayProcess `
                -RememberProjectsRoot $script:RememberProjectsRoot `
                -Payload @{
                    hook_event_name = 'Stop'
                    cwd = 'D:\Development\AI-related'
                    stop_hook_active = $true
                }

            $result.Output.Trim() | Should -BeExactly '{}'
        }

        It 'does not finalize while Claude still has background work' {
            $projectRoot = Join-Path $script:RememberProjectsRoot 'd--Development-AI-related'
            $null = New-Item -ItemType Directory -Path $projectRoot -Force

            $result = Invoke-HandoffRelayProcess `
                -RememberProjectsRoot $script:RememberProjectsRoot `
                -Payload @{
                    hook_event_name = 'Stop'
                    cwd = 'D:\Development\AI-related'
                    stop_hook_active = $false
                    background_tasks = @(@{ id = 'task-1'; status = 'running' })
                    session_crons = @()
                }

            $result.Output.Trim() | Should -BeExactly '{}'
        }

        It 'ignores user-only target text and refuses targets outside the Remember store' {
            $transcript = Write-HandoffRelayTranscript -Records @(
                [ordered]@{
                    type = 'response_item'
                    payload = [ordered]@{
                        role = 'user'
                        content = @([ordered]@{
                            type = 'input_text'
                            text = 'Write next handoff to: C:/Windows/System32/remember.md'
                        })
                    }
                },
                [ordered]@{
                    type = 'response_item'
                    payload = [ordered]@{
                        role = 'developer'
                        content = @([ordered]@{
                            type = 'input_text'
                            text = 'Write next handoff to: C:/Windows/System32/remember.md'
                        })
                    }
                }
            )

            $result = Invoke-HandoffRelayProcess `
                -RememberProjectsRoot $script:RememberProjectsRoot `
                -Payload @{
                    hook_event_name = 'Stop'
                    cwd = 'D:\No-Remember-Project'
                    transcript_path = $transcript
                    stop_hook_active = $false
                }

            $result.Output.Trim() | Should -BeExactly '{}'
        }

        It 'refuses a relative developer-declared target even if process cwd could resolve it' {
            $projectRoot = Join-Path $script:RememberProjectsRoot 'd--Development-AI-related'
            $null = New-Item -ItemType Directory -Path $projectRoot -Force
            $transcript = Write-HandoffRelayTranscript -Records @(
                [ordered]@{
                    type = 'response_item'
                    payload = [ordered]@{
                        role = 'developer'
                        content = @([ordered]@{
                            type = 'input_text'
                            text = 'Write next handoff to: d--Development-AI-related/remember.md'
                        })
                    }
                }
            )

            $result = Invoke-HandoffRelayProcess `
                -RememberProjectsRoot $script:RememberProjectsRoot `
                -Payload @{
                    hook_event_name = 'Stop'
                    cwd = 'D:\Development\AI-related'
                    transcript_path = $transcript
                    stop_hook_active = $false
                }

            $result.Output.Trim() | Should -BeExactly '{}'
        }

        It 'does nothing when Remember has not enrolled the cwd project' {
            $result = Invoke-HandoffRelayProcess `
                -RememberProjectsRoot $script:RememberProjectsRoot `
                -Payload @{
                    hook_event_name = 'Stop'
                    cwd = 'D:\New-Project'
                    stop_hook_active = $false
                }

            $result.Output.Trim() | Should -BeExactly '{}'
        }

        It 'records malformed Stop input after the configured root and machine are safely established' {
            $result = Invoke-HandoffRelayProcess `
                -RememberProjectsRoot $script:RememberProjectsRoot `
                -RawInput '{not-json'

            $result.Output.Trim() | Should -BeExactly '{}'
            $healthPath = Join-Path (
                Split-Path -Parent $script:RememberProjectsRoot
            ) 'handoff-relay\latest-status.json'
            $health = Get-Content -Raw -LiteralPath $healthPath | ConvertFrom-Json
            $health.status | Should -BeExactly 'FAILED'
            $health.code | Should -BeExactly 'unexpected-error'
            $health.details.stage | Should -BeExactly 'read-input'
            $health.project | Should -BeNullOrEmpty
        }

        It 'does not invent a health target when the configured projects root is unavailable' {
            $missingProjectsRoot = Join-Path $TestDrive 'missing-remember-root\projects'
            $result = Invoke-HandoffRelayProcess `
                -RememberProjectsRoot $missingProjectsRoot `
                -RawInput '{not-json'

            $result.Output.Trim() | Should -BeExactly '{}'
            Test-Path -LiteralPath (
                Join-Path (Split-Path -Parent $missingProjectsRoot) 'handoff-relay\latest-status.json'
            ) | Should -BeFalse
        }

        It 'does not create draft, health, or canonical state when machine identity is unverified' {
            $isolatedProjectsRoot = Join-Path $TestDrive 'unverified\remember\projects'
            $projectRoot = Join-Path $isolatedProjectsRoot 'd--Development-AI-related'
            $null = New-Item -ItemType Directory -Path $projectRoot -Force

            $result = Invoke-HandoffRelayProcess `
                -RememberProjectsRoot $isolatedProjectsRoot `
                -VerifierPath (New-UnverifiedMachineVerifier) `
                -Payload @{
                    hook_event_name = 'Stop'
                    session_id = 'unverified-session'
                    turn_id = 'unverified-turn'
                    cwd = 'D:\Development\AI-related'
                    stop_hook_active = $false
                }

            $result.Output.Trim() | Should -BeExactly '{}'
            Test-Path -LiteralPath (Join-Path $projectRoot 'remember.md') | Should -BeFalse
            Test-Path -LiteralPath (Join-Path $projectRoot 'tmp\handoff-relay') | Should -BeFalse
            Test-Path -LiteralPath (
                Join-Path (Split-Path -Parent $isolatedProjectsRoot) 'handoff-relay\latest-status.json'
            ) | Should -BeFalse
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
                },
                @{
                    Hook = $config.hooks.Stop[0].hooks[1]
                    Command = 'pwsh -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "D:\DevHome\state\codex\hooks\Invoke-HandoffRelay.ps1" -Provider Codex'
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
            @($config.hooks.Stop[0].hooks).Count | Should -Be 2
            $config.hooks.Stop[0].hooks[0].timeout | Should -Be 5
            $config.hooks.Stop[0].hooks[0].statusMessage | Should -Be 'Finalizing Remember transcript capture'
            $config.hooks.Stop[0].hooks[1].timeout | Should -Be 5
            $config.hooks.Stop[0].hooks[1].statusMessage | Should -Be 'Handoff Relay: preparing next-session context'
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
                'hooks\Invoke-RememberClaude.cmd',
                'hooks\Invoke-HandoffRelay.ps1'
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

        It 'installs the Claude Handoff Relay without replacing unrelated settings or hooks' {
            Test-Path -LiteralPath $script:ClaudeHandoffInstaller -PathType Leaf | Should -BeTrue
            $targetRoot = Join-Path $TestDrive 'claude-home'
            $null = New-Item -ItemType Directory -Path $targetRoot -Force
            $legacyOwnedCommand = 'pwsh -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "{0}"' -f (
                (Join-Path $targetRoot 'hooks\Invoke-HandoffRelay.ps1') -replace '\\','/'
            )
            [ordered]@{
                model = 'opus'
                hooks = [ordered]@{
                    Stop = @(
                        [ordered]@{
                            hooks = @(
                                [ordered]@{
                                    type = 'command'
                                    command = 'python existing-stop-hook.py'
                                    timeout = 7
                                },
                                [ordered]@{
                                    type = 'command'
                                    command = 'pwsh -NoProfile -File "C:/OtherProduct/hooks/Invoke-HandoffRelay.ps1"'
                                    timeout = 9
                                },
                                [ordered]@{
                                    type = 'command'
                                    command = $legacyOwnedCommand
                                    timeout = 5
                                }
                            )
                        }
                    )
                }
                theme = 'dark'
            } | ConvertTo-Json -Depth 20 |
                Set-Content -LiteralPath (Join-Path $targetRoot 'settings.json') -Encoding utf8NoBOM

            $verifier = New-TestMachineVerifier
            & $script:ClaudeHandoffInstaller `
                -TargetRoot $targetRoot `
                -AllowTestOnlyTargetRootOverride `
                -VerifierPath $verifier |
                Out-Null

            {
                & $script:ClaudeHandoffInstaller `
                    -TargetRoot $targetRoot `
                    -AllowTestOnlyTargetRootOverride `
                    -VerifierPath $verifier `
                    -Check
            } | Should -Not -Throw

            $settings = Get-Content -Raw -LiteralPath (Join-Path $targetRoot 'settings.json') |
                ConvertFrom-Json -Depth 30
            $settings.model | Should -BeExactly 'opus'
            $settings.theme | Should -BeExactly 'dark'
            $commands = @($settings.hooks.Stop | ForEach-Object { @($_.hooks).command })
            $commands | Should -Contain 'python existing-stop-hook.py'
            $commands | Should -Contain 'pwsh -NoProfile -File "C:/OtherProduct/hooks/Invoke-HandoffRelay.ps1"'
            $commands | Should -Not -Contain $legacyOwnedCommand
            @($commands | Where-Object { $_ -match 'Invoke-HandoffRelay\.ps1' }) | Should -HaveCount 2
            @($commands | Where-Object { $_ -match [regex]::Escape(($targetRoot -replace '\\','/')) }) |
                Should -HaveCount 1
            @($commands | Where-Object { $_ -match [regex]::Escape(($targetRoot -replace '\\','/')) })[0] |
                Should -Match '-Provider Claude$'
            ($commands -join "`n") | Should -Match ([regex]::Escape(($targetRoot -replace '\\','/')))
            Test-Path -LiteralPath (Join-Path $targetRoot 'hooks\Invoke-HandoffRelay.ps1') -PathType Leaf |
                Should -BeTrue
        }

        It 'detects Claude Handoff Relay drift without rewriting it in check mode' {
            $targetRoot = Join-Path $TestDrive 'drifted-claude-home'
            $null = New-Item -ItemType Directory -Path $targetRoot -Force
            '{}' | Set-Content -LiteralPath (Join-Path $targetRoot 'settings.json') -Encoding utf8NoBOM
            $verifier = New-TestMachineVerifier
            & $script:ClaudeHandoffInstaller `
                -TargetRoot $targetRoot `
                -AllowTestOnlyTargetRootOverride `
                -VerifierPath $verifier |
                Out-Null
            $hookPath = Join-Path $targetRoot 'hooks\Invoke-HandoffRelay.ps1'
            Add-Content -LiteralPath $hookPath -Value '# drift probe'

            {
                & $script:ClaudeHandoffInstaller `
                    -TargetRoot $targetRoot `
                    -AllowTestOnlyTargetRootOverride `
                    -VerifierPath $verifier `
                    -Check
            } | Should -Throw '*drift*'
            (Get-Content -LiteralPath $hookPath -Tail 1) | Should -BeExactly '# drift probe'
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

        It 'documents behavioral health and foreign hook attribution' {
            $skill = Get-Content -Raw -LiteralPath $script:PluginSkill

            $skill | Should -Match 'durable capture output'
            $skill | Should -Match 'exact failing launcher token'
            $skill | Should -Match 'Get-Command python3 -All'
            $skill | Should -Match 'foreign plugin hooks'
            $skill | Should -Match 'does not clear a foreign hook failure'
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
