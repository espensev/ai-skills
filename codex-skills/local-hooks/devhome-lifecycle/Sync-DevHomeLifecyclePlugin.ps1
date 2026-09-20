#Requires -Version 7.0
[CmdletBinding(SupportsShouldProcess, ConfirmImpact = 'Medium')]
param(
    [Parameter(Mandatory = $false)]
    [string] $CodexHome = 'D:\DevHome\state\codex',

    [Parameter(Mandatory = $false)]
    [switch] $AllowTestOnlyCodexHomeOverride,

    [Parameter(Mandatory = $false)]
    [switch] $Check,

    [Parameter(Mandatory = $false)]
    [switch] $Force,

    [Parameter(Mandatory = $false)]
    [string] $CodexCommand = 'codex',

    [Parameter(Mandatory = $false)]
    [string] $VerifierPath = $(
        Join-Path `
            ([Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData)) `
            'common_dev\v2\Test-LocalMachineIdentity.ps1'
    ),

    [Parameter(Mandatory = $false)]
    [string] $ExpectedMachineId = 'snd-desk',

    [Parameter(Mandatory = $false)]
    [string] $ExpectedInstallationId = 'ca96d510-7d87-4cec-8e1a-bd8fc3866903'
)

$ErrorActionPreference = 'Stop'

if ($Check -and $Force) {
    throw 'Check and Force cannot be used together.'
}

$MarketplaceName = 'ai-skills'
$PluginName = 'devhome-lifecycle'
$PluginId = "$PluginName@$MarketplaceName"
$CorePayloadFiles = @(
    '.codex-plugin/plugin.json',
    'hooks/hooks.json',
    'Sync-DevHomeLifecyclePlugin.ps1',
    'Sync-DevHomeCodexHooks.ps1',
    'Install-DevHomeCodexHooks.ps1',
    'Install-DevHomeClaudeHandoffRelay.ps1',
    'hooks.json',
    'hooks/Invoke-DevHomeHook.ps1',
    'hooks/Invoke-HandoffRelay.ps1'
)
# What Codex itself loads or runs from the cache, together with skills/**. The
# SessionStart hook delegates to the source checkout through -SourcePackageRoot,
# so every other payload file is an inert copy there.
$LoadedPayloadFiles = @(
    '.codex-plugin/plugin.json',
    'hooks/hooks.json',
    'Sync-DevHomeCodexHooks.ps1',
    '.mcp.json'
)
$ConvergeCommand = '.\scripts\Install-AgentSkills.ps1 -Provider Codex -CodexLocalPlugin DevHomeLifecycle'
$InstalledVerifierPath = Join-Path `
    ([Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData)) `
    'common_dev\v2\Test-LocalMachineIdentity.ps1'

