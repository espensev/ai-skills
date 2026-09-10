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

function Invoke-CodexJson {
    param([Parameter(Mandatory)][string[]] $Arguments)

    $commandText = "$CodexCommand $($Arguments -join ' ')"
    $hadCodexHome = Test-Path Env:CODEX_HOME
    $previousCodexHome = $env:CODEX_HOME
    try {
        $env:CODEX_HOME = $ResolvedCodexHome
        $global:LASTEXITCODE = 0
        try {
            $output = @(& $CodexCommand @Arguments 2>&1)
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

    $outputText = ($output | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine
    if ($exitCode -ne 0) {
        throw "Codex command failed with exit code ${exitCode}: $commandText. Output: $outputText"
    }
    try {
        return $outputText | ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        throw "Codex command returned invalid JSON: $commandText. Output: $outputText"
    }
}

function Get-MarketplaceRegistration {
    $result = Invoke-CodexJson -Arguments @('plugin', 'marketplace', 'list', '--json')
    if ($result.PSObject.Properties.Name -notcontains 'marketplaces') {
        throw 'Codex marketplace list JSON did not contain a marketplaces collection.'
    }

    $matches = @($result.marketplaces | Where-Object { $_.name -ceq $MarketplaceName })
    if ($matches.Count -gt 1) {
        throw "Codex reported multiple '$MarketplaceName' marketplace registrations."
    }
    if ($matches.Count -eq 0) {
        return $null
    }

    return $matches[0]
}

function Get-InstalledPlugin {
    $result = Invoke-CodexJson -Arguments @('plugin', 'list', '--json', '--available')
    if (
        $result.PSObject.Properties.Name -notcontains 'installed' -or
        $result.PSObject.Properties.Name -notcontains 'available'
    ) {
        throw 'Codex plugin list JSON did not contain installed and available collections.'
    }

    $matches = @($result.installed | Where-Object { $_.pluginId -ceq $PluginId })
    if ($matches.Count -gt 1) {
        throw "Codex reported multiple installed '$PluginId' plugins."
    }
    if ($matches.Count -eq 0) {
        return $null
    }

    return $matches[0]
}

function Get-PayloadDrift {
    $drift = [System.Collections.Generic.List[string]]::new()
    if (-not (Test-Path -LiteralPath $CachePath -PathType Container)) {
        $drift.Add('plugin cache missing')
        return @($drift)
    }

    foreach ($relativePath in $PayloadFiles) {
        $sourcePath = Join-Path $PackageRoot $relativePath
        $cachedPath = Join-Path $CachePath $relativePath
        $displayPath = $relativePath.Replace('\', '/')
        if (-not (Test-Path -LiteralPath $cachedPath -PathType Leaf)) {
            $drift.Add("$displayPath missing")
            continue
        }

        $sourceHash = (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash
        $cachedHash = (Get-FileHash -LiteralPath $cachedPath -Algorithm SHA256).Hash
        if ($sourceHash -cne $cachedHash) {
            $drift.Add("$displayPath differs")
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
            $drift.Add("$cachedSkillFile unexpected")
        }
    }

    $cachedMcpManifestPath = Join-Path $CachePath '.mcp.json'
    if (
        -not $SourceHasMcpManifest -and
        (Test-Path -LiteralPath $cachedMcpManifestPath -PathType Leaf)
    ) {
        $drift.Add('.mcp.json unexpected')
    }

    return @($drift)
}

function Get-ConvergenceState {
    $marketplace = Get-MarketplaceRegistration
    $installedPlugin = $null
    $drift = [System.Collections.Generic.List[string]]::new()
    $status = 'CURRENT'
    $marketplaceRoot = $null

    if ($null -eq $marketplace) {
        $status = 'MISSING'
        $drift.Add("marketplace $MarketplaceName missing")
    }
    elseif ([string]::IsNullOrWhiteSpace([string]$marketplace.root)) {
        $status = 'CONFLICT'
        $drift.Add("marketplace $MarketplaceName has no local root")
    }
    else {
        try {
            $marketplaceRoot = Resolve-NormalizedPath -Path ([string]$marketplace.root)
        }
        catch {
            $status = 'CONFLICT'
            $drift.Add("marketplace $MarketplaceName root is invalid")
        }
        if ($status -ne 'CONFLICT' -and -not (Test-SamePath -Left $marketplaceRoot -Right $RepoRoot)) {
            $status = 'CONFLICT'
            $drift.Add("marketplace $MarketplaceName points elsewhere: $marketplaceRoot")
        }
    }

    if ($status -ne 'CONFLICT') {
        $installedPlugin = Get-InstalledPlugin
        if ($null -eq $installedPlugin) {
            if ($status -eq 'CURRENT') {
                $status = 'MISSING'
            }
            $drift.Add("plugin $PluginId missing")
        }
        elseif ([string]$installedPlugin.version -cne $PluginVersion) {
            if ($status -eq 'CURRENT') {
                $status = 'STALE'
            }
            $drift.Add("plugin version $($installedPlugin.version) differs from $PluginVersion")
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

    [pscustomobject][ordered]@{
        Status = $status
        Action = 'NONE'
        Changed = $false
        Marketplace = $MarketplaceName
        MarketplaceRoot = $marketplaceRoot
        PluginId = $PluginId
        Version = $PluginVersion
        InstalledVersion = if ($null -eq $installedPlugin) { $null } else { [string]$installedPlugin.version }
        Source = $PackageRoot
        Repository = $RepoRoot
        Cache = $CachePath
        Files = $PayloadFiles.Count
        Drift = @($drift)
        MachineId = $null
        MarketplacePresent = $null -ne $marketplace
        PluginInstalled = $null -ne $installedPlugin
    }
}

function Assert-VerifiedMachine {
    if (-not (Test-Path -LiteralPath $VerifierPath -PathType Leaf)) {
        throw "Machine verifier is missing: $VerifierPath"
    }

    $identity = & $VerifierPath
    if ($null -eq $identity) {
        throw 'Machine verifier returned no identity.'
    }
    $identity = @($identity)[-1]
    if (
        $identity.status -cne 'VERIFIED' -or
        $identity.machineId -cne $ExpectedMachineId -or
        $identity.instanceId -cne $ExpectedInstallationId
    ) {
        throw "Machine identity mismatch. Expected VERIFIED $ExpectedMachineId/$ExpectedInstallationId."
    }

    return $identity
}

$initialState = Get-ConvergenceState
if ($Check) {
    $initialState
    return
}
if ($initialState.Status -eq 'CONFLICT') {
    throw "The '$MarketplaceName' marketplace points elsewhere or is invalid: $($initialState.Drift -join '; ')"
}
if ($initialState.Status -eq 'CURRENT' -and -not $Force) {
    $initialState
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
    $initialState
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
    $null = Invoke-CodexJson -Arguments @(
        'plugin', 'add', $PluginId, '--json'
    )
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
$finalState
