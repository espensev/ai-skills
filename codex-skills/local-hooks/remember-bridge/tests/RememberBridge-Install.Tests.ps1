Describe 'Install-RememberBridge.ps1' {
    BeforeAll {
        $script:PackageRoot = Split-Path -Parent $PSScriptRoot
        $script:Installer = Join-Path $script:PackageRoot 'Install-RememberBridge.ps1'
        $script:SourceScript = Join-Path $script:PackageRoot 'Invoke-RememberBridge.py'
        $script:ExpectedInstallationId = 'ca96d510-7d87-4cec-8e1a-bd8fc3866903'

        function New-FakeBridgeEnvironment {
            $root = Join-Path $TestDrive ([guid]::NewGuid().ToString('N'))
            $null = New-Item -ItemType Directory -Path $root -Force

            $goodVerifier = Join-Path $root 'good-verifier.ps1'
            @"
[pscustomobject]@{
    status = 'VERIFIED'
    machineId = 'snd-desk'
    instanceId = '$($script:ExpectedInstallationId)'
}
"@ | Set-Content -LiteralPath $goodVerifier -Encoding utf8NoBOM

            $badVerifier = Join-Path $root 'bad-verifier.ps1'
            @'
[pscustomobject]@{
    status = 'MISMATCH'
    machineId = 'wrong-machine'
    instanceId = 'wrong-installation'
}
'@ | Set-Content -LiteralPath $badVerifier -Encoding utf8NoBOM

            [pscustomobject]@{
                Root = $root
                TargetRoot = Join-Path $root 'bridge'
                Installed = Join-Path (Join-Path (Join-Path $root 'bridge') 'bin') 'Invoke-RememberBridge.py'
                GoodVerifier = $goodVerifier
                BadVerifier = $badVerifier
            }
        }

        function Invoke-TestInstaller {
            param(
                [switch] $Check,
                [switch] $NoOverride,
                [string] $VerifierPath = $script:Fake.GoodVerifier
            )

            $parameters = @{
                TargetRoot = $script:Fake.TargetRoot
                VerifierPath = $VerifierPath
            }
            if (-not $NoOverride) {
                $parameters.AllowTestOnlyTargetRootOverride = $true
            }
            if ($Check) {
                $parameters.Check = $true
            }

            & $script:Installer @parameters
        }

        function Get-Sha256 {
            param([Parameter(Mandatory)][string] $Path)
            (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
        }
    }

    BeforeEach {
        $script:Fake = New-FakeBridgeEnvironment
    }

    It 'ships the bridge script next to the installer' {
        Test-Path -LiteralPath $script:Installer -PathType Leaf | Should -BeTrue
        Test-Path -LiteralPath $script:SourceScript -PathType Leaf | Should -BeTrue
    }

    It 'refuses an alternate target without the test-only override' {
        { Invoke-TestInstaller -Check -NoOverride } | Should -Throw -ExpectedMessage '*Refusing alternate bridge target*'
        Test-Path -LiteralPath $script:Fake.TargetRoot | Should -BeFalse
    }

    It 'refuses a filesystem root as the target' {
        { & $script:Installer -TargetRoot 'C:\' -AllowTestOnlyTargetRootOverride -Check } | Should -Throw -ExpectedMessage '*filesystem root*'
    }

    It 'reports drift for a missing install in -Check mode without touching the target' {
        { Invoke-TestInstaller -Check } | Should -Throw -ExpectedMessage '*missing:*'
        Test-Path -LiteralPath $script:Fake.TargetRoot | Should -BeFalse
    }

    It 'refuses to install when the machine verifier does not return VERIFIED' {
        { Invoke-TestInstaller -VerifierPath $script:Fake.BadVerifier } | Should -Throw -ExpectedMessage '*Machine identity mismatch*'
        Test-Path -LiteralPath $script:Fake.Installed | Should -BeFalse
    }

    It 'installs into the bin folder under the target root, then reports CURRENT and UNCHANGED' {
        $result = Invoke-TestInstaller
        $result.Status | Should -Be 'INSTALLED'
        $result.MachineId | Should -Be 'snd-desk'
        $result.Backup | Should -BeNullOrEmpty
        Test-Path -LiteralPath $script:Fake.Installed -PathType Leaf | Should -BeTrue
        Get-Sha256 $script:Fake.Installed | Should -Be (Get-Sha256 $script:SourceScript)
        ($result.Probe -join "`n") | Should -Match 'plugin_root=|probe skipped'

        $check = Invoke-TestInstaller -Check
        $check.Status | Should -Be 'CURRENT'

        $again = Invoke-TestInstaller
        $again.Status | Should -Be 'UNCHANGED'
        $again.Backup | Should -BeNullOrEmpty
    }

    It 'backs up a drifted installed copy before replacing it' {
        $null = Invoke-TestInstaller
        Add-Content -LiteralPath $script:Fake.Installed -Value '# drift'

        { Invoke-TestInstaller -Check } | Should -Throw -ExpectedMessage '*hash mismatch*'

        $result = Invoke-TestInstaller
        $result.Status | Should -Be 'INSTALLED'
        $result.Backup | Should -Not -BeNullOrEmpty
        $backupCopy = Join-Path $result.Backup 'Invoke-RememberBridge.py'
        Test-Path -LiteralPath $backupCopy -PathType Leaf | Should -BeTrue
        (Get-Content -LiteralPath $backupCopy -Raw) | Should -Match '# drift'
        Get-Sha256 $script:Fake.Installed | Should -Be (Get-Sha256 $script:SourceScript)
    }

    It 'honours -WhatIf by not writing anything' {
        $null = & $script:Installer -TargetRoot $script:Fake.TargetRoot -AllowTestOnlyTargetRootOverride -VerifierPath $script:Fake.GoodVerifier -WhatIf
        Test-Path -LiteralPath $script:Fake.Installed | Should -BeFalse
    }
}
