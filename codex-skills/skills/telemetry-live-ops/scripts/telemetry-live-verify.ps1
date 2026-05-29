[CmdletBinding()]
param(
    [string]$RepoRoot = '',

    [string]$RemoteBaseUrl = '',

    [string]$ObserverBaseUrl = '',

    [string]$RemoteTargetName = '',

    [int]$DirectIterations = 5,

    [int]$ObserverIterations = 3,

    [int]$SensorLimit = 10
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

$RemoteBaseUrl = Resolve-StringSetting `
    -CurrentValue $RemoteBaseUrl `
    -EnvironmentNames @('OLLAMA_TELEMETRY_REMOTE_URL') `
    -FallbackValue 'http://192.168.2.5:43217'

$ObserverBaseUrl = Resolve-StringSetting `
    -CurrentValue $ObserverBaseUrl `
    -EnvironmentNames @('OLLAMA_TELEMETRY_OBSERVER_URL') `
    -FallbackValue 'http://127.0.0.1:43191'

$RemoteTargetName = Resolve-StringSetting `
    -CurrentValue $RemoteTargetName `
    -EnvironmentNames @('OLLAMA_TELEMETRY_REMOTE_HOST') `
    -FallbackValue 'snd-host'

$repoScript = Join-Path $RepoRoot 'native\scripts\verify-live-deployment.ps1'

Assert-PathExists -Path $repoScript

& $repoScript `
    -RemoteBaseUrl $RemoteBaseUrl `
    -ObserverBaseUrl $ObserverBaseUrl `
    -RemoteTargetName $RemoteTargetName `
    -DirectIterations $DirectIterations `
    -ObserverIterations $ObserverIterations `
    -SensorLimit $SensorLimit
