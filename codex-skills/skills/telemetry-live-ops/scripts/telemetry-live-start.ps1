[CmdletBinding()]
param(
    [string]$RepoRoot = '',

    [string]$SshHost = '',

    [string]$RemoteBaseUrl = '',

    [string]$ObserverBaseUrl = '',

    [switch]$RunVerification,

    [int]$VerificationDirectIterations = 3,

    [int]$VerificationObserverIterations = 3,

    [int]$VerificationSensorLimit = 10
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Get-EnvironmentValue {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Names
    )

    foreach ($name in $Names) {
        foreach ($scope in 'Process', 'User', 'Machine') {
            $value = [System.Environment]::GetEnvironmentVariable($name, $scope)
            if (-not [string]::IsNullOrWhiteSpace($value)) {
                return $value.Trim()
            }
        }
    }

    return $null
}

function Resolve-StringSetting {
    param(
        [AllowEmptyString()]
        [Parameter(Mandatory = $true)]
        [string]$CurrentValue,

        [Parameter(Mandatory = $true)]
        [string[]]$EnvironmentNames,

        [Parameter(Mandatory = $true)]
        [string]$FallbackValue
    )

    if (-not [string]::IsNullOrWhiteSpace($CurrentValue)) {
        return $CurrentValue
    }

    $value = Get-EnvironmentValue -Names $EnvironmentNames
    if (-not [string]::IsNullOrWhiteSpace($value)) {
        return $value
    }

    return $FallbackValue
}

function Assert-PathExists {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Required path does not exist: $Path"
    }
}

$RepoRoot = Resolve-StringSetting `
    -CurrentValue $RepoRoot `
    -EnvironmentNames @('OLLAMA_TELEMETRY_REPO') `
    -FallbackValue 'D:\Development\AI-data-handling\ollama-telemetry'

$SshHost = Resolve-StringSetting `
    -CurrentValue $SshHost `
    -EnvironmentNames @('OLLAMA_TELEMETRY_REMOTE_HOST') `
    -FallbackValue 'snd-host'

$RemoteBaseUrl = Resolve-StringSetting `
    -CurrentValue $RemoteBaseUrl `
    -EnvironmentNames @('OLLAMA_TELEMETRY_REMOTE_URL') `
    -FallbackValue 'http://192.168.2.5:43217'

$ObserverBaseUrl = Resolve-StringSetting `
    -CurrentValue $ObserverBaseUrl `
    -EnvironmentNames @('OLLAMA_TELEMETRY_OBSERVER_URL') `
    -FallbackValue 'http://127.0.0.1:43191'

$remoteUri = [Uri]$RemoteBaseUrl
$repoScript = Join-Path $RepoRoot 'native\scripts\start-remote-host-stack.ps1'

Assert-PathExists -Path $repoScript

$invokeArgs = @{
    SshHost = $SshHost
    ApiHost = $remoteUri.Host
    ApiPort = $remoteUri.Port
    ObserverBaseUrl = $ObserverBaseUrl
    VerificationDirectIterations = $VerificationDirectIterations
    VerificationObserverIterations = $VerificationObserverIterations
    VerificationSensorLimit = $VerificationSensorLimit
}

if ($RunVerification) {
    $invokeArgs['RunVerification'] = $true
}

& $repoScript @invokeArgs
