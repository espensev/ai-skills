BeforeAll {
    $script:RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
    $script:ModuleRoot = Join-Path $script:RepoRoot 'scripts\AiEnvironment'
    $script:ModulePath = Join-Path $script:ModuleRoot 'AiEnvironment.psd1'
    Import-Module $script:ModulePath -Force

    function Write-TestJson {
        param(
            [Parameter(Mandatory)][string] $Path,
            [Parameter(Mandatory)][object] $Value
        )
        $null = New-Item -ItemType Directory -Path (Split-Path -Parent $Path) -Force
        $Value | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $Path -Encoding utf8NoBOM
    }

    function Copy-TestFile {
        param(
            [Parameter(Mandatory)][string] $SourceRoot,
            [Parameter(Mandatory)][string] $TargetRoot,
            [Parameter(Mandatory)][string] $RelativePath
        )
        $source = Join-Path $SourceRoot ($RelativePath -replace '/', '\')
        $target = Join-Path $TargetRoot ($RelativePath -replace '/', '\')
        $null = New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force
        Copy-Item -LiteralPath $source -Destination $target -Force
    }

    function New-TestLockResource {
        param(
            [Parameter(Mandatory)][string] $Id,
            [Parameter(Mandatory)][string] $SourceRoot,
            [Parameter(Mandatory)][string[]] $Paths,
            [string] $Version,
            [string] $TrustHash
        )
        $resource = [ordered]@{
            id = $Id
            payload = @($Paths | ForEach-Object {
                [ordered]@{
                    path = $_
                    sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $SourceRoot ($_ -replace '/', '\'))).Hash
                }
            })
        }
        if (-not [string]::IsNullOrWhiteSpace($Version)) {
            $resource.version = $Version
        }
        if (-not [string]::IsNullOrWhiteSpace($TrustHash)) {
            $resource.trustHash = $TrustHash
        }
        return $resource
    }

    function Get-TestSurfaceDigest {
        param([Parameter(Mandatory)][string[]] $Roots)
        $rows = foreach ($root in $Roots) {
            if (-not (Test-Path -LiteralPath $root -PathType Container)) { continue }
            foreach ($file in Get-ChildItem -LiteralPath $root -Recurse -File -Force | Sort-Object FullName) {
                '{0}|{1}' -f $file.FullName, (Get-FileHash -Algorithm SHA256 -LiteralPath $file.FullName).Hash
            }
        }
        return $rows -join "`n"
    }

    function New-AiEnvironmentFixture {
        $root = Join-Path $TestDrive ([guid]::NewGuid().ToString('N'))
        $repo = Join-Path $root 'repo'
        $codexHome = Join-Path $root 'codex'
        $claudeHome = Join-Path $root 'claude'
        $agentsHome = Join-Path $root 'agents'
        $controlRoot = Join-Path $root 'control'
        $pluginSource = Join-Path $repo 'lifecycle-plugin'
        $codexHookSource = Join-Path $repo 'codex-hook'
        $claudeHookSource = Join-Path $repo 'claude-hook'
        $pluginCacheRoot = Join-Path $codexHome 'plugins\cache\ai-skills\devhome-lifecycle'
        $pluginTarget = Join-Path $pluginCacheRoot '1.0.0'

        $null = New-Item -ItemType Directory -Path $repo,$codexHome,$claudeHome,$agentsHome,$controlRoot,$pluginSource,$codexHookSource,$claudeHookSource -Force
        Set-Content -LiteralPath (Join-Path $pluginSource 'plugin.txt') -Value 'locked plugin payload' -Encoding utf8NoBOM
        Write-TestJson -Path (Join-Path $pluginSource '.codex-plugin\plugin.json') -Value ([ordered]@{
            name = 'fixture-lifecycle'
            version = '1.0.0'
        })
        $marketplaceManifest = Join-Path $repo '.agents\plugins\marketplace.json'
        $null = New-Item -ItemType Directory -Path (Split-Path -Parent $marketplaceManifest) -Force
        Set-Content -LiteralPath $marketplaceManifest -Value '{"name":"fixture"}' -Encoding utf8NoBOM
        Set-Content -LiteralPath (Join-Path $codexHookSource 'hooks.json') -Value '{"hooks":{}}' -Encoding utf8NoBOM
        $claudeHookPath = Join-Path $claudeHookSource 'hooks\Invoke-HandoffRelay.ps1'
        $null = New-Item -ItemType Directory -Path (Split-Path -Parent $claudeHookPath) -Force
        Set-Content -LiteralPath $claudeHookPath -Value '# test relay' -Encoding utf8NoBOM
        Copy-TestFile -SourceRoot $pluginSource -TargetRoot $pluginTarget -RelativePath 'plugin.txt'
        Copy-TestFile -SourceRoot $pluginSource -TargetRoot $pluginTarget -RelativePath '.codex-plugin/plugin.json'
        Copy-TestFile -SourceRoot $codexHookSource -TargetRoot $codexHome -RelativePath 'hooks.json'
        Copy-TestFile -SourceRoot $claudeHookSource -TargetRoot $claudeHome -RelativePath 'hooks/Invoke-HandoffRelay.ps1'

        git -C $repo init --quiet --initial-branch main
        git -C $repo config user.email 'ai-environment-tests@example.invalid'
        git -C $repo config user.name 'AI Environment Tests'
        git -C $repo config core.autocrlf false
        git -C $repo add --all
        git -C $repo commit --quiet -m 'fixture base'
        if ($LASTEXITCODE -ne 0) { throw 'Failed to commit AI environment fixture.' }
        $head = (git -C $repo rev-parse HEAD).Trim()

        $codexCommand = Join-Path $root 'codex.cmd'
        @'
@echo off
if "%~1"=="--version" (
  echo codex-cli 9.9.9
  exit /b 0
)
if "%~1"=="plugin" if "%~2"=="marketplace" if "%~3"=="list" (
  if "%AI_ENV_TEST_CODEX_FAIL%"=="1" exit /b 17
  echo {"marketplaces":[]}
  exit /b 0
)
exit /b 64
'@ | Set-Content -LiteralPath $codexCommand -Encoding ascii

        $claudeCommand = Join-Path $root 'claude.cmd'
        @'
@echo off
if "%~1"=="--version" (
  echo 8.8.8 (Claude Code^)
  exit /b 0
)
exit /b 64
'@ | Set-Content -LiteralPath $claudeCommand -Encoding ascii

        $existingSkillPath = Join-Path $agentsHome 'skills\discover\SKILL.md'
        $null = New-Item -ItemType Directory -Path (Split-Path -Parent $existingSkillPath) -Force
        Set-Content -LiteralPath $existingSkillPath -Value '# Discover' -Encoding utf8NoBOM
        Write-TestJson -Path (Join-Path $agentsHome '.skill-lock.json') -Value ([ordered]@{
            version = 3
            skills = [ordered]@{ discover = [ordered]@{ source = 'fixture' } }
            dismissed = [ordered]@{}
        })

        $codexConfigPath = Join-Path $codexHome 'config.toml'
        @"
[marketplaces.ai-skills]
source_type = 'local'
source = '$repo'

[plugins."devhome-lifecycle@ai-skills"]
enabled = true

[hooks.state."fixture-trust-record"]
trusted_hash = "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

[[skills.config]]
path = '$existingSkillPath'
enabled = false
"@ | Set-Content -LiteralPath $codexConfigPath -Encoding utf8NoBOM

        $claudeSettingsPath = Join-Path $claudeHome 'settings.json'
        Write-TestJson -Path $claudeSettingsPath -Value ([ordered]@{
            skillOverrides = [ordered]@{ discover = 'on'; review = 'off' }
            hooks = [ordered]@{
                Stop = @([ordered]@{
                    hooks = @([ordered]@{
                        type = 'command'
                        command = "pwsh -File `"$($claudeHome -replace '\\','/')/hooks/Invoke-HandoffRelay.ps1`""
                        timeout = 5
                        statusMessage = 'Handoff Relay: preparing next-session context'
                    })
                })
            }
            enabledPlugins = [ordered]@{ 'remember@claude-plugins-official' = $true }
        })

        $rememberInstallPath = Join-Path $claudeHome 'plugins\cache\remember\1.0.0'
        $null = New-Item -ItemType Directory -Path $rememberInstallPath -Force
        $pluginRegistryPath = Join-Path $claudeHome 'plugins\installed_plugins.json'
        Write-TestJson -Path $pluginRegistryPath -Value ([ordered]@{
            version = 2
            plugins = [ordered]@{
                'remember@claude-plugins-official' = @([ordered]@{
                    scope = 'user'
                    installPath = $rememberInstallPath
                    version = '1.0.0'
                })
            }
        })

        $profilePath = Join-Path $controlRoot 'profile.json'
        $lockPath = Join-Path $controlRoot 'lock.json'
        $profile = [ordered]@{
            schema = 'ai-skills/ai-environment-profile/v1'
            id = 'test-machine'
            machine = [ordered]@{
                id = 'test-machine'
                instanceId = '11111111-1111-4111-8111-111111111111'
            }
            source = [ordered]@{ repositoryRoot = $repo }
            providers = [ordered]@{
                codex = [ordered]@{
                    command = 'codex'
                    homePath = $codexHome
                    configPath = $codexConfigPath
                    pluginRegistryPath = (Join-Path $codexHome 'plugins')
                }
                claude = [ordered]@{
                    command = 'claude'
                    homePath = $claudeHome
                    configPath = $claudeSettingsPath
                    pluginRegistryPath = $pluginRegistryPath
                }
            }
            sharedSkills = [ordered]@{
                root = (Join-Path $agentsHome 'skills')
                lockPath = (Join-Path $agentsHome '.skill-lock.json')
            }
            resources = @(
                [ordered]@{
                    id = 'marketplace:ai-skills'
                    provider = 'codex'
                    kind = 'marketplace'
                    ownership = 'managed'
                    desired = [ordered]@{ name = 'ai-skills'; sourcePath = $repo }
                },
                [ordered]@{
                    id = 'plugin:devhome-lifecycle'
                    provider = 'codex'
                    kind = 'plugin'
                    ownership = 'managed'
                    desired = [ordered]@{
                        name = 'devhome-lifecycle@ai-skills'
                        enabled = $true
                        sourceRoot = $pluginSource
                        cacheRoot = $pluginCacheRoot
                        trustRecordKey = 'fixture-trust-record'
                        projectionReasonCode = 'OWNED_PLUGIN_PAYLOAD_MISMATCH'
                    }
                },
                [ordered]@{
                    id = 'hook:codex-lifecycle'
                    provider = 'codex'
                    kind = 'hook'
                    ownership = 'managed'
                    desired = [ordered]@{
                        sourceRoot = $codexHookSource
                        targetRoot = $codexHome
                        projectionReasonCode = 'CODEX_HOOK_PROJECTION_MISMATCH'
                    }
                },
                [ordered]@{
                    id = 'hook:claude-handoff-relay'
                    provider = 'claude'
                    kind = 'hook'
                    ownership = 'managed'
                    desired = [ordered]@{
                        sourceRoot = $claudeHookSource
                        targetRoot = $claudeHome
                        registrationContains = 'hooks/Invoke-HandoffRelay.ps1'
                        projectionReasonCode = 'CLAUDE_HANDOFF_PROJECTION_MISMATCH'
                    }
                },
                [ordered]@{
                    id = 'plugin:remember'
                    provider = 'claude'
                    kind = 'plugin'
                    ownership = 'observed'
                    desired = [ordered]@{ name = 'remember@claude-plugins-official'; enabled = $true }
                },
                [ordered]@{
                    id = 'skill-policy:codex'
                    provider = 'codex'
                    kind = 'skill-policy'
                    ownership = 'observed'
                    desired = [ordered]@{}
                },
                [ordered]@{
                    id = 'skill-policy:claude'
                    provider = 'claude'
                    kind = 'skill-policy'
                    ownership = 'observed'
                    desired = [ordered]@{}
                },
                [ordered]@{
                    id = 'skill-root:shared'
                    provider = 'shared'
                    kind = 'skill-root'
                    ownership = 'observed'
                    desired = [ordered]@{}
                }
            )
            acceptance = @([ordered]@{
                id = 'remember-posttooluse'
                provider = 'claude'
                ownership = 'manual-gate'
                description = 'Fixture Remember capture passes.'
            })
        }
        $lock = [ordered]@{
            schema = 'ai-skills/ai-environment-lock/v1'
            profileId = 'test-machine'
            state = 'accepted'
            capturedAtUtc = '2026-08-22T00:00:00Z'
            source = [ordered]@{
                repository = 'https://example.invalid/fixture.git'
                commit = $head
                requireCleanWorktree = $true
            }
            providers = [ordered]@{
                codex = [ordered]@{ testedVersions = @('9.9.9') }
                claude = [ordered]@{ testedVersions = @('8.8.8') }
            }
            resources = @(
                (New-TestLockResource -Id 'plugin:devhome-lifecycle' -SourceRoot $pluginSource -Paths @('plugin.txt', '.codex-plugin/plugin.json') -Version '1.0.0' -TrustHash 'sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'),
                (New-TestLockResource -Id 'hook:codex-lifecycle' -SourceRoot $codexHookSource -Paths @('hooks.json')),
                (New-TestLockResource -Id 'hook:claude-handoff-relay' -SourceRoot $claudeHookSource -Paths @('hooks/Invoke-HandoffRelay.ps1'))
            )
            acceptance = @([ordered]@{
                id = 'remember-posttooluse'
                status = 'PASS'
                checkedAtUtc = '2026-08-22T00:00:00Z'
                evidence = 'fixture pass'
            })
        }
        Write-TestJson -Path $profilePath -Value $profile
        Write-TestJson -Path $lockPath -Value $lock

        return [pscustomobject]@{
            Root = $root
            Repo = $repo
            CodexHome = $codexHome
            ClaudeHome = $claudeHome
            AgentsHome = $agentsHome
            CodexConfigPath = $codexConfigPath
            ProfilePath = $profilePath
            LockPath = $lockPath
        }
    }
}

Describe 'AI environment module contract' {
    BeforeEach {
        $script:PreviousPath = $env:Path
        Remove-Item Env:AI_ENV_TEST_CODEX_FAIL -ErrorAction SilentlyContinue
        Remove-Item Env:AI_ENV_TEST_CHILD_PID -ErrorAction SilentlyContinue
        Remove-Item Env:AI_ENV_SCHEMA_PROBE -ErrorAction SilentlyContinue
        $script:Fixture = New-AiEnvironmentFixture
        $env:Path = "$($script:Fixture.Root);$($script:PreviousPath)"
    }

    AfterEach {
        $env:Path = $script:PreviousPath
        Remove-Item Env:AI_ENV_TEST_CODEX_FAIL -ErrorAction SilentlyContinue
        Remove-Item Env:AI_ENV_TEST_CHILD_PID -ErrorAction SilentlyContinue
        Remove-Item Env:AI_ENV_SCHEMA_PROBE -ErrorAction SilentlyContinue
    }

    It 'exports the Phase 2 observation, planning, and lock lifecycle interface' {
        $exports = @(Get-Command -Module AiEnvironment | Select-Object -ExpandProperty Name | Sort-Object)
        $exports | Should -Be @(
            'Approve-AiEnvironmentLock',
            'Get-AiEnvironmentState',
            'New-AiEnvironmentPlan',
            'Save-AiEnvironmentState',
            'Test-AiEnvironment',
            'Update-AiEnvironmentLock'
        )
    }

    It 'keeps the checked-in profile and lock valid against their schemas' {
        $profileJson = Get-Content -Raw -LiteralPath (Join-Path $script:ModuleRoot 'profiles\snd-desk.json')
        $lockJson = Get-Content -Raw -LiteralPath (Join-Path $script:ModuleRoot 'locks\snd-desk.lock.json')
        $profileJson | Test-Json -SchemaFile (Join-Path $script:ModuleRoot 'schemas\profile.schema.json') | Should -BeTrue
        $lockJson | Test-Json -SchemaFile (Join-Path $script:ModuleRoot 'schemas\lock.schema.json') | Should -BeTrue
    }

    It 'keeps the checked-in candidate lock backed by raw blobs at its commit' {
        $profile = Get-Content -Raw -LiteralPath (Join-Path $script:ModuleRoot 'profiles\snd-desk.json') | ConvertFrom-Json -Depth 100
        $lock = Get-Content -Raw -LiteralPath (Join-Path $script:ModuleRoot 'locks\snd-desk.lock.json') | ConvertFrom-Json -Depth 100
        $expectedPayloadCount = @($lock.resources | ForEach-Object { @($_.payload).Count } | Measure-Object -Sum).Sum
        $expectedVersionCount = @($lock.resources | Where-Object {
            $lockResource = $_
            $profileResource = @($profile.resources | Where-Object id -eq $lockResource.id)[0]
            [string]$profileResource.kind -eq 'plugin' -or -not [string]::IsNullOrWhiteSpace([string]$lockResource.version)
        }).Count

        $expectedPayloadCount | Should -BeGreaterThan 0
        $expectedVersionCount | Should -BeGreaterThan 0

        # The checked-in profile names this workstation. Prove the lock blobs
        # against the clone under test when that path is somewhere else.
        $recordedRoot = [System.IO.Path]::TrimEndingDirectorySeparator([string]$profile.source.repositoryRoot)
        $checkoutRoot = [System.IO.Path]::TrimEndingDirectorySeparator($script:RepoRoot)
        if (-not [string]::Equals($recordedRoot, $checkoutRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
            $profile.source.repositoryRoot = $checkoutRoot
            foreach ($resource in @($profile.resources)) {
                $sourceRoot = [string]$resource.desired.sourceRoot
                if ([string]::IsNullOrWhiteSpace($sourceRoot)) { continue }
                $normalized = [System.IO.Path]::TrimEndingDirectorySeparator($sourceRoot)
                if (-not $normalized.StartsWith($recordedRoot, [System.StringComparison]::OrdinalIgnoreCase)) { continue }
                $suffix = $normalized.Substring($recordedRoot.Length).TrimStart('\', '/')
                $resource.desired.sourceRoot = if ([string]::IsNullOrWhiteSpace($suffix)) {
                    $checkoutRoot
                }
                else {
                    Join-Path $checkoutRoot $suffix
                }
            }
        }

        $module = Get-Module AiEnvironment
        $observation = & $module {
            param($CandidateProfile, $CandidateLock)
            Get-AiLockCommitPayloadObservation `
                -Profile $CandidateProfile `
                -Lock $CandidateLock `
                -RepositoryRoot ([string]$CandidateProfile.source.repositoryRoot)
        } $profile $lock
        $observation.CommitObjectValid | Should -BeTrue
        $observation.PayloadExpected | Should -Be $expectedPayloadCount
        $observation.PayloadMatched | Should -Be $expectedPayloadCount
        $observation.VersionExpected | Should -Be $expectedVersionCount
        $observation.VersionMatched | Should -Be $expectedVersionCount
        $observation.MappingFailures | Should -Be 0
        $observation.BlobFailures | Should -Be 0
        $observation.Verified | Should -BeTrue
    }

    It 'rejects resource shapes that have no provider adapter in the profile schema' {
        $profile = Get-Content -Raw -LiteralPath $script:Fixture.ProfilePath | ConvertFrom-Json -Depth 100
        $profile.resources += [pscustomobject][ordered]@{
            id = 'plugin:unobserved-shared'
            provider = 'shared'
            kind = 'plugin'
            ownership = 'managed'
            desired = [pscustomobject][ordered]@{}
        }

        ($profile | ConvertTo-Json -Depth 100) |
            Test-Json -SchemaFile (Join-Path $script:ModuleRoot 'schemas\profile.schema.json') -ErrorAction SilentlyContinue |
            Should -BeFalse
        Write-TestJson -Path $script:Fixture.ProfilePath -Value $profile
        { Get-AiEnvironmentState -ProfilePath $script:Fixture.ProfilePath -LockPath $script:Fixture.LockPath } |
            Should -Throw '*failed schema validation*'
    }

    It 'fails closed at runtime when a declared managed resource has no provider adapter' {
        $profile = Get-Content -Raw -LiteralPath $script:Fixture.ProfilePath | ConvertFrom-Json -Depth 100
        $lock = Get-Content -Raw -LiteralPath $script:Fixture.LockPath | ConvertFrom-Json -Depth 100
        $profile.resources += [pscustomobject][ordered]@{
            id = 'plugin:unobserved-shared'
            provider = 'shared'
            kind = 'plugin'
            ownership = 'managed'
            desired = [pscustomobject][ordered]@{}
        }
        $module = Get-Module AiEnvironment

        {
            & $module {
                param($CandidateProfile, $CandidateLock)
                Assert-AiDocumentContracts -Profile $CandidateProfile -Lock $CandidateLock
            } $profile $lock
        } | Should -Throw '*no supported observation adapter*'
    }

    It 'reports CURRENT for a fully accepted deterministic fixture' {
        $state = Get-AiEnvironmentState -ProfilePath $script:Fixture.ProfilePath -LockPath $script:Fixture.LockPath

        $state.Status | Should -BeExactly 'CURRENT'
        $state.ActiveStatuses | Should -Be @('CURRENT')
        $state.PromotionReady | Should -BeTrue
        $state.RepairReady | Should -BeTrue
        @($state.Reasons) | Should -HaveCount 0
        $state.Providers.Codex.ControlPlane.Available | Should -BeTrue
        $state.Providers.Codex.ControlPlane.TimedOut | Should -BeFalse
        $state.Providers.Codex.Plugins[0].TrustHashValidated | Should -BeTrue
        $state.Providers.Claude.Hooks[0].RegistrationPresent | Should -BeTrue
        $state.Providers.Claude.PluginRegistry.Available | Should -BeTrue

        ($state | ConvertTo-Json -Depth 100) |
            Test-Json -SchemaFile (Join-Path $script:ModuleRoot 'schemas\state.schema.json') |
            Should -BeTrue
    }

    It 'observes the external startup hook without a payload lock: <Mutation>' -ForEach @(
        @{ Mutation = 'none'; Expected = $true }
        @{ Mutation = 'missing'; Expected = $false }
        @{ Mutation = 'event'; Expected = $false }
        @{ Mutation = 'matcher'; Expected = $false }
        @{ Mutation = 'command'; Expected = $false }
        @{ Mutation = 'timeout'; Expected = $false }
        @{ Mutation = 'async'; Expected = $false }
        @{ Mutation = 'duplicate'; Expected = $false }
        @{ Mutation = 'disableAllHooks'; Expected = $false }
        @{ Mutation = 'script'; Expected = $false }
    ) {
        $profile = Get-Content -Raw -LiteralPath $script:Fixture.ProfilePath | ConvertFrom-Json -Depth 100
        $settingsPath = Join-Path $script:Fixture.ClaudeHome 'settings.json'
        $settings = Get-Content -Raw -LiteralPath $settingsPath | ConvertFrom-Json -Depth 100
        $scriptPath = Join-Path $script:Fixture.Root 'verify-note.ps1'
        Set-Content -LiteralPath $scriptPath -Value "throw 'The observer must never run this script.'"
        $command = 'pwsh -NoProfile -File "' + $scriptPath + '" -Summary'
        $profile.resources += [pscustomobject]@{
            id = 'hook:claude-handoff-verify'; provider = 'claude'; kind = 'hook'; ownership = 'observed'
            desired = [pscustomobject]@{
                event = 'SessionStart'; matcher = 'startup|resume|clear'
                command = $command; scriptPath = $scriptPath; timeout = 10
            }
        }
        $handler = [pscustomobject]@{ type = 'command'; command = $command; timeout = 10 }
        $registration = [pscustomobject]@{ matcher = 'startup|resume|clear'; hooks = @($handler) }
        $settings.hooks | Add-Member -NotePropertyName SessionStart -NotePropertyValue @($registration)
        switch ($Mutation) {
            'missing' { $settings.PSObject.Properties.Remove('hooks') }
            'event' { $settings.hooks.PSObject.Properties.Remove('SessionStart'); $settings.hooks.Stop += $registration }
            'matcher' { $registration.matcher = 'compact' }
            'command' { $handler.command += ' -Unexpected' }
            'timeout' { $handler.timeout = 1 }
            'async' { $handler | Add-Member -NotePropertyName async -NotePropertyValue $true }
            'duplicate' { $settings.hooks.SessionStart += $registration }
            'disableAllHooks' { $settings | Add-Member -NotePropertyName disableAllHooks -NotePropertyValue $true }
            'script' { Remove-Item -LiteralPath $scriptPath }
        }
        Write-TestJson -Path $script:Fixture.ProfilePath -Value $profile
        Write-TestJson -Path $settingsPath -Value $settings
        $settingsDigest = (Get-FileHash -LiteralPath $settingsPath).Hash
        $state = Get-AiEnvironmentState -ProfilePath $script:Fixture.ProfilePath -LockPath $script:Fixture.LockPath
        $hook = @($state.Providers.Claude.Hooks | Where-Object Id -eq 'hook:claude-handoff-verify')[0]
        $hook.RegistrationPresent | Should -Be $Expected
        $hook.Payload | Should -BeNullOrEmpty
        @($state.Reasons | Where-Object { $_.ResourceId -eq $hook.Id -and $_.Code -eq 'CLAUDE_STARTUP_HOOK_DRIFT' }).Count |
            Should -Be $(if ($Expected) { 0 } else { 1 })
        @($state.Reasons | Where-Object Code -eq 'RESOURCE_LOCK_MISSING') | Should -HaveCount 0
        (Get-FileHash -LiteralPath $settingsPath).Hash | Should -BeExactly $settingsDigest
    }

    It 'derives the managed Codex plugin cache target from lock version without profile edits' {
        $profile = Get-Content -Raw -LiteralPath $script:Fixture.ProfilePath | ConvertFrom-Json -Depth 100
        $lock = Get-Content -Raw -LiteralPath $script:Fixture.LockPath | ConvertFrom-Json -Depth 100
        $profileResource = @($profile.resources | Where-Object id -eq 'plugin:devhome-lifecycle')[0]
        $lockResource = @($lock.resources | Where-Object id -eq 'plugin:devhome-lifecycle')[0]
        $sourceRoot = [string]$profileResource.desired.sourceRoot
        $cacheRoot = [string]$profileResource.desired.cacheRoot
        $manifestPath = Join-Path $sourceRoot '.codex-plugin\plugin.json'
        $manifest = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json -Depth 20
        $manifest.version = '0.3.0'
        Write-TestJson -Path $manifestPath -Value $manifest

        $lockResource.version = '0.3.0'
        $versionTarget = Join-Path $cacheRoot $lockResource.version
        foreach ($entry in @($lockResource.payload)) {
            Copy-TestFile -SourceRoot $sourceRoot -TargetRoot $versionTarget -RelativePath ([string]$entry.path)
            $entry.sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $sourceRoot ([string]$entry.path -replace '/', '\'))).Hash
        }
        git -C $script:Fixture.Repo add --all
        git -C $script:Fixture.Repo commit --quiet -m 'fixture plugin 0.3.0'
        if ($LASTEXITCODE -ne 0) { throw 'Failed to commit versioned plugin fixture.' }
        $lock.source.commit = (git -C $script:Fixture.Repo rev-parse HEAD).Trim()
        Write-TestJson -Path $script:Fixture.LockPath -Value $lock

        $state = Get-AiEnvironmentState -ProfilePath $script:Fixture.ProfilePath -LockPath $script:Fixture.LockPath

        $state.Status | Should -BeExactly 'CURRENT'
        $state.Providers.Codex.Plugins[0].Payload.TargetMatched | Should -Be 2
        $state.Reasons.Code | Should -Not -Contain 'OWNED_PLUGIN_PAYLOAD_MISMATCH'
        Test-Path -LiteralPath (Join-Path $cacheRoot '1.0.0\plugin.txt') | Should -BeTrue
    }

    It 'fails closed when the managed Codex plugin lock version is missing or unsafe' -ForEach @(
        @{ Case = 'missing'; Version = $null },
        @{ Case = 'unsafe'; Version = '..\escape' }
    ) {
        $lock = Get-Content -Raw -LiteralPath $script:Fixture.LockPath | ConvertFrom-Json -Depth 100
        $lockResource = @($lock.resources | Where-Object id -eq 'plugin:devhome-lifecycle')[0]
        if ($null -eq $Version) {
            $lockResource.PSObject.Properties.Remove('version')
        }
        else {
            $lockResource.version = $Version
        }
        Write-TestJson -Path $script:Fixture.LockPath -Value $lock

        $state = Get-AiEnvironmentState -ProfilePath $script:Fixture.ProfilePath -LockPath $script:Fixture.LockPath
        $payloadCheck = $state.Checks | Where-Object Id -eq 'resource.plugin:devhome-lifecycle.payload'

        $state.Reasons.Code | Should -Contain 'RESOURCE_LOCK_MISSING'
        $payloadCheck.Result | Should -BeExactly 'FAIL'
        $payloadCheck.ReasonCode | Should -BeExactly 'RESOURCE_LOCK_MISSING'
        $state.PromotionReady | Should -BeFalse
        $state.RepairReady | Should -BeFalse
    }

    It 'isolates a broken foreign marketplace while preserving owned observations' {
        $profile = Get-Content -Raw -LiteralPath $script:Fixture.ProfilePath | ConvertFrom-Json -Depth 100
        $profile.resources += [pscustomobject][ordered]@{
            id = 'marketplace:wt-local'
            provider = 'codex'
            kind = 'marketplace'
            ownership = 'observed'
            desired = [pscustomobject][ordered]@{ name = 'wt-local' }
        }
        Write-TestJson -Path $script:Fixture.ProfilePath -Value $profile
        $invalidMarketplace = Join-Path $script:Fixture.Root 'invalid-marketplace'
        $null = New-Item -ItemType Directory -Path $invalidMarketplace -Force
        Add-Content -LiteralPath $script:Fixture.CodexConfigPath -Encoding utf8NoBOM -Value @"

[marketplaces.wt-local]
source_type = 'local'
source = '$invalidMarketplace'
"@
        @'
@echo off
if "%~1"=="--version" (
  echo codex-cli 9.9.9
  exit /b 0
)
if "%~1"=="plugin" if "%~2"=="marketplace" if "%~3"=="list" exit /b 17
exit /b 64
'@ | Set-Content -LiteralPath (Join-Path $script:Fixture.Root 'codex.cmd') -Encoding ascii

        $state = Get-AiEnvironmentState -ProfilePath $script:Fixture.ProfilePath -LockPath $script:Fixture.LockPath

        $state.Status | Should -BeExactly 'DEGRADED_FOREIGN_MARKETPLACE'
        $state.Reasons.Code | Should -Contain 'FOREIGN_MARKETPLACE_MANIFEST_INVALID'
        $state.Reasons.Code | Should -Contain 'CODEX_CONTROL_PLANE_UNAVAILABLE'
        $state.Providers.Codex.Plugins[0].Payload.TargetMatched | Should -Be 2
        $state.Providers.Claude.Hooks[0].RegistrationPresent | Should -BeTrue

        $plan = $state | New-AiEnvironmentPlan
        ($plan.Actions | Where-Object Id -eq 'action:foreign-marketplace-manifest-invalid:marketplace:wt-local').Type |
            Should -BeExactly 'REVIEW_FOREIGN_OWNER'
        ($plan.Actions | Where-Object Id -eq 'action:codex-control-plane-unavailable:provider:codex').Type |
            Should -BeExactly 'REVIEW_FOREIGN_OWNER'
    }

    It 'routes a missing foreign marketplace root to owner review' {
        $profile = Get-Content -Raw -LiteralPath $script:Fixture.ProfilePath | ConvertFrom-Json -Depth 100
        $profile.resources += [pscustomobject][ordered]@{
            id = 'marketplace:wt-local'
            provider = 'codex'
            kind = 'marketplace'
            ownership = 'observed'
            desired = [pscustomobject][ordered]@{ name = 'wt-local' }
        }
        Write-TestJson -Path $script:Fixture.ProfilePath -Value $profile
        $missingMarketplace = Join-Path $script:Fixture.Root 'missing-marketplace'
        Add-Content -LiteralPath $script:Fixture.CodexConfigPath -Encoding utf8NoBOM -Value @"

[marketplaces.wt-local]
source_type = 'local'
source = '$missingMarketplace'
"@

        $state = Get-AiEnvironmentState -ProfilePath $script:Fixture.ProfilePath -LockPath $script:Fixture.LockPath
        $plan = $state | New-AiEnvironmentPlan

        $state.Status | Should -BeExactly 'DEGRADED_FOREIGN_MARKETPLACE'
        $state.Reasons.Code | Should -Contain 'FOREIGN_MARKETPLACE_ROOT_MISSING'
        ($plan.Actions | Where-Object Id -eq 'action:foreign-marketplace-root-missing:marketplace:wt-local').Type |
            Should -BeExactly 'REVIEW_FOREIGN_OWNER'
    }

    It 'reports a declared observed marketplace that is absent from the Codex config' {
        $profile = Get-Content -Raw -LiteralPath $script:Fixture.ProfilePath | ConvertFrom-Json -Depth 100
        $profile.resources += [pscustomobject][ordered]@{
            id = 'marketplace:wt-local'
            provider = 'codex'
            kind = 'marketplace'
            ownership = 'observed'
            desired = [pscustomobject][ordered]@{ name = 'wt-local' }
        }
        Write-TestJson -Path $script:Fixture.ProfilePath -Value $profile

        $state = Get-AiEnvironmentState -ProfilePath $script:Fixture.ProfilePath -LockPath $script:Fixture.LockPath
        $plan = $state | New-AiEnvironmentPlan
        $registrationCheck = $state.Checks | Where-Object Id -eq 'resource.marketplace:wt-local.registration'

        $state.Status | Should -BeExactly 'DEGRADED_FOREIGN_MARKETPLACE'
        $state.Reasons.Code | Should -Contain 'FOREIGN_MARKETPLACE_NOT_CONFIGURED'
        $registrationCheck.Result | Should -BeExactly 'DEGRADED'
        $registrationCheck.ReasonCode | Should -BeExactly 'FOREIGN_MARKETPLACE_NOT_CONFIGURED'
        $registrationCheck.Evidence | Should -Match 'configured=False'
        $registrationCheck.Evidence | Should -Match 'inspected=False'
        ($plan.Actions | Where-Object Id -eq 'action:foreign-marketplace-not-configured:marketplace:wt-local').Type |
            Should -BeExactly 'REVIEW_FOREIGN_OWNER'
    }

    It 'does not assert source health for an observed marketplace it cannot inspect' {
        $profile = Get-Content -Raw -LiteralPath $script:Fixture.ProfilePath | ConvertFrom-Json -Depth 100
        $profile.resources += [pscustomobject][ordered]@{
            id = 'marketplace:wt-local'
            provider = 'codex'
            kind = 'marketplace'
            ownership = 'observed'
            desired = [pscustomobject][ordered]@{ name = 'wt-local' }
        }
        Write-TestJson -Path $script:Fixture.ProfilePath -Value $profile
        Add-Content -LiteralPath $script:Fixture.CodexConfigPath -Encoding utf8NoBOM -Value @"

[marketplaces.wt-local]
source_type = 'git'
source = 'https://example.invalid/wt-local.git'
"@

        $state = Get-AiEnvironmentState -ProfilePath $script:Fixture.ProfilePath -LockPath $script:Fixture.LockPath
        $registrationCheck = $state.Checks | Where-Object Id -eq 'resource.marketplace:wt-local.registration'

        $state.Status | Should -BeExactly 'CURRENT'
        @($state.Reasons) | Should -HaveCount 0
        $registrationCheck.Result | Should -BeExactly 'UNKNOWN'
        $registrationCheck.ReasonCode | Should -BeExactly 'FOREIGN_MARKETPLACE_SOURCE_UNINSPECTED'
        $registrationCheck.Evidence | Should -Match 'sourceType=git'
        $registrationCheck.Evidence | Should -Match 'inspected=False'
        $registrationCheck.Evidence | Should -Not -Match 'sourceExists='
    }

    It 'reads single-quoted Codex plugin table headers' {
        (Get-Content -Raw -LiteralPath $script:Fixture.CodexConfigPath).Replace(
            '[plugins."devhome-lifecycle@ai-skills"]',
            "[plugins.'devhome-lifecycle@ai-skills']"
        ) | Set-Content -LiteralPath $script:Fixture.CodexConfigPath -Encoding utf8NoBOM

        $state = Get-AiEnvironmentState -ProfilePath $script:Fixture.ProfilePath -LockPath $script:Fixture.LockPath

        $state.Status | Should -BeExactly 'CURRENT'
        $state.Providers.Codex.Plugins[0].Configured | Should -BeTrue
        $state.Providers.Codex.Plugins[0].Enabled | Should -BeTrue
    }

    It 'fails closed when a managed marketplace registration is incomplete' {
        (Get-Content -Raw -LiteralPath $script:Fixture.CodexConfigPath).Replace(
            "source_type = 'local'",
            '# source type intentionally absent'
        ) | Set-Content -LiteralPath $script:Fixture.CodexConfigPath -Encoding utf8NoBOM

        $state = Get-AiEnvironmentState -ProfilePath $script:Fixture.ProfilePath -LockPath $script:Fixture.LockPath
        $plan = $state | New-AiEnvironmentPlan
        $registrationCheck = $state.Checks | Where-Object Id -eq 'resource.marketplace:ai-skills.registration'

        $state.Status | Should -BeExactly 'DRIFTED'
        $state.Reasons.Code | Should -Contain 'OWNED_MARKETPLACE_MISSING'
        $registrationCheck.Result | Should -BeExactly 'FAIL'
        ($plan.Actions | Where-Object Id -eq 'action:owned-marketplace-missing:marketplace:ai-skills').Type |
            Should -BeExactly 'RECONCILE_FROM_ACCEPTED_LOCK'
    }

    It 'parses TOML inline comments without turning false into true' {
        (Get-Content -Raw -LiteralPath $script:Fixture.CodexConfigPath).Replace(
            'enabled = true',
            'enabled = false # disabled by fixture'
        ) | Set-Content -LiteralPath $script:Fixture.CodexConfigPath -Encoding utf8NoBOM

        $state = Get-AiEnvironmentState -ProfilePath $script:Fixture.ProfilePath -LockPath $script:Fixture.LockPath
        $plan = $state | New-AiEnvironmentPlan

        $state.Status | Should -BeExactly 'DRIFTED'
        $state.Providers.Codex.Plugins[0].Enabled | Should -BeFalse
        $state.Reasons.Code | Should -Contain 'OWNED_PLUGIN_DISABLED'
        ($plan.Actions | Where-Object Id -eq 'action:owned-plugin-disabled:plugin:devhome-lifecycle').Type |
            Should -BeExactly 'RECONCILE_FROM_ACCEPTED_LOCK'
    }

    It 'fails closed when the Claude plugin registry is unavailable' {
        $profile = Get-Content -Raw -LiteralPath $script:Fixture.ProfilePath | ConvertFrom-Json -Depth 100
        Remove-Item -LiteralPath ([string]$profile.providers.claude.pluginRegistryPath)

        $state = Get-AiEnvironmentState -ProfilePath $script:Fixture.ProfilePath -LockPath $script:Fixture.LockPath
        $plan = $state | New-AiEnvironmentPlan
        $registryCheck = $state.Checks | Where-Object Id -eq 'provider.claude.plugin-registry'

        $state.Status | Should -BeExactly 'DRIFTED'
        $state.Providers.Claude.PluginRegistry.Available | Should -BeFalse
        $state.Reasons.Code | Should -Contain 'CLAUDE_PLUGIN_REGISTRY_UNAVAILABLE'
        $registryCheck.Result | Should -BeExactly 'FAIL'
        ($plan.Actions | Where-Object Id -eq 'action:claude-plugin-registry-unavailable:plugin-registry:claude').Type |
            Should -BeExactly 'REVIEW_OBSERVED_DRIFT'
    }

    It 'correlates declared Claude plugins with registry records' {
        $profile = Get-Content -Raw -LiteralPath $script:Fixture.ProfilePath | ConvertFrom-Json -Depth 100
        Write-TestJson -Path ([string]$profile.providers.claude.pluginRegistryPath) -Value ([ordered]@{
            version = 2
            plugins = [ordered]@{}
        })

        $state = Get-AiEnvironmentState -ProfilePath $script:Fixture.ProfilePath -LockPath $script:Fixture.LockPath
        $plan = $state | New-AiEnvironmentPlan
        $missingRecordActions = @($plan.Actions | Where-Object Id -like 'action:claude-plugin-record-missing:*')

        $state.Status | Should -BeExactly 'DRIFTED'
        $state.Providers.Claude.PluginRegistry.Available | Should -BeTrue
        $state.Providers.Claude.PluginRegistry.MissingDeclaredPluginRecords | Should -Be 1
        @($state.Reasons | Where-Object Code -eq 'CLAUDE_PLUGIN_RECORD_MISSING') | Should -HaveCount 2
        $missingRecordActions | Should -HaveCount 2
        @($missingRecordActions.Type | Select-Object -Unique) | Should -Be @('REVIEW_OBSERVED_DRIFT')
    }

    It 'observes empty Claude enabledPlugins and empty shared skill lock maps under strict mode' {
        $claudeSettingsPath = Join-Path $script:Fixture.ClaudeHome 'settings.json'
        $settings = Get-Content -Raw -LiteralPath $claudeSettingsPath | ConvertFrom-Json -Depth 100
        $settings.enabledPlugins = [ordered]@{}
        Write-TestJson -Path $claudeSettingsPath -Value $settings

        Write-TestJson -Path (Join-Path $script:Fixture.AgentsHome '.skill-lock.json') -Value ([ordered]@{
            version = 3
            skills = [ordered]@{}
            dismissed = [ordered]@{}
        })

        $state = Get-AiEnvironmentState -ProfilePath $script:Fixture.ProfilePath -LockPath $script:Fixture.LockPath -ErrorAction Stop
        $stateSchema = Join-Path $script:ModuleRoot 'schemas\state.schema.json'

        ($state | ConvertTo-Json -Depth 100) | Test-Json -SchemaFile $stateSchema | Should -BeTrue
        $state.Status | Should -BeExactly 'DRIFTED'
        $state.Providers.Claude.PluginRegistry.DeclaredPlugins | Should -Be 0
        $state.Providers.Claude.Plugins[0].Configured | Should -BeFalse
        $state.SharedSkills.RecordedCount | Should -Be 0
        $state.SharedSkills.MissingRecordedPathCount | Should -Be 0
        $state.SharedSkills.UnrecordedCount | Should -Be 1
        $state.SharedSkills.Complete | Should -BeFalse
        $state.Reasons.Code | Should -Contain 'CLAUDE_PLUGIN_DISABLED'
        $state.Reasons.Code | Should -Contain 'SHARED_SKILL_LOCK_INCOMPLETE'
    }

    It 'bounds a hung provider command and preserves the static fallback' {
        $pidFile = Join-Path $script:Fixture.Root 'hung-provider-child.pid'
        $env:AI_ENV_TEST_CHILD_PID = $pidFile
        @'
@echo off
if "%~1"=="--version" (
  echo codex-cli 9.9.9
  exit /b 0
)
if "%~1"=="plugin" if "%~2"=="marketplace" if "%~3"=="list" (
  python -B -c "import os, time; open(os.environ['AI_ENV_TEST_CHILD_PID'], 'w', encoding='ascii').write(str(os.getpid())); time.sleep(30)"
  exit /b 17
)
exit /b 64
'@ | Set-Content -LiteralPath (Join-Path $script:Fixture.Root 'codex.cmd') -Encoding ascii

        $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
        $state = Get-AiEnvironmentState -ProfilePath $script:Fixture.ProfilePath -LockPath $script:Fixture.LockPath
        $stopwatch.Stop()

        $stopwatch.Elapsed.TotalSeconds | Should -BeLessThan 12
        $state.Status | Should -BeExactly 'DEGRADED_FOREIGN_MARKETPLACE'
        $state.Providers.Codex.ControlPlane.Available | Should -BeFalse
        $state.Providers.Codex.ControlPlane.TimedOut | Should -BeTrue
        $state.Providers.Codex.ControlPlane.ObservationMode | Should -BeExactly 'static-owned-state-fallback'
        $state.Providers.Codex.Plugins[0].Payload.TargetMatched | Should -Be 2
        $state.Reasons.Code | Should -Contain 'CODEX_CONTROL_PLANE_UNAVAILABLE'
        Test-Path -LiteralPath $pidFile -PathType Leaf | Should -BeTrue
        Start-Sleep -Milliseconds 200
        $childPid = [int](Get-Content -Raw -LiteralPath $pidFile)
        @(Get-Process -Id $childPid -ErrorAction SilentlyContinue) | Should -HaveCount 0
    }

    It 'marks an unseen provider version as untested' {
        $lock = Get-Content -Raw -LiteralPath $script:Fixture.LockPath | ConvertFrom-Json -Depth 100
        $lock.providers.codex.testedVersions = @('9.9.8')
        Write-TestJson -Path $script:Fixture.LockPath -Value $lock

        $state = Get-AiEnvironmentState -ProfilePath $script:Fixture.ProfilePath -LockPath $script:Fixture.LockPath

        $state.Status | Should -BeExactly 'UNTESTED_PROVIDER_VERSION'
        $state.Reasons.Code | Should -Contain 'PROVIDER_VERSION_NOT_IN_LOCK'
    }

    It 'keeps hook trust as an explicit manual gate' {
        (Get-Content -Raw -LiteralPath $script:Fixture.CodexConfigPath).Replace(
            'trusted_hash = "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"',
            '# trust intentionally absent'
        ) | Set-Content -LiteralPath $script:Fixture.CodexConfigPath -Encoding utf8NoBOM

        $state = Get-AiEnvironmentState -ProfilePath $script:Fixture.ProfilePath -LockPath $script:Fixture.LockPath

        $state.Status | Should -BeExactly 'PENDING_TRUST'
        $state.Reasons.Code | Should -Contain 'OWNED_HOOK_TRUST_RECORD_MISSING'
        ($state | New-AiEnvironmentPlan).Actions.Type | Should -Contain 'MANUAL_TRUST_REVIEW'
    }

    It 'fails closed when the expected hook trust hash is not locked' {
        $lock = Get-Content -Raw -LiteralPath $script:Fixture.LockPath | ConvertFrom-Json -Depth 100
        $lock.resources[0].PSObject.Properties.Remove('trustHash')
        Write-TestJson -Path $script:Fixture.LockPath -Value $lock

        $state = Get-AiEnvironmentState -ProfilePath $script:Fixture.ProfilePath -LockPath $script:Fixture.LockPath
        $plan = $state | New-AiEnvironmentPlan

        $state.Status | Should -BeExactly 'PENDING_TRUST'
        $state.Providers.Codex.Plugins[0].TrustHashValidated | Should -BeFalse
        $state.Reasons.Code | Should -Contain 'OWNED_HOOK_TRUST_HASH_NOT_LOCKED'
        ($plan.Actions | Where-Object Id -eq 'action:owned-hook-trust-hash-not-locked:plugin:devhome-lifecycle').Type |
            Should -BeExactly 'MANUAL_TRUST_REVIEW'
    }

    It 'fails closed when the persisted and locked hook trust hashes differ' {
        (Get-Content -Raw -LiteralPath $script:Fixture.CodexConfigPath).Replace(
            'sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
            'sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
        ) | Set-Content -LiteralPath $script:Fixture.CodexConfigPath -Encoding utf8NoBOM

        $state = Get-AiEnvironmentState -ProfilePath $script:Fixture.ProfilePath -LockPath $script:Fixture.LockPath
        $plan = $state | New-AiEnvironmentPlan

        $state.Status | Should -BeExactly 'PENDING_TRUST'
        $state.Providers.Codex.Plugins[0].TrustHashValidated | Should -BeFalse
        $state.Reasons.Code | Should -Contain 'OWNED_HOOK_TRUST_HASH_MISMATCH'
        ($plan.Actions | Where-Object Id -eq 'action:owned-hook-trust-hash-mismatch:plugin:devhome-lifecycle').Type |
            Should -BeExactly 'MANUAL_TRUST_REVIEW'
    }

    It 'keeps reason precedence and plan action ordering deterministic' {
        $profile = Get-Content -Raw -LiteralPath $script:Fixture.ProfilePath | ConvertFrom-Json -Depth 100
        $profile.resources += [pscustomobject][ordered]@{
            id = 'marketplace:wt-local'
            provider = 'codex'
            kind = 'marketplace'
            ownership = 'observed'
            desired = [pscustomobject][ordered]@{ name = 'wt-local' }
        }
        Write-TestJson -Path $script:Fixture.ProfilePath -Value $profile

        $invalidMarketplace = Join-Path $script:Fixture.Root 'invalid-marketplace'
        $null = New-Item -ItemType Directory -Path $invalidMarketplace -Force
        Add-Content -LiteralPath $script:Fixture.CodexConfigPath -Encoding utf8NoBOM -Value @"

[marketplaces.wt-local]
source_type = 'local'
source = '$invalidMarketplace'
"@
        (Get-Content -Raw -LiteralPath $script:Fixture.CodexConfigPath).Replace(
            'enabled = true',
            'enabled = false # disabled by deterministic fixture'
        ) | Set-Content -LiteralPath $script:Fixture.CodexConfigPath -Encoding utf8NoBOM
        @'
@echo off
if "%~1"=="--version" (
  echo codex-cli 9.9.9
  exit /b 0
)
if "%~1"=="plugin" if "%~2"=="marketplace" if "%~3"=="list" exit /b 17
exit /b 64
'@ | Set-Content -LiteralPath (Join-Path $script:Fixture.Root 'codex.cmd') -Encoding ascii

        $lock = Get-Content -Raw -LiteralPath $script:Fixture.LockPath | ConvertFrom-Json -Depth 100
        $lock.acceptance[0].status = 'FAIL'
        $lock.acceptance[0].evidence = 'deterministic failure'
        Write-TestJson -Path $script:Fixture.LockPath -Value $lock

        $state = Get-AiEnvironmentState -ProfilePath $script:Fixture.ProfilePath -LockPath $script:Fixture.LockPath
        $firstPlan = $state | New-AiEnvironmentPlan
        $secondPlan = $state | New-AiEnvironmentPlan

        $state.Status | Should -BeExactly 'ACCEPTANCE_FAILED'
        @($state.Reasons.Code) | Should -Be @(
            'REMEMBER_ACCEPTANCE_FAILED',
            'OWNED_PLUGIN_DISABLED',
            'FOREIGN_MARKETPLACE_MANIFEST_INVALID',
            'CODEX_CONTROL_PLANE_UNAVAILABLE'
        )
        @($firstPlan.Actions | ForEach-Object { "$($_.Id)|$($_.Type)" }) | Should -Be @(
            'action:codex-control-plane-unavailable:provider:codex|REVIEW_FOREIGN_OWNER',
            'action:foreign-marketplace-manifest-invalid:marketplace:wt-local|REVIEW_FOREIGN_OWNER',
            'action:owned-plugin-disabled:plugin:devhome-lifecycle|RECONCILE_FROM_ACCEPTED_LOCK',
            'action:remember-acceptance-failed:acceptance:remember-posttooluse|RUN_ACCEPTANCE_GATE'
        )
        ($firstPlan | ConvertTo-Json -Depth 20 -Compress) |
            Should -BeExactly ($secondPlan | ConvertTo-Json -Depth 20 -Compress)
    }

    It 'does not hide a failed behavioral acceptance gate' {
        $lock = Get-Content -Raw -LiteralPath $script:Fixture.LockPath | ConvertFrom-Json -Depth 100
        $lock.acceptance[0].status = 'FAIL'
        $lock.acceptance[0].evidence = 'synthetic timeout'
        Write-TestJson -Path $script:Fixture.LockPath -Value $lock

        $state = Get-AiEnvironmentState -ProfilePath $script:Fixture.ProfilePath -LockPath $script:Fixture.LockPath

        $state.Status | Should -BeExactly 'ACCEPTANCE_FAILED'
        $state.Reasons.Code | Should -Contain 'REMEMBER_ACCEPTANCE_FAILED'
        $state.PromotionReady | Should -BeFalse
    }

    It 'reports unaccepted source changes without staging or repairing them' {
        Set-Content -LiteralPath (Join-Path $script:Fixture.Repo 'local-only.txt') -Value 'dirty' -Encoding utf8NoBOM

        $state = Get-AiEnvironmentState -ProfilePath $script:Fixture.ProfilePath -LockPath $script:Fixture.LockPath

        $state.Status | Should -BeExactly 'SOURCE_UNTRUSTED'
        $state.Source.WorktreeClean | Should -BeFalse
        $state.Source.Reproducible | Should -BeFalse
        $state.RepairReady | Should -BeFalse
        $state.Reasons.Code | Should -Contain 'SOURCE_WORKTREE_DIRTY'
        @(git -C $script:Fixture.Repo diff --cached --name-only) | Should -HaveCount 0
    }

    It 'rejects a dirty lock hash that is absent from the locked commit' {
        $profile = Get-Content -Raw -LiteralPath $script:Fixture.ProfilePath | ConvertFrom-Json -Depth 100
        $lock = Get-Content -Raw -LiteralPath $script:Fixture.LockPath | ConvertFrom-Json -Depth 100
        $sourcePath = Join-Path ([string]$profile.resources[1].desired.sourceRoot) 'plugin.txt'
        $lockResource = @($lock.resources | Where-Object id -eq 'plugin:devhome-lifecycle')[0]
        $targetRoot = Join-Path ([string]$profile.resources[1].desired.cacheRoot) ([string]$lockResource.version)
        $targetPath = Join-Path $targetRoot 'plugin.txt'
        Set-Content -LiteralPath $sourcePath -Value 'dirty payload B' -Encoding utf8NoBOM
        Copy-Item -LiteralPath $sourcePath -Destination $targetPath -Force
        $lock.resources[0].payload[0].sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $sourcePath).Hash
        Write-TestJson -Path $script:Fixture.LockPath -Value $lock

        $state = Get-AiEnvironmentState -ProfilePath $script:Fixture.ProfilePath -LockPath $script:Fixture.LockPath

        $state.Reasons.Code | Should -Contain 'LOCK_COMMIT_PAYLOAD_MISMATCH'
        ($state.Checks | Where-Object Id -eq 'source.lock-commit-payload').Result | Should -BeExactly 'FAIL'
        $state.Reasons.Code | Should -Not -Contain 'LOCK_PAYLOAD_MISMATCH'
        $state.PromotionReady | Should -BeFalse
        $state.RepairReady | Should -BeFalse
    }

    It 'rejects a lock payload path that is only untracked' {
        $profile = Get-Content -Raw -LiteralPath $script:Fixture.ProfilePath | ConvertFrom-Json -Depth 100
        $lock = Get-Content -Raw -LiteralPath $script:Fixture.LockPath | ConvertFrom-Json -Depth 100
        $sourcePath = Join-Path ([string]$profile.resources[1].desired.sourceRoot) 'untracked.txt'
        $lockResource = @($lock.resources | Where-Object id -eq 'plugin:devhome-lifecycle')[0]
        $targetRoot = Join-Path ([string]$profile.resources[1].desired.cacheRoot) ([string]$lockResource.version)
        $targetPath = Join-Path $targetRoot 'untracked.txt'
        Set-Content -LiteralPath $sourcePath -Value 'untracked locked payload' -Encoding utf8NoBOM
        Copy-Item -LiteralPath $sourcePath -Destination $targetPath -Force
        $lock.resources[0].payload += [pscustomobject][ordered]@{
            path = 'untracked.txt'
            sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $sourcePath).Hash
        }
        Write-TestJson -Path $script:Fixture.LockPath -Value $lock

        $state = Get-AiEnvironmentState -ProfilePath $script:Fixture.ProfilePath -LockPath $script:Fixture.LockPath

        $state.Reasons.Code | Should -Contain 'LOCK_COMMIT_PAYLOAD_MISMATCH'
        ($state.Checks | Where-Object Id -eq 'source.lock-commit-payload').Result | Should -BeExactly 'FAIL'
        $state.PromotionReady | Should -BeFalse
        $state.RepairReady | Should -BeFalse
    }

    It 'rejects a non-commit Git object in the lock commit field' {
        $lock = Get-Content -Raw -LiteralPath $script:Fixture.LockPath | ConvertFrom-Json -Depth 100
        $lock.source.commit = (git -C $script:Fixture.Repo rev-parse 'HEAD^{tree}').Trim()
        Write-TestJson -Path $script:Fixture.LockPath -Value $lock

        $state = Get-AiEnvironmentState -ProfilePath $script:Fixture.ProfilePath -LockPath $script:Fixture.LockPath

        $state.Reasons.Code | Should -Contain 'LOCK_COMMIT_PAYLOAD_MISMATCH'
        ($state.Checks | Where-Object Id -eq 'source.lock-commit-payload').Result | Should -BeExactly 'FAIL'
        $state.Source.Reproducible | Should -BeFalse
        $state.PromotionReady | Should -BeFalse
        $state.RepairReady | Should -BeFalse
    }

    It 'does not reconcile an accepted managed resource missing from the lock' {
        $lock = Get-Content -Raw -LiteralPath $script:Fixture.LockPath | ConvertFrom-Json -Depth 100
        $lock.resources = @($lock.resources | Where-Object id -ne 'hook:codex-lifecycle')
        Write-TestJson -Path $script:Fixture.LockPath -Value $lock

        $state = Get-AiEnvironmentState -ProfilePath $script:Fixture.ProfilePath -LockPath $script:Fixture.LockPath
        $plan = $state | New-AiEnvironmentPlan

        $state.Reasons.Code | Should -Contain 'RESOURCE_LOCK_MISSING'
        $state.RepairReady | Should -BeFalse
        ($plan.Actions | Where-Object Id -eq 'action:resource-lock-missing:hook:codex-lifecycle').Type |
            Should -BeExactly 'BLOCK_PROMOTION'
    }

    It 'fails closed when bounded Git observation cannot complete' {
        @'
@echo off
exit /b 17
'@ | Set-Content -LiteralPath (Join-Path $script:Fixture.Root 'git.cmd') -Encoding ascii

        $state = Get-AiEnvironmentState -ProfilePath $script:Fixture.ProfilePath -LockPath $script:Fixture.LockPath
        $plan = $state | New-AiEnvironmentPlan

        $state.Status | Should -BeExactly 'SOURCE_UNTRUSTED'
        $state.Source.WorktreeClean | Should -BeFalse
        $state.Source.Reproducible | Should -BeFalse
        $state.Reasons.Code | Should -Contain 'SOURCE_GIT_OBSERVATION_FAILED'
        ($state.Checks | Where-Object Id -eq 'source.git-observation').Result | Should -BeExactly 'FAIL'
        ($plan.Actions | Where-Object Id -eq 'action:source-git-observation-failed:source:ai-skills').Type |
            Should -BeExactly 'BLOCK_PROMOTION'
    }

    It 'keeps Get, Plan, and Test read-only toward all observed roots' {
        Set-Content -LiteralPath (Join-Path $script:Fixture.Repo 'local-only.txt') -Value 'dirty' -Encoding utf8NoBOM
        $roots = @($script:Fixture.CodexHome, $script:Fixture.ClaudeHome, $script:Fixture.AgentsHome)
        $before = Get-TestSurfaceDigest $roots

        $state = Get-AiEnvironmentState -ProfilePath $script:Fixture.ProfilePath -LockPath $script:Fixture.LockPath
        $plan = $state | New-AiEnvironmentPlan
        $verification = $state | Test-AiEnvironment
        $after = Get-TestSurfaceDigest $roots

        $after | Should -BeExactly $before
        $plan.ReadOnly | Should -BeTrue
        $plan.CanApply | Should -BeFalse
        $plan.Actions.Type | Should -Contain 'BLOCK_PROMOTION'
        $verification.Passed | Should -BeFalse
    }

    It 'rejects empty and duplicate lock payloads' {
        $lockSchema = Join-Path $script:ModuleRoot 'schemas\lock.schema.json'
        $lock = Get-Content -Raw -LiteralPath $script:Fixture.LockPath | ConvertFrom-Json -Depth 100
        $lock.resources[0].payload = @()
        ($lock | ConvertTo-Json -Depth 100) | Test-Json -SchemaFile $lockSchema -ErrorAction SilentlyContinue | Should -BeFalse
        Write-TestJson -Path $script:Fixture.LockPath -Value $lock
        { Get-AiEnvironmentState -ProfilePath $script:Fixture.ProfilePath -LockPath $script:Fixture.LockPath } |
            Should -Throw '*failed schema validation*'

        $script:Fixture = New-AiEnvironmentFixture
        $lock = Get-Content -Raw -LiteralPath $script:Fixture.LockPath | ConvertFrom-Json -Depth 100
        $lock.resources[0].payload = @($lock.resources[0].payload[0], $lock.resources[0].payload[0])
        ($lock | ConvertTo-Json -Depth 100) | Test-Json -SchemaFile $lockSchema -ErrorAction SilentlyContinue | Should -BeFalse

        $script:Fixture = New-AiEnvironmentFixture
        $lock = Get-Content -Raw -LiteralPath $script:Fixture.LockPath | ConvertFrom-Json -Depth 100
        $lock.resources[0].payload += [pscustomobject][ordered]@{
            path = 'PLUGIN.TXT'
            sha256 = [string]$lock.resources[0].payload[0].sha256
        }
        ($lock | ConvertTo-Json -Depth 100) | Test-Json -SchemaFile $lockSchema | Should -BeTrue
        Write-TestJson -Path $script:Fixture.LockPath -Value $lock
        { Get-AiEnvironmentState -ProfilePath $script:Fixture.ProfilePath -LockPath $script:Fixture.LockPath } |
            Should -Throw '*Duplicate lock payload path*'
    }

    It 'constrains stable nested observed-state fields in the state schema' {
        $state = Get-AiEnvironmentState -ProfilePath $script:Fixture.ProfilePath -LockPath $script:Fixture.LockPath
        $stateJson = $state | ConvertTo-Json -Depth 100
        $stateSchema = Join-Path $script:ModuleRoot 'schemas\state.schema.json'

        $stateJson | Test-Json -SchemaFile $stateSchema | Should -BeTrue
        foreach ($mutation in @('owned-string', 'unexpected-control-plane', 'invalid-resource-status', 'duplicate-status', 'missing-required')) {
            $candidate = $stateJson | ConvertFrom-Json -Depth 100
            switch ($mutation) {
                'owned-string' { $candidate.Checks[0].Owned = 'true' }
                'unexpected-control-plane' {
                    $candidate.Providers.Codex.ControlPlane | Add-Member -NotePropertyName Unexpected -NotePropertyValue $true
                }
                'invalid-resource-status' { $candidate.Resources[0].Status = 'BROKEN' }
                'duplicate-status' { $candidate.ActiveStatuses = @('CURRENT', 'CURRENT') }
                'missing-required' { $candidate.Providers.Codex.ControlPlane.PSObject.Properties.Remove('Available') }
            }
            ($candidate | ConvertTo-Json -Depth 100) | Test-Json -SchemaFile $stateSchema -ErrorAction SilentlyContinue | Should -BeFalse
        }
    }

    It 'enforces profile and lock schemas before invoking either provider' {
        foreach ($scenario in @('invalid-provider', 'invalid-kind', 'invalid-lock-state')) {
            $script:Fixture = New-AiEnvironmentFixture
            $env:Path = "$($script:Fixture.Root);$($script:PreviousPath)"
            $probePath = Join-Path $script:Fixture.Root "$scenario.provider-invoked"
            $env:AI_ENV_SCHEMA_PROBE = $probePath
            @'
@echo off
echo invoked>>"%AI_ENV_SCHEMA_PROBE%"
exit /b 90
'@ | Set-Content -LiteralPath (Join-Path $script:Fixture.Root 'codex.cmd') -Encoding ascii
            @'
@echo off
echo invoked>>"%AI_ENV_SCHEMA_PROBE%"
exit /b 90
'@ | Set-Content -LiteralPath (Join-Path $script:Fixture.Root 'claude.cmd') -Encoding ascii

            if ($scenario -ceq 'invalid-lock-state') {
                $lock = Get-Content -Raw -LiteralPath $script:Fixture.LockPath | ConvertFrom-Json -Depth 100
                $lock.state = 'bogus-lock-state'
                Write-TestJson -Path $script:Fixture.LockPath -Value $lock
            }
            else {
                $profile = Get-Content -Raw -LiteralPath $script:Fixture.ProfilePath | ConvertFrom-Json -Depth 100
                if ($scenario -ceq 'invalid-provider') {
                    $profile.resources[0].provider = 'bogus-provider'
                }
                else {
                    $profile.resources[0].kind = 'bogus-kind'
                }
                Write-TestJson -Path $script:Fixture.ProfilePath -Value $profile
            }

            { Get-AiEnvironmentState -ProfilePath $script:Fixture.ProfilePath -LockPath $script:Fixture.LockPath } |
                Should -Throw '*failed schema validation*'
            Test-Path -LiteralPath $probePath | Should -BeFalse
        }
    }

    It 'rejects unsupported schemas and duplicate resource ids' {
        $profile = Get-Content -Raw -LiteralPath $script:Fixture.ProfilePath | ConvertFrom-Json -Depth 100
        $profile.schema = 'ai-skills/ai-environment-profile/v99'
        Write-TestJson -Path $script:Fixture.ProfilePath -Value $profile
        { Get-AiEnvironmentState -ProfilePath $script:Fixture.ProfilePath -LockPath $script:Fixture.LockPath } |
            Should -Throw '*Unsupported AI environment document schema*'

        $script:Fixture = New-AiEnvironmentFixture
        $profile = Get-Content -Raw -LiteralPath $script:Fixture.ProfilePath | ConvertFrom-Json -Depth 100
        $profile.providers.codex.command = (Join-Path $script:Fixture.Root 'codex.cmd')
        Write-TestJson -Path $script:Fixture.ProfilePath -Value $profile
        { Get-AiEnvironmentState -ProfilePath $script:Fixture.ProfilePath -LockPath $script:Fixture.LockPath } |
            Should -Throw '*failed schema validation*'

        $script:Fixture = New-AiEnvironmentFixture
        $profile = Get-Content -Raw -LiteralPath $script:Fixture.ProfilePath | ConvertFrom-Json -Depth 100
        $profile.resources += $profile.resources[0]
        Write-TestJson -Path $script:Fixture.ProfilePath -Value $profile
        { Get-AiEnvironmentState -ProfilePath $script:Fixture.ProfilePath -LockPath $script:Fixture.LockPath } |
            Should -Throw '*Duplicate profile resource id*'
    }

    It 'accepts a descendant commit when managed sourceRoots are unchanged and fails closed when they change or roll back' {
        $docsDir = Join-Path $script:Fixture.Repo 'docs'
        $null = New-Item -ItemType Directory -Path $docsDir -Force
        Set-Content -LiteralPath (Join-Path $docsDir 'notes.md') -Value '# unrelated commit' -Encoding utf8NoBOM
        git -C $script:Fixture.Repo add --all
        git -C $script:Fixture.Repo commit --quiet -m 'docs commit outside managed sourceRoots'

        $descendantState = Get-AiEnvironmentState -ProfilePath $script:Fixture.ProfilePath -LockPath $script:Fixture.LockPath
        $descendantState.Status | Should -BeExactly 'CURRENT'
        $descendantState.Source.HeadMatchesLock | Should -BeTrue
        $descendantState.Source.Reproducible | Should -BeTrue
        $descendantState.PromotionReady | Should -BeTrue

        $descendantHead = (git -C $script:Fixture.Repo rev-parse HEAD).Trim()
        $lock = Get-Content -Raw -LiteralPath $script:Fixture.LockPath | ConvertFrom-Json -Depth 100
        $baseCommit = [string]$lock.source.commit
        $lock.source.commit = $descendantHead
        Write-TestJson -Path $script:Fixture.LockPath -Value $lock
        git -C $script:Fixture.Repo checkout --quiet $baseCommit
        $rollbackState = Get-AiEnvironmentState -ProfilePath $script:Fixture.ProfilePath -LockPath $script:Fixture.LockPath
        $rollbackState.Source.HeadMatchesLock | Should -BeFalse
        $rollbackState.Reasons.Code | Should -Contain 'SOURCE_COMMIT_MISMATCH'

        git -C $script:Fixture.Repo checkout --quiet main
        $lock.source.commit = $baseCommit
        Write-TestJson -Path $script:Fixture.LockPath -Value $lock
        Set-Content -LiteralPath (Join-Path $script:Fixture.Repo 'lifecycle-plugin\extra.txt') -Value 'new tracked file in managed sourceRoot' -Encoding utf8NoBOM
        git -C $script:Fixture.Repo add --all
        git -C $script:Fixture.Repo commit --quiet -m 'change inside managed sourceRoot'

        $changedRootState = Get-AiEnvironmentState -ProfilePath $script:Fixture.ProfilePath -LockPath $script:Fixture.LockPath
        $changedRootState.Source.HeadMatchesLock | Should -BeFalse
        $changedRootState.Reasons.Code | Should -Contain 'SOURCE_COMMIT_MISMATCH'
        $changedRootState.PromotionReady | Should -BeFalse
    }

    It 'captures a candidate lock with Update-AiEnvironmentLock and promotes to accepted across in-repo commits' {
        $inRepoLockPath = Join-Path $script:Fixture.Repo 'locks\fixture.lock.json'
        Copy-Item -LiteralPath $script:Fixture.LockPath -Destination (New-Item -ItemType File -Path $inRepoLockPath -Force).FullName -Force
        git -C $script:Fixture.Repo add --all
        git -C $script:Fixture.Repo commit --quiet -m 'seed tracked lock'

        @'
@echo off
if "%~1"=="--version" (
  echo codex-cli 10.1.0
  exit /b 0
)
if "%~1"=="plugin" if "%~2"=="marketplace" if "%~3"=="list" (
  echo {"marketplaces":[]}
  exit /b 0
)
exit /b 64
'@ | Set-Content -LiteralPath (Join-Path $script:Fixture.Root 'codex.cmd') -Encoding ascii
        @'
@echo off
if "%~1"=="--version" (
  echo 9.2.0 (Claude Code^)
  exit /b 0
)
exit /b 64
'@ | Set-Content -LiteralPath (Join-Path $script:Fixture.Root 'claude.cmd') -Encoding ascii
        (Get-Content -Raw -LiteralPath $script:Fixture.CodexConfigPath).Replace(
            'sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
            'sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc'
        ) | Set-Content -LiteralPath $script:Fixture.CodexConfigPath -Encoding utf8NoBOM

        $stagedLockPath = Join-Path $script:Fixture.Root 'captured.lock.json'
        Copy-Item -LiteralPath $inRepoLockPath -Destination $stagedLockPath -Force
        $captureReceipt = Update-AiEnvironmentLock -ProfilePath $script:Fixture.ProfilePath -LockPath $stagedLockPath
        $captureReceipt.State | Should -BeExactly 'candidate'
        $captureReceipt.CodexVersion | Should -BeExactly '10.1.0'
        $captureReceipt.ClaudeVersion | Should -BeExactly '9.2.0'

        Copy-Item -LiteralPath $stagedLockPath -Destination $inRepoLockPath -Force
        git -C $script:Fixture.Repo add --all
        git -C $script:Fixture.Repo commit --quiet -m 'commit candidate lock'

        $candidateState = Get-AiEnvironmentState -ProfilePath $script:Fixture.ProfilePath -LockPath $inRepoLockPath
        @($candidateState.Reasons.Code) | Should -Be @('LOCK_NOT_ACCEPTED')

        Copy-Item -LiteralPath $inRepoLockPath -Destination $stagedLockPath -Force
        $approveReceipt = Approve-AiEnvironmentLock -ProfilePath $script:Fixture.ProfilePath -LockPath $stagedLockPath
        $approveReceipt.State | Should -BeExactly 'accepted'
        $approveReceipt.Status | Should -BeExactly 'CURRENT'

        Copy-Item -LiteralPath $stagedLockPath -Destination $inRepoLockPath -Force
        git -C $script:Fixture.Repo add --all
        git -C $script:Fixture.Repo commit --quiet -m 'promote lock to accepted'

        $acceptedState = Get-AiEnvironmentState -ProfilePath $script:Fixture.ProfilePath -LockPath $inRepoLockPath
        $acceptedState.Status | Should -BeExactly 'CURRENT'
        $acceptedState.PromotionReady | Should -BeTrue
        $acceptedState.Source.HeadMatchesLock | Should -BeTrue
        ($acceptedState | Test-AiEnvironment).Passed | Should -BeTrue
    }

    It 'refuses Update-AiEnvironmentLock and Approve-AiEnvironmentLock when fail-closed preconditions fail' {
        Set-Content -LiteralPath (Join-Path $script:Fixture.Repo 'dirty.txt') -Value 'uncommitted' -Encoding utf8NoBOM
        { Update-AiEnvironmentLock -ProfilePath $script:Fixture.ProfilePath -LockPath $script:Fixture.LockPath } |
            Should -Throw '*dirty Git worktree*'
        Remove-Item -LiteralPath (Join-Path $script:Fixture.Repo 'dirty.txt') -Force

        Set-Content -LiteralPath (Join-Path $script:Fixture.CodexHome 'hooks.json') -Value '{"hooks":{"drifted":true}}' -Encoding utf8NoBOM
        { Update-AiEnvironmentLock -ProfilePath $script:Fixture.ProfilePath -LockPath $script:Fixture.LockPath } |
            Should -Throw '*Installed target payload missing or drifted*'
        Copy-TestFile -SourceRoot (Join-Path $script:Fixture.Repo 'codex-hook') -TargetRoot $script:Fixture.CodexHome -RelativePath 'hooks.json'

        $lock = Get-Content -Raw -LiteralPath $script:Fixture.LockPath | ConvertFrom-Json -Depth 100
        $lock.state = 'candidate'
        $lock.acceptance[0].status = 'NOT_RUN'
        Write-TestJson -Path $script:Fixture.LockPath -Value $lock
        { Approve-AiEnvironmentLock -ProfilePath $script:Fixture.ProfilePath -LockPath $script:Fixture.LockPath } |
            Should -Throw '*ACCEPTANCE_NOT_RUN*'
    }

    It 'writes schema-valid observed state snapshots and enforces machine identity when requested' {
        $previousStateRoot = $env:DEVHOME_STATE_ROOT
        try {
            $stateRoot = Join-Path $script:Fixture.Root 'devhome-state'
            $env:DEVHOME_STATE_ROOT = $stateRoot
            $goodVerifier = Join-Path $script:Fixture.Root 'verify-ok.ps1'
            @'
[pscustomobject]@{
    status = 'VERIFIED'
    machineId = 'test-machine'
    instanceId = '11111111-1111-4111-8111-111111111111'
}
'@ | Set-Content -LiteralPath $goodVerifier -Encoding utf8NoBOM

            $badVerifier = Join-Path $script:Fixture.Root 'verify-bad.ps1'
            @'
[pscustomobject]@{
    status = 'FAILED'
    machineId = 'other-host'
    instanceId = '22222222-2222-4222-8222-222222222222'
}
'@ | Set-Content -LiteralPath $badVerifier -Encoding utf8NoBOM

            $state = Get-AiEnvironmentState -ProfilePath $script:Fixture.ProfilePath -LockPath $script:Fixture.LockPath
            { $state | Save-AiEnvironmentState -VerifierPath $badVerifier } |
                Should -Throw '*identity verification failed*'

            $receipt = $state | Save-AiEnvironmentState -VerifierPath $goodVerifier
            Test-Path -LiteralPath $receipt.Path -PathType Leaf | Should -BeTrue
            $savedJson = Get-Content -Raw -LiteralPath $receipt.Path
            $savedJson | Test-Json -SchemaFile (Join-Path $script:ModuleRoot 'schemas\state.schema.json') | Should -BeTrue
        }
        finally {
            if ($null -eq $previousStateRoot) {
                Remove-Item Env:DEVHOME_STATE_ROOT -ErrorAction SilentlyContinue
            }
            else {
                $env:DEVHOME_STATE_ROOT = $previousStateRoot
            }
        }
    }
}

Describe 'AI environment state hygiene scripts' {
    BeforeAll {
        $script:RepairScript = Join-Path $script:RepoRoot 'scripts\Repair-CodexSkillConfig.ps1'
        $script:SyncLockScript = Join-Path $script:RepoRoot 'scripts\Sync-SharedSkillLock.ps1'
    }

    BeforeEach {
        $script:PreviousPath = $env:Path
        $script:Fixture = New-AiEnvironmentFixture
        $env:Path = "$($script:Fixture.Root);$($script:PreviousPath)"
    }

    AfterEach {
        $env:Path = $script:PreviousPath
    }

    It 'prunes only missing disabled simple [[skills.config]] blocks and preserves all other TOML content' {
        $missingDisabledPath = Join-Path $script:Fixture.CodexHome 'skills\retired-skill\SKILL.md'
        $missingEnabledPath = Join-Path $script:Fixture.CodexHome 'skills\missing-enabled\SKILL.md'
        Add-Content -LiteralPath $script:Fixture.CodexConfigPath -Encoding utf8NoBOM -Value @"

[[skills.config]]
name = 'name-only-rule'
enabled = false

[[skills.config]]
path = '$missingDisabledPath'
enabled = false

[[skills.config]]
path = '$missingEnabledPath'
enabled = true

# Keep trailing section comment
[desktop]
followUpQueueMode = "steer"
"@

        $checkBefore = & $script:RepairScript -ConfigPath $script:Fixture.CodexConfigPath -Check
        $LASTEXITCODE | Should -Be 1
        $checkBefore.PrunedCount | Should -Be 1
        $checkBefore.RetainedMissingCount | Should -Be 1

        $dryRun = & $script:RepairScript -ConfigPath $script:Fixture.CodexConfigPath -DryRun
        $dryRun.Status | Should -BeExactly 'DryRun'
        $dryRun.PrunedCount | Should -Be 1
        (Get-Content -Raw -LiteralPath $script:Fixture.CodexConfigPath) | Should -Match 'retired-skill'

        $badVerifier = Join-Path $script:Fixture.Root 'bad-verifier.ps1'
        Set-Content -LiteralPath $badVerifier -Value "[pscustomobject]@{ status = 'FAILED'; machineId = 'wrong' }" -Encoding utf8NoBOM
        { & $script:RepairScript -ConfigPath $script:Fixture.CodexConfigPath -VerifierPath $badVerifier } |
            Should -Throw '*identity verification failed*'

        $applied = & $script:RepairScript -ConfigPath $script:Fixture.CodexConfigPath
        $applied.Status | Should -BeExactly 'Updated'
        $applied.PrunedCount | Should -Be 1
        $applied.ByNameBlocks | Should -Be 1
        $applied.ExistingPathBlocks | Should -Be 1
        $applied.RetainedMissingCount | Should -Be 1
        Test-Path -LiteralPath $applied.BackupPath -PathType Leaf | Should -BeTrue

        $afterText = Get-Content -Raw -LiteralPath $script:Fixture.CodexConfigPath
        $afterText | Should -Not -Match 'retired-skill'
        $afterText | Should -Match 'name-only-rule'
        $afterText | Should -Match 'missing-enabled'
        $afterText | Should -Match '# Keep trailing section comment'
        $afterText | Should -Match 'followUpQueueMode = "steer"'
    }

    It 'reconciles shared .skill-lock.json idempotently with seed provenance and clears SHARED_SKILL_LOCK_INCOMPLETE' {
        $skillsRoot = Join-Path $script:Fixture.AgentsHome 'skills'
        $lockPath = Join-Path $script:Fixture.AgentsHome '.skill-lock.json'
        Remove-Item -LiteralPath $lockPath -Force

        foreach ($skillName in @('agents-sdk', 'verify', 'custom-local')) {
            $skillFile = Join-Path $skillsRoot "$skillName\SKILL.md"
            $null = New-Item -ItemType Directory -Path (Split-Path -Parent $skillFile) -Force
            Set-Content -LiteralPath $skillFile -Value "# $skillName" -Encoding utf8NoBOM
        }

        $seedPath = Join-Path $script:Fixture.Root 'seed.skill-lock.json'
        Write-TestJson -Path $seedPath -Value ([ordered]@{
            version = 3
            skills = [ordered]@{
                'agents-sdk' = [ordered]@{
                    source = 'cloudflare/skills'
                    sourceType = 'github'
                    sourceUrl = 'https://github.com/cloudflare/skills.git'
                    skillPath = 'skills/agents-sdk/SKILL.md'
                    skillFolderHash = '0123456789abcdef0123456789abcdef01234567'
                    installedAt = '2026-06-26T04:34:02.814Z'
                    updatedAt = '2026-06-26T04:34:02.814Z'
                }
                'uninstalled-legacy' = [ordered]@{
                    source = 'microsoft/azure-skills'
                    sourceType = 'github'
                }
            }
            dismissed = [ordered]@{}
        })

        $beforeState = Get-AiEnvironmentState -ProfilePath $script:Fixture.ProfilePath -LockPath $script:Fixture.LockPath
        $beforeState.Reasons.Code | Should -Contain 'SHARED_SKILL_LOCK_INCOMPLETE'

        $checkBefore = & $script:SyncLockScript -SkillsRoot $skillsRoot -LockPath $lockPath -Check
        $LASTEXITCODE | Should -Be 1
        $checkBefore.Status | Should -BeExactly 'Drift'

        $dryRun = & $script:SyncLockScript -SkillsRoot $skillsRoot -LockPath $lockPath -SeedLockPath $seedPath -AiSkillsRepositoryRoot $script:RepoRoot -DryRun
        $dryRun.Status | Should -BeExactly 'DryRun'
        Test-Path -LiteralPath $lockPath | Should -BeFalse

        $applied = & $script:SyncLockScript -SkillsRoot $skillsRoot -LockPath $lockPath -SeedLockPath $seedPath -AiSkillsRepositoryRoot $script:RepoRoot
        $applied.Status | Should -BeExactly 'Updated'
        $applied.InstalledCount | Should -Be 4
        $applied.RecordedCount | Should -Be 4
        $applied.CarriedFromSeed | Should -Be 1
        $applied.ClassifiedAiSkills | Should -Be 2
        $applied.ClassifiedLocal | Should -Be 1

        $writtenLock = Get-Content -Raw -LiteralPath $lockPath | ConvertFrom-Json -Depth 50
        $writtenLock.skills.'agents-sdk'.source | Should -BeExactly 'cloudflare/skills'
        $writtenLock.skills.verify.source | Should -BeExactly 'espensev/ai-skills'
        $writtenLock.skills.'custom-local'.source | Should -BeExactly 'local/agents-skills'
        $writtenLock.skills.PSObject.Properties['uninstalled-legacy'] | Should -BeNullOrEmpty

        $secondRun = & $script:SyncLockScript -SkillsRoot $skillsRoot -LockPath $lockPath -AiSkillsRepositoryRoot $script:RepoRoot
        $secondRun.Status | Should -BeExactly 'Current'
        $secondRun.Changed | Should -BeFalse

        $checkAfter = & $script:SyncLockScript -SkillsRoot $skillsRoot -LockPath $lockPath -AiSkillsRepositoryRoot $script:RepoRoot -Check
        $LASTEXITCODE | Should -Be 0
        $checkAfter.Status | Should -BeExactly 'Current'

        $afterState = Get-AiEnvironmentState -ProfilePath $script:Fixture.ProfilePath -LockPath $script:Fixture.LockPath
        $afterState.SharedSkills.Complete | Should -BeTrue
        $afterState.Reasons.Code | Should -Not -Contain 'SHARED_SKILL_LOCK_INCOMPLETE'
    }
}
