function Get-AiProperty {
    param(
        [AllowNull()][object] $InputObject,
        [Parameter(Mandatory)][string] $Name,
        [AllowNull()][object] $Default = $null
    )

    if ($null -eq $InputObject) {
        return $Default
    }

    $property = $InputObject.PSObject.Properties[$Name]
    if ($null -eq $property) {
        return $Default
    }

    return $property.Value
}

function Read-AiJsonDocument {
    param(
        [Parameter(Mandatory)][string] $Path,
        [Parameter(Mandatory)][string] $ExpectedSchema,
        [Parameter(Mandatory)][string] $SchemaPath
    )

    $resolvedPath = [System.IO.Path]::GetFullPath(
        [Environment]::ExpandEnvironmentVariables($Path)
    )
    if (-not (Test-Path -LiteralPath $resolvedPath -PathType Leaf)) {
        throw "AI environment document missing: $resolvedPath"
    }

    try {
        $rawJson = Get-Content -Raw -LiteralPath $resolvedPath
        $document = $rawJson | ConvertFrom-Json -Depth 100
    }
    catch {
        throw "AI environment document is not valid JSON: $resolvedPath. $($_.Exception.Message)"
    }

    $schema = [string](Get-AiProperty -InputObject $document -Name 'schema')
    if ($schema -cne $ExpectedSchema) {
        throw "Unsupported AI environment document schema '$schema' in $resolvedPath; expected '$ExpectedSchema'."
    }

    $resolvedSchemaPath = [System.IO.Path]::GetFullPath($SchemaPath)
    if (-not (Test-Path -LiteralPath $resolvedSchemaPath -PathType Leaf)) {
        throw "AI environment JSON Schema missing: $resolvedSchemaPath"
    }
    try {
        $schemaValid = $rawJson | Test-Json -SchemaFile $resolvedSchemaPath -ErrorAction SilentlyContinue
    }
    catch {
        throw "AI environment JSON Schema could not be evaluated: $resolvedSchemaPath. $($_.Exception.Message)"
    }
    if (-not $schemaValid) {
        throw "AI environment document failed schema validation: $resolvedPath"
    }

    return $document
}

function Assert-AiJsonValueMatchesSchema {
    param(
        [Parameter(Mandatory)][object] $Value,
        [Parameter(Mandatory)][string] $SchemaPath,
        [Parameter(Mandatory)][string] $Label
    )

    $resolvedSchemaPath = [System.IO.Path]::GetFullPath($SchemaPath)
    try {
        $json = $Value | ConvertTo-Json -Depth 100
        $schemaValid = $json | Test-Json -SchemaFile $resolvedSchemaPath -ErrorAction SilentlyContinue
    }
    catch {
        throw "$Label schema could not be evaluated. $($_.Exception.Message)"
    }
    if (-not $schemaValid) {
        throw "$Label failed schema validation."
    }
}

function Assert-AiDocumentContracts {
    param(
        [Parameter(Mandatory)][object] $Profile,
        [Parameter(Mandatory)][object] $Lock
    )

    $profileId = [string](Get-AiProperty $Profile 'id')
    if ($profileId -notmatch '^[a-z0-9]+(?:-[a-z0-9]+)*$') {
        throw "Unsafe AI environment profile id: $profileId"
    }
    if ([string](Get-AiProperty $Lock 'profileId') -cne $profileId) {
        throw "AI environment lock profileId does not match profile '$profileId'."
    }
    if ([string]$Profile.providers.codex.command -cne 'codex' -or [string]$Profile.providers.claude.command -cne 'claude') {
        throw 'Provider commands are fixed to codex and claude; profile-supplied executable paths are not allowed.'
    }

    foreach ($collectionCase in @(
        [pscustomobject]@{ Name = 'profile resource'; Values = @($Profile.resources); Property = 'id' },
        [pscustomobject]@{ Name = 'lock resource'; Values = @($Lock.resources); Property = 'id' },
        [pscustomobject]@{ Name = 'profile acceptance'; Values = @($Profile.acceptance); Property = 'id' },
        [pscustomobject]@{ Name = 'lock acceptance'; Values = @($Lock.acceptance); Property = 'id' }
    )) {
        $ids = @($collectionCase.Values | ForEach-Object { [string](Get-AiProperty $_ $collectionCase.Property) })
        $duplicates = @($ids | Group-Object | Where-Object Count -gt 1 | Select-Object -ExpandProperty Name)
        if ($duplicates.Count -gt 0) {
            throw "Duplicate $($collectionCase.Name) id(s): $($duplicates -join ', ')"
        }
    }

    $supportedObservationAdapters = @(
        'codex/marketplace/managed',
        'codex/marketplace/observed',
        'codex/plugin/managed',
        'codex/hook/managed',
        'codex/skill-policy/observed',
        'claude/plugin/observed',
        'claude/hook/managed',
        'claude/skill-policy/observed',
        'shared/skill-root/observed'
    )
    foreach ($resource in @($Profile.resources)) {
        $resourceId = [string](Get-AiProperty $resource 'id')
        if ($resourceId -notmatch '^[a-z][a-z0-9-]*:[a-z0-9][a-z0-9@.-]*$') {
            throw "Unsafe AI environment resource id: $resourceId"
        }
        $ownership = [string](Get-AiProperty $resource 'ownership')
        if ($ownership -notin @('managed', 'observed', 'forbidden', 'manual-gate')) {
            throw "Unsupported ownership for resource '$resourceId'."
        }
        $adapterShape = @(
            [string](Get-AiProperty $resource 'provider'),
            [string](Get-AiProperty $resource 'kind'),
            $ownership
        ) -join '/'
        if ($adapterShape -cnotin $supportedObservationAdapters) {
            throw "Resource '$resourceId' has no supported observation adapter for '$adapterShape'."
        }
    }

    $pathKeyRoot = Join-Path ([System.IO.Path]::GetTempPath()) 'ai-environment-lock-path-key'
    foreach ($lockResource in @($Lock.resources)) {
        $resourceId = [string](Get-AiProperty $lockResource 'id')
        $profileResource = @($Profile.resources | Where-Object { [string]$_.id -ceq $resourceId }) |
            Select-Object -First 1
        $payload = @($lockResource.payload)
        if ([string](Get-AiProperty $profileResource 'ownership') -ceq 'managed' -and $payload.Count -eq 0) {
            throw "Managed resource lock payload cannot be empty: $resourceId"
        }

        $pathKeys = [System.Collections.Generic.HashSet[string]]::new(
            [System.StringComparer]::OrdinalIgnoreCase
        )
        foreach ($entry in $payload) {
            $relativePath = [string](Get-AiProperty $entry 'path')
            if ([string]::IsNullOrWhiteSpace($relativePath)) {
                throw "Lock resource '$resourceId' contains an empty payload path."
            }
            $pathKey = Resolve-AiChildPath -Root $pathKeyRoot -RelativePath $relativePath
            if (-not $pathKeys.Add($pathKey)) {
                throw "Duplicate lock payload path '$relativePath' in resource '$resourceId'."
            }
        }
    }
}

