function Get-ClaudeEnvironmentObservation {
    param(
        [Parameter(Mandatory)][object] $Profile,
        [Parameter(Mandatory)][object] $Lock,
        [Parameter(Mandatory)][AllowEmptyCollection()][System.Collections.Generic.List[object]] $Reasons,
        [Parameter(Mandatory)][AllowEmptyCollection()][System.Collections.Generic.List[object]] $Checks
    )

    $providerProfile = $Profile.providers.claude
    $providerLock = $Lock.providers.claude
    $settingsPath = Resolve-AiPath ([string]$providerProfile.configPath)
    $version = Get-AiProviderVersion -Provider 'claude' -ProviderProfile $providerProfile -ProviderLock $providerLock -Reasons $Reasons -Checks $Checks
    $settingsDigest = Get-AiFileDigest $settingsPath
    $settings = $null
    try {
        if (-not (Test-Path -LiteralPath $settingsPath -PathType Leaf)) {
            throw 'settings file missing'
        }
        $settings = Get-Content -Raw -LiteralPath $settingsPath | ConvertFrom-Json -Depth 100
        Add-AiCheck -Checks $Checks -Id 'provider.claude.config' -Result 'PASS' -Severity 'INFO' -ReasonCode 'CLAUDE_CONFIG_PARSED' -Owned $true -Evidence "digest=$settingsDigest"
    }
    catch {
        Add-AiReason -Reasons $Reasons -Code 'CLAUDE_CONFIG_PARSE_FAILED' -Status 'DRIFTED' -Severity 'ERROR' -Lane 'activation' -Provider 'claude' -ResourceId 'provider:claude' -Detail 'The Claude settings file could not be parsed by the safe observer.' -Evidence "digest=$settingsDigest"
        Add-AiCheck -Checks $Checks -Id 'provider.claude.config' -Result 'FAIL' -Severity 'ERROR' -ReasonCode 'CLAUDE_CONFIG_PARSE_FAILED' -Owned $true -Evidence "digest=$settingsDigest"
        $settings = [pscustomobject][ordered]@{}
    }

    $enabledPlugins = Get-AiProperty $settings 'enabledPlugins'
    $declaredPluginNames = @(
        if ($null -ne $enabledPlugins) {
            $enabledPlugins.PSObject.Properties.Name | Sort-Object -Unique
        }
    )

    $registryPathValue = [string](Get-AiProperty $providerProfile 'pluginRegistryPath')
    $registryVersion = $null
    $registryConfigured = -not [string]::IsNullOrWhiteSpace($registryPathValue)
    $registryFilePresent = $false
    $registryParsed = $false
    $registryPluginsTablePresent = $false
    $registryAvailable = $false
    $registryRecords = [ordered]@{}
    $pluginIdCount = 0
    $pluginRecordCount = 0
    $missingInstallPathCount = 0
    if ($registryConfigured) {
        try {
            $registryPath = Resolve-AiPath $registryPathValue
            $registryFilePresent = Test-Path -LiteralPath $registryPath -PathType Leaf
            if ($registryFilePresent) {
                $registry = Get-Content -Raw -LiteralPath $registryPath | ConvertFrom-Json -Depth 100
                $registryParsed = $true
                $registryVersion = Get-AiProperty $registry 'version'
                $pluginsObject = Get-AiProperty $registry 'plugins'
                $registryPluginsTablePresent = $null -ne $pluginsObject -and
                    $pluginsObject -is [System.Management.Automation.PSCustomObject]
                if ($registryPluginsTablePresent) {
                    foreach ($property in @($pluginsObject.PSObject.Properties | Sort-Object Name)) {
                        $records = @($property.Value | Where-Object { $null -ne $_ })
                        $registryRecords[[string]$property.Name] = $records
                        $pluginIdCount++
                        $pluginRecordCount += $records.Count
                        foreach ($record in $records) {
                            $installPath = [string](Get-AiProperty $record 'installPath')
                            try {
                                if ([string]::IsNullOrWhiteSpace($installPath) -or -not (Test-Path -LiteralPath (Resolve-AiPath $installPath) -PathType Container)) {
                                    $missingInstallPathCount++
                                }
                            }
                            catch {
                                $missingInstallPathCount++
                            }
                        }
                    }
                    $registryAvailable = $true
                }
            }
        }
        catch {
            $registryAvailable = $false
        }
    }

    $uncorrelatedDeclaredPluginNames = @(
        if ($registryAvailable) {
            $declaredPluginNames | Where-Object {
                -not (@($registryRecords.Keys) -ccontains [string]$_) -or @($registryRecords[$_]).Count -eq 0
            }
        }
        else {
            $declaredPluginNames
        }
    )
    if (-not $registryAvailable) {
        Add-AiReason -Reasons $Reasons -Code 'CLAUDE_PLUGIN_REGISTRY_UNAVAILABLE' -Status 'DRIFTED' -Severity 'ERROR' -Lane 'artifact' -Provider 'claude' -ResourceId 'plugin-registry:claude' -Detail 'The Claude plugin registry is missing, unparseable, or has no plugins table.' -Evidence "configured=$registryConfigured;filePresent=$registryFilePresent;parsed=$registryParsed;pluginsTablePresent=$registryPluginsTablePresent"
    }
    elseif ($uncorrelatedDeclaredPluginNames.Count -gt 0) {
        Add-AiReason -Reasons $Reasons -Code 'CLAUDE_PLUGIN_RECORD_MISSING' -Status 'DRIFTED' -Severity 'ERROR' -Lane 'artifact' -Provider 'claude' -ResourceId 'plugin-registry:claude' -Detail 'Claude declares enabled-plugin entries that have no corresponding registry records.' -Evidence "declared=$($declaredPluginNames.Count);missingRecords=$($uncorrelatedDeclaredPluginNames.Count)"
    }
    if ($missingInstallPathCount -gt 0) {
        Add-AiReason -Reasons $Reasons -Code 'CLAUDE_PLUGIN_RECORD_PATH_MISSING' -Status 'DRIFTED' -Severity 'WARNING' -Lane 'artifact' -Provider 'claude' -ResourceId 'plugin-registry:claude' -Detail 'Claude has installed-plugin records whose cache path is missing.' -Evidence "ids=$pluginIdCount;records=$pluginRecordCount;missingPaths=$missingInstallPathCount"
    }
    $registryHealthy = $registryAvailable -and
        $uncorrelatedDeclaredPluginNames.Count -eq 0 -and
        $missingInstallPathCount -eq 0
    $registryReasonCode = if (-not $registryAvailable) {
        'CLAUDE_PLUGIN_REGISTRY_UNAVAILABLE'
    }
    elseif ($uncorrelatedDeclaredPluginNames.Count -gt 0) {
        'CLAUDE_PLUGIN_RECORD_MISSING'
    }
    else {
        'CLAUDE_PLUGIN_RECORD_PATH_MISSING'
    }
    Add-AiCheck -Checks $Checks -Id 'provider.claude.plugin-registry' -Result $(if ($registryHealthy) { 'PASS' } else { 'FAIL' }) -Severity $(if (-not $registryAvailable -or $uncorrelatedDeclaredPluginNames.Count -gt 0) { 'ERROR' } elseif ($missingInstallPathCount -gt 0) { 'WARNING' } else { 'INFO' }) -ReasonCode $registryReasonCode -Owned $false -Evidence "available=$registryAvailable;version=$registryVersion;ids=$pluginIdCount;records=$pluginRecordCount;missingPaths=$missingInstallPathCount;declared=$($declaredPluginNames.Count);missingRecords=$($uncorrelatedDeclaredPluginNames.Count)"

    $hookRows = [System.Collections.Generic.List[object]]::new()
    foreach ($resource in @($Profile.resources | Where-Object { $_.provider -ceq 'claude' -and $_.kind -ceq 'hook' } | Sort-Object id)) {
        $payload = Compare-AiLockedPayload -ProfileResource $resource -LockResource (Get-AiLockResource -Lock $Lock -Id ([string]$resource.id)) -Reasons $Reasons -Checks $Checks
        $registrationContains = ([string](Get-AiProperty $resource.desired 'registrationContains')).Replace('\', '/')
        $registrationPresent = $true
        if (-not [string]::IsNullOrWhiteSpace($registrationContains)) {
            $registrationPresent = $false
            $hooksObject = Get-AiProperty $settings 'hooks'
            $stopHandlers = @()
            if ($null -ne $hooksObject) {
                $stopProperty = $hooksObject.PSObject.Properties['Stop']
                if ($null -ne $stopProperty) {
                    foreach ($registration in @($stopProperty.Value)) {
                        $stopHandlers += @((Get-AiProperty $registration 'hooks' @()))
                    }
                }
            }
            foreach ($handler in $stopHandlers) {
                $command = ([string](Get-AiProperty $handler 'command')).Replace('\', '/')
                if ($command.Contains($registrationContains, [System.StringComparison]::OrdinalIgnoreCase)) {
                    $registrationPresent = $true
                    break
                }
            }
            if (-not $registrationPresent) {
                Add-AiReason -Reasons $Reasons -Code 'CLAUDE_HANDOFF_REGISTRATION_MISSING' -Status 'DRIFTED' -Severity 'ERROR' -Lane 'activation' -Provider 'claude' -ResourceId ([string]$resource.id) -Detail 'The managed Claude Stop registration is absent.' -Evidence "handler=$registrationContains"
            }
            Add-AiCheck -Checks $Checks -Id "resource.$($resource.id).registration" -Result $(if ($registrationPresent) { 'PASS' } else { 'FAIL' }) -Severity $(if ($registrationPresent) { 'INFO' } else { 'ERROR' }) -ReasonCode 'CLAUDE_HANDOFF_REGISTRATION_MISSING' -Owned $true -Evidence "registrationPresent=$registrationPresent"
        }

        $hookRows.Add([pscustomobject][ordered]@{
            Id = [string]$resource.id
            Ownership = [string]$resource.ownership
            RegistrationPresent = $registrationPresent
            Payload = $payload
        }) | Out-Null
    }

    $pluginRows = [System.Collections.Generic.List[object]]::new()
    foreach ($resource in @($Profile.resources | Where-Object { $_.provider -ceq 'claude' -and $_.kind -ceq 'plugin' } | Sort-Object id)) {
        $name = [string](Get-AiProperty $resource.desired 'name')
        $enabled = $null
        $configured = $false
        if ($null -ne $enabledPlugins) {
            $pluginProperty = $enabledPlugins.PSObject.Properties[$name]
            if ($null -ne $pluginProperty) {
                $configured = $true
                $enabled = [bool]$pluginProperty.Value
            }
        }
        $desiredEnabled = Get-AiProperty $resource.desired 'enabled'
        if ($null -ne $desiredEnabled -and [bool]$enabled -ne [bool]$desiredEnabled) {
            Add-AiReason -Reasons $Reasons -Code 'CLAUDE_PLUGIN_DISABLED' -Status 'DRIFTED' -Severity $(if ([string]$resource.ownership -ceq 'managed') { 'ERROR' } else { 'WARNING' }) -Lane 'activation' -Provider 'claude' -ResourceId ([string]$resource.id) -Detail 'Claude plugin enablement does not match the wanted-state profile.' -Evidence "configured=$configured;enabled=$enabled;desired=$desiredEnabled"
        }
        Add-AiCheck -Checks $Checks -Id "resource.$($resource.id).activation" -Result $(if ($configured -and [bool]$enabled -eq [bool]$desiredEnabled) { 'PASS' } else { 'FAIL' }) -Severity $(if ([string]$resource.ownership -ceq 'managed') { 'ERROR' } else { 'WARNING' }) -ReasonCode 'CLAUDE_PLUGIN_DISABLED' -Owned $([string]$resource.ownership -ceq 'managed') -Evidence "configured=$configured;enabled=$enabled;desired=$desiredEnabled"

        $registryRecordPresent = $registryAvailable -and
            @($registryRecords.Keys) -ccontains $name -and
            @($registryRecords[$name]).Count -gt 0
        $pluginRegistryReasonCode = if ($registryAvailable) { 'CLAUDE_PLUGIN_RECORD_MISSING' } else { 'CLAUDE_PLUGIN_REGISTRY_UNAVAILABLE' }
        if ($registryAvailable -and -not $registryRecordPresent) {
            Add-AiReason -Reasons $Reasons -Code 'CLAUDE_PLUGIN_RECORD_MISSING' -Status 'DRIFTED' -Severity $(if ([string]$resource.ownership -ceq 'managed') { 'ERROR' } else { 'WARNING' }) -Lane 'artifact' -Provider 'claude' -ResourceId ([string]$resource.id) -Detail 'The declared Claude plugin has no corresponding registry record.' -Evidence "configured=$configured;registryRecordPresent=$registryRecordPresent"
        }
        Add-AiCheck -Checks $Checks -Id "resource.$($resource.id).registry" -Result $(if ($registryRecordPresent) { 'PASS' } else { 'FAIL' }) -Severity $(if ($registryRecordPresent) { 'INFO' } elseif (-not $registryAvailable -or [string]$resource.ownership -ceq 'managed') { 'ERROR' } else { 'WARNING' }) -ReasonCode $pluginRegistryReasonCode -Owned $([string]$resource.ownership -ceq 'managed') -Evidence "registryAvailable=$registryAvailable;registryRecordPresent=$registryRecordPresent"

        $pluginRows.Add([pscustomobject][ordered]@{
            Id = [string]$resource.id
            Name = $name
            Ownership = [string]$resource.ownership
            Configured = $configured
            Enabled = $enabled
            RegistryRecordPresent = $registryRecordPresent
        }) | Out-Null
    }

    $skillOverrides = Get-AiProperty $settings 'skillOverrides'
    $overrideValues = @()
    if ($null -ne $skillOverrides) {
        $overrideValues = @($skillOverrides.PSObject.Properties | ForEach-Object { [string]$_.Value })
    }
    $onCount = @($overrideValues | Where-Object { $_ -ceq 'on' }).Count
    $offCount = @($overrideValues | Where-Object { $_ -ceq 'off' }).Count
    $otherCount = $overrideValues.Count - $onCount - $offCount
    if ($otherCount -gt 0) {
        Add-AiReason -Reasons $Reasons -Code 'CLAUDE_SKILL_OVERRIDE_UNKNOWN' -Status 'DRIFTED' -Severity 'WARNING' -Lane 'activation' -Provider 'claude' -ResourceId 'skill-policy:claude' -Detail 'Claude contains skill override values outside the supported on/off policy.' -Evidence "entries=$($overrideValues.Count);unknown=$otherCount"
    }
    Add-AiCheck -Checks $Checks -Id 'resource.skill-policy:claude.values' -Result $(if ($otherCount -eq 0) { 'PASS' } else { 'FAIL' }) -Severity $(if ($otherCount -eq 0) { 'INFO' } else { 'WARNING' }) -ReasonCode 'CLAUDE_SKILL_OVERRIDE_UNKNOWN' -Owned $false -Evidence "entries=$($overrideValues.Count);on=$onCount;off=$offCount;unknown=$otherCount"

    return [pscustomobject][ordered]@{
        Version = $version
        Home = '{CLAUDE_HOME}'
        Config = '{CLAUDE_HOME}/settings.json'
        ConfigDigest = $settingsDigest
        Plugins = @($pluginRows)
        Hooks = @($hookRows)
        Skills = [pscustomobject][ordered]@{
            OverrideEntries = $overrideValues.Count
            On = $onCount
            Off = $offCount
            Unknown = $otherCount
        }
        PluginRegistry = [pscustomobject][ordered]@{
            Available = $registryAvailable
            Version = $registryVersion
            PluginIds = $pluginIdCount
            Records = $pluginRecordCount
            MissingInstallPaths = $missingInstallPathCount
            DeclaredPlugins = $declaredPluginNames.Count
            MissingDeclaredPluginRecords = $uncorrelatedDeclaredPluginNames.Count
        }
    }
}
