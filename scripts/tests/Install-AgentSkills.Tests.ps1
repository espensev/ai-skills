BeforeAll {
    $script:RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
    $script:Installer = Join-Path $script:RepoRoot "scripts\Install-AgentSkills.ps1"
    $script:Comparator = Join-Path $script:RepoRoot "scripts\Compare-AgentSkillRoots.ps1"
    $script:RegistryPath = Join-Path $script:RepoRoot "scripts\retired-skills.json"
    $script:Registry = Get-Content -Raw -LiteralPath $script:RegistryPath | ConvertFrom-Json
    $script:RetiredNames = @($script:Registry.retired_skills | ForEach-Object { [string]$_.name })
}

Describe "selective skill installation" -Tag 'SelectiveSkills' {
    It "updates only the requested skill and preserves unrelated skills, support files and retired entries" {
        $target = Join-Path $TestDrive 'selective-codex'
        foreach ($name in @('handoff', 'qa', 'agent-report')) {
            New-Item -ItemType Directory -Path (Join-Path $target $name) -Force | Out-Null
            Set-Content -LiteralPath (Join-Path $target "$name\SKILL.md") -Value "existing $name"
        }
        Set-Content -LiteralPath (Join-Path $target 'planning-contract.md') -Value 'existing contract'
        $preserved = @('qa\SKILL.md', 'agent-report\SKILL.md', 'planning-contract.md')
        $hashes = @{}
        foreach ($path in $preserved) { $hashes[$path] = (Get-FileHash -LiteralPath (Join-Path $target $path)).Hash }
        & $script:Installer -Provider Codex -CodexTargets $target -SkillNames handoff -Force | Out-Null
        (Get-FileHash -LiteralPath (Join-Path $target 'handoff\SKILL.md')).Hash |
            Should -BeExactly (Get-FileHash -LiteralPath (Join-Path $script:RepoRoot 'codex-skills\skills\handoff\SKILL.md')).Hash
        foreach ($path in $preserved) { (Get-FileHash -LiteralPath (Join-Path $target $path)).Hash | Should -BeExactly $hashes[$path] }
        @(Get-ChildItem -LiteralPath $target -Force) | Should -HaveCount 4
    }

    It "validates the entire selection before creating any target" {
        $target = Join-Path $TestDrive 'invalid-selection'
        { & $script:Installer -Provider Codex -CodexTargets $target -SkillNames @('handoff', '../outside') -Force } |
            Should -Throw '*Invalid selected skill*'
        Test-Path -LiteralPath $target | Should -BeFalse
        { & $script:Installer -Provider Codex -CodexTargets $target -SkillNames @('handoff', 'missing-skill') -Force } |
            Should -Throw '*Invalid selected skill*'
        Test-Path -LiteralPath $target | Should -BeFalse
    }

    It "requires a single provider and excludes plugin synchronization when selecting skills" {
        { & $script:Installer -SkillNames handoff } | Should -Throw '*single provider*'
        { & $script:Installer -Provider Codex -SkillNames handoff -CodexLocalPlugin DevHomeLifecycle } |
            Should -Throw '*separate invocation*'
    }

    It "honors selective dry-run without creating the target" {
        $target = Join-Path $TestDrive 'selective-dry-run'
        & $script:Installer -Provider Codex -CodexTargets $target -SkillNames handoff -Force -DryRun | Out-Null
        Test-Path -LiteralPath $target | Should -BeFalse
    }
}

Describe "content-aware repair without -Force" -Tag 'Repair' {
    BeforeAll {
        function Get-SourceHash {
            param ([string]$RelativePath)
            (Get-FileHash -LiteralPath (Join-Path $script:RepoRoot "codex-skills\$RelativePath")).Hash
        }
    }

    It "repairs an emptied skill directory and missing runtime files on a bare run" {
        $target = Join-Path $TestDrive 'repair-emptied'
        & $script:Installer -Provider Codex -CodexTargets $target *>&1 | Out-Null
        Get-ChildItem -LiteralPath (Join-Path $target 'qa') -Force | Remove-Item -Recurse -Force
        Remove-Item -LiteralPath (Join-Path $target 'scripts\task_manager.py')
        Remove-Item -LiteralPath (Join-Path $target 'scripts\analysis\engine.py')

        $output = (& $script:Installer -Provider Codex -CodexTargets $target 6>&1) | Out-String

        $output | Should -Match ([regex]::Escape('Skill repaired [Codex]: qa (1 missing: SKILL.md)'))
        $output | Should -Match ([regex]::Escape('Directory repaired [Codex]: scripts/analysis (1 missing: engine.py)'))
        (Get-FileHash -LiteralPath (Join-Path $target 'qa\SKILL.md')).Hash | Should -BeExactly (Get-SourceHash 'skills\qa\SKILL.md')
        foreach ($path in @('scripts\task_manager.py', 'scripts\analysis\engine.py')) {
            (Get-FileHash -LiteralPath (Join-Path $target $path)).Hash | Should -BeExactly (Get-SourceHash $path)
        }
    }

    It "restores only the missing files and keeps a locally edited file" {
        $target = Join-Path $TestDrive 'repair-partial'
        $skillDir = Join-Path $target 'deep-audit'
        New-Item -ItemType Directory -Path $skillDir -Force | Out-Null
        Set-Content -LiteralPath (Join-Path $skillDir 'SKILL.md') -Value 'local edit'
        $editedHash = (Get-FileHash -LiteralPath (Join-Path $skillDir 'SKILL.md')).Hash

        $output = (& $script:Installer -Provider Codex -CodexTargets $target -SkillNames deep-audit 6>&1) | Out-String

        $output | Should -Match ([regex]::Escape('Skill repaired [Codex]: deep-audit (3 missing:'))
        (Get-FileHash -LiteralPath (Join-Path $skillDir 'SKILL.md')).Hash | Should -BeExactly $editedHash
        foreach ($path in @('examples\depth-test.md', 'references\mode-contracts.md', 'references\state-and-report-contracts.md')) {
            (Get-FileHash -LiteralPath (Join-Path $skillDir $path)).Hash | Should -BeExactly (Get-SourceHash "skills\deep-audit\$path")
        }
    }

    It "reports the repair under -DryRun without writing" {
        $target = Join-Path $TestDrive 'repair-dry-run'
        New-Item -ItemType Directory -Path (Join-Path $target 'qa') -Force | Out-Null

        $output = (& $script:Installer -Provider Codex -CodexTargets $target -SkillNames qa -DryRun 6>&1) | Out-String

        $output | Should -Match ([regex]::Escape('Skill would-repair [Codex]: qa (1 missing: SKILL.md)'))
        @(Get-ChildItem -LiteralPath (Join-Path $target 'qa') -Force) | Should -HaveCount 0
    }

    It "throws when a copy leaves SKILL.md absent after the run" {
        # A directory squatting on SKILL.md makes Copy-Item copy into it without
        # error, so only the post-install verification can notice the missing file.
        $target = Join-Path $TestDrive 'verify-absent'
        New-Item -ItemType Directory -Path (Join-Path $target 'qa\SKILL.md') -Force | Out-Null

        { & $script:Installer -Provider Codex -CodexTargets $target -SkillNames qa 6>$null } |
            Should -Throw '*Post-install verification failed*qa/SKILL.md*'
    }
}