function Resolve-NormalizedPath {
    param([Parameter(Mandatory)][string] $Path)

    $expanded = [Environment]::ExpandEnvironmentVariables($Path)
    if ($expanded.StartsWith('\\?\UNC\', [System.StringComparison]::OrdinalIgnoreCase)) {
        $expanded = '\\' + $expanded.Substring(8)
    }
    elseif ($expanded.StartsWith('\\?\', [System.StringComparison]::OrdinalIgnoreCase)) {
        $expanded = $expanded.Substring(4)
    }

    $fullPath = [System.IO.Path]::GetFullPath($expanded)
    $pathRoot = [System.IO.Path]::GetPathRoot($fullPath)
    if ([string]::Equals($fullPath, $pathRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $pathRoot
    }

    return $fullPath.TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    )
}

function Test-SamePath {
    param(
        [Parameter(Mandatory)][string] $Left,
        [Parameter(Mandatory)][string] $Right
    )

    return [string]::Equals(
        (Resolve-NormalizedPath -Path $Left),
        (Resolve-NormalizedPath -Path $Right),
        [System.StringComparison]::OrdinalIgnoreCase
    )
}

function Test-GeneratedCapabilityPath {
    param([Parameter(Mandatory)][string] $RelativePath)

    $normalized = $RelativePath.Replace('\', '/')
    $segments = @($normalized.Split('/', [System.StringSplitOptions]::RemoveEmptyEntries))
    $generatedDirectories = @(
        '__pycache__',
        '.pytest_cache',
        '.mypy_cache',
        '.ruff_cache',
        'node_modules'
    )
    if (@($segments | Where-Object { $_ -in $generatedDirectories }).Count -gt 0) {
        return $true
    }

    $fileName = [System.IO.Path]::GetFileName($normalized)
    if ($fileName -in @('.DS_Store', 'Thumbs.db')) {
        return $true
    }

    return [System.IO.Path]::GetExtension($fileName) -in @('.pyc', '.pyo', '.pyd')
}

function ConvertTo-DriftEntry {
    param(
        [Parameter(Mandatory)][string] $Text,
        [string] $RelativePath
    )

    $loaded = $true
    if (-not [string]::IsNullOrEmpty($RelativePath)) {
        $normalized = $RelativePath.Replace('\', '/')
        $loaded = $normalized -in $LoadedPayloadFiles -or
            $normalized.StartsWith('skills/', [System.StringComparison]::OrdinalIgnoreCase)
    }

    [pscustomobject]@{
        Text = $Text
        Loaded = $loaded
    }
}

function Get-SkillCapabilityFiles {
    param([Parameter(Mandatory)][string] $Root)

    $skillsRoot = Join-Path $Root 'skills'
    if (-not (Test-Path -LiteralPath $skillsRoot -PathType Container)) {
        return @()
    }

    $files = foreach ($file in Get-ChildItem -LiteralPath $skillsRoot -Recurse -Force -File) {
        $relativePath = [System.IO.Path]::GetRelativePath($Root, $file.FullName).Replace('\', '/')
        if (-not (Test-GeneratedCapabilityPath -RelativePath $relativePath)) {
            $relativePath
        }
    }

    return @($files | Sort-Object -Unique)
}

function Get-SourcePackageRootArgument {
    param([Parameter(Mandatory)][string] $Command)

    $pattern = "(?i)(?:^|\s)-SourcePackageRoot\s+(?:`"(?<double>[^`"]+)`"|'(?<single>[^']+)'|(?<bare>\S+))"
    $match = [regex]::Match($Command, $pattern)
    if (-not $match.Success) {
        return $null
    }
    foreach ($groupName in @('double', 'single', 'bare')) {
        if ($match.Groups[$groupName].Success) {
            return $match.Groups[$groupName].Value
        }
    }

    return $null
}

$PackageRoot = Resolve-NormalizedPath -Path $PSScriptRoot
$RepoRoot = Resolve-NormalizedPath -Path (Join-Path $PackageRoot '..\..\..')
$ExpectedPackageRoot = Resolve-NormalizedPath -Path (
    Join-Path $RepoRoot 'codex-skills\local-hooks\devhome-lifecycle'
)
if (-not (Test-SamePath -Left $PackageRoot -Right $ExpectedPackageRoot)) {
    throw "Unable to derive the Ai-Skills repository root safely from package path: $PackageRoot"
}

$PhysicalCodexHome = Resolve-NormalizedPath -Path 'D:\DevHome\state\codex'
$ResolvedCodexHome = Resolve-NormalizedPath -Path $CodexHome
$codexPathRoot = Resolve-NormalizedPath -Path ([System.IO.Path]::GetPathRoot($ResolvedCodexHome))
if (Test-SamePath -Left $ResolvedCodexHome -Right $codexPathRoot) {
    throw "Refusing to use a filesystem root as CODEX_HOME: $ResolvedCodexHome"
}
if (
    -not (Test-SamePath -Left $ResolvedCodexHome -Right $PhysicalCodexHome) -and
    -not $AllowTestOnlyCodexHomeOverride
) {
    throw "Refusing alternate Codex home '$ResolvedCodexHome'; lifecycle plugin state is pinned to the physical DevHome CODEX_HOME '$PhysicalCodexHome'. Use the test-only override only for isolated tests."
}

$MarketplaceManifestPath = Join-Path $RepoRoot '.agents\plugins\marketplace.json'
if (-not (Test-Path -LiteralPath $MarketplaceManifestPath -PathType Leaf)) {
    throw "Ai-Skills marketplace manifest is missing: $MarketplaceManifestPath"
}
try {
    $marketplaceManifest = Get-Content -Raw -LiteralPath $MarketplaceManifestPath |
        ConvertFrom-Json -ErrorAction Stop
}
catch {
    throw "Ai-Skills marketplace manifest is invalid JSON: $MarketplaceManifestPath. $($_.Exception.Message)"
}
if ($marketplaceManifest.name -cne $MarketplaceName) {
    throw "Ai-Skills marketplace manifest must declare name '$MarketplaceName'."
}
$declaredPlugins = @($marketplaceManifest.plugins | Where-Object { $_.name -ceq $PluginName })
if ($declaredPlugins.Count -ne 1) {
    throw "Ai-Skills marketplace must declare exactly one '$PluginName' plugin."
}
$declaredPlugin = $declaredPlugins[0]
if ($declaredPlugin.source.source -cne 'local' -or [string]::IsNullOrWhiteSpace($declaredPlugin.source.path)) {
    throw "Ai-Skills marketplace plugin '$PluginName' must use a local source path."
}
$DeclaredPackageRoot = Resolve-NormalizedPath -Path (
    Join-Path $RepoRoot ([string]$declaredPlugin.source.path)
)
if (-not (Test-SamePath -Left $DeclaredPackageRoot -Right $PackageRoot)) {
    throw "Ai-Skills marketplace plugin '$PluginName' does not point at this package."
}

$PluginManifestPath = Join-Path $PackageRoot '.codex-plugin\plugin.json'
if (-not (Test-Path -LiteralPath $PluginManifestPath -PathType Leaf)) {
    throw "Plugin manifest is missing: $PluginManifestPath"
}
try {
    $pluginManifest = Get-Content -Raw -LiteralPath $PluginManifestPath |
        ConvertFrom-Json -ErrorAction Stop
}
catch {
    throw "Plugin manifest is invalid JSON: $PluginManifestPath. $($_.Exception.Message)"
}
if ($pluginManifest.name -cne $PluginName -or [string]::IsNullOrWhiteSpace($pluginManifest.version)) {
    throw "Plugin manifest must declare '$PluginName' and a version."
}
$PluginVersion = [string]$pluginManifest.version
$CachePath = Join-Path $ResolvedCodexHome "plugins\cache\$MarketplaceName\$PluginName\$PluginVersion"

$SourceSkillFiles = @(Get-SkillCapabilityFiles -Root $PackageRoot)
$SourceMcpManifestPath = Join-Path $PackageRoot '.mcp.json'
$SourceHasMcpManifest = Test-Path -LiteralPath $SourceMcpManifestPath -PathType Leaf
$PayloadFiles = @(
    $CorePayloadFiles
    $SourceSkillFiles
    if ($SourceHasMcpManifest) {
        '.mcp.json'
    }
) | Sort-Object -Unique

foreach ($relativePath in $PayloadFiles) {
    $sourcePath = Join-Path $PackageRoot $relativePath
    if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
        throw "Closed plugin payload source is missing: $relativePath"
    }
}

$PluginHooksPath = Join-Path $PackageRoot 'hooks\hooks.json'
try {
    $pluginHooks = Get-Content -Raw -LiteralPath $PluginHooksPath |
        ConvertFrom-Json -ErrorAction Stop
}
catch {
    throw "Plugin hook configuration is invalid JSON: $PluginHooksPath. $($_.Exception.Message)"
}
$sessionStartCommands = @(
    $pluginHooks.hooks.SessionStart |
        ForEach-Object { $_.hooks } |
        Where-Object { $_.type -ceq 'command' }
)
if ($sessionStartCommands.Count -ne 1) {
    throw 'Plugin hooks must declare exactly one SessionStart command reconciler.'
}
$startupCommand = $sessionStartCommands[0]
$commandVariants = [ordered]@{
    command = [string]$startupCommand.command
    commandWindows = [string]$startupCommand.commandWindows
}
foreach ($variant in $commandVariants.GetEnumerator()) {
    $declaredSourceRoot = Get-SourcePackageRootArgument -Command $variant.Value
    if ([string]::IsNullOrWhiteSpace($declaredSourceRoot)) {
        throw "Plugin SessionStart $($variant.Key) must declare -SourcePackageRoot."
    }
    try {
        $resolvedDeclaredSourceRoot = Resolve-NormalizedPath -Path $declaredSourceRoot
    }
    catch {
        throw "Plugin SessionStart $($variant.Key) has an invalid -SourcePackageRoot: $declaredSourceRoot"
    }
    if (-not (Test-SamePath -Left $resolvedDeclaredSourceRoot -Right $PackageRoot)) {
        throw "Plugin SessionStart $($variant.Key) -SourcePackageRoot does not match this package root: $PackageRoot"
    }
}

function Resolve-CodexExecutable {
    # An application or script file only, so the printed path is what runs; a
    # same-named alias or function never stands in for Codex.
    $candidates = @(
        Get-Command -Name $CodexCommand -CommandType Application, ExternalScript -ErrorAction SilentlyContinue
    )
    if ($candidates.Count -eq 0) {
        throw "Codex command was not found as an application or script: $CodexCommand"
    }

    return [string]$candidates[0].Source
}

function Invoke-Codex {
    param([Parameter(Mandatory)][string[]] $Arguments)

    $commandText = "$CodexExecutable $($Arguments -join ' ')"
    # The exit code is read below; a session-wide preference must not turn it
    # into an exception that reads as "could not start".
    $PSNativeCommandUseErrorActionPreference = $false
    $hadCodexHome = Test-Path Env:CODEX_HOME
    $previousCodexHome = $env:CODEX_HOME
    try {
        $env:CODEX_HOME = $ResolvedCodexHome
        $global:LASTEXITCODE = 0
        try {
            $output = @(& $CodexExecutable @Arguments 2>&1)
            $exitCode = $global:LASTEXITCODE
        }
        catch {
            throw "Codex command could not start: $commandText. $($_.Exception.Message)"
        }
    }
    finally {
        if ($hadCodexHome) {
            $env:CODEX_HOME = $previousCodexHome
        }
        else {
            Remove-Item Env:CODEX_HOME -ErrorAction SilentlyContinue
        }
    }

    # Under 2>&1 stderr arrives as error records and stdout as strings. Only
    # stdout is a JSON document; stderr is kept for failure messages.
    $standardError = @($output | Where-Object { $_ -is [System.Management.Automation.ErrorRecord] })
    $standardOutput = @($output | Where-Object { $_ -isnot [System.Management.Automation.ErrorRecord] })

    [pscustomobject]@{
        CommandText = $commandText
        ExitCode = $exitCode
        StandardOutput = ($standardOutput | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine
        StandardError = ($standardError | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine
    }
}

function Invoke-CodexJson {
    param([Parameter(Mandatory)][string[]] $Arguments)

    $result = Invoke-Codex -Arguments $Arguments
    $outputText = (
        @($result.StandardOutput, $result.StandardError) |
            Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    ) -join [Environment]::NewLine
    if ($result.ExitCode -ne 0) {
        throw "Codex command failed with exit code $($result.ExitCode): $($result.CommandText). Output: $outputText"
    }
    try {
        return $result.StandardOutput | ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        throw "Codex command returned invalid JSON: $($result.CommandText). Output: $outputText"
    }
}

function Get-CodexVersion {
    # Informational only: a Codex that cannot report its version still converges.
    try {
        $result = Invoke-Codex -Arguments @('--version')
    }
    catch {
        return $null
    }
    if ($result.ExitCode -ne 0 -or [string]::IsNullOrWhiteSpace($result.StandardOutput)) {
        return $null
    }

    return $result.StandardOutput.Trim()
}

function Get-MarketplaceRegistration {
    $result = Invoke-CodexJson -Arguments @('plugin', 'marketplace', 'list', '--json')
    if ($result.PSObject.Properties.Name -notcontains 'marketplaces') {
        throw 'Codex marketplace list JSON did not contain a marketplaces collection.'
    }

    $registrations = @($result.marketplaces | Where-Object { $_.name -ceq $MarketplaceName })
    if ($registrations.Count -gt 1) {
        throw "Codex reported multiple '$MarketplaceName' marketplace registrations."
    }
    if ($registrations.Count -eq 0) {
        return $null
    }

    return $registrations[0]
}

function Get-InstalledPlugin {
    # No --available: that adds the whole remote catalog (about 1.9 MB on Codex
    # 0.155.1) to read one installed record.
    $result = Invoke-CodexJson -Arguments @('plugin', 'list', '--json')
    if ($result.PSObject.Properties.Name -notcontains 'installed') {
        throw 'Codex plugin list JSON did not contain an installed collection.'
    }

    $installedRecords = @($result.installed | Where-Object { $_.pluginId -ceq $PluginId })
    if ($installedRecords.Count -gt 1) {
        throw "Codex reported multiple installed '$PluginId' plugins."
    }
    if ($installedRecords.Count -eq 0) {
        return $null
    }

    return $installedRecords[0]
}

function Get-PayloadDrift {
    $drift = [System.Collections.Generic.List[object]]::new()
    if (-not (Test-Path -LiteralPath $CachePath -PathType Container)) {
        $drift.Add((ConvertTo-DriftEntry -Text 'plugin cache missing'))
        return @($drift)
    }

    foreach ($relativePath in $PayloadFiles) {
        $sourcePath = Join-Path $PackageRoot $relativePath
        $cachedPath = Join-Path $CachePath $relativePath
        $displayPath = $relativePath.Replace('\', '/')
        if (-not (Test-Path -LiteralPath $cachedPath -PathType Leaf)) {
            $drift.Add((ConvertTo-DriftEntry -Text "$displayPath missing" -RelativePath $displayPath))
            continue
        }

        $sourceHash = (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash
        $cachedHash = (Get-FileHash -LiteralPath $cachedPath -Algorithm SHA256).Hash
        if ($sourceHash -cne $cachedHash) {
            $drift.Add((ConvertTo-DriftEntry -Text "$displayPath differs" -RelativePath $displayPath))
        }
    }

    $sourceSkillSet = [System.Collections.Generic.HashSet[string]]::new(
        [System.StringComparer]::OrdinalIgnoreCase
    )
    foreach ($relativePath in $SourceSkillFiles) {
        $null = $sourceSkillSet.Add($relativePath)
    }
    foreach ($cachedSkillFile in @(Get-SkillCapabilityFiles -Root $CachePath)) {
        if (-not $sourceSkillSet.Contains($cachedSkillFile)) {
            $drift.Add((ConvertTo-DriftEntry -Text "$cachedSkillFile unexpected" -RelativePath $cachedSkillFile))
        }
    }

    $cachedMcpManifestPath = Join-Path $CachePath '.mcp.json'
    if (
        -not $SourceHasMcpManifest -and
        (Test-Path -LiteralPath $cachedMcpManifestPath -PathType Leaf)
    ) {
        $drift.Add((ConvertTo-DriftEntry -Text '.mcp.json unexpected' -RelativePath '.mcp.json'))
    }

    return @($drift)
}

function Get-ConvergenceState {
    $marketplace = Get-MarketplaceRegistration
    $installedPlugin = $null
    $drift = [System.Collections.Generic.List[object]]::new()
    $status = 'CURRENT'
    $marketplaceRoot = $null

    if ($null -eq $marketplace) {
        $status = 'MISSING'
        $drift.Add((ConvertTo-DriftEntry -Text "marketplace $MarketplaceName missing"))
    }
    elseif ([string]::IsNullOrWhiteSpace([string]$marketplace.root)) {
        $status = 'CONFLICT'
        $drift.Add((ConvertTo-DriftEntry -Text "marketplace $MarketplaceName has no local root"))
    }
    else {
        try {
            $marketplaceRoot = Resolve-NormalizedPath -Path ([string]$marketplace.root)
        }
        catch {
            $status = 'CONFLICT'
            $drift.Add((ConvertTo-DriftEntry -Text "marketplace $MarketplaceName root is invalid"))
        }
        if ($status -ne 'CONFLICT' -and -not (Test-SamePath -Left $marketplaceRoot -Right $RepoRoot)) {
            $status = 'CONFLICT'
            $drift.Add((ConvertTo-DriftEntry -Text "marketplace $MarketplaceName points elsewhere: $marketplaceRoot"))
        }
    }

    if ($status -ne 'CONFLICT') {
        $installedPlugin = Get-InstalledPlugin
        if ($null -eq $installedPlugin) {
            if ($status -eq 'CURRENT') {
                $status = 'MISSING'
            }
            $drift.Add((ConvertTo-DriftEntry -Text "plugin $PluginId missing"))
        }
        elseif ([string]$installedPlugin.version -cne $PluginVersion) {
            if ($status -eq 'CURRENT') {
                $status = 'STALE'
            }
            $drift.Add((ConvertTo-DriftEntry -Text "plugin version $($installedPlugin.version) differs from $PluginVersion"))
        }

        if ($null -ne $installedPlugin) {
            $payloadDrift = @(Get-PayloadDrift)
            if ($payloadDrift.Count -gt 0) {
                if ($status -eq 'CURRENT') {
                    $status = 'STALE'
                }
                foreach ($entry in $payloadDrift) {
                    $drift.Add($entry)
                }
            }
        }
    }

    # Codex owns the enabled flag; it is reported, never written. Unknown stays
    # $null when a Codex version omits the key.
    $enabled = $null
    if ($null -ne $installedPlugin -and $installedPlugin.PSObject.Properties.Name -contains 'enabled') {
        $enabled = [bool]$installedPlugin.enabled
    }

    [pscustomobject][ordered]@{
        Status = $status
        Action = 'NONE'
        Changed = $false
        NextStep = $null
        Marketplace = $MarketplaceName
        MarketplaceRoot = $marketplaceRoot
        PluginId = $PluginId
        Version = $PluginVersion
        InstalledVersion = if ($null -eq $installedPlugin) { $null } else { [string]$installedPlugin.version }
        Enabled = $enabled
        TrustReviewRequired = $false
        Source = $PackageRoot
        Repository = $RepoRoot
        Cache = $CachePath
        CodexHome = $ResolvedCodexHome
        CodexExecutable = $CodexExecutable
        CodexVersion = $CodexVersion
        Files = $PayloadFiles.Count
        Drift = @($drift | ForEach-Object { $_.Text })
        LoadedDrift = @($drift | Where-Object { $_.Loaded } | ForEach-Object { $_.Text })
        MachineId = $null
        MarketplacePresent = $null -ne $marketplace
        PluginInstalled = $null -ne $installedPlugin
    }
}

function Complete-ConvergenceState {
    param([Parameter(Mandatory)] $State)

    # Trust is Codex-owned and its hash is not derivable from source, so any
    # change to the installed plugin asks for a review rather than guessing.
    $State.TrustReviewRequired = [bool]$State.Changed
    $State.NextStep = if ($State.Status -eq 'CONFLICT') {
        "Point the Codex '$MarketplaceName' marketplace at $RepoRoot, then run this again. Nothing was changed."
    }
    elseif ($State.Status -ne 'CURRENT') {
        if (@($State.LoadedDrift).Count -eq 0) {
            "Only inert cache copies drifted, so Codex behaves the same. Converge when convenient: $ConvergeCommand"
        }
        else {
            "Converge now: $ConvergeCommand"
        }
    }
    elseif ($State.Enabled -eq $false) {
        "$PluginId is installed but disabled in Codex, so its SessionStart reconciler does not run. Enable it in Codex."
    }
    elseif ($State.Changed) {
        'Restart Codex, confirm the plugin is enabled, and review the SessionStart reconciler in /hooks.'
    }
    else {
        $null
    }

    return $State
}

function Assert-VerifiedMachine {
    if (
        (Test-SamePath -Left $ResolvedCodexHome -Right $PhysicalCodexHome) -and
        -not (Test-SamePath -Left $VerifierPath -Right $InstalledVerifierPath)
    ) {
        throw "Refusing verifier override '$VerifierPath' for the physical DevHome CODEX_HOME; mutations there are gated by the installed verifier: $InstalledVerifierPath"
    }
    if (-not (Test-Path -LiteralPath $VerifierPath -PathType Leaf)) {
        throw "Machine verifier is missing: $VerifierPath"
    }

    $results = @(& $VerifierPath)
    if ($results.Count -ne 1) {
        throw "Machine verifier must return exactly one result; it returned $($results.Count)."
    }
    $identity = $results[0]
    if (
        $identity.status -cne 'VERIFIED' -or
        $identity.machineId -cne $ExpectedMachineId -or
        $identity.instanceId -cne $ExpectedInstallationId
    ) {
        throw "Machine identity mismatch. Expected VERIFIED $ExpectedMachineId/$ExpectedInstallationId."
    }

    return $identity
}

$CodexExecutable = Resolve-CodexExecutable
$CodexVersion = Get-CodexVersion

$initialState = Get-ConvergenceState
if ($Check) {
    # Read-only, and the exit code carries the verdict: 0 only when CURRENT. The
    # state object is still emitted, so a caller that invokes this with & (the
    # installer's -DryRun) keeps the full report and reads $LASTEXITCODE.
    Complete-ConvergenceState -State $initialState
    if ($initialState.Status -eq 'CURRENT') {
        exit 0
    }
    exit 1
}
if ($initialState.Status -eq 'CONFLICT') {
    throw "The '$MarketplaceName' marketplace points elsewhere or is invalid: $($initialState.Drift -join '; ')"
}
if ($initialState.Status -eq 'CURRENT' -and -not $Force) {
    Complete-ConvergenceState -State $initialState
    return
}

$operation = if ($Force) {
    "Force refresh $PluginId from $RepoRoot"
}
else {
    "Converge $PluginId from $RepoRoot"
}
if (-not $PSCmdlet.ShouldProcess($ResolvedCodexHome, $operation)) {
    $initialState.Action = 'WOULD_CONVERGE'
    Complete-ConvergenceState -State $initialState
    return
}

$identity = Assert-VerifiedMachine
$marketplaceWasMissing = -not $initialState.MarketplacePresent
$pluginWasInstalled = $initialState.PluginInstalled
$refreshInstalledPlugin = $false
if ($pluginWasInstalled) {
    $refreshInstalledPlugin = $Force -or
        $initialState.InstalledVersion -cne $PluginVersion -or
        @(Get-PayloadDrift).Count -gt 0
}

if ($marketplaceWasMissing) {
    $null = Invoke-CodexJson -Arguments @(
        'plugin', 'marketplace', 'add', $RepoRoot, '--json'
    )
    $registeredMarketplace = Get-MarketplaceRegistration
    if (
        $null -eq $registeredMarketplace -or
        [string]::IsNullOrWhiteSpace([string]$registeredMarketplace.root) -or
        -not (Test-SamePath -Left ([string]$registeredMarketplace.root) -Right $RepoRoot)
    ) {
        throw "Codex marketplace registration did not converge to the Ai-Skills repository: $RepoRoot"
    }
}

if ($refreshInstalledPlugin) {
    $null = Invoke-CodexJson -Arguments @(
        'plugin', 'remove', $PluginId, '--json'
    )
}
if (-not $pluginWasInstalled -or $refreshInstalledPlugin) {
    try {
        $null = Invoke-CodexJson -Arguments @(
            'plugin', 'add', $PluginId, '--json'
        )
    }
    catch {
        if (-not $refreshInstalledPlugin) {
            throw
        }
        # Codex 0.155.1 has no plugin refresh command (marketplace upgrade covers
        # Git marketplaces only), so remove then add is not atomic.
        throw "Codex removed $PluginId but could not add it back, so the plugin is now uninstalled. Re-run this command to reinstall it. $($_.Exception.Message)"
    }
}

$finalState = Get-ConvergenceState
if ($finalState.Status -ne 'CURRENT') {
    throw "Lifecycle plugin synchronization did not converge: $($finalState.Drift -join '; ')"
}

$finalState.Action = if ($marketplaceWasMissing -and -not $pluginWasInstalled) {
    'REGISTERED_AND_INSTALLED'
}
elseif ($marketplaceWasMissing) {
    if ($refreshInstalledPlugin) { 'REGISTERED_AND_REFRESHED' } else { 'REGISTERED' }
}
elseif ($refreshInstalledPlugin) {
    'REFRESHED'
}
else {
    'INSTALLED'
}
$finalState.Changed = $true
$finalState.MachineId = $identity.machineId
Complete-ConvergenceState -State $finalState
