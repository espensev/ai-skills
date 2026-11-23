BeforeAll {
    $script:RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
    $script:SyncScript = Join-Path $script:RepoRoot "scripts\Sync-GrandSweepZCode.ps1"
    $script:CanonicalSkill = Join-Path $script:RepoRoot "codex-skills\skills\grand-sweep"
}

Describe "Sync-GrandSweepZCode" -Tag 'GrandSweepZCode' {
    Context "check mode (read-only)" {
        It "reports drift and exits non-zero when the target is missing" {
            $targetRoot = Join-Path $TestDrive 'missing-target'
            $out = & $script:SyncScript -TargetSkillRoot $targetRoot 2>&1
            $LASTEXITCODE | Should -Not -Be 0
            ($out -join "`n") | Should -Match 'missing'
        }

        It "reports drift and exits non-zero when a projected file differs" {
            $targetRoot = Join-Path $TestDrive 'drifted-target'
            & $script:SyncScript -TargetSkillRoot $targetRoot -Apply | Out-Null
            $LASTEXITCODE | Should -Be 0
            Set-Content -LiteralPath (Join-Path $targetRoot 'SKILL.md') -Value 'drifted'

            $out = & $script:SyncScript -TargetSkillRoot $targetRoot 2>&1
            $LASTEXITCODE | Should -Not -Be 0
            ($out -join "`n") | Should -Match 'SKILL\.md'
        }

        It "reports drift and exits non-zero when the target carries an extra file" {
            $targetRoot = Join-Path $TestDrive 'extra-target'
            & $script:SyncScript -TargetSkillRoot $targetRoot -Apply | Out-Null
            Set-Content -LiteralPath (Join-Path $targetRoot 'stray.txt') -Value 'stray'

            $out = & $script:SyncScript -TargetSkillRoot $targetRoot 2>&1
            $LASTEXITCODE | Should -Not -Be 0
            ($out -join "`n") | Should -Match 'stray\.txt'
        }

        It "exits zero and changes nothing when the target is in sync" {
            $targetRoot = Join-Path $TestDrive 'synced-target'
            & $script:SyncScript -TargetSkillRoot $targetRoot -Apply | Out-Null
            $before = Get-ChildItem -LiteralPath $targetRoot -Recurse -File | ForEach-Object { $_.FullName + ':' + (Get-FileHash -LiteralPath $_.FullName).Hash }

            $out = & $script:SyncScript -TargetSkillRoot $targetRoot 2>&1
            $LASTEXITCODE | Should -Be 0
            $after = Get-ChildItem -LiteralPath $targetRoot -Recurse -File | ForEach-Object { $_.FullName + ':' + (Get-FileHash -LiteralPath $_.FullName).Hash }
            $after | Should -Be $before
        }
    }

    Context "apply mode" {
        It "projects the canonical skill and nothing else" {
            $targetRoot = Join-Path $TestDrive 'apply-target'
            $out = & $script:SyncScript -TargetSkillRoot $targetRoot -Apply 2>&1
            $LASTEXITCODE | Should -Be 0
            ($out -join "`n") | Should -Match 'grand-sweep'

            Test-Path -LiteralPath (Join-Path $targetRoot 'SKILL.md') | Should -BeTrue
            Test-Path -LiteralPath (Join-Path $targetRoot 'references\engine-traps.md') | Should -BeTrue
            Test-Path -LiteralPath (Join-Path $targetRoot 'references\lifecycle.md') | Should -BeTrue
            Test-Path -LiteralPath (Join-Path $targetRoot 'templates\tender-prompt.md') | Should -BeTrue
            # other codex-skills entries must not leak into the projection
            Test-Path -LiteralPath (Join-Path $targetRoot 'review') | Should -BeFalse

            $sourceFiles = Get-ChildItem -LiteralPath $script:CanonicalSkill -Recurse -File
            foreach ($file in $sourceFiles) {
                $relative = $file.FullName.Substring($script:CanonicalSkill.Length).TrimStart('\', '/')
                $projected = Join-Path $targetRoot $relative
                (Get-FileHash -LiteralPath $projected).Hash |
                    Should -BeExactly (Get-FileHash -LiteralPath $file.FullName).Hash
            }
        }

        It "replaces only the named skill directory, removing extras and preserving unrelated siblings" {
            $parent = Join-Path $TestDrive 'replace-parent'
            $targetRoot = Join-Path $parent 'grand-sweep'
            $sibling = Join-Path $parent 'other-skill'
            New-Item -ItemType Directory -Path $sibling -Force | Out-Null
            Set-Content -LiteralPath (Join-Path $sibling 'SKILL.md') -Value 'other'
            & $script:SyncScript -TargetSkillRoot $targetRoot -Apply | Out-Null
            Set-Content -LiteralPath (Join-Path $targetRoot 'SKILL.md') -Value 'stale'
            Set-Content -LiteralPath (Join-Path $targetRoot 'old-reference.md') -Value 'extra'
            New-Item -ItemType Directory -Path (Join-Path $targetRoot 'old-dir') -Force | Out-Null
            Set-Content -LiteralPath (Join-Path $targetRoot 'old-dir\old.md') -Value 'extra'

            & $script:SyncScript -TargetSkillRoot $targetRoot -Apply | Out-Null
            $LASTEXITCODE | Should -Be 0
            (Get-Content -LiteralPath (Join-Path $targetRoot 'SKILL.md') -Raw) |
                Should -BeExactly (Get-Content -LiteralPath (Join-Path $script:CanonicalSkill 'SKILL.md') -Raw)
            Test-Path -LiteralPath (Join-Path $targetRoot 'old-reference.md') | Should -BeFalse
            Test-Path -LiteralPath (Join-Path $targetRoot 'old-dir') | Should -BeFalse
            (Get-Content -LiteralPath (Join-Path $sibling 'SKILL.md') -Raw).Trim() | Should -BeExactly 'other'
        }
    }

    Context "refusals" {
        It "refuses an unsafe skill name" {
            { & $script:SyncScript -SkillName '../escape' -TargetSkillRoot (Join-Path $TestDrive 'unsafe1') } |
                Should -Throw
            { & $script:SyncScript -SkillName 'Grand_Sweep' -TargetSkillRoot (Join-Path $TestDrive 'unsafe2') } |
                Should -Throw
        }

        It "refuses a skill that is not the canonical grand-sweep package" {
            { & $script:SyncScript -SkillName 'not-a-skill' -TargetSkillRoot (Join-Path $TestDrive 'unsafe3') } |
                Should -Throw '*not a packaged skill*'
        }

        It "refuses a target that resolves inside the canonical package" {
            $inside = Join-Path $script:CanonicalSkill 'sub\dir'
            { & $script:SyncScript -TargetSkillRoot $inside -Apply } |
                Should -Throw '*inside the canonical*'
        }

        It "refuses a target that is a reparse point and leaves what it points to untouched" {
            $realDirectory = Join-Path $TestDrive 'junction-real'
            New-Item -ItemType Directory -Path $realDirectory -Force | Out-Null
            Set-Content -LiteralPath (Join-Path $realDirectory 'keep.txt') -Value 'keep'
            $junction = Join-Path $TestDrive 'junction-link'
            New-Item -ItemType Junction -Path $junction -Target $realDirectory | Out-Null

            { & $script:SyncScript -TargetSkillRoot $junction -Apply } |
                Should -Throw '*reparse point*'
            Test-Path -LiteralPath (Join-Path $realDirectory 'keep.txt') | Should -BeTrue
            Test-Path -LiteralPath (Join-Path $realDirectory 'SKILL.md') | Should -BeFalse
        }

        It "refuses a target that is a file" {
            $filePath = Join-Path $TestDrive 'target-file'
            Set-Content -LiteralPath $filePath -Value 'not a directory'

            { & $script:SyncScript -TargetSkillRoot $filePath -Apply } |
                Should -Throw '*not a skill directory*'
        }
    }
}