Describe "read-only install check" -Tag 'Check' {
    BeforeAll {
        function Invoke-InstallerCheck {
            param ([string]$Target)
            $output = (& pwsh -NoProfile -File $script:Installer -Provider Codex -CodexTargets $Target -Check 2>&1) | Out-String
            [pscustomobject]@{ ExitCode = $LASTEXITCODE; Output = $output }
        }

        function Get-TreeSnapshot {
            param ([string]$Root)
            @(Get-ChildItem -LiteralPath $Root -Recurse -Force | Sort-Object FullName | ForEach-Object {
                if ($_.PSIsContainer) { "$($_.FullName) <dir>" } else { "$($_.FullName) $((Get-FileHash -LiteralPath $_.FullName).Hash)" }
            }) -join "`n"
        }
    }

    It "passes a clean install and treats a CRLF-only difference as clean" {
        $target = Join-Path $TestDrive 'check-clean'
        & $script:Installer -Provider Codex -CodexTargets $target *>&1 | Out-Null
        $skillFile = Join-Path $target 'qa\SKILL.md'
        [System.IO.File]::WriteAllText($skillFile, ([System.IO.File]::ReadAllText($skillFile) -replace "`r?`n", "`r`n"))
        (Get-FileHash -LiteralPath $skillFile).Hash |
            Should -Not -BeExactly (Get-FileHash -LiteralPath (Join-Path $script:RepoRoot 'codex-skills\skills\qa\SKILL.md')).Hash

        $result = Invoke-InstallerCheck $target

        $result.ExitCode | Should -Be 0
        $result.Output | Should -Match ([regex]::Escape("Check [Codex]: $target"))
        $result.Output | Should -Match 'PASS'
    }

    It "fails on a missing SKILL.md without writing anything" {
        $target = Join-Path $TestDrive 'check-missing'
        & $script:Installer -Provider Codex -CodexTargets $target *>&1 | Out-Null
        Remove-Item -LiteralPath (Join-Path $target 'qa\SKILL.md')
        New-Item -ItemType Directory -Path (Join-Path $target "$($script:RetiredNames[0])") -Force | Out-Null
        $before = Get-TreeSnapshot $target

        $result = Invoke-InstallerCheck $target

        $result.ExitCode | Should -Not -Be 0
        $result.Output | Should -Match ([regex]::Escape('FINDING Missing [Codex] Skill qa/SKILL.md'))
        Get-TreeSnapshot $target | Should -BeExactly $before
    }

    It "fails on drifted content" {
        $target = Join-Path $TestDrive 'check-drift'
        & $script:Installer -Provider Codex -CodexTargets $target *>&1 | Out-Null
        Add-Content -LiteralPath (Join-Path $target 'scripts\analysis\engine.py') -Value '# local drift'

        $result = Invoke-InstallerCheck $target

        $result.ExitCode | Should -Not -Be 0
        $result.Output | Should -Match ([regex]::Escape('FINDING Drifted [Codex] Directory scripts/analysis/engine.py'))
    }

    It "refuses -Force or -DryRun alongside -Check" {
        $target = Join-Path $TestDrive 'check-exclusive'
        { & $script:Installer -Provider Codex -CodexTargets $target -Check -Force } | Should -Throw '*Check cannot be combined*'
        { & $script:Installer -Provider Codex -CodexTargets $target -Check -DryRun } | Should -Throw '*Check cannot be combined*'
        Test-Path -LiteralPath $target | Should -BeFalse
    }
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