function Resolve-AiPath {
    param(
        [Parameter(Mandatory)][string] $Path,
        [string] $BasePath
    )

    $expanded = [Environment]::ExpandEnvironmentVariables($Path)
    if ($expanded.StartsWith('\\?\')) {
        $expanded = $expanded.Substring(4)
    }
    if (-not [System.IO.Path]::IsPathRooted($expanded)) {
        if ([string]::IsNullOrWhiteSpace($BasePath)) {
            throw "Relative path has no base path: $Path"
        }
        $expanded = Join-Path $BasePath $expanded
    }
    return [System.IO.Path]::GetFullPath($expanded)
}

function Resolve-AiChildPath {
    param(
        [Parameter(Mandatory)][string] $Root,
        [Parameter(Mandatory)][string] $RelativePath
    )

    if ([System.IO.Path]::IsPathRooted($RelativePath)) {
        throw "Payload path must be relative: $RelativePath"
    }

    $resolvedRoot = Resolve-AiPath $Root
    $resolvedChild = [System.IO.Path]::GetFullPath((Join-Path $resolvedRoot ($RelativePath -replace '/', '\')))
    $rootPrefix = $resolvedRoot.TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
    if (-not $resolvedChild.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Payload path escapes its resource root: $RelativePath"
    }
    return $resolvedChild
}

function Get-AiFileDigest {
    param([Parameter(Mandatory)][string] $Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $null
    }
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToUpperInvariant()
}

function Add-AiReason {
    param(
        [Parameter(Mandatory)][AllowEmptyCollection()][System.Collections.Generic.List[object]] $Reasons,
        [Parameter(Mandatory)][string] $Code,
        [Parameter(Mandatory)][ValidateSet('CURRENT', 'DRIFTED', 'PENDING_TRUST', 'UNTESTED_PROVIDER_VERSION', 'SOURCE_UNTRUSTED', 'DEGRADED_FOREIGN_MARKETPLACE', 'ACCEPTANCE_FAILED')][string] $Status,
        [Parameter(Mandatory)][ValidateSet('INFO', 'WARNING', 'ERROR', 'BLOCKER')][string] $Severity,
        [Parameter(Mandatory)][ValidateSet('source', 'artifact', 'projection', 'activation', 'trust', 'compatibility', 'acceptance')][string] $Lane,
        [string] $Provider = 'shared',
        [string] $ResourceId = 'environment',
        [Parameter(Mandatory)][string] $Detail,
        [string] $Evidence = ''
    )

    $Reasons.Add([pscustomobject][ordered]@{
        Code = $Code
        Status = $Status
        Severity = $Severity
        Provider = $Provider
        ResourceId = $ResourceId
        Lane = $Lane
        Detail = $Detail
        Evidence = $Evidence
    }) | Out-Null
}

function Add-AiCheck {
    param(
        [Parameter(Mandatory)][AllowEmptyCollection()][System.Collections.Generic.List[object]] $Checks,
        [Parameter(Mandatory)][string] $Id,
        [Parameter(Mandatory)][ValidateSet('PASS', 'FAIL', 'UNKNOWN', 'NOT_RUN', 'DEGRADED')][string] $Result,
        [Parameter(Mandatory)][ValidateSet('INFO', 'WARNING', 'ERROR', 'BLOCKER')][string] $Severity,
        [Parameter(Mandatory)][string] $ReasonCode,
        [Parameter(Mandatory)][bool] $Owned,
        [string] $Evidence = ''
    )

    $Checks.Add([pscustomobject][ordered]@{
        Id = $Id
        Result = $Result
        Severity = $Severity
        ReasonCode = $ReasonCode
        Owned = $Owned
        Evidence = $Evidence
    }) | Out-Null
}

function Get-AiProfileResource {
    param(
        [Parameter(Mandatory)][object] $Profile,
        [Parameter(Mandatory)][string] $Id
    )
    return @($Profile.resources | Where-Object { [string]$_.id -ceq $Id }) | Select-Object -First 1
}

function Get-AiLockResource {
    param(
        [Parameter(Mandatory)][object] $Lock,
        [Parameter(Mandatory)][string] $Id
    )
    return @($Lock.resources | Where-Object { [string]$_.id -ceq $Id }) | Select-Object -First 1
}

function Invoke-AiProcess {
    param(
        [Parameter(Mandatory)][string] $Command,
        [string[]] $Arguments = @(),
        [ValidateRange(1, 300000)][int] $TimeoutMilliseconds = 5000
    )

    $commandFound = $false
    $process = $null
    try {
        $resolvedCommand = Get-Command -Name $Command -CommandType Application -ErrorAction Stop |
            Select-Object -First 1
        $commandFound = $true
        $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
        $startInfo.FileName = $resolvedCommand.Source
        $startInfo.UseShellExecute = $false
        $startInfo.CreateNoWindow = $true
        $startInfo.RedirectStandardOutput = $true
        $startInfo.RedirectStandardError = $true
        foreach ($argument in @($Arguments)) {
            $startInfo.ArgumentList.Add([string]$argument)
        }

        $process = [System.Diagnostics.Process]::new()
        $process.StartInfo = $startInfo
        $null = $process.Start()
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        $streamTasks = [System.Threading.Tasks.Task[]]@($stdoutTask, $stderrTask)
        if (-not $process.WaitForExit($TimeoutMilliseconds)) {
            $terminationError = ''
            try {
                $process.Kill($true)
            }
            catch {
                $terminationError = $_.Exception.Message
            }
            try {
                $null = $process.WaitForExit(1000)
            }
            catch {
                if ([string]::IsNullOrWhiteSpace($terminationError)) {
                    $terminationError = $_.Exception.Message
                }
            }

            $stdout = ''
            $stderr = ''
            try {
                if ([System.Threading.Tasks.Task]::WaitAll($streamTasks, 1000)) {
                    $stdout = $stdoutTask.GetAwaiter().GetResult().Trim()
                    $stderr = $stderrTask.GetAwaiter().GetResult().Trim()
                }
            }
            catch { }

            return [pscustomobject][ordered]@{
                Found = $true
                Available = $false
                TimedOut = $true
                Status = 'TimedOut'
                ExitCode = -1
                StdOut = $stdout
                StdErr = $stderr
                Error = if ([string]::IsNullOrWhiteSpace($terminationError)) {
                    "Process timed out after $TimeoutMilliseconds ms."
                }
                else {
                    "Process timed out after $TimeoutMilliseconds ms; process-tree termination reported: $terminationError"
                }
            }
        }

        $process.WaitForExit()
        $streamDrainMilliseconds = [Math]::Min($TimeoutMilliseconds, 1000)
        if (-not [System.Threading.Tasks.Task]::WaitAll($streamTasks, $streamDrainMilliseconds)) {
            return [pscustomobject][ordered]@{
                Found = $true
                Available = $false
                TimedOut = $true
                Status = 'TimedOut'
                ExitCode = -1
                StdOut = ''
                StdErr = ''
                Error = "Process output did not close within $streamDrainMilliseconds ms after exit."
            }
        }
        return [pscustomobject][ordered]@{
            Found = $true
            Available = $true
            TimedOut = $false
            Status = 'Completed'
            ExitCode = $process.ExitCode
            StdOut = $stdoutTask.Result.Trim()
            StdErr = $stderrTask.Result.Trim()
            Error = ''
        }
    }
    catch {
        return [pscustomobject][ordered]@{
            Found = $commandFound
            Available = $false
            TimedOut = $false
            Status = 'Unavailable'
            ExitCode = -1
            StdOut = ''
            StdErr = ''
            Error = $_.Exception.Message
        }
    }
    finally {
        if ($null -ne $process) {
            $process.Dispose()
        }
    }
}

function Get-AiGitBlobDigest {
    param(
        [Parameter(Mandatory)][string] $RepositoryRoot,
        [Parameter(Mandatory)][string] $ObjectSpec,
        [ValidateRange(1, 300000)][int] $TimeoutMilliseconds = 5000
    )

    $commandFound = $false
    $process = $null
    $output = $null
    try {
        $resolvedCommand = Get-Command -Name 'git' -CommandType Application -ErrorAction Stop |
            Select-Object -First 1
        $commandFound = $true
        $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
        $startInfo.FileName = $resolvedCommand.Source
        $startInfo.UseShellExecute = $false
        $startInfo.CreateNoWindow = $true
        $startInfo.RedirectStandardOutput = $true
        $startInfo.RedirectStandardError = $true
        foreach ($argument in @('-C', $RepositoryRoot, 'cat-file', 'blob', $ObjectSpec)) {
            $startInfo.ArgumentList.Add([string]$argument)
        }

        $process = [System.Diagnostics.Process]::new()
        $process.StartInfo = $startInfo
        $null = $process.Start()
        $output = [System.IO.MemoryStream]::new()
        $stdoutTask = $process.StandardOutput.BaseStream.CopyToAsync($output)
        $stderrTask = $process.StandardError.ReadToEndAsync()
        if (-not $process.WaitForExit($TimeoutMilliseconds)) {
            try { $process.Kill($true) } catch { }
            try { $null = $process.WaitForExit(1000) } catch { }
            return [pscustomobject][ordered]@{
                Found = $true
                TimedOut = $true
                ExitCode = -1
                Digest = $null
                Bytes = [byte[]]@()
            }
        }

        $process.WaitForExit()
        $null = $stdoutTask.GetAwaiter().GetResult()
        $null = $stderrTask.GetAwaiter().GetResult()
        if ($process.ExitCode -ne 0) {
            return [pscustomobject][ordered]@{
                Found = $true
                TimedOut = $false
                ExitCode = $process.ExitCode
                Digest = $null
                Bytes = [byte[]]@()
            }
        }

        $bytes = $output.ToArray()
        $sha256 = [System.Security.Cryptography.SHA256]::Create()
        try {
            $digest = ([System.BitConverter]::ToString($sha256.ComputeHash($bytes))).Replace('-', '')
        }
        finally {
            $sha256.Dispose()
        }
        return [pscustomobject][ordered]@{
            Found = $true
            TimedOut = $false
            ExitCode = 0
            Digest = $digest
            Bytes = $bytes
        }
    }
    catch {
        return [pscustomobject][ordered]@{
            Found = $commandFound
            TimedOut = $false
            ExitCode = -1
            Digest = $null
            Bytes = [byte[]]@()
        }
    }
    finally {
        if ($null -ne $output) { $output.Dispose() }
        if ($null -ne $process) { $process.Dispose() }
    }
}

function Get-AiProviderVersion {
    param(
        [Parameter(Mandatory)][string] $Provider,
        [Parameter(Mandatory)][object] $ProviderProfile,
        [Parameter(Mandatory)][object] $ProviderLock,
        [Parameter(Mandatory)][AllowEmptyCollection()][System.Collections.Generic.List[object]] $Reasons,
        [Parameter(Mandatory)][AllowEmptyCollection()][System.Collections.Generic.List[object]] $Checks
    )

    $commandResult = Invoke-AiProcess -Command ([string]$ProviderProfile.command) -Arguments @('--version')
    $version = $null
    if ($commandResult.Found -and $commandResult.ExitCode -eq 0 -and $commandResult.StdOut -match '(?<![0-9])([0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?)') {
        $version = $Matches[1]
    }

    $testedVersions = @($ProviderLock.testedVersions | ForEach-Object { [string]$_ })
    $versionAccepted = -not [string]::IsNullOrWhiteSpace($version) -and $version -in $testedVersions
    if (-not $versionAccepted) {
        Add-AiReason -Reasons $Reasons `
            -Code 'PROVIDER_VERSION_NOT_IN_LOCK' `
            -Status 'UNTESTED_PROVIDER_VERSION' `
            -Severity 'ERROR' `
            -Lane 'compatibility' `
            -Provider $Provider `
            -ResourceId "provider:$Provider" `
            -Detail "The observed $Provider version is unavailable or is not in the tested lock." `
            -Evidence "observed=$version;tested=$($testedVersions -join ',')"
    }
    Add-AiCheck -Checks $Checks `
        -Id "provider.$Provider.version" `
        -Result $(if ($versionAccepted) { 'PASS' } else { 'FAIL' }) `
        -Severity $(if ($versionAccepted) { 'INFO' } else { 'ERROR' }) `
        -ReasonCode 'PROVIDER_VERSION_NOT_IN_LOCK' `
        -Owned $true `
        -Evidence "observed=$version;tested=$($testedVersions -join ',')"

    return $version
}

function Remove-AiTomlInlineComment {
    param([Parameter(Mandatory)][AllowEmptyString()][string] $Value)

    $quoteKind = ''
    $escaped = $false
    for ($index = 0; $index -lt $Value.Length; $index++) {
        $character = $Value[$index]
        if ($quoteKind -ceq 'basic') {
            if ($escaped) {
                $escaped = $false
            }
            elseif ($character -ceq '\') {
                $escaped = $true
            }
            elseif ($character -ceq '"') {
                $quoteKind = ''
            }
            continue
        }
        if ($quoteKind -ceq 'literal') {
            if ($character -ceq "'") {
                $quoteKind = ''
            }
            continue
        }

        if ($character -ceq '#') {
            return $Value.Substring(0, $index)
        }
        if ($character -ceq '"') {
            $quoteKind = 'basic'
        }
        elseif ($character -ceq "'") {
            $quoteKind = 'literal'
        }
    }

    if (-not [string]::IsNullOrEmpty($quoteKind)) {
        throw 'Malformed TOML scalar: unterminated quoted string.'
    }
    return $Value
}

function ConvertFrom-AiTomlScalar {
    param([Parameter(Mandatory)][AllowEmptyString()][string] $Value)

    $trimmed = (Remove-AiTomlInlineComment -Value $Value).Trim()
    if ([string]::IsNullOrWhiteSpace($trimmed)) {
        throw 'Malformed TOML scalar: value is empty.'
    }
    if ($trimmed[0] -eq "'") {
        if ($trimmed.Length -lt 2 -or $trimmed[-1] -ne "'") {
            throw 'Malformed TOML literal string.'
        }
        $literal = $trimmed.Substring(1, $trimmed.Length - 2)
        if ($literal.Contains("'")) {
            throw 'Malformed TOML literal string.'
        }
        return $literal
    }
    if ($trimmed[0] -eq '"') {
        if ($trimmed.Length -lt 2 -or $trimmed[-1] -ne '"') {
            throw 'Malformed TOML basic string.'
        }
        try {
            $parsed = $trimmed | ConvertFrom-Json -ErrorAction Stop
        }
        catch {
            throw "Malformed TOML basic string. $($_.Exception.Message)"
        }
        if ($parsed -isnot [string]) {
            throw 'Malformed TOML basic string.'
        }
        return $parsed
    }
    if ($trimmed -ceq 'true') { return $true }
    if ($trimmed -ceq 'false') { return $false }
    if ($trimmed -match '^-?[0-9]+$') {
        try {
            return [long]$trimmed
        }
        catch {
            throw "Malformed TOML integer '$trimmed'."
        }
    }
    throw "Unsupported or malformed TOML scalar '$trimmed'."
}

function Unquote-AiTomlKey {
    param([Parameter(Mandatory)][string] $Key)

    $trimmed = $Key.Trim()
    if ($trimmed.Length -ge 2 -and $trimmed[0] -eq $trimmed[-1] -and $trimmed[0] -in @("'", '"')) {
        return $trimmed.Substring(1, $trimmed.Length - 2)
    }
    return $trimmed
}

function Read-AiCodexConfig {
    param([Parameter(Mandatory)][string] $Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Codex config missing: $Path"
    }

    $marketplaces = [ordered]@{}
    $plugins = [ordered]@{}
    $hooks = [ordered]@{}
    $skills = [System.Collections.Generic.List[object]]::new()
    $sectionKind = $null
    $sectionName = $null
    $currentSkill = $null

    foreach ($rawLine in Get-Content -LiteralPath $Path) {
        $line = $rawLine.Trim()
        if ([string]::IsNullOrWhiteSpace($line) -or $line.StartsWith('#')) {
            continue
        }

        if ($line -ceq '[[skills.config]]') {
            $sectionKind = 'skill'
            $sectionName = $null
            $currentSkill = [pscustomobject][ordered]@{ Path = $null; Name = $null; Enabled = $null }
            $skills.Add($currentSkill) | Out-Null
            continue
        }
        if ($line -match '^\[marketplaces\.([^\]]+)\]$') {
            $sectionKind = 'marketplace'
            $sectionName = Unquote-AiTomlKey $Matches[1]
            if (-not $marketplaces.Contains($sectionName)) {
                $marketplaces[$sectionName] = [pscustomobject][ordered]@{
                    Name = $sectionName
                    SourceType = $null
                    Source = $null
                }
            }
            continue
        }
        if ($line -match '^\[plugins\.("[^"]+"|''[^'']+'')\]$') {
            $sectionKind = 'plugin'
            $sectionName = Unquote-AiTomlKey $Matches[1]
            if (-not $plugins.Contains($sectionName)) {
                $plugins[$sectionName] = [pscustomobject][ordered]@{ Name = $sectionName; Enabled = $null }
            }
            continue
        }
        if ($line -match '^\[hooks\.state\.(.+)\]$') {
            $sectionKind = 'hook'
            $sectionName = Unquote-AiTomlKey $Matches[1]
            if (-not $hooks.Contains($sectionName)) {
                $hooks[$sectionName] = [pscustomobject][ordered]@{
                    Key = $sectionName
                    TrustRecordPresent = $false
                    TrustedHash = $null
                }
            }
            continue
        }
        if ($line.StartsWith('[')) {
            $sectionKind = $null
            $sectionName = $null
            $currentSkill = $null
            continue
        }
        if ($line -notmatch '^([A-Za-z0-9_-]+)\s*=\s*(.*)$') {
            continue
        }

        $name = $Matches[1]
        $rawValue = $Matches[2]
        switch ($sectionKind) {
            'marketplace' {
                if ($name -cin @('source_type', 'source')) {
                    $value = ConvertFrom-AiTomlScalar $rawValue
                    if ($value -isnot [string]) {
                        throw "Malformed TOML string for marketplaces.$sectionName.$name."
                    }
                    if ($name -ceq 'source_type') { $marketplaces[$sectionName].SourceType = $value }
                    if ($name -ceq 'source') { $marketplaces[$sectionName].Source = $value }
                }
            }
            'plugin' {
                if ($name -ceq 'enabled') {
                    $value = ConvertFrom-AiTomlScalar $rawValue
                    if ($value -isnot [bool]) {
                        throw "Malformed TOML boolean for plugins.$sectionName.enabled."
                    }
                    $plugins[$sectionName].Enabled = $value
                }
            }
            'hook' {
                if ($name -ceq 'trusted_hash') {
                    $value = ConvertFrom-AiTomlScalar $rawValue
                    if ($value -isnot [string]) {
                        throw "Malformed TOML string for hooks.state.$sectionName.trusted_hash."
                    }
                    $hooks[$sectionName].TrustedHash = $value
                    if (-not [string]::IsNullOrWhiteSpace($value)) {
                        $hooks[$sectionName].TrustRecordPresent = $true
                    }
                }
            }
            'skill' {
                if ($name -cin @('path', 'name')) {
                    $value = ConvertFrom-AiTomlScalar $rawValue
                    if ($value -isnot [string]) {
                        throw "Malformed TOML string for skills.config.$name."
                    }
                    if ($name -ceq 'path') { $currentSkill.Path = $value }
                    if ($name -ceq 'name') { $currentSkill.Name = $value }
                }
                if ($name -ceq 'enabled') {
                    $value = ConvertFrom-AiTomlScalar $rawValue
                    if ($value -isnot [bool]) {
                        throw 'Malformed TOML boolean for skills.config.enabled.'
                    }
                    $currentSkill.Enabled = $value
                }
            }
        }
    }

    return [pscustomobject][ordered]@{
        Marketplaces = $marketplaces
        Plugins = $plugins
        Hooks = $hooks
        Skills = @($skills)
    }
}

function Get-AiLockCommitPayloadObservation {
    param(
        [Parameter(Mandatory)][object] $Profile,
        [Parameter(Mandatory)][object] $Lock,
        [Parameter(Mandatory)][string] $RepositoryRoot
    )

    $resolvedRepositoryRoot = Resolve-AiPath $RepositoryRoot
    $commit = [string]$Lock.source.commit
    $payloadExpected = @($Lock.resources | ForEach-Object { @($_.payload).Count } | Measure-Object -Sum).Sum
    if ($null -eq $payloadExpected) { $payloadExpected = 0 }
    $versionExpected = @($Lock.resources | Where-Object {
        $profileResource = Get-AiProfileResource -Profile $Profile -Id ([string]$_.id)
        [string](Get-AiProperty $profileResource 'kind') -ceq 'plugin' -or
            -not [string]::IsNullOrWhiteSpace([string](Get-AiProperty $_ 'version'))
    }).Count
    $payloadMatched = 0
    $versionMatched = 0
    $mappingFailures = 0
    $blobFailures = 0
    $timedOut = $false

    $commitType = Invoke-AiProcess -Command 'git' -Arguments @('-C', $resolvedRepositoryRoot, 'cat-file', '-t', $commit)
    $commitObjectValid = $commitType.Found -and
        -not [bool]$commitType.TimedOut -and
        $commitType.ExitCode -eq 0 -and
        $commitType.StdOut.Trim() -ceq 'commit'
    $timedOut = [bool]$commitType.TimedOut

    if ($commitObjectValid) {
        foreach ($lockResource in @($Lock.resources | Sort-Object id)) {
            $profileResource = Get-AiProfileResource -Profile $Profile -Id ([string]$lockResource.id)
            $sourceRootValue = [string](Get-AiProperty (Get-AiProperty $profileResource 'desired') 'sourceRoot')
            $resourceVersion = [string](Get-AiProperty $lockResource 'version')
            $versionRequired = [string](Get-AiProperty $profileResource 'kind') -ceq 'plugin' -or
                -not [string]::IsNullOrWhiteSpace($resourceVersion)
            $versionManifestObserved = $false
            if ($null -eq $profileResource -or [string]::IsNullOrWhiteSpace($sourceRootValue)) {
                $mappingFailures++
                continue
            }
            if ($versionRequired -and [string]::IsNullOrWhiteSpace($resourceVersion)) {
                $mappingFailures++
            }

            foreach ($entry in @($lockResource.payload)) {
                $relativePath = [string](Get-AiProperty $entry 'path')
                $expectedDigest = ([string](Get-AiProperty $entry 'sha256')).ToUpperInvariant()
                try {
                    $sourcePath = Resolve-AiChildPath -Root $sourceRootValue -RelativePath $relativePath
                    $repositoryRelativePath = [System.IO.Path]::GetRelativePath($resolvedRepositoryRoot, $sourcePath)
                    if ([System.IO.Path]::IsPathRooted($repositoryRelativePath) -or
                        $repositoryRelativePath -ceq '..' -or
                        $repositoryRelativePath.StartsWith("..$([System.IO.Path]::DirectorySeparatorChar)", [System.StringComparison]::Ordinal)) {
                        throw 'Resource source root is outside the repository.'
                    }
                    $gitPath = $repositoryRelativePath.Replace('\', '/')
                }
                catch {
                    $mappingFailures++
                    continue
                }

                $blob = Get-AiGitBlobDigest -RepositoryRoot $resolvedRepositoryRoot -ObjectSpec "$commit`:$gitPath"
                $timedOut = $timedOut -or [bool]$blob.TimedOut
                if ($blob.ExitCode -eq 0 -and [string]$blob.Digest -ceq $expectedDigest) {
                    $payloadMatched++
                }
                else {
                    $blobFailures++
                }

                if ($versionRequired -and $relativePath.Replace('\', '/') -ceq '.codex-plugin/plugin.json') {
                    $versionManifestObserved = $true
                    if ($blob.ExitCode -eq 0 -and -not [string]::IsNullOrWhiteSpace($resourceVersion)) {
                        try {
                            $utf8 = [System.Text.UTF8Encoding]::new($false, $true)
                            $manifest = $utf8.GetString([byte[]]$blob.Bytes) | ConvertFrom-Json -Depth 50
                            if ([string](Get-AiProperty $manifest 'version') -ceq $resourceVersion) {
                                $versionMatched++
                            }
                        }
                        catch { }
                    }
                }
            }

            if ($versionRequired -and -not $versionManifestObserved) {
                $mappingFailures++
            }
        }
    }

    $verified = $commitObjectValid -and
        $payloadMatched -eq $payloadExpected -and
        $versionMatched -eq $versionExpected -and
        $mappingFailures -eq 0 -and
        $blobFailures -eq 0 -and
        -not $timedOut
    return [pscustomobject][ordered]@{
        Verified = $verified
        CommitObjectValid = $commitObjectValid
        PayloadExpected = [int]$payloadExpected
        PayloadMatched = $payloadMatched
        VersionExpected = $versionExpected
        VersionMatched = $versionMatched
        MappingFailures = $mappingFailures
        BlobFailures = $blobFailures
        TimedOut = $timedOut
    }
}

function Compare-AiLockedPayload {
    param(
        [Parameter(Mandatory)][object] $ProfileResource,
        [AllowNull()][object] $LockResource,
        [Parameter(Mandatory)][AllowEmptyCollection()][System.Collections.Generic.List[object]] $Reasons,
        [Parameter(Mandatory)][AllowEmptyCollection()][System.Collections.Generic.List[object]] $Checks
    )

    $resourceId = [string]$ProfileResource.id
    $provider = [string]$ProfileResource.provider
    $owned = [string]$ProfileResource.ownership -ceq 'managed'
    if ($null -eq $LockResource) {
        Add-AiReason -Reasons $Reasons `
            -Code 'RESOURCE_LOCK_MISSING' `
            -Status 'SOURCE_UNTRUSTED' `
            -Severity 'ERROR' `
            -Lane 'artifact' `
            -Provider $provider `
            -ResourceId $resourceId `
            -Detail 'The resource has no payload entry in the lock.'
        Add-AiCheck -Checks $Checks -Id "resource.$resourceId.payload" -Result 'FAIL' -Severity 'ERROR' -ReasonCode 'RESOURCE_LOCK_MISSING' -Owned $owned
        return [pscustomobject][ordered]@{ Expected = 0; SourceMatched = 0; TargetMatched = 0; Missing = 0; Mismatched = 0 }
    }

    $sourceRoot = [string](Get-AiProperty $ProfileResource.desired 'sourceRoot')
    $targetRoot = [string](Get-AiProperty $ProfileResource.desired 'targetRoot')
    $payload = @($LockResource.payload)
    $sourceMatched = 0
    $targetMatched = 0
    $missing = 0
    $mismatched = 0
    foreach ($entry in $payload) {
        $relativePath = [string]$entry.path
        $expectedHash = ([string]$entry.sha256).ToUpperInvariant()
        $sourcePath = Resolve-AiChildPath -Root $sourceRoot -RelativePath $relativePath
        $targetPath = Resolve-AiChildPath -Root $targetRoot -RelativePath $relativePath
        $sourceHash = Get-AiFileDigest $sourcePath
        $targetHash = Get-AiFileDigest $targetPath
        if ($null -eq $sourceHash) {
            $missing++
        }
        elseif ($sourceHash -ceq $expectedHash) {
            $sourceMatched++
        }
        else {
            $mismatched++
        }
        if ($null -eq $targetHash) {
            $missing++
        }
        elseif ($targetHash -ceq $expectedHash) {
            $targetMatched++
        }
        else {
            $mismatched++
        }
    }

    $sourceHealthy = $sourceMatched -eq $payload.Count
    $targetHealthy = $targetMatched -eq $payload.Count
    $evidence = "expected=$($payload.Count);sourceMatched=$sourceMatched;targetMatched=$targetMatched;missing=$missing;mismatched=$mismatched"
    if (-not $sourceHealthy) {
        Add-AiReason -Reasons $Reasons `
            -Code 'LOCK_PAYLOAD_MISMATCH' `
            -Status 'SOURCE_UNTRUSTED' `
            -Severity 'ERROR' `
            -Lane 'artifact' `
            -Provider $provider `
            -ResourceId $resourceId `
            -Detail 'The source payload does not match the candidate or accepted lock.' `
            -Evidence $evidence
    }
    if (-not $targetHealthy) {
        $projectionReasonCode = [string](Get-AiProperty $ProfileResource.desired 'projectionReasonCode' 'RESOURCE_PROJECTION_MISMATCH')
        Add-AiReason -Reasons $Reasons `
            -Code $projectionReasonCode `
            -Status 'DRIFTED' `
            -Severity 'ERROR' `
            -Lane 'projection' `
            -Provider $provider `
            -ResourceId $resourceId `
            -Detail 'The installed payload does not match the locked payload.' `
            -Evidence $evidence
    }
    Add-AiCheck -Checks $Checks `
        -Id "resource.$resourceId.payload" `
        -Result $(if ($sourceHealthy -and $targetHealthy) { 'PASS' } else { 'FAIL' }) `
        -Severity $(if ($sourceHealthy -and $targetHealthy) { 'INFO' } else { 'ERROR' }) `
        -ReasonCode $(if ($sourceHealthy -and $targetHealthy) { 'PAYLOAD_MATCH' } else { 'LOCK_PAYLOAD_MISMATCH' }) `
        -Owned $owned `
        -Evidence $evidence

    return [pscustomobject][ordered]@{
        Expected = $payload.Count
        SourceMatched = $sourceMatched
        TargetMatched = $targetMatched
        Missing = $missing
        Mismatched = $mismatched
    }
}

function Get-AiGitObservation {
    param(
        [Parameter(Mandatory)][object] $Profile,
        [Parameter(Mandatory)][object] $Lock,
        [Parameter(Mandatory)][AllowEmptyCollection()][System.Collections.Generic.List[object]] $Reasons,
        [Parameter(Mandatory)][AllowEmptyCollection()][System.Collections.Generic.List[object]] $Checks
    )

    $repositoryRoot = Resolve-AiPath ([string]$Profile.source.repositoryRoot)
    $gitMetadataPresent = Test-Path -LiteralPath (Join-Path $repositoryRoot '.git')
    $head = $null
    $branch = $null
    $dirtyCount = 0
    $gitObservationFailed = $false
    $lockCommitPayloadObservation = [pscustomobject][ordered]@{
        Verified = $false
        CommitObjectValid = $false
        PayloadExpected = @($Lock.resources | ForEach-Object { @($_.payload).Count } | Measure-Object -Sum).Sum
        PayloadMatched = 0
        VersionExpected = @($Lock.resources | Where-Object { -not [string]::IsNullOrWhiteSpace([string](Get-AiProperty $_ 'version')) }).Count
        VersionMatched = 0
        MappingFailures = 0
        BlobFailures = 0
        TimedOut = $false
    }
    if (-not $gitMetadataPresent) {
        Add-AiReason -Reasons $Reasons -Code 'SOURCE_GIT_METADATA_MISSING' -Status 'SOURCE_UNTRUSTED' -Severity 'BLOCKER' -Lane 'source' -ResourceId 'source:ai-skills' -Detail 'The source root has no Git metadata.'
        Add-AiCheck -Checks $Checks -Id 'source.git-metadata' -Result 'FAIL' -Severity 'BLOCKER' -ReasonCode 'SOURCE_GIT_METADATA_MISSING' -Owned $true
    }
    else {
        $headResult = Invoke-AiProcess -Command 'git' -Arguments @('-C', $repositoryRoot, 'rev-parse', 'HEAD')
        $branchResult = Invoke-AiProcess -Command 'git' -Arguments @('-C', $repositoryRoot, 'branch', '--show-current')
        if ($headResult.ExitCode -eq 0) { $head = $headResult.StdOut.Trim() }
        else { $gitObservationFailed = $true }
        if ($branchResult.ExitCode -eq 0) { $branch = $branchResult.StdOut.Trim() }
        else { $gitObservationFailed = $true }
        foreach ($arguments in @(
            @('-C', $repositoryRoot, 'diff', '--name-only', '--ignore-space-at-eol'),
            @('-C', $repositoryRoot, 'diff', '--cached', '--name-only'),
            @('-C', $repositoryRoot, 'ls-files', '--others', '--exclude-standard')
        )) {
            $result = Invoke-AiProcess -Command 'git' -Arguments $arguments
            if ($result.ExitCode -eq 0 -and -not [string]::IsNullOrWhiteSpace($result.StdOut)) {
                $dirtyCount += @($result.StdOut -split '\r?\n' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }).Count
            }
            elseif ($result.ExitCode -ne 0) {
                $gitObservationFailed = $true
            }
        }
        Add-AiCheck -Checks $Checks -Id 'source.git-metadata' -Result 'PASS' -Severity 'INFO' -ReasonCode 'SOURCE_GIT_METADATA_PRESENT' -Owned $true -Evidence "head=$head"
        if ($gitObservationFailed) {
            Add-AiReason -Reasons $Reasons -Code 'SOURCE_GIT_OBSERVATION_FAILED' -Status 'SOURCE_UNTRUSTED' -Severity 'BLOCKER' -Lane 'source' -ResourceId 'source:ai-skills' -Detail 'One or more bounded Git observations did not complete successfully.' -Evidence 'complete=false'
        }
        Add-AiCheck -Checks $Checks -Id 'source.git-observation' -Result $(if ($gitObservationFailed) { 'FAIL' } else { 'PASS' }) -Severity $(if ($gitObservationFailed) { 'BLOCKER' } else { 'INFO' }) -ReasonCode 'SOURCE_GIT_OBSERVATION_FAILED' -Owned $true -Evidence "complete=$(-not $gitObservationFailed)"
        $lockCommitPayloadObservation = Get-AiLockCommitPayloadObservation -Profile $Profile -Lock $Lock -RepositoryRoot $repositoryRoot
    }

    $lockCommitEvidence = "commitObjectValid=$($lockCommitPayloadObservation.CommitObjectValid);payloadExpected=$($lockCommitPayloadObservation.PayloadExpected);payloadMatched=$($lockCommitPayloadObservation.PayloadMatched);versionExpected=$($lockCommitPayloadObservation.VersionExpected);versionMatched=$($lockCommitPayloadObservation.VersionMatched);mappingFailures=$($lockCommitPayloadObservation.MappingFailures);blobFailures=$($lockCommitPayloadObservation.BlobFailures);timedOut=$($lockCommitPayloadObservation.TimedOut)"
    if (-not $lockCommitPayloadObservation.Verified) {
        Add-AiReason -Reasons $Reasons -Code 'LOCK_COMMIT_PAYLOAD_MISMATCH' -Status 'SOURCE_UNTRUSTED' -Severity 'BLOCKER' -Lane 'artifact' -ResourceId 'lock:ai-environment' -Detail 'The lock commit, raw payload blobs, or committed plugin version do not match the lock.' -Evidence $lockCommitEvidence
    }
    Add-AiCheck -Checks $Checks -Id 'source.lock-commit-payload' -Result $(if ($lockCommitPayloadObservation.Verified) { 'PASS' } else { 'FAIL' }) -Severity $(if ($lockCommitPayloadObservation.Verified) { 'INFO' } else { 'BLOCKER' }) -ReasonCode 'LOCK_COMMIT_PAYLOAD_MISMATCH' -Owned $true -Evidence $lockCommitEvidence

    $headMatchesLock = -not [string]::IsNullOrWhiteSpace($head) -and $head -ceq [string]$Lock.source.commit
    if ($gitMetadataPresent -and -not $headMatchesLock) {
        Add-AiReason -Reasons $Reasons -Code 'SOURCE_COMMIT_MISMATCH' -Status 'SOURCE_UNTRUSTED' -Severity 'BLOCKER' -Lane 'source' -ResourceId 'source:ai-skills' -Detail 'The source HEAD does not match the lock commit.' -Evidence "head=$head;lock=$($Lock.source.commit)"
    }
    if ($dirtyCount -gt 0) {
        Add-AiReason -Reasons $Reasons -Code 'SOURCE_WORKTREE_DIRTY' -Status 'SOURCE_UNTRUSTED' -Severity 'ERROR' -Lane 'source' -ResourceId 'source:ai-skills' -Detail 'The source worktree contains unaccepted changes.' -Evidence "substantivePaths=$dirtyCount"
    }
    if ([string]$Lock.state -cne 'accepted') {
        Add-AiReason -Reasons $Reasons -Code 'LOCK_NOT_ACCEPTED' -Status 'SOURCE_UNTRUSTED' -Severity 'BLOCKER' -Lane 'artifact' -ResourceId 'lock:ai-environment' -Detail 'The current lock is a candidate and is not an accepted promotion artifact.' -Evidence "state=$($Lock.state)"
    }

    $worktreeClean = $dirtyCount -eq 0 -and -not $gitObservationFailed
    Add-AiCheck -Checks $Checks -Id 'source.worktree' -Result $(if ($worktreeClean) { 'PASS' } else { 'FAIL' }) -Severity $(if ($worktreeClean) { 'INFO' } else { 'ERROR' }) -ReasonCode 'SOURCE_WORKTREE_DIRTY' -Owned $true -Evidence "substantivePaths=$dirtyCount"
    Add-AiCheck -Checks $Checks -Id 'source.lock' -Result $(if ([string]$Lock.state -ceq 'accepted' -and $headMatchesLock) { 'PASS' } else { 'FAIL' }) -Severity $(if ([string]$Lock.state -ceq 'accepted' -and $headMatchesLock) { 'INFO' } else { 'BLOCKER' }) -ReasonCode 'LOCK_NOT_ACCEPTED' -Owned $true -Evidence "state=$($Lock.state);headMatches=$headMatchesLock"

    $reproducible = $gitMetadataPresent -and -not $gitObservationFailed -and $lockCommitPayloadObservation.Verified -and $headMatchesLock -and [string]$Lock.state -ceq 'accepted' -and (
        -not [bool]$Lock.source.requireCleanWorktree -or $worktreeClean
    )
    return [pscustomobject][ordered]@{
        Repository = '{REPO_ROOT}'
        GitMetadataPresent = $gitMetadataPresent
        Head = $head
        Branch = $branch
        WorktreeClean = $worktreeClean
        DirtyPathCount = $dirtyCount
        LockState = [string]$Lock.state
        LockCommit = [string]$Lock.source.commit
        HeadMatchesLock = $headMatchesLock
        Reproducible = $reproducible
    }
}

function Get-AiSharedSkillObservation {
    param(
        [Parameter(Mandatory)][object] $Profile,
        [Parameter(Mandatory)][AllowEmptyCollection()][System.Collections.Generic.List[object]] $Reasons,
        [Parameter(Mandatory)][AllowEmptyCollection()][System.Collections.Generic.List[object]] $Checks
    )

    $root = Resolve-AiPath ([string]$Profile.sharedSkills.root)
    $lockPath = Resolve-AiPath ([string]$Profile.sharedSkills.lockPath)
    $installedNames = @()
    if (Test-Path -LiteralPath $root -PathType Container) {
        $installedNames = @(Get-ChildItem -LiteralPath $root -Directory -Force | Where-Object {
            Test-Path -LiteralPath (Join-Path $_.FullName 'SKILL.md') -PathType Leaf
        } | Select-Object -ExpandProperty Name | Sort-Object -Unique)
    }

    $recordedNames = @()
    $missingRecordedPaths = 0
    $lockVersion = $null
    if (Test-Path -LiteralPath $lockPath -PathType Leaf) {
        try {
            $skillLock = Get-Content -Raw -LiteralPath $lockPath | ConvertFrom-Json -Depth 100
            $lockVersion = Get-AiProperty $skillLock 'version'
            $skillsObject = Get-AiProperty $skillLock 'skills'
            if ($null -ne $skillsObject) {
                $recordedNames = @($skillsObject.PSObject.Properties.Name | Sort-Object -Unique)
                foreach ($property in $skillsObject.PSObject.Properties) {
                    $recordedPath = [string](Get-AiProperty $property.Value 'path')
                    if (-not [string]::IsNullOrWhiteSpace($recordedPath) -and -not (Test-Path -LiteralPath (Resolve-AiPath $recordedPath))) {
                        $missingRecordedPaths++
                    }
                }
            }
        }
        catch {
            $missingRecordedPaths++
        }
    }
    else {
        $missingRecordedPaths++
    }

    $missingRecordedPaths += @($recordedNames | Where-Object { $_ -notin $installedNames }).Count
    $unrecordedCount = @($installedNames | Where-Object { $_ -notin $recordedNames }).Count
    $complete = $missingRecordedPaths -eq 0 -and $unrecordedCount -eq 0
    $evidence = "installed=$($installedNames.Count);recorded=$($recordedNames.Count);missingRecordedPaths=$missingRecordedPaths;unrecorded=$unrecordedCount"
    if (-not $complete) {
        Add-AiReason -Reasons $Reasons -Code 'SHARED_SKILL_LOCK_INCOMPLETE' -Status 'DRIFTED' -Severity 'WARNING' -Lane 'artifact' -Provider 'shared' -ResourceId 'skill-root:shared' -Detail 'The shared skill lock does not fully describe the installed shared skill root.' -Evidence $evidence
    }
    Add-AiCheck -Checks $Checks -Id 'shared-skills.lock-coverage' -Result $(if ($complete) { 'PASS' } else { 'FAIL' }) -Severity $(if ($complete) { 'INFO' } else { 'WARNING' }) -ReasonCode 'SHARED_SKILL_LOCK_INCOMPLETE' -Owned $false -Evidence $evidence

    return [pscustomobject][ordered]@{
        Root = '{AGENTS_HOME}/skills'
        Lock = '{AGENTS_HOME}/.skill-lock.json'
        LockVersion = $lockVersion
        InstalledCount = $installedNames.Count
        RecordedCount = $recordedNames.Count
        MissingRecordedPathCount = $missingRecordedPaths
        UnrecordedCount = $unrecordedCount
        Complete = $complete
    }
}

function Get-AiTopStatus {
    param([Parameter(Mandatory)][AllowNull()][AllowEmptyCollection()][object[]] $Reasons)

    $active = @($Reasons | Where-Object { $null -ne $_ } | ForEach-Object { [string]$_.Status } | Sort-Object -Unique)
    if ($active.Count -eq 0) {
        return 'CURRENT'
    }
    foreach ($candidate in @(
        'ACCEPTANCE_FAILED',
        'SOURCE_UNTRUSTED',
        'PENDING_TRUST',
        'UNTESTED_PROVIDER_VERSION',
        'DRIFTED',
        'DEGRADED_FOREIGN_MARKETPLACE'
    )) {
        if ($candidate -in $active) {
            return $candidate
        }
    }
    return 'DRIFTED'
}

function Sort-AiReasons {
    param([Parameter(Mandatory)][AllowNull()][AllowEmptyCollection()][object[]] $Reasons)

    $rank = @{ BLOCKER = 0; ERROR = 1; WARNING = 2; INFO = 3 }
    return @($Reasons | Sort-Object `
        @{ Expression = { $rank[[string]$_.Severity] } }, `
        Provider, ResourceId, Lane, Code -Unique)
}
