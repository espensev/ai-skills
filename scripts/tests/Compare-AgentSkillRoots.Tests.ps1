BeforeAll {
    $script:RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))

    # The comparator resolves its manifests from its own location, so a copy
    # inside a synthetic repo compares against a small package whose bytes the
    # tests control: default "alpha", optional "beta", source-only "gamma".
    $script:FakeRepo = Join-Path $TestDrive "repo"
    $scriptsDir = Join-Path $script:FakeRepo "scripts"
    New-Item -ItemType Directory -Path $scriptsDir -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $script:RepoRoot "scripts\Compare-AgentSkillRoots.ps1") -Destination $scriptsDir
    Set-Content -LiteralPath (Join-Path $scriptsDir "retired-skills.json") -Value '{"schema":"ai-skills/retired-skills/v1","retired_skills":[]}'
    $script:Comparator = Join-Path $scriptsDir "Compare-AgentSkillRoots.ps1"

    $script:PackageRoot = Join-Path $script:FakeRepo "claude-skills"
    New-Item -ItemType Directory -Path (Join-Path $script:PackageRoot "package") -Force | Out-Null
    @{
        default_skills = @("alpha")
        optional_skills = @("beta")
        source_only_skills = @("gamma")
        contract_files = @()
        optional_contract_files = @()
        runtime_files = @("scripts/tool.py")
        runtime_directories = @()
    } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $script:PackageRoot "package\install-manifest.json")

    function Write-Bytes {
        param ([string]$Path, [byte[]]$Bytes)
        New-Item -ItemType Directory -Path (Split-Path -Parent $Path) -Force | Out-Null
        [System.IO.File]::WriteAllBytes($Path, $Bytes)
    }

    function Write-Text {
        param ([string]$Path, [string]$Text)
        Write-Bytes $Path ([System.Text.UTF8Encoding]::new($false).GetBytes($Text))
    }

    Write-Text (Join-Path $script:PackageRoot "skills\alpha\SKILL.md") "# alpha`nfirst line`nsecond line`n"
    Write-Text (Join-Path $script:PackageRoot "skills\alpha\notes.md") "alpha notes`n"
    Write-Bytes (Join-Path $script:PackageRoot "skills\alpha\icon.png") ([byte[]](0x89, 0x50, 0x4E, 0x47, 0x0A, 0x00, 0x0A))
    Write-Text (Join-Path $script:PackageRoot "skills\beta\SKILL.md") "# beta`n"
    Write-Text (Join-Path $script:PackageRoot "skills\gamma\SKILL.md") "# gamma`n"
    Write-Text (Join-Path $script:PackageRoot "scripts\tool.py") "print('tool')`n"

    function New-InstalledRoot {
        param ([string]$Name)

        $root = Join-Path $TestDrive $Name
        New-Item -ItemType Directory -Path (Join-Path $root "scripts") -Force | Out-Null
        foreach ($skill in @("alpha", "beta")) {
            Copy-Item -LiteralPath (Join-Path $script:PackageRoot "skills\$skill") -Destination $root -Recurse
        }
        Copy-Item -LiteralPath (Join-Path $script:PackageRoot "scripts\tool.py") -Destination (Join-Path $root "scripts")
        return $root
    }

    function ConvertTo-CrLf {
        param ([string]$Path)
        $text = [System.IO.File]::ReadAllText($Path).Replace("`r`n", "`n").Replace("`n", "`r`n")
        Write-Text $Path $text
    }

    function Invoke-Comparator {
        param ([string]$Root, [switch]$IncludeExtra)

        $arguments = @("-NoProfile", "-File", $script:Comparator, "-Provider", "Claude", "-ClaudeTargets", $Root)
        if ($IncludeExtra) {
            $arguments += "-IncludeExtra"
        }
        return ((& pwsh @arguments 2>&1) | Out-String)
    }

    function Get-FindingPattern {
        param ([string]$Status, [string]$Path, [string]$Root)
        return [regex]::Escape("FINDING $Status [Claude] Skill $Path <- $Root")
    }

    $script:PassLine = "PASS - local agent skill roots match manifest-listed files"
}

