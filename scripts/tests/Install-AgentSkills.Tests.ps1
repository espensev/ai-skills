BeforeAll {
    $script:RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
    $script:Installer = Join-Path $script:RepoRoot "scripts\Install-AgentSkills.ps1"
    $script:Comparator = Join-Path $script:RepoRoot "scripts\Compare-AgentSkillRoots.ps1"
    $script:RegistryPath = Join-Path $script:RepoRoot "scripts\retired-skills.json"
    $script:Registry = Get-Content -Raw -LiteralPath $script:RegistryPath | ConvertFrom-Json
    $script:RetiredNames = @($script:Registry.retired_skills | ForEach-Object { [string]$_.name })
}

Describe "retired skill installation contract" {
    It "keeps the complete retirement set in one registry" {
        $script:Registry.schema | Should -Be "ai-skills/retired-skills/v1"
        $required = @(
            "agent-report",
            "api-design",
            "backend-patterns",
            "deep-research",
            "e2e-testing",
            "frontend-patterns",
            "loop",
            "observer-test",
            "refactor-planner",
            "session-stats",
            "token-audit",
            "worktree-manager"
        )
        foreach ($name in $required) {
            $script:RetiredNames | Should -Contain $name
        }
        @($script:RetiredNames | Sort-Object -Unique).Count | Should -Be $script:RetiredNames.Count
    }

    It "reports each retired directory in dry-run mode without deleting it" {
        $target = Join-Path $TestDrive "dry-codex"
        New-Item -ItemType Directory -Path $target -Force | Out-Null
        foreach ($name in $script:RetiredNames) {
            New-Item -ItemType Directory -Path (Join-Path $target $name) -Force | Out-Null
        }

        $output = (& $script:Installer `
            -Provider Codex `
            -CodexTargets $target `
            -Force `
            -DryRun 6>&1) | Out-String

        foreach ($name in $script:RetiredNames) {
            Test-Path -LiteralPath (Join-Path $target $name) | Should -BeTrue
            $output | Should -Match ([regex]::Escape("Retired skill would-remove [Codex]: $name ->"))
        }
    }

    It "prunes only retired directories and leaves both fake roots comparator-clean" {
        $codexTarget = Join-Path $TestDrive "codex-skills"
        $claudeTarget = Join-Path $TestDrive "claude-skills"
        foreach ($target in @($codexTarget, $claudeTarget)) {
            New-Item -ItemType Directory -Path $target -Force | Out-Null
            New-Item -ItemType Directory -Path (Join-Path $target "keep-me") -Force | Out-Null
            Set-Content -LiteralPath (Join-Path $target "keep-me\marker.txt") -Value "preserve"
            foreach ($name in $script:RetiredNames) {
                $retiredPath = Join-Path $target $name
                New-Item -ItemType Directory -Path $retiredPath -Force | Out-Null
                Set-Content -LiteralPath (Join-Path $retiredPath "stale.txt") -Value "stale"
            }
        }

        $redOutput = (& pwsh -NoProfile -File $script:Comparator `
            -Provider Codex `
            -CodexTargets $codexTarget 2>&1) | Out-String
        $LASTEXITCODE | Should -Be 0
        $redOutput | Should -Match "RetiredInstalled"

        $installOutput = (& $script:Installer `
            -Provider Both `
            -CodexTargets $codexTarget `
            -ClaudeTargets $claudeTarget `
            -Force 6>&1) | Out-String

        foreach ($providerCase in @(
            @{ Name = "Codex"; Target = $codexTarget },
            @{ Name = "Claude"; Target = $claudeTarget }
        )) {
            Test-Path -LiteralPath (Join-Path $providerCase.Target "keep-me\marker.txt") | Should -BeTrue
            foreach ($name in $script:RetiredNames) {
                Test-Path -LiteralPath (Join-Path $providerCase.Target $name) | Should -BeFalse
                $installOutput | Should -Match ([regex]::Escape("Retired skill removed [$($providerCase.Name)]: $name ->"))
            }
        }

        Test-Path -LiteralPath (Join-Path $codexTarget "repo-conventions\SKILL.md") | Should -BeTrue
        Test-Path -LiteralPath (Join-Path $codexTarget "usage-stats\SKILL.md") | Should -BeTrue
        Test-Path -LiteralPath (Join-Path $claudeTarget "usage-stats\SKILL.md") | Should -BeTrue

        $greenOutput = (& pwsh -NoProfile -File $script:Comparator `
            -Provider Both `
            -CodexTargets $codexTarget `
            -ClaudeTargets $claudeTarget `
            -FailOnMissingOrStale 2>&1) | Out-String
        $LASTEXITCODE | Should -Be 0
        $greenOutput | Should -Match "PASS - local agent skill roots match manifest-listed files"
    }
}
