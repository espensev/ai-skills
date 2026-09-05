Describe 'DevHome lifecycle plugin cache synchronization' {
    BeforeAll {
        $script:PackageRoot = Split-Path -Parent $PSScriptRoot
        $script:RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $script:PackageRoot '..\..\..'))
        $script:Synchronizer = Join-Path $script:PackageRoot 'Sync-DevHomeLifecyclePlugin.ps1'
        $script:ExpectedInstallationId = 'ca96d510-7d87-4cec-8e1a-bd8fc3866903'
        $script:PhysicalCodexHome = 'D:\DevHome\state\codex'

        function New-FakeCodexEnvironment {
            $root = Join-Path $TestDrive ([guid]::NewGuid().ToString('N'))
            $null = New-Item -ItemType Directory -Path $root -Force

            $statePath = Join-Path $root 'state.json'
            [ordered]@{
                marketplaceRoot = $null
                installed = $false
                installedVersion = $null
                installedSourceRoot = $null
                calls = @()
                codexHomes = @()
                mutations = @()
                failure = $null
            } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $statePath -Encoding utf8NoBOM

            $fakeCodexScript = Join-Path $root 'fake-codex.ps1'
            @'
$ErrorActionPreference = 'Stop'
$cliArgs = @($args)
$state = Get-Content -Raw -LiteralPath $env:FAKE_CODEX_STATE | ConvertFrom-Json
$key = $cliArgs -join ' '
$state.calls = @($state.calls) + $key
$state.codexHomes = @($state.codexHomes) + [string]$env:CODEX_HOME

function Save-State {
    $state | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $env:FAKE_CODEX_STATE -Encoding utf8NoBOM
}

if ($state.failure -eq 'marketplace-list-nonzero' -and $key -eq 'plugin marketplace list --json') {
    Save-State
    [Console]::Error.WriteLine('synthetic marketplace list failure')
    exit 19
}
if ($state.failure -eq 'marketplace-list-invalid-json' -and $key -eq 'plugin marketplace list --json') {
    Save-State
    Write-Output '{invalid-json'
    exit 0
}

if ($key -eq 'plugin marketplace list --json') {
    $marketplaces = @()
    if (-not [string]::IsNullOrWhiteSpace([string]$state.marketplaceRoot)) {
        $marketplaces = @([ordered]@{
            name = 'ai-skills'
            root = [string]$state.marketplaceRoot
        })
    }
    Save-State
    [ordered]@{ marketplaces = $marketplaces } | ConvertTo-Json -Depth 8
    exit 0
}

if ($cliArgs.Count -eq 5 -and $cliArgs[0] -eq 'plugin' -and $cliArgs[1] -eq 'marketplace' -and $cliArgs[2] -eq 'add' -and $cliArgs[4] -eq '--json') {
    if (-not (Test-Path -LiteralPath $env:FAKE_IDENTITY_MARKER -PathType Leaf)) {
        [Console]::Error.WriteLine('mutation reached fake Codex before identity verification')
        exit 51
    }
    $state.marketplaceRoot = [System.IO.Path]::GetFullPath($cliArgs[3])
    $state.mutations = @($state.mutations) + 'marketplace-add'
    Save-State
    [ordered]@{ name = 'ai-skills'; root = $state.marketplaceRoot } | ConvertTo-Json -Compress
    exit 0
}

if ($key -eq 'plugin list --json --available') {
    $installed = @()
    $available = @()
    $inventoryRoot = if ($state.installed -and -not [string]::IsNullOrWhiteSpace([string]$state.installedSourceRoot)) {
        [string]$state.installedSourceRoot
    }
    else {
        [string]$state.marketplaceRoot
    }
    if (-not [string]::IsNullOrWhiteSpace($inventoryRoot)) {
        $sourcePath = Join-Path $inventoryRoot 'codex-skills\local-hooks\devhome-lifecycle'
        $manifestPath = Join-Path $sourcePath '.codex-plugin\plugin.json'
        if (Test-Path -LiteralPath $manifestPath -PathType Leaf) {
            $manifest = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json
            $entry = [ordered]@{
                pluginId = 'devhome-lifecycle@ai-skills'
                name = 'devhome-lifecycle'
                marketplaceName = 'ai-skills'
                version = if ($state.installed) { [string]$state.installedVersion } else { [string]$manifest.version }
                installed = [bool]$state.installed
                enabled = [bool]$state.installed
                source = [ordered]@{ source = 'local'; path = $sourcePath }
            }
            if ($state.installed) {
                $installed = @($entry)
            }
            else {
                $available = @($entry)
            }
        }
    }
    Save-State
    [ordered]@{ installed = $installed; available = $available } | ConvertTo-Json -Depth 12
    exit 0
}

if ($cliArgs.Count -eq 4 -and $cliArgs[0] -eq 'plugin' -and $cliArgs[1] -eq 'add' -and $cliArgs[2] -eq 'devhome-lifecycle@ai-skills' -and $cliArgs[3] -eq '--json') {
    if (-not (Test-Path -LiteralPath $env:FAKE_IDENTITY_MARKER -PathType Leaf)) {
        [Console]::Error.WriteLine('mutation reached fake Codex before identity verification')
        exit 51
    }
    $sourcePath = Join-Path ([string]$state.marketplaceRoot) 'codex-skills\local-hooks\devhome-lifecycle'
    $manifest = Get-Content -Raw -LiteralPath (Join-Path $sourcePath '.codex-plugin\plugin.json') | ConvertFrom-Json
    $cachePath = Join-Path $env:CODEX_HOME "plugins\cache\ai-skills\devhome-lifecycle\$($manifest.version)"
    if (Test-Path -LiteralPath $cachePath) {
        [System.IO.Directory]::Delete($cachePath, $true)
    }
    $null = New-Item -ItemType Directory -Path (Split-Path -Parent $cachePath) -Force
    Copy-Item -LiteralPath $sourcePath -Destination $cachePath -Recurse -Force
    $state.installed = $true
    $state.installedVersion = [string]$manifest.version
    $state.installedSourceRoot = [string]$state.marketplaceRoot
    $state.mutations = @($state.mutations) + 'plugin-add'
    Save-State
    [ordered]@{ pluginId = 'devhome-lifecycle@ai-skills'; version = $manifest.version } | ConvertTo-Json -Compress
    exit 0
}

if ($cliArgs.Count -eq 4 -and $cliArgs[0] -eq 'plugin' -and $cliArgs[1] -eq 'remove' -and $cliArgs[2] -eq 'devhome-lifecycle@ai-skills' -and $cliArgs[3] -eq '--json') {
    if (-not (Test-Path -LiteralPath $env:FAKE_IDENTITY_MARKER -PathType Leaf)) {
        [Console]::Error.WriteLine('mutation reached fake Codex before identity verification')
        exit 51
    }
    $cacheRoot = Join-Path $env:CODEX_HOME 'plugins\cache\ai-skills\devhome-lifecycle'
    if (Test-Path -LiteralPath $cacheRoot) {
        [System.IO.Directory]::Delete($cacheRoot, $true)
    }
    $state.installed = $false
    $state.installedVersion = $null
    $state.installedSourceRoot = $null
    $state.mutations = @($state.mutations) + 'plugin-remove'
    Save-State
    [ordered]@{ pluginId = 'devhome-lifecycle@ai-skills'; removed = $true } | ConvertTo-Json -Compress
    exit 0
}

Save-State
[Console]::Error.WriteLine("unsupported fake Codex command: $key")
exit 64
'@ | Set-Content -LiteralPath $fakeCodexScript -Encoding utf8NoBOM

            $fakeCodexCommand = Join-Path $root 'fake-codex.cmd'
            @'
@echo off
pwsh -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%~dp0fake-codex.ps1" %*
exit /b %ERRORLEVEL%
'@ | Set-Content -LiteralPath $fakeCodexCommand -Encoding ascii

            $goodVerifier = Join-Path $root 'good-verifier.ps1'
            @"
Set-Content -LiteralPath `$env:FAKE_IDENTITY_MARKER -Value 'VERIFIED' -Encoding ascii
[pscustomobject]@{
    status = 'VERIFIED'
    machineId = 'snd-desk'
    instanceId = '$($script:ExpectedInstallationId)'
}
"@ | Set-Content -LiteralPath $goodVerifier -Encoding utf8NoBOM

            $badVerifier = Join-Path $root 'bad-verifier.ps1'
            @"
[pscustomobject]@{
    status = 'MISMATCH'
    machineId = 'wrong-machine'
    instanceId = 'wrong-installation'
}
"@ | Set-Content -LiteralPath $badVerifier -Encoding utf8NoBOM

            [pscustomobject]@{
                Root = $root
                StatePath = $statePath
                CodexHome = Join-Path $root 'codex-home'
                CodexCommand = $fakeCodexCommand
                GoodVerifier = $goodVerifier
                BadVerifier = $badVerifier
                IdentityMarker = Join-Path $root 'identity-verified.txt'
            }
        }

        function Get-FakeState {
            Get-Content -Raw -LiteralPath $script:Fake.StatePath | ConvertFrom-Json
        }

        function Set-FakeState {
            param(
                [Parameter(Mandatory)]
                [scriptblock] $Update
            )

            $state = Get-FakeState
            & $Update $state
            $state | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $script:Fake.StatePath -Encoding utf8NoBOM
        }

        function Invoke-TestSynchronizer {
            param(
                [switch] $Check,
                [switch] $Force,
                [string] $VerifierPath = $script:Fake.GoodVerifier
            )

            $parameters = @{
                CodexHome = $script:Fake.CodexHome
                CodexCommand = $script:Fake.CodexCommand
                VerifierPath = $VerifierPath
                AllowTestOnlyCodexHomeOverride = $true
            }
            if ($Check) {
                $parameters.Check = $true
            }
            if ($Force) {
                $parameters.Force = $true
            }

            & $script:Synchronizer @parameters
        }
    }

    BeforeEach {
        $script:Fake = New-FakeCodexEnvironment
        $env:FAKE_CODEX_STATE = $script:Fake.StatePath
        $env:FAKE_IDENTITY_MARKER = $script:Fake.IdentityMarker
    }

    AfterEach {
        Remove-Item Env:FAKE_CODEX_STATE -ErrorAction SilentlyContinue
        Remove-Item Env:FAKE_IDENTITY_MARKER -ErrorAction SilentlyContinue
    }

    It 'reports a missing marketplace and plugin without mutating in check mode' {
        Test-Path -LiteralPath $script:Synchronizer -PathType Leaf | Should -BeTrue

        $result = Invoke-TestSynchronizer -Check -VerifierPath $script:Fake.BadVerifier

        $result.Status | Should -BeExactly 'MISSING'
        $result.Action | Should -BeExactly 'NONE'
        @((Get-FakeState).mutations) | Should -HaveCount 0
        Test-Path -LiteralPath $script:Fake.IdentityMarker | Should -BeFalse
    }

    It 'registers the marketplace, installs the plugin, and proves the closed payload converged' {
        $result = Invoke-TestSynchronizer
        $state = Get-FakeState

        $result.Status | Should -BeExactly 'CURRENT'
        $result.Action | Should -BeExactly 'REGISTERED_AND_INSTALLED'
        $result.Changed | Should -BeTrue
        $result.Files | Should -Be 10
        @($result.Drift) | Should -HaveCount 0
        @($state.mutations) | Should -Be @('marketplace-add', 'plugin-add')
        Test-Path -LiteralPath $result.Cache -PathType Container | Should -BeTrue
    }

    It 'detects stale cache payload read-only and repairs it with remove plus add' {
        $installed = Invoke-TestSynchronizer
        $driftedPath = Join-Path $installed.Cache 'hooks\Invoke-DevHomeHook.ps1'
        Add-Content -LiteralPath $driftedPath -Value '# synthetic stale cache'
        Set-FakeState { param($state) $state.mutations = @() }
        Remove-Item -LiteralPath $script:Fake.IdentityMarker -ErrorAction SilentlyContinue

        $check = Invoke-TestSynchronizer -Check -VerifierPath $script:Fake.BadVerifier
        $check.Status | Should -BeExactly 'STALE'
        @($check.Drift) | Should -Contain 'hooks/Invoke-DevHomeHook.ps1 differs'
        (Get-Content -LiteralPath $driftedPath -Tail 1) | Should -BeExactly '# synthetic stale cache'
        @((Get-FakeState).mutations) | Should -HaveCount 0

        $repaired = Invoke-TestSynchronizer
        $repaired.Status | Should -BeExactly 'CURRENT'
        $repaired.Action | Should -BeExactly 'REFRESHED'
        @((Get-FakeState).mutations) | Should -Be @('plugin-remove', 'plugin-add')
        (Get-Content -LiteralPath $driftedPath -Tail 1) | Should -Not -BeExactly '# synthetic stale cache'
    }

    It 'is a no-op when the marketplace and closed cache payload are current' {
        $null = Invoke-TestSynchronizer
        Set-FakeState { param($state) $state.mutations = @() }
        Remove-Item -LiteralPath $script:Fake.IdentityMarker -ErrorAction SilentlyContinue

        $result = Invoke-TestSynchronizer -VerifierPath $script:Fake.BadVerifier

        $result.Status | Should -BeExactly 'CURRENT'
        $result.Action | Should -BeExactly 'NONE'
        $result.Changed | Should -BeFalse
        @((Get-FakeState).mutations) | Should -HaveCount 0
        Test-Path -LiteralPath $script:Fake.IdentityMarker | Should -BeFalse
    }

    It 'registers a missing marketplace without refreshing a current installed cache' {
        $null = Invoke-TestSynchronizer
        Set-FakeState {
            param($state)
            $state.marketplaceRoot = $null
            $state.mutations = @()
        }
        Remove-Item -LiteralPath $script:Fake.IdentityMarker -ErrorAction SilentlyContinue

        $result = Invoke-TestSynchronizer

        $result.Status | Should -BeExactly 'CURRENT'
        $result.Action | Should -BeExactly 'REGISTERED'
        @((Get-FakeState).mutations) | Should -Be @('marketplace-add')
    }

    It 'force refreshes a current installed plugin' {
        $null = Invoke-TestSynchronizer
        Set-FakeState { param($state) $state.mutations = @() }
        Remove-Item -LiteralPath $script:Fake.IdentityMarker -ErrorAction SilentlyContinue

        $result = Invoke-TestSynchronizer -Force

        $result.Status | Should -BeExactly 'CURRENT'
        $result.Action | Should -BeExactly 'REFRESHED'
        @((Get-FakeState).mutations) | Should -Be @('plugin-remove', 'plugin-add')
    }

    It 'fails closed when the ai-skills marketplace points at a different repository' {
        $otherRoot = Join-Path $script:Fake.Root 'other-repository'
        $null = New-Item -ItemType Directory -Path $otherRoot -Force
        Set-FakeState { param($state) $state.marketplaceRoot = $otherRoot }

        { Invoke-TestSynchronizer } | Should -Throw '*ai-skills*points elsewhere*'
        @((Get-FakeState).mutations) | Should -HaveCount 0
        Test-Path -LiteralPath $script:Fake.IdentityMarker | Should -BeFalse
    }

    It 'rejects identity failure before the first Codex mutation' {
        { Invoke-TestSynchronizer -VerifierPath $script:Fake.BadVerifier } |
            Should -Throw '*Machine identity mismatch*'

        @((Get-FakeState).mutations) | Should -HaveCount 0
        Test-Path -LiteralPath $script:Fake.IdentityMarker | Should -BeFalse
    }

    It 'refuses a filesystem root as CODEX_HOME before querying Codex' {
        $filesystemRoot = [System.IO.Path]::GetPathRoot($script:Fake.CodexHome)

        {
            & $script:Synchronizer `
                -CodexHome $filesystemRoot `
                -CodexCommand $script:Fake.CodexCommand `
                -VerifierPath $script:Fake.GoodVerifier `
                -Check
        } | Should -Throw '*filesystem root as CODEX_HOME*'

        @((Get-FakeState).calls) | Should -HaveCount 0
    }

    It 'ignores ambient AppData CODEX_HOME and queries the physical DevHome Codex root' {
        $ambientCodexHome = Join-Path $script:Fake.Root 'AppData\Local\Codex'
        $hadCodexHome = Test-Path Env:CODEX_HOME
        $previousCodexHome = $env:CODEX_HOME
        try {
            $env:CODEX_HOME = $ambientCodexHome
            $result = & $script:Synchronizer `
                -CodexCommand $script:Fake.CodexCommand `
                -VerifierPath $script:Fake.BadVerifier `
                -Check
        }
        finally {
            if ($hadCodexHome) {
                $env:CODEX_HOME = $previousCodexHome
            }
            else {
                Remove-Item Env:CODEX_HOME -ErrorAction SilentlyContinue
            }
        }

        $result.Cache | Should -BeExactly (
            Join-Path $script:PhysicalCodexHome 'plugins\cache\ai-skills\devhome-lifecycle\0.3.1'
        )
        $observedHomes = @((Get-FakeState).codexHomes | Select-Object -Unique)
        $observedHomes | Should -HaveCount 1
        $observedHomes[0] | Should -BeExactly $script:PhysicalCodexHome
    }

    It 'rejects an alternate Codex home before the first Codex CLI query' {
        {
            & $script:Synchronizer `
                -CodexHome $script:Fake.CodexHome `
                -CodexCommand $script:Fake.CodexCommand `
                -VerifierPath $script:Fake.BadVerifier `
                -Check
        } | Should -Throw '*physical DevHome CODEX_HOME*test-only*'

        @((Get-FakeState).calls) | Should -HaveCount 0
    }

    It 'refuses an alternate clone whose startup hook still delegates to the canonical package' {
        $alternateRepo = Join-Path $script:Fake.Root 'alternate-repository'
        $alternatePackageParent = Join-Path $alternateRepo 'codex-skills\local-hooks'
        $alternateMarketplaceParent = Join-Path $alternateRepo '.agents\plugins'
        $null = New-Item -ItemType Directory -Path $alternatePackageParent,$alternateMarketplaceParent -Force
        Copy-Item -LiteralPath $script:PackageRoot `
            -Destination (Join-Path $alternatePackageParent 'devhome-lifecycle') `
            -Recurse `
            -Force
        Copy-Item -LiteralPath (Join-Path $script:RepoRoot '.agents\plugins\marketplace.json') `
            -Destination (Join-Path $alternateMarketplaceParent 'marketplace.json') `
            -Force
        $alternateSynchronizer = Join-Path $alternatePackageParent `
            'devhome-lifecycle\Sync-DevHomeLifecyclePlugin.ps1'

        {
            & $alternateSynchronizer `
                -CodexHome $script:Fake.CodexHome `
                -CodexCommand $script:Fake.CodexCommand `
                -VerifierPath $script:Fake.GoodVerifier `
                -AllowTestOnlyCodexHomeOverride `
                -Check
        } | Should -Throw '*SourcePackageRoot*does not match this package root*'

        @((Get-FakeState).calls) | Should -HaveCount 0
    }

    It 'ignores generated cache files outside the explicit closed payload' {
        $installed = Invoke-TestSynchronizer
        $generatedRoot = Join-Path $installed.Cache 'hooks\__pycache__'
        $null = New-Item -ItemType Directory -Path $generatedRoot -Force
        Set-Content -LiteralPath (Join-Path $generatedRoot 'probe.pyc') -Value 'generated' -Encoding ascii

        $result = Invoke-TestSynchronizer -Check -VerifierPath $script:Fake.BadVerifier

        $result.Status | Should -BeExactly 'CURRENT'
        @($result.Drift) | Should -HaveCount 0
    }

    It 'detects and repairs cache-only skill files and an unexpected MCP manifest' {
        $installed = Invoke-TestSynchronizer
        $orphanedSkill = Join-Path $installed.Cache 'skills\orphaned-helper\SKILL.md'
        $null = New-Item -ItemType Directory -Path (Split-Path -Parent $orphanedSkill) -Force
        @'
---
name: orphaned-helper
description: Synthetic cache-only capability used by the convergence test.
---

# Orphaned helper
'@ | Set-Content -LiteralPath $orphanedSkill -Encoding utf8NoBOM
        Set-Content -LiteralPath (Join-Path $installed.Cache '.mcp.json') `
            -Value '{"mcpServers":{}}' `
            -Encoding utf8NoBOM
        Set-FakeState { param($state) $state.mutations = @() }
        Remove-Item -LiteralPath $script:Fake.IdentityMarker -ErrorAction SilentlyContinue

        $check = Invoke-TestSynchronizer -Check -VerifierPath $script:Fake.BadVerifier
        $check.Status | Should -BeExactly 'STALE'
        @($check.Drift) | Should -Contain 'skills/orphaned-helper/SKILL.md unexpected'
        @($check.Drift) | Should -Contain '.mcp.json unexpected'
        @((Get-FakeState).mutations) | Should -HaveCount 0

        $repaired = Invoke-TestSynchronizer
        $repaired.Status | Should -BeExactly 'CURRENT'
        $repaired.Action | Should -BeExactly 'REFRESHED'
        @((Get-FakeState).mutations) | Should -Be @('plugin-remove', 'plugin-add')
        Test-Path -LiteralPath $orphanedSkill | Should -BeFalse
        Test-Path -LiteralPath (Join-Path $installed.Cache '.mcp.json') | Should -BeFalse
    }

    It 'surfaces a nonzero Codex CLI result with command context' {
        Set-FakeState { param($state) $state.failure = 'marketplace-list-nonzero' }

        { Invoke-TestSynchronizer -Check } |
            Should -Throw '*Codex command failed*plugin marketplace list --json*synthetic marketplace list failure*'
    }

    It 'rejects invalid JSON from the Codex CLI with command context' {
        Set-FakeState { param($state) $state.failure = 'marketplace-list-invalid-json' }

        { Invoke-TestSynchronizer -Check } |
            Should -Throw '*Codex command returned invalid JSON*plugin marketplace list --json*'
    }
}