Describe "Compare-AgentSkillRoots content comparison" {
    It "does not report copies that differ from source only by CRLF line endings" {
        $root = New-InstalledRoot "crlf-only"
        foreach ($relative in @("alpha\SKILL.md", "alpha\notes.md", "scripts\tool.py")) {
            ConvertTo-CrLf (Join-Path $root $relative)
            (Get-FileHash -LiteralPath (Join-Path $root $relative)).Hash |
                Should -Not -Be (Get-FileHash -LiteralPath (Join-Path $script:PackageRoot ($relative -replace '^alpha', 'skills\alpha'))).Hash
        }

        $output = Invoke-Comparator $root
        $LASTEXITCODE | Should -Be 0
        $output | Should -Not -Match "FINDING"
        $output | Should -Match ([regex]::Escape($script:PassLine))
    }

    It "reports real content changes as Stale even when line endings also differ" {
        $root = New-InstalledRoot "real-change"
        Write-Text (Join-Path $root "alpha\SKILL.md") "# ALPHA`r`nfirst line`r`nsecond line`r`n"
        Write-Text (Join-Path $root "alpha\notes.md") "alpha notes`nlocal edit`n"

        $output = Invoke-Comparator $root
        $output | Should -Match (Get-FindingPattern "Stale" "alpha/SKILL.md" $root)
        $output | Should -Match (Get-FindingPattern "Stale" "alpha/notes.md" $root)
    }

    It "compares binary files raw so a line-ending rewrite is Stale" {
        $root = New-InstalledRoot "binary"
        Write-Bytes (Join-Path $root "alpha\icon.png") ([byte[]](0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x00, 0x0D, 0x0A))

        $output = Invoke-Comparator $root
        $output | Should -Match (Get-FindingPattern "Stale" "alpha/icon.png" $root)
    }
}

Describe "Compare-AgentSkillRoots skill directories without SKILL.md" {
    It "reports a source-only skill directory without SKILL.md as Missing, but does not demand the skill" {
        $root = New-InstalledRoot "source-only"
        $output = Invoke-Comparator $root
        $output | Should -Not -Match "gamma"

        New-Item -ItemType Directory -Path (Join-Path $root "gamma") -Force | Out-Null
        Set-Content -LiteralPath (Join-Path $root "gamma\leftover.txt") -Value "orphaned"

        $output = Invoke-Comparator $root
        $output | Should -Match (Get-FindingPattern "Missing" "gamma/SKILL.md" $root)
    }

    It "reports a manifest skill directory that was emptied as Missing SKILL.md" {
        $root = New-InstalledRoot "emptied"
        Get-ChildItem -LiteralPath (Join-Path $root "beta") -Force | Remove-Item -Recurse -Force

        $output = Invoke-Comparator $root
        $output | Should -Match (Get-FindingPattern "Missing" "beta/SKILL.md" $root)
    }

    It "reports an orphan directory without SKILL.md under -IncludeExtra, not manifest-owned or dot directories" {
        $root = New-InstalledRoot "orphan"
        New-Item -ItemType Directory -Path (Join-Path $root "orphan") -Force | Out-Null
        Set-Content -LiteralPath (Join-Path $root "orphan\readme.txt") -Value "no skill here"
        New-Item -ItemType Directory -Path (Join-Path $root ".system") -Force | Out-Null

        $output = Invoke-Comparator $root -IncludeExtra
        $output | Should -Match (Get-FindingPattern "Extra" "orphan" $root)
        $output | Should -Not -Match ([regex]::Escape("Skill scripts <-"))
        $output | Should -Not -Match ([regex]::Escape(".system"))
    }
}

Describe "Compare-AgentSkillRoots path reporting" {
    It "attributes a stray file named NUL to its owning skill" {
        $root = New-InstalledRoot "device-name"
        $nulPath = "\\?\" + (Join-Path $root "alpha\NUL")
        [System.IO.File]::WriteAllText($nulPath, "stray redirect output")
        try {
            $output = Invoke-Comparator $root
            $output | Should -Match (Get-FindingPattern "ExtraFile" "alpha/NUL" $root)
            $output | Should -Not -Match ([regex]::Escape("//./NUL"))
        } finally {
            # Remove-Item cannot delete a DOS device name; TestDrive teardown would fail.
            [System.IO.File]::Delete($nulPath)
        }
    }
}
