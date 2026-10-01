BeforeAll {
    $script:RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))

    function Invoke-FixtureValidator {
        $output = (& pwsh -NoProfile -File $script:Validator -StrictSkillManifest -SkipExportSmoke -SkipInstallerSmoke 2>&1) | Out-String
        return [pscustomobject]@{ ExitCode = $LASTEXITCODE; Output = $output }
    }

    function Set-FixtureSkill {
        param ([string]$Name, [string]$Text)

        $skillRoot = Join-Path $script:PackageRoot "skills\$Name"
        New-Item -ItemType Directory -Path $skillRoot -Force | Out-Null
        Set-Content -LiteralPath (Join-Path $skillRoot "SKILL.md") -Value $Text
    }

    function Set-FixtureReadme {
        param ([int]$Count)

        Set-Content -LiteralPath (Join-Path $script:FakeRepo "README.md") -Value "$Count install-ready skills`n| **fixture-skills** | $Count |"
    }
}

Describe "Test-ReadyPackages source-only validation" {
    BeforeEach {
        # The validator finds its manifests relative to itself. Each test gets
        # a fresh synthetic repo rather than altering the real provider skills.
        $script:FakeRepo = Join-Path $TestDrive ([guid]::NewGuid().ToString("N"))
        $scriptsDir = Join-Path $script:FakeRepo "scripts"
        New-Item -ItemType Directory -Path $scriptsDir -Force | Out-Null
        Copy-Item -LiteralPath (Join-Path $script:RepoRoot "scripts\Test-ReadyPackages.ps1") -Destination $scriptsDir
        $script:Validator = Join-Path $scriptsDir "Test-ReadyPackages.ps1"
        @{
            packages = @(@{ name = "fixture-skills"; path = "fixture-skills"; status = "ready"; strategy = "portable-runtime" })
        } | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $script:FakeRepo "release-manifest.json")

        $script:PackageRoot = Join-Path $script:FakeRepo "fixture-skills"
        New-Item -ItemType Directory -Path (Join-Path $script:PackageRoot "package") -Force | Out-Null
        $script:InstallManifestPath = Join-Path $script:PackageRoot "package\install-manifest.json"
        $script:InstallManifest = @{
            default_skills = @("alpha")
            optional_skills = @()
            source_only_skills = @("gamma")
            contract_files = @()
            optional_contract_files = @()
            runtime_files = @()
            runtime_directories = @()
        }
        $script:InstallManifest | ConvertTo-Json | Set-Content -LiteralPath $script:InstallManifestPath
        Set-FixtureReadme 1
        foreach ($name in @("alpha", "gamma")) {
            Set-FixtureSkill $name "---`nname: $name`ndescription: Use when testing fixture metadata.`n---`n# $name"
        }
        $script:SourceOnlySkillPath = Join-Path $script:PackageRoot "skills\gamma\SKILL.md"
    }

    It "allows external script and command references without counting source-only skills as shipping" {
        Add-Content -LiteralPath $script:SourceOnlySkillPath -Value 'Run scripts/external.py and /gamma in the external provider.'

        $result = Invoke-FixtureValidator
        $result.ExitCode | Should -Be 0
        $result.Output | Should -Match 'fixture-skills\s+portable-runtime\s+1\s+1'
        $result.Output | Should -Match 'PASS - ready package validation completed'
        $result.Output | Should -Not -Match 'FAIL -'
    }

    It "rejects a source-only directory without SKILL.md" {
        Remove-Item -LiteralPath $script:SourceOnlySkillPath

        $result = Invoke-FixtureValidator
        $result.ExitCode | Should -Be 1
        $result.Output | Should -Match ([regex]::Escape('fixture-skills skill missing: skills/gamma/SKILL.md'))
    }

    It "rejects a source-only frontmatter name that differs from its folder" {
        Set-FixtureSkill "gamma" "---`nname: wrong`ndescription: Use when testing fixture metadata.`n---"

        $result = Invoke-FixtureValidator
        $result.ExitCode | Should -Be 1
        $result.Output | Should -Match ([regex]::Escape("fixture-skills skill frontmatter name does not match folder: gamma (declares 'wrong')"))
    }

    It "rejects <Case> source-only descriptions" -ForEach @(
        @{ Case = "missing"; Description = ""; Diagnostic = "frontmatter missing description" }
        @{ Case = "non-discovery"; Description = "description: Fixture metadata."; Diagnostic = "description lacks discovery trigger" }
    ) {
        Set-FixtureSkill "gamma" "---`nname: gamma`n$Description`n---"

        $result = Invoke-FixtureValidator
        $result.ExitCode | Should -Be 1
        $result.Output | Should -Match ([regex]::Escape("fixture-skills skill ${Diagnostic}: gamma"))
    }

    It "rejects an unreferenced source-only support file in <Directory>" -ForEach @(
        @{ Directory = "references" }
        @{ Directory = "examples" }
        @{ Directory = "assets" }
        @{ Directory = "scripts" }
    ) {
        $supportDir = Join-Path $script:PackageRoot "skills\gamma\$Directory"
        New-Item -ItemType Directory -Path $supportDir -Force | Out-Null
        Set-Content -LiteralPath (Join-Path $supportDir "local.txt") -Value "fixture support"

        $result = Invoke-FixtureValidator
        $result.ExitCode | Should -Be 1
        $result.Output | Should -Match ([regex]::Escape("fixture-skills skill support file is not referenced by SKILL.md: gamma/$Directory/local.txt"))
    }

    It "accepts a mentioned source-only support file" {
        $supportDir = Join-Path $script:PackageRoot "skills\gamma\references"
        New-Item -ItemType Directory -Path $supportDir -Force | Out-Null
        Set-Content -LiteralPath (Join-Path $supportDir "local.txt") -Value "fixture support"
        Add-Content -LiteralPath $script:SourceOnlySkillPath -Value 'Read references/local.txt.'

        $result = Invoke-FixtureValidator
        $result.ExitCode | Should -Be 0
        $result.Output | Should -Match 'PASS - ready package validation completed'
    }

    It "continues rejecting source-only overlap with <List>" -ForEach @(
        @{ List = "default_skills" }
        @{ List = "optional_skills" }
    ) {
        $script:InstallManifest[$List] += "gamma"
        $script:InstallManifest | ConvertTo-Json | Set-Content -LiteralPath $script:InstallManifestPath
        Set-FixtureReadme 2

        $result = Invoke-FixtureValidator
        $result.ExitCode | Should -Be 1
        $result.Output | Should -Match ([regex]::Escape('fixture-skills exports source-only skills: gamma'))
    }

    It "continues rejecting unbundled scripts and source-only commands in installable skills" {
        Add-Content -LiteralPath (Join-Path $script:PackageRoot "skills\alpha\SKILL.md") -Value 'Run scripts/external.py and /gamma.'

        $result = Invoke-FixtureValidator
        $result.ExitCode | Should -Be 1
        $result.Output | Should -Match ([regex]::Escape('fixture-skills skill references unbundled script path: alpha -> scripts/external.py'))
        $result.Output | Should -Match ([regex]::Escape('fixture-skills skill references source-only skill command: alpha -> /gamma'))
    }
}
