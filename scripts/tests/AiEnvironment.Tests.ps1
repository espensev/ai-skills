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
        $pluginTarget = Join-Path $codexHome 'plugins\cache\ai-skills\devhome-lifecycle\1.0.0'

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
                        targetRoot = $pluginTarget
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

    It 'exports only the Phase 1 read-only interface' {
        $exports = @(Get-Command -Module AiEnvironment | Select-Object -ExpandProperty Name | Sort-Object)
        $exports | Should -Be @(
            'Get-AiEnvironmentState',
            'New-AiEnvironmentPlan',
            'Test-AiEnvironment'
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
  powershell.exe -NoProfile -Command "$PID | Set-Content -LiteralPath $env:AI_ENV_TEST_CHILD_PID; Start-Sleep -Seconds 30"
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
        $targetPath = Join-Path ([string]$profile.resources[1].desired.targetRoot) 'plugin.txt'
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
        $targetPath = Join-Path ([string]$profile.resources[1].desired.targetRoot) 'untracked.txt'
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
}
