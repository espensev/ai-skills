function Get-CodexEnvironmentObservation {
    param(
        [Parameter(Mandatory)][object] $Profile,
        [Parameter(Mandatory)][object] $Lock,
        [Parameter(Mandatory)][AllowEmptyCollection()][System.Collections.Generic.List[object]] $Reasons,
        [Parameter(Mandatory)][AllowEmptyCollection()][System.Collections.Generic.List[object]] $Checks
    )

    $providerProfile = $Profile.providers.codex
    $providerLock = $Lock.providers.codex
    $codexHome = Resolve-AiPath ([string]$providerProfile.homePath)
    $configPath = Resolve-AiPath ([string]$providerProfile.configPath)
    $version = Get-AiProviderVersion -Provider 'codex' -ProviderProfile $providerProfile -ProviderLock $providerLock -Reasons $Reasons -Checks $Checks

    $configDigest = Get-AiFileDigest $configPath
    $configModel = $null
    try {
        $configModel = Read-AiCodexConfig $configPath
        Add-AiCheck -Checks $Checks -Id 'provider.codex.config' -Result 'PASS' -Severity 'INFO' -ReasonCode 'CODEX_CONFIG_PARSED' -Owned $true -Evidence "digest=$configDigest"
    }
    catch {
        Add-AiReason -Reasons $Reasons -Code 'CODEX_CONFIG_PARSE_FAILED' -Status 'DRIFTED' -Severity 'ERROR' -Lane 'activation' -Provider 'codex' -ResourceId 'provider:codex' -Detail 'The Codex config could not be parsed by the safe observer.' -Evidence "digest=$configDigest"
        Add-AiCheck -Checks $Checks -Id 'provider.codex.config' -Result 'FAIL' -Severity 'ERROR' -ReasonCode 'CODEX_CONFIG_PARSE_FAILED' -Owned $true -Evidence "digest=$configDigest"
        $configModel = [pscustomobject][ordered]@{
            Marketplaces = [ordered]@{}
            Plugins = [ordered]@{}
            Hooks = [ordered]@{}
            Skills = @()
        }
    }

    $marketplaceRows = [System.Collections.Generic.List[object]]::new()
    $foreignMarketplaceDegraded = $false
    foreach ($resource in @($Profile.resources | Where-Object { $_.provider -ceq 'codex' -and $_.kind -ceq 'marketplace' } | Sort-Object id)) {
        $name = [string](Get-AiProperty $resource.desired 'name')
        $configured = @($configModel.Marketplaces.Keys) -ccontains $name
        $entry = if ($configured) { $configModel.Marketplaces[$name] } else { $null }
        $sourceType = [string](Get-AiProperty $entry 'SourceType')
        $sourceTypeMatches = $sourceType -ceq 'local'
        $source = [string](Get-AiProperty $entry 'Source')
        $sourceExists = $false
        $sourceManifestValid = $false
        if ($configured -and $sourceTypeMatches -and -not [string]::IsNullOrWhiteSpace($source)) {
            try {
                $resolvedSource = Resolve-AiPath $source
                $sourceExists = Test-Path -LiteralPath $resolvedSource -PathType Container
                if ($sourceExists) {
                    foreach ($relativeManifestPath in @(
                        '.agents\plugins\marketplace.json',
                        '.codex-plugin\marketplace.json',
                        'marketplace.json'
                    )) {
                        $manifestPath = Join-Path $resolvedSource $relativeManifestPath
                        if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
                            continue
                        }
                        try {
                            $manifest = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json -Depth 100
                            if ($manifest -is [System.Management.Automation.PSCustomObject]) {
                                $sourceManifestValid = $true
                                break
                            }
                        }
                        catch {
                            continue
                        }
                    }
                }
            }
            catch {
                $sourceExists = $false
                $sourceManifestValid = $false
            }
        }
        $sourceMatches = $false
        $expectedSource = [string](Get-AiProperty $resource.desired 'sourcePath')
        if (-not [string]::IsNullOrWhiteSpace($expectedSource) -and -not [string]::IsNullOrWhiteSpace($source)) {
            try {
                $sourceMatches = (Resolve-AiPath $source).Equals(
                    (Resolve-AiPath $expectedSource),
                    [System.StringComparison]::OrdinalIgnoreCase
                )
            }
            catch {
                $sourceMatches = $false
            }
        }

        $managed = [string]$resource.ownership -ceq 'managed'
        $managedRegistrationHealthy = $configured -and
            $sourceTypeMatches -and
            $sourceExists -eq $true -and
            $sourceManifestValid -eq $true -and
            $sourceMatches -eq $true
        if ($managed -and -not $managedRegistrationHealthy) {
            Add-AiReason -Reasons $Reasons -Code 'OWNED_MARKETPLACE_MISSING' -Status 'DRIFTED' -Severity 'ERROR' -Lane 'activation' -Provider 'codex' -ResourceId ([string]$resource.id) -Detail 'The managed Codex marketplace is absent, incomplete, unavailable, or points at the wrong source.' -Evidence "configured=$configured;sourceTypeMatches=$sourceTypeMatches;sourceExists=$sourceExists;manifestValid=$sourceManifestValid;sourceMatches=$sourceMatches"
        }
        $foreignMarketplaceIssue = $false
        if (-not $managed -and $configured -and $sourceTypeMatches -and $sourceExists -eq $false) {
            $foreignMarketplaceDegraded = $true
            $foreignMarketplaceIssue = $true
            Add-AiReason -Reasons $Reasons -Code 'FOREIGN_MARKETPLACE_ROOT_MISSING' -Status 'DEGRADED_FOREIGN_MARKETPLACE' -Severity 'WARNING' -Lane 'compatibility' -Provider 'codex' -ResourceId ([string]$resource.id) -Detail 'An observed foreign Codex marketplace points at a missing local root.' -Evidence "marketplace=$name"
        }
        elseif (-not $managed -and $configured -and $sourceTypeMatches -and $sourceManifestValid -eq $false) {
            $foreignMarketplaceDegraded = $true
            $foreignMarketplaceIssue = $true
            Add-AiReason -Reasons $Reasons -Code 'FOREIGN_MARKETPLACE_MANIFEST_INVALID' -Status 'DEGRADED_FOREIGN_MARKETPLACE' -Severity 'WARNING' -Lane 'compatibility' -Provider 'codex' -ResourceId ([string]$resource.id) -Detail 'An observed foreign Codex marketplace root has no supported manifest.' -Evidence "marketplace=$name"
        }
        $marketplaceReasonCode = if ($managed) {
            'OWNED_MARKETPLACE_MISSING'
        }
        elseif ($sourceExists -eq $false) {
            'FOREIGN_MARKETPLACE_ROOT_MISSING'
        }
        else {
            'FOREIGN_MARKETPLACE_MANIFEST_INVALID'
        }
        Add-AiCheck -Checks $Checks `
            -Id "resource.$($resource.id).registration" `
            -Result $(if ($managedRegistrationHealthy -or (-not $managed -and -not $foreignMarketplaceIssue)) { 'PASS' } elseif (-not $managed) { 'DEGRADED' } else { 'FAIL' }) `
            -Severity $(if ($managed) { 'ERROR' } else { 'WARNING' }) `
            -ReasonCode $marketplaceReasonCode `
            -Owned $managed `
            -Evidence "configured=$configured;sourceTypeMatches=$sourceTypeMatches;sourceExists=$sourceExists;manifestValid=$sourceManifestValid;sourceMatches=$sourceMatches"

        $marketplaceRows.Add([pscustomobject][ordered]@{
            Id = [string]$resource.id
            Name = $name
            Ownership = [string]$resource.ownership
            Configured = $configured
            SourceType = $sourceType
            SourceTypeMatches = $sourceTypeMatches
            SourceExists = $sourceExists
            SourceManifestValid = $sourceManifestValid
            SourceMatches = $sourceMatches
        }) | Out-Null
    }

    $controlPlaneResult = Invoke-AiProcess -Command ([string]$providerProfile.command) -Arguments @('plugin', 'marketplace', 'list', '--json')
    $controlPlaneTimedOut = [bool](Get-AiProperty $controlPlaneResult 'TimedOut' $false)
    $controlPlaneAvailable = -not $controlPlaneTimedOut -and $controlPlaneResult.Found -and $controlPlaneResult.ExitCode -eq 0
    if ($controlPlaneAvailable) {
        try {
            $null = $controlPlaneResult.StdOut | ConvertFrom-Json -Depth 50
        }
        catch {
            $controlPlaneAvailable = $false
        }
    }
    if (-not $controlPlaneAvailable) {
        Add-AiReason -Reasons $Reasons -Code 'CODEX_CONTROL_PLANE_UNAVAILABLE' -Status 'DEGRADED_FOREIGN_MARKETPLACE' -Severity 'WARNING' -Lane 'compatibility' -Provider 'codex' -ResourceId 'provider:codex' -Detail 'Codex marketplace enumeration is unavailable; owned resources were observed through the static fallback.' -Evidence "exitCode=$($controlPlaneResult.ExitCode);timedOut=$controlPlaneTimedOut;foreignMarketplaceDegraded=$foreignMarketplaceDegraded"
    }
    Add-AiCheck -Checks $Checks -Id 'provider.codex.control-plane' -Result $(if ($controlPlaneAvailable) { 'PASS' } else { 'DEGRADED' }) -Severity $(if ($controlPlaneAvailable) { 'INFO' } else { 'WARNING' }) -ReasonCode 'CODEX_CONTROL_PLANE_UNAVAILABLE' -Owned $false -Evidence "exitCode=$($controlPlaneResult.ExitCode);timedOut=$controlPlaneTimedOut;fallback=static-owned-state"

    $pluginRows = [System.Collections.Generic.List[object]]::new()
    foreach ($resource in @($Profile.resources | Where-Object { $_.provider -ceq 'codex' -and $_.kind -ceq 'plugin' } | Sort-Object id)) {
        $name = [string](Get-AiProperty $resource.desired 'name')
        $configured = $configModel.Plugins.Contains($name)
        $enabled = if ($configured) { Get-AiProperty $configModel.Plugins[$name] 'Enabled' } else { $null }
        $desiredEnabled = Get-AiProperty $resource.desired 'enabled'
        if ($null -ne $desiredEnabled -and ([bool]$enabled -ne [bool]$desiredEnabled)) {
            Add-AiReason -Reasons $Reasons -Code 'OWNED_PLUGIN_DISABLED' -Status 'DRIFTED' -Severity 'ERROR' -Lane 'activation' -Provider 'codex' -ResourceId ([string]$resource.id) -Detail 'The managed Codex plugin enablement does not match intent.' -Evidence "configured=$configured;enabled=$enabled;desired=$desiredEnabled"
        }

        $lockResource = Get-AiLockResource -Lock $Lock -Id ([string]$resource.id)
        $payload = $null
        if (-not [string]::IsNullOrWhiteSpace([string](Get-AiProperty $resource.desired 'sourceRoot'))) {
            $payload = Compare-AiLockedPayload -ProfileResource $resource -LockResource $lockResource -Reasons $Reasons -Checks $Checks
        }

        $trustRecordKey = [string](Get-AiProperty $resource.desired 'trustRecordKey')
        $trustRecordPresent = $true
        $trustHashValidated = $true
        if (-not [string]::IsNullOrWhiteSpace($trustRecordKey)) {
            $trustRecord = if (@($configModel.Hooks.Keys) -ccontains $trustRecordKey) { $configModel.Hooks[$trustRecordKey] } else { $null }
            $trustRecordPresent = $null -ne $trustRecord -and [bool](Get-AiProperty $trustRecord 'TrustRecordPresent' $false)
            $expectedTrustHash = [string](Get-AiProperty $lockResource 'trustHash')
            $actualTrustHash = [string](Get-AiProperty $trustRecord 'TrustedHash')
            $trustHashValidated = $trustRecordPresent -and
                -not [string]::IsNullOrWhiteSpace($expectedTrustHash) -and
                -not [string]::IsNullOrWhiteSpace($actualTrustHash) -and
                $actualTrustHash.Equals($expectedTrustHash, [System.StringComparison]::OrdinalIgnoreCase)
            $trustReasonCode = if ([string]::IsNullOrWhiteSpace($expectedTrustHash)) {
                'OWNED_HOOK_TRUST_HASH_NOT_LOCKED'
            }
            elseif (-not $trustRecordPresent) {
                'OWNED_HOOK_TRUST_RECORD_MISSING'
            }
            else {
                'OWNED_HOOK_TRUST_HASH_MISMATCH'
            }
            if (-not $trustHashValidated) {
                $trustDetail = switch ($trustReasonCode) {
                    'OWNED_HOOK_TRUST_HASH_NOT_LOCKED' { 'The lock has no accepted hook trust hash for the managed plugin.'; break }
                    'OWNED_HOOK_TRUST_RECORD_MISSING' { 'The managed plugin hook has no persisted trust record.'; break }
                    default { 'The persisted hook trust hash does not match the accepted lock.' }
                }
                Add-AiReason -Reasons $Reasons -Code $trustReasonCode -Status 'PENDING_TRUST' -Severity 'ERROR' -Lane 'trust' -Provider 'codex' -ResourceId ([string]$resource.id) -Detail $trustDetail -Evidence "recordPresent=$trustRecordPresent;expectedHashPresent=$(-not [string]::IsNullOrWhiteSpace($expectedTrustHash));actualHashPresent=$(-not [string]::IsNullOrWhiteSpace($actualTrustHash));hashMatches=$trustHashValidated"
            }
            Add-AiCheck -Checks $Checks -Id "resource.$($resource.id).trust" -Result $(if ($trustHashValidated) { 'PASS' } else { 'FAIL' }) -Severity $(if ($trustHashValidated) { 'INFO' } else { 'ERROR' }) -ReasonCode $(if ($trustHashValidated) { 'OWNED_HOOK_TRUST_VALIDATED' } else { $trustReasonCode }) -Owned $true -Evidence "recordPresent=$trustRecordPresent;expectedHashPresent=$(-not [string]::IsNullOrWhiteSpace($expectedTrustHash));actualHashPresent=$(-not [string]::IsNullOrWhiteSpace($actualTrustHash));hashMatches=$trustHashValidated"
        }

        $pluginRows.Add([pscustomobject][ordered]@{
            Id = [string]$resource.id
            Name = $name
            Ownership = [string]$resource.ownership
            Configured = $configured
            Enabled = $enabled
            Version = [string](Get-AiProperty $lockResource 'version')
            TrustRecordPresent = $trustRecordPresent
            TrustHashValidated = $trustHashValidated
            Payload = $payload
        }) | Out-Null
    }

    $hookRows = [System.Collections.Generic.List[object]]::new()
    foreach ($resource in @($Profile.resources | Where-Object { $_.provider -ceq 'codex' -and $_.kind -ceq 'hook' } | Sort-Object id)) {
        $payload = Compare-AiLockedPayload -ProfileResource $resource -LockResource (Get-AiLockResource -Lock $Lock -Id ([string]$resource.id)) -Reasons $Reasons -Checks $Checks
        $hookRows.Add([pscustomobject][ordered]@{
            Id = [string]$resource.id
            Ownership = [string]$resource.ownership
            Payload = $payload
        }) | Out-Null
    }

    $skillEntries = @($configModel.Skills)
    $disabledCount = @($skillEntries | Where-Object { $_.Enabled -eq $false }).Count
    $missingPathCount = 0
    foreach ($entry in $skillEntries) {
        $path = [string](Get-AiProperty $entry 'Path')
        if ([string]::IsNullOrWhiteSpace($path)) {
            continue
        }
        try {
            if (-not (Test-Path -LiteralPath (Resolve-AiPath $path) -PathType Leaf)) {
                $missingPathCount++
            }
        }
        catch {
            $missingPathCount++
        }
    }
    if ($missingPathCount -gt 0) {
        Add-AiReason -Reasons $Reasons -Code 'SKILL_SUPPRESSION_PATH_MISSING' -Status 'DRIFTED' -Severity 'WARNING' -Lane 'activation' -Provider 'codex' -ResourceId 'skill-policy:codex' -Detail 'Codex has path-specific skill suppressions whose target files no longer exist.' -Evidence "entries=$($skillEntries.Count);missingPaths=$missingPathCount"
    }
    Add-AiCheck -Checks $Checks -Id 'resource.skill-policy:codex.paths' -Result $(if ($missingPathCount -eq 0) { 'PASS' } else { 'FAIL' }) -Severity $(if ($missingPathCount -eq 0) { 'INFO' } else { 'WARNING' }) -ReasonCode 'SKILL_SUPPRESSION_PATH_MISSING' -Owned $false -Evidence "entries=$($skillEntries.Count);missingPaths=$missingPathCount"

    return [pscustomobject][ordered]@{
        Version = $version
        Home = '{CODEX_HOME}'
        Config = '{CODEX_HOME}/config.toml'
        ConfigDigest = $configDigest
        ControlPlane = [pscustomobject][ordered]@{
            Available = $controlPlaneAvailable
            TimedOut = $controlPlaneTimedOut
            ExitCode = $controlPlaneResult.ExitCode
            ObservationMode = if ($controlPlaneAvailable) { 'cli-and-static' } else { 'static-owned-state-fallback' }
        }
        Marketplaces = @($marketplaceRows)
        Plugins = @($pluginRows)
        Hooks = @($hookRows)
        Skills = [pscustomobject][ordered]@{
            PolicyEntries = $skillEntries.Count
            DisabledEntries = $disabledCount
            MissingPathEntries = $missingPathCount
        }
    }
}
