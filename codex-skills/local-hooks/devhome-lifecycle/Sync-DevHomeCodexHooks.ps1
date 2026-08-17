[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string] $SourcePackageRoot,

    [Parameter(Mandatory = $false)]
    [string] $TargetRoot = 'D:\DevHome\state\codex',

    [Parameter(Mandatory = $false)]
    [switch] $AllowTestOnlyTargetRootOverride,

    [Parameter(Mandatory = $false)]
    [switch] $Check,

    [Parameter(Mandatory = $false)]
    [switch] $Quiet,

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

$physicalTargetRoot = [System.IO.Path]::GetFullPath('D:\DevHome\state\codex').TrimEnd(
    [System.IO.Path]::DirectorySeparatorChar,
    [System.IO.Path]::AltDirectorySeparatorChar
)
$resolvedTargetRoot = [System.IO.Path]::GetFullPath(
    [Environment]::ExpandEnvironmentVariables($TargetRoot)
).TrimEnd(
    [System.IO.Path]::DirectorySeparatorChar,
    [System.IO.Path]::AltDirectorySeparatorChar
)
if (
    -not [string]::Equals(
        $resolvedTargetRoot,
        $physicalTargetRoot,
        [System.StringComparison]::OrdinalIgnoreCase
    ) -and
    -not $AllowTestOnlyTargetRootOverride
) {
    throw "Refusing alternate runtime target '$resolvedTargetRoot'; lifecycle hooks are pinned to the physical DevHome Codex root '$physicalTargetRoot'. Use the test-only override only for isolated tests."
}

$resolvedSourcePackageRoot = if ([string]::IsNullOrWhiteSpace($SourcePackageRoot)) {
    $PSScriptRoot
}
else {
    [System.IO.Path]::GetFullPath(
        [Environment]::ExpandEnvironmentVariables($SourcePackageRoot)
    ).TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    )
}

$installerPath = Join-Path $resolvedSourcePackageRoot 'Install-DevHomeCodexHooks.ps1'
if (-not (Test-Path -LiteralPath $installerPath -PathType Leaf)) {
    throw "DevHome lifecycle source installer is missing: $installerPath"
}

$installerParameters = @{
    TargetRoot = $resolvedTargetRoot
    VerifierPath = $VerifierPath
    ExpectedMachineId = $ExpectedMachineId
    ExpectedInstallationId = $ExpectedInstallationId
}
if ($AllowTestOnlyTargetRootOverride) {
    $installerParameters.AllowTestOnlyTargetRootOverride = $true
}

if ($Check) {
    $result = & $installerPath @installerParameters -Check
    if (-not $Quiet) {
        $result
    }
    return
}

try {
    $current = & $installerPath @installerParameters -Check
    if (-not $Quiet) {
        $current
    }
    return
}
catch {
    $driftMessage = $_.Exception.Message
}

try {
    $result = @(& $installerPath @installerParameters)[-1]
}
catch {
    throw "DevHome lifecycle synchronization failed after '$driftMessage': $($_.Exception.Message)"
}

if ($null -eq $result -or $result.Status -notin @('INSTALLED', 'UNCHANGED')) {
    throw 'DevHome lifecycle synchronization returned an unexpected result.'
}

$null = & $installerPath @installerParameters -Check
if (-not $Quiet) {
    $result
}
