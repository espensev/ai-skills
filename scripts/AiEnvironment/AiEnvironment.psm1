Set-StrictMode -Version Latest

$privateRoot = Join-Path $PSScriptRoot 'Private'
foreach ($privateFile in @(
    'Common.ps1',
    'Get-CodexEnvironmentObservation.ps1',
    'Get-ClaudeEnvironmentObservation.ps1'
)) {
    . (Join-Path $privateRoot $privateFile)
}

$script:DefaultProfilePath = Join-Path $PSScriptRoot 'profiles\snd-desk.json'
$script:DefaultLockPath = Join-Path $PSScriptRoot 'locks\snd-desk.lock.json'
$script:ProfileSchemaPath = Join-Path $PSScriptRoot 'schemas\profile.schema.json'
$script:LockSchemaPath = Join-Path $PSScriptRoot 'schemas\lock.schema.json'
$script:StateSchemaPath = Join-Path $PSScriptRoot 'schemas\state.schema.json'

function Get-AiEnvironmentState {
    [CmdletBinding()]
    param(
        [string] $ProfilePath = $script:DefaultProfilePath,
        [string] $LockPath = $script:DefaultLockPath
    )

    $profile = Read-AiJsonDocument -Path $ProfilePath -ExpectedSchema 'ai-skills/ai-environment-profile/v1' -SchemaPath $script:ProfileSchemaPath
    $lock = Read-AiJsonDocument -Path $LockPath -ExpectedSchema 'ai-skills/ai-environment-lock/v1' -SchemaPath $script:LockSchemaPath
    Assert-AiDocumentContracts -Profile $profile -Lock $lock

    $reasons = [System.Collections.Generic.List[object]]::new()
    $checks = [System.Collections.Generic.List[object]]::new()
    $source = Get-AiGitObservation -Profile $profile -Lock $lock -Reasons $reasons -Checks $checks
    $codex = Get-CodexEnvironmentObservation -Profile $profile -Lock $lock -Reasons $reasons -Checks $checks
    $claude = Get-ClaudeEnvironmentObservation -Profile $profile -Lock $lock -Reasons $reasons -Checks $checks
    $sharedSkills = Get-AiSharedSkillObservation -Profile $profile -Reasons $reasons -Checks $checks

    $acceptanceRows = [System.Collections.Generic.List[object]]::new()
    foreach ($acceptance in @($profile.acceptance | Sort-Object id)) {
        $acceptanceId = [string]$acceptance.id
        $lockAcceptance = @($lock.acceptance | Where-Object { [string]$_.id -ceq $acceptanceId }) | Select-Object -First 1
        $status = if ($null -eq $lockAcceptance) { 'NOT_RUN' } else { [string]$lockAcceptance.status }
        $evidence = if ($null -eq $lockAcceptance) { 'no lock record' } else { [string]$lockAcceptance.evidence }
        if ($status -ceq 'FAIL') {
            Add-AiReason -Reasons $reasons -Code 'REMEMBER_ACCEPTANCE_FAILED' -Status 'ACCEPTANCE_FAILED' -Severity 'BLOCKER' -Lane 'acceptance' -Provider ([string]$acceptance.provider) -ResourceId "acceptance:$acceptanceId" -Detail ([string]$acceptance.description) -Evidence $evidence
        }
        elseif ($status -cne 'PASS') {
            Add-AiReason -Reasons $reasons -Code 'ACCEPTANCE_NOT_RUN' -Status 'ACCEPTANCE_FAILED' -Severity 'BLOCKER' -Lane 'acceptance' -Provider ([string]$acceptance.provider) -ResourceId "acceptance:$acceptanceId" -Detail 'A required behavioral acceptance gate has not passed.' -Evidence $evidence
        }
        Add-AiCheck -Checks $checks -Id "acceptance.$acceptanceId" -Result $status -Severity $(if ($status -ceq 'PASS') { 'INFO' } else { 'BLOCKER' }) -ReasonCode $(if ($status -ceq 'PASS') { 'ACCEPTANCE_PASSED' } elseif ($status -ceq 'FAIL') { 'REMEMBER_ACCEPTANCE_FAILED' } else { 'ACCEPTANCE_NOT_RUN' }) -Owned $([string]$acceptance.ownership -ceq 'managed') -Evidence $evidence
        $checkedAtUtc = $null
        if ($null -ne $lockAcceptance) {
            $checkedAtValue = Get-AiProperty $lockAcceptance 'checkedAtUtc'
            $checkedAtUtc = if ($checkedAtValue -is [DateTime]) {
                $checkedAtValue.ToUniversalTime().ToString('o')
            }
            else {
                [string]$checkedAtValue
            }
        }
        $acceptanceRows.Add([pscustomobject][ordered]@{
            Id = $acceptanceId
            Provider = [string]$acceptance.provider
            Ownership = [string]$acceptance.ownership
            Status = $status
            CheckedAtUtc = $checkedAtUtc
        }) | Out-Null
    }

    $sortedReasons = Sort-AiReasons @($reasons)
    $resourceRows = foreach ($resource in @($profile.resources | Sort-Object id)) {
        $resourceReasons = @($sortedReasons | Where-Object { [string]$_.ResourceId -ceq [string]$resource.id })
        [pscustomobject][ordered]@{
            Id = [string]$resource.id
            Provider = [string]$resource.provider
            Kind = [string]$resource.kind
            Ownership = [string]$resource.ownership
            Status = if ($resourceReasons.Count -eq 0) { 'CURRENT' } else { Get-AiTopStatus $resourceReasons }
            ReasonCodes = @($resourceReasons | Select-Object -ExpandProperty Code -Unique | Sort-Object)
        }
    }

    $activeStatuses = @($sortedReasons | Select-Object -ExpandProperty Status -Unique | Sort-Object)
    if ($activeStatuses.Count -eq 0) {
        $activeStatuses = @('CURRENT')
    }
    $topStatus = Get-AiTopStatus $sortedReasons
    $repairBlockingReasons = @($sortedReasons | Where-Object {
        $_.Code -in @(
            'LOCK_NOT_ACCEPTED',
            'SOURCE_GIT_METADATA_MISSING',
            'SOURCE_GIT_OBSERVATION_FAILED',
            'SOURCE_WORKTREE_DIRTY',
            'SOURCE_COMMIT_MISMATCH',
            'LOCK_COMMIT_PAYLOAD_MISMATCH',
            'LOCK_PAYLOAD_MISMATCH',
            'RESOURCE_LOCK_MISSING'
        )
    })

    $state = [pscustomobject][ordered]@{
        Schema = 'ai-skills/ai-environment-state/v1'
        ProfileId = [string]$profile.id
        ObservedAtUtc = [DateTime]::UtcNow.ToString('o')
        Machine = [pscustomobject][ordered]@{
            ExpectedId = [string]$profile.machine.id
            ExpectedInstanceId = [string]$profile.machine.instanceId
            Verification = 'NOT_REQUIRED_FOR_READ_ONLY_OBSERVATION'
        }
        Source = $source
        Providers = [pscustomobject][ordered]@{
            Codex = $codex
            Claude = $claude
        }
        SharedSkills = $sharedSkills
        Resources = @($resourceRows)
        Acceptance = [pscustomobject][ordered]@{
            Passed = @($acceptanceRows | Where-Object Status -ne 'PASS').Count -eq 0
            Checks = @($acceptanceRows)
        }
        Checks = @($checks | Sort-Object Id, ReasonCode -Unique)
        Reasons = @($sortedReasons)
        ActiveStatuses = @($activeStatuses)
        Status = $topStatus
        PromotionReady = $topStatus -ceq 'CURRENT'
        RepairReady = [bool]$source.Reproducible -and $repairBlockingReasons.Count -eq 0
    }
    Assert-AiJsonValueMatchesSchema -Value $state -SchemaPath $script:StateSchemaPath -Label 'AI environment observed state'
    return $state
}

function New-AiEnvironmentPlan {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory, ValueFromPipeline)][object] $State
    )

    process {
        if ([string](Get-AiProperty $State 'Schema') -cne 'ai-skills/ai-environment-state/v1') {
            throw 'New-AiEnvironmentPlan requires an ai-skills/ai-environment-state/v1 snapshot.'
        }

        $actions = [System.Collections.Generic.List[object]]::new()
        foreach ($reason in @($State.Reasons)) {
            $resource = @($State.Resources | Where-Object { [string]$_.Id -ceq [string]$reason.ResourceId }) | Select-Object -First 1
            $ownership = if ($null -eq $resource) { 'observed' } else { [string]$resource.Ownership }
            $actionType = switch ([string]$reason.Code) {
                { $_ -in @('LOCK_NOT_ACCEPTED', 'SOURCE_GIT_METADATA_MISSING', 'SOURCE_GIT_OBSERVATION_FAILED', 'SOURCE_WORKTREE_DIRTY', 'SOURCE_COMMIT_MISMATCH', 'LOCK_COMMIT_PAYLOAD_MISMATCH', 'LOCK_PAYLOAD_MISMATCH', 'RESOURCE_LOCK_MISSING') } { 'BLOCK_PROMOTION'; break }
                { $_ -in @('REMEMBER_ACCEPTANCE_FAILED', 'ACCEPTANCE_NOT_RUN') } { 'RUN_ACCEPTANCE_GATE'; break }
                { $_ -in @('OWNED_HOOK_TRUST_RECORD_MISSING', 'OWNED_HOOK_TRUST_HASH_NOT_LOCKED', 'OWNED_HOOK_TRUST_HASH_MISMATCH') } { 'MANUAL_TRUST_REVIEW'; break }
                'PROVIDER_VERSION_NOT_IN_LOCK' { 'RUN_COMPATIBILITY_GATE'; break }
                { $_ -in @('FOREIGN_MARKETPLACE_NOT_CONFIGURED', 'FOREIGN_MARKETPLACE_ROOT_MISSING', 'FOREIGN_MARKETPLACE_MANIFEST_INVALID', 'CODEX_CONTROL_PLANE_UNAVAILABLE') } { 'REVIEW_FOREIGN_OWNER'; break }
                default {
                    if ($ownership -ceq 'managed' -and [bool]$State.RepairReady) {
                        'RECONCILE_FROM_ACCEPTED_LOCK'
                    }
                    elseif ($ownership -ceq 'managed') {
                        'BLOCKED_RECONCILIATION'
                    }
                    else {
                        'REVIEW_OBSERVED_DRIFT'
                    }
                }
            }
            $actions.Add([pscustomobject][ordered]@{
                Id = "action:$($reason.Code.ToLowerInvariant().Replace('_', '-')):$($reason.ResourceId)"
                Type = $actionType
                ResourceId = [string]$reason.ResourceId
                Ownership = $ownership
                Lane = [string]$reason.Lane
                RequiresApproval = $true
                Detail = [string]$reason.Detail
            }) | Out-Null
        }

        return [pscustomobject][ordered]@{
            Schema = 'ai-skills/ai-environment-plan/v1'
            ProfileId = [string]$State.ProfileId
            StateStatus = [string]$State.Status
            ReadOnly = $true
            CanApply = $false
            Actions = @($actions | Sort-Object Id -Unique)
        }
    }
}

function Test-AiEnvironment {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory, ValueFromPipeline)][object] $State
    )

    process {
        if ([string](Get-AiProperty $State 'Schema') -cne 'ai-skills/ai-environment-state/v1') {
            throw 'Test-AiEnvironment requires an ai-skills/ai-environment-state/v1 snapshot.'
        }
        $blockingReasons = @($State.Reasons | Where-Object Severity -in @('ERROR', 'BLOCKER'))
        $failedChecks = @($State.Checks | Where-Object Result -in @('FAIL', 'NOT_RUN'))
        return [pscustomobject][ordered]@{
            Schema = 'ai-skills/ai-environment-verification/v1'
            ProfileId = [string]$State.ProfileId
            Passed = [bool]$State.PromotionReady
            Status = [string]$State.Status
            BlockingReasonCount = $blockingReasons.Count
            FailedCheckCount = $failedChecks.Count
            BlockingReasonCodes = @($blockingReasons | Select-Object -ExpandProperty Code -Unique | Sort-Object)
        }
    }
}

function Format-AiLockUtcTimestamp {
    param([Parameter(Mandatory)][object] $Value)

    if ($Value -is [DateTime]) {
        return $Value.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    }
    if ($Value -is [DateTimeOffset]) {
        return $Value.UtcDateTime.ToString('yyyy-MM-ddTHH:mm:ssZ')
    }
    return [string]$Value
}

function Save-AiEnvironmentState {
    [CmdletBinding(SupportsShouldProcess)]
    param(
        [Parameter(ValueFromPipeline)][object] $State,
        [string] $ProfilePath = $script:DefaultProfilePath,
        [string] $LockPath = $script:DefaultLockPath,
        [string] $OutputPath = '',
        [string] $VerifierPath = '',
        [switch] $PassThru
    )

    process {
        $effectiveState = if ($null -eq $State) {
            Get-AiEnvironmentState -ProfilePath $ProfilePath -LockPath $LockPath
        }
        else {
            $State
        }

        if ([string](Get-AiProperty $effectiveState 'Schema') -cne 'ai-skills/ai-environment-state/v1') {
            throw 'Save-AiEnvironmentState requires an ai-skills/ai-environment-state/v1 snapshot.'
        }
        Assert-AiJsonValueMatchesSchema -Value $effectiveState -SchemaPath $script:StateSchemaPath -Label 'AI environment observed state'

        $profileId = [string](Get-AiProperty $effectiveState 'ProfileId')
        if ($profileId -notmatch '^[a-z0-9]+(?:-[a-z0-9]+)*$') {
            throw "Unsafe AI environment profile id: $profileId"
        }

        $resolvedOutputPath = if (-not [string]::IsNullOrWhiteSpace($OutputPath)) {
            Resolve-AiPath $OutputPath
        }
        else {
            $stateRoot = if (-not [string]::IsNullOrWhiteSpace($env:DEVHOME_STATE_ROOT)) {
                $env:DEVHOME_STATE_ROOT
            }
            elseif (-not [string]::IsNullOrWhiteSpace($env:MACHINE_CODE_ROOT)) {
                Join-Path $env:MACHINE_CODE_ROOT 'DevHome\state'
            }
            else {
                ''
            }
            if ([string]::IsNullOrWhiteSpace($stateRoot)) {
                throw 'OutputPath is required when neither DEVHOME_STATE_ROOT nor MACHINE_CODE_ROOT is set.'
            }
            Resolve-AiPath (Join-Path $stateRoot "ai-environment\$profileId.observed.json")
        }

        if ($PSCmdlet.ShouldProcess($resolvedOutputPath, 'Write AI environment observed state')) {
            Assert-AiControllerIdentity `
                -ExpectedMachineId ([string]$effectiveState.Machine.ExpectedId) `
                -ExpectedInstanceId ([string]$effectiveState.Machine.ExpectedInstanceId) `
                -TargetPath $resolvedOutputPath `
                -VerifierPath $VerifierPath
            Write-AiJsonFileAtomic -Path $resolvedOutputPath -Value $effectiveState
        }

        if ($PassThru) {
            return $effectiveState
        }
        return [pscustomobject][ordered]@{
            Schema = 'ai-skills/ai-environment-state-receipt/v1'
            Path = $resolvedOutputPath
            ProfileId = $profileId
            Status = [string]$effectiveState.Status
            PromotionReady = [bool]$effectiveState.PromotionReady
        }
    }
}

function Update-AiEnvironmentLock {
    [CmdletBinding(SupportsShouldProcess)]
    param(
        [string] $ProfilePath = $script:DefaultProfilePath,
        [string] $LockPath = $script:DefaultLockPath,
        [string] $RepositoryUrl = '',
        [object[]] $Acceptance = @(),
        [string] $VerifierPath = '',
        [switch] $PassThru
    )

    $profile = Read-AiJsonDocument -Path $ProfilePath -ExpectedSchema 'ai-skills/ai-environment-profile/v1' -SchemaPath $script:ProfileSchemaPath
    $resolvedLockPath = Resolve-AiPath $LockPath
    $existingLock = $null
    if (Test-Path -LiteralPath $resolvedLockPath -PathType Leaf) {
        $existingLock = Read-AiJsonDocument -Path $resolvedLockPath -ExpectedSchema 'ai-skills/ai-environment-lock/v1' -SchemaPath $script:LockSchemaPath
        Assert-AiDocumentContracts -Profile $profile -Lock $existingLock
    }

    $repositoryRoot = Resolve-AiPath ([string]$profile.source.repositoryRoot)
    if (-not (Test-Path -LiteralPath (Join-Path $repositoryRoot '.git'))) {
        throw 'Cannot capture an AI environment lock: source repository has no Git metadata.'
    }

    $headResult = Invoke-AiProcess -Command 'git' -Arguments @('-C', $repositoryRoot, 'rev-parse', 'HEAD')
    if (-not $headResult.Found -or [bool]$headResult.TimedOut -or $headResult.ExitCode -ne 0 -or $headResult.StdOut.Trim() -notmatch '^[a-f0-9]{40}$') {
        throw 'Cannot capture an AI environment lock: unable to resolve clean 40-character Git HEAD.'
    }
    $head = $headResult.StdOut.Trim()

    $dirtyCount = 0
    foreach ($arguments in @(
        @('-C', $repositoryRoot, 'diff', '--name-only', '--ignore-space-at-eol'),
        @('-C', $repositoryRoot, 'diff', '--cached', '--name-only'),
        @('-C', $repositoryRoot, 'ls-files', '--others', '--exclude-standard')
    )) {
        $statusResult = Invoke-AiProcess -Command 'git' -Arguments $arguments
        if (-not $statusResult.Found -or [bool]$statusResult.TimedOut -or $statusResult.ExitCode -ne 0) {
            throw 'Cannot capture an AI environment lock: Git worktree cleanliness check failed.'
        }
        if (-not [string]::IsNullOrWhiteSpace($statusResult.StdOut)) {
            $dirtyCount += @($statusResult.StdOut -split '\r?\n' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }).Count
        }
    }
    if ($dirtyCount -gt 0) {
        throw "Cannot capture an AI environment lock from a dirty Git worktree (substantivePaths=$dirtyCount)."
    }

    $effectiveRepositoryUrl = if (-not [string]::IsNullOrWhiteSpace($RepositoryUrl)) {
        $RepositoryUrl.Trim()
    }
    elseif ($null -ne $existingLock -and -not [string]::IsNullOrWhiteSpace([string]$existingLock.source.repository)) {
        [string]$existingLock.source.repository
    }
    else {
        $remoteResult = Invoke-AiProcess -Command 'git' -Arguments @('-C', $repositoryRoot, 'remote', 'get-url', 'origin')
        if (-not $remoteResult.Found -or [bool]$remoteResult.TimedOut -or $remoteResult.ExitCode -ne 0 -or [string]::IsNullOrWhiteSpace($remoteResult.StdOut)) {
            throw 'Cannot capture an AI environment lock: RepositoryUrl was not supplied and git remote origin is unavailable.'
        }
        $remoteResult.StdOut.Trim()
    }

    $providerVersions = @{}
    foreach ($providerName in @('codex', 'claude')) {
        $providerProfile = Get-AiProperty $profile.providers $providerName
        $versionResult = Invoke-AiProcess -Command ([string]$providerProfile.command) -Arguments @('--version')
        if (-not $versionResult.Found -or [bool]$versionResult.TimedOut -or $versionResult.ExitCode -ne 0 -or
            $versionResult.StdOut -notmatch '(?<![0-9])([0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?)') {
            throw "Cannot capture an AI environment lock: unable to observe live $providerName CLI version."
        }
        $providerVersions[$providerName] = $Matches[1]
    }

    $codexConfigPath = Resolve-AiPath ([string]$profile.providers.codex.configPath)
    $codexConfig = Read-AiCodexConfig $codexConfigPath

    $semverPattern = '^[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?(?:\+[0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?$'
    $resourceLocks = [System.Collections.Generic.List[object]]::new()
    foreach ($resource in @($profile.resources)) {
        $desired = Get-AiProperty $resource 'desired'
        $sourceRootValue = [string](Get-AiProperty $desired 'sourceRoot')
        if ([string]::IsNullOrWhiteSpace($sourceRootValue)) {
            continue
        }

        $resourceId = [string]$resource.id
        $sourceRoot = Resolve-AiPath $sourceRootValue
        $existingResource = if ($null -ne $existingLock) { Get-AiLockResource -Lock $existingLock -Id $resourceId } else { $null }
        $payloadPaths = @(
            if ($null -ne $existingResource) {
                $existingResource.payload | ForEach-Object { [string]$_.path }
            }
            else {
                $relativeRoot = [System.IO.Path]::GetRelativePath($repositoryRoot, $sourceRoot).Replace('\', '/')
                $lsResult = Invoke-AiProcess -Command 'git' -Arguments @('-C', $repositoryRoot, 'ls-files', '--', $relativeRoot)
                if (-not $lsResult.Found -or [bool]$lsResult.TimedOut -or $lsResult.ExitCode -ne 0) {
                    throw "Cannot enumerate tracked payload files for '$resourceId'."
                }
                $lsResult.StdOut -split '\r?\n' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | ForEach-Object {
                    $_.Substring($relativeRoot.TrimEnd('/').Length).TrimStart('/')
                }
            }
        )
        if ($payloadPaths.Count -eq 0) {
            throw "Managed resource '$resourceId' resolved zero payload paths."
        }

        $resourceVersion = $null
        if ([string]$resource.kind -ceq 'plugin' -or ($null -ne $existingResource -and -not [string]::IsNullOrWhiteSpace([string](Get-AiProperty $existingResource 'version')))) {
            $manifestPath = Resolve-AiChildPath -Root $sourceRoot -RelativePath '.codex-plugin/plugin.json'
            if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
                throw "Plugin manifest missing for '$resourceId': $manifestPath"
            }
            $manifest = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json -Depth 50
            $resourceVersion = [string](Get-AiProperty $manifest 'version')
            if ($resourceVersion -notmatch $semverPattern) {
                throw "Plugin manifest version '$resourceVersion' for '$resourceId' is missing or invalid."
            }
        }

        $targetRoot = if ([string]$resource.kind -ceq 'plugin' -and -not [string]::IsNullOrWhiteSpace([string](Get-AiProperty $desired 'cacheRoot'))) {
            Resolve-AiChildPath -Root ([string]$desired.cacheRoot) -RelativePath $resourceVersion
        }
        else {
            Resolve-AiPath ([string](Get-AiProperty $desired 'targetRoot'))
        }

        $payloadEntries = [System.Collections.Generic.List[object]]::new()
        foreach ($relativePath in $payloadPaths) {
            $sourceFile = Resolve-AiChildPath -Root $sourceRoot -RelativePath $relativePath
            $targetFile = Resolve-AiChildPath -Root $targetRoot -RelativePath $relativePath
            $sourceDigest = Get-AiFileDigest $sourceFile
            if ($null -eq $sourceDigest) {
                throw "Managed source payload missing for '$resourceId': $relativePath"
            }
            $targetDigest = Get-AiFileDigest $targetFile
            if ($null -eq $targetDigest -or $targetDigest -cne $sourceDigest) {
                throw "Installed target payload missing or drifted from source for '$resourceId': $relativePath"
            }
            $payloadEntries.Add([ordered]@{
                path = $relativePath
                sha256 = $sourceDigest
            }) | Out-Null
        }

        $trustHash = $null
        $trustRecordKey = [string](Get-AiProperty $desired 'trustRecordKey')
        if (-not [string]::IsNullOrWhiteSpace($trustRecordKey)) {
            $trustRecord = if (@($codexConfig.Hooks.Keys) -ccontains $trustRecordKey) { $codexConfig.Hooks[$trustRecordKey] } else { $null }
            $actualTrustHash = [string](Get-AiProperty $trustRecord 'TrustedHash')
            if ($null -eq $trustRecord -or
                -not [bool](Get-AiProperty $trustRecord 'TrustRecordPresent' $false) -or
                $actualTrustHash -notmatch '^sha256:[A-Fa-f0-9]{64}$') {
                throw "Persisted Codex hook trust hash is missing or invalid for '$resourceId' ('$trustRecordKey')."
            }
            $trustHash = $actualTrustHash
        }

        $entryLock = [ordered]@{
            id = $resourceId
        }
        if (-not [string]::IsNullOrWhiteSpace($resourceVersion)) {
            $entryLock.version = $resourceVersion
        }
        if (-not [string]::IsNullOrWhiteSpace($trustHash)) {
            $entryLock.trustHash = $trustHash
        }
        $entryLock.payload = @($payloadEntries)
        $resourceLocks.Add($entryLock) | Out-Null
    }

    $capturedAtUtc = [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')
    $acceptanceLocks = [System.Collections.Generic.List[object]]::new()
    foreach ($profileAcceptance in @($profile.acceptance)) {
        $acceptanceId = [string]$profileAcceptance.id
        $overrideEntry = @($Acceptance | Where-Object { [string](Get-AiProperty $_ 'id') -ceq $acceptanceId }) | Select-Object -First 1
        $priorEntry = if ($null -ne $existingLock) {
            @($existingLock.acceptance | Where-Object { [string]$_.id -ceq $acceptanceId }) | Select-Object -First 1
        }
        else {
            $null
        }
        $selected = if ($null -ne $overrideEntry) { $overrideEntry } else { $priorEntry }
        if ($null -ne $selected) {
            $checkedValue = Get-AiProperty $selected 'checkedAtUtc'
            $acceptanceLocks.Add([ordered]@{
                id = $acceptanceId
                status = [string](Get-AiProperty $selected 'status')
                checkedAtUtc = if ($null -eq $checkedValue -or [string]::IsNullOrWhiteSpace([string]$checkedValue)) {
                    $capturedAtUtc
                }
                else {
                    Format-AiLockUtcTimestamp $checkedValue
                }
                evidence = [string](Get-AiProperty $selected 'evidence')
            }) | Out-Null
        }
        else {
            $acceptanceLocks.Add([ordered]@{
                id = $acceptanceId
                status = 'NOT_RUN'
                checkedAtUtc = $capturedAtUtc
                evidence = 'Acceptance gate has not been recorded for this candidate lock.'
            }) | Out-Null
        }
    }

    $requireCleanWorktree = if ($null -ne $existingLock) {
        [bool]$existingLock.source.requireCleanWorktree
    }
    else {
        $true
    }
    $candidateLock = [ordered]@{
        schema = 'ai-skills/ai-environment-lock/v1'
        profileId = [string]$profile.id
        state = 'candidate'
        capturedAtUtc = $capturedAtUtc
        source = [ordered]@{
            repository = $effectiveRepositoryUrl
            commit = $head
            requireCleanWorktree = $requireCleanWorktree
        }
        providers = [ordered]@{
            codex = [ordered]@{ testedVersions = @([string]$providerVersions['codex']) }
            claude = [ordered]@{ testedVersions = @([string]$providerVersions['claude']) }
        }
        resources = @($resourceLocks)
        acceptance = @($acceptanceLocks)
    }

    Assert-AiJsonValueMatchesSchema -Value $candidateLock -SchemaPath $script:LockSchemaPath -Label 'AI environment candidate lock'
    $validatedLock = ($candidateLock | ConvertTo-Json -Depth 100) | ConvertFrom-Json -Depth 100
    Assert-AiDocumentContracts -Profile $profile -Lock $validatedLock
    $blobObservation = Get-AiLockCommitPayloadObservation -Profile $profile -Lock $validatedLock -RepositoryRoot $repositoryRoot
    if (-not [bool]$blobObservation.Verified) {
        throw 'Captured lock payloads failed raw Git blob verification against HEAD.'
    }

    if ($PSCmdlet.ShouldProcess($resolvedLockPath, 'Capture candidate AI environment lock')) {
        Assert-AiControllerIdentity `
            -ExpectedMachineId ([string]$profile.machine.id) `
            -ExpectedInstanceId ([string]$profile.machine.instanceId) `
            -TargetPath $resolvedLockPath `
            -VerifierPath $VerifierPath
        Write-AiJsonFileAtomic -Path $resolvedLockPath -Value $candidateLock
    }

    if ($PassThru) {
        return $validatedLock
    }
    return [pscustomobject][ordered]@{
        Schema = 'ai-skills/ai-environment-lock-receipt/v1'
        Path = $resolvedLockPath
        ProfileId = [string]$profile.id
        State = 'candidate'
        Commit = $head
        CodexVersion = [string]$providerVersions['codex']
        ClaudeVersion = [string]$providerVersions['claude']
    }
}

function Approve-AiEnvironmentLock {
    [CmdletBinding(SupportsShouldProcess)]
    param(
        [string] $ProfilePath = $script:DefaultProfilePath,
        [string] $LockPath = $script:DefaultLockPath,
        [string] $VerifierPath = '',
        [switch] $PassThru
    )

    $profile = Read-AiJsonDocument -Path $ProfilePath -ExpectedSchema 'ai-skills/ai-environment-profile/v1' -SchemaPath $script:ProfileSchemaPath
    $resolvedLockPath = Resolve-AiPath $LockPath
    $lock = Read-AiJsonDocument -Path $resolvedLockPath -ExpectedSchema 'ai-skills/ai-environment-lock/v1' -SchemaPath $script:LockSchemaPath
    Assert-AiDocumentContracts -Profile $profile -Lock $lock

    if ([string]$lock.state -ceq 'retired') {
        throw 'Cannot promote a retired AI environment lock.'
    }

    $normalizedResources = @(foreach ($resource in @($lock.resources)) {
        $entry = [ordered]@{
            id = [string]$resource.id
        }
        $version = [string](Get-AiProperty $resource 'version')
        if (-not [string]::IsNullOrWhiteSpace($version)) {
            $entry.version = $version
        }
        $trustHash = [string](Get-AiProperty $resource 'trustHash')
        if (-not [string]::IsNullOrWhiteSpace($trustHash)) {
            $entry.trustHash = $trustHash
        }
        $entry.payload = @(
            foreach ($payloadItem in @($resource.payload)) {
                [ordered]@{
                    path = [string]$payloadItem.path
                    sha256 = ([string]$payloadItem.sha256).ToUpperInvariant()
                }
            }
        )
        $entry
    })
    $normalizedAcceptance = @(foreach ($acceptanceItem in @($lock.acceptance)) {
        [ordered]@{
            id = [string]$acceptanceItem.id
            status = [string]$acceptanceItem.status
            checkedAtUtc = Format-AiLockUtcTimestamp (Get-AiProperty $acceptanceItem 'checkedAtUtc')
            evidence = [string]$acceptanceItem.evidence
        }
    })

    $acceptedLock = [ordered]@{
        schema = 'ai-skills/ai-environment-lock/v1'
        profileId = [string]$lock.profileId
        state = 'accepted'
        capturedAtUtc = Format-AiLockUtcTimestamp (Get-AiProperty $lock 'capturedAtUtc')
        source = [ordered]@{
            repository = [string]$lock.source.repository
            commit = [string]$lock.source.commit
            requireCleanWorktree = [bool]$lock.source.requireCleanWorktree
        }
        providers = [ordered]@{
            codex = [ordered]@{ testedVersions = @($lock.providers.codex.testedVersions | ForEach-Object { [string]$_ }) }
            claude = [ordered]@{ testedVersions = @($lock.providers.claude.testedVersions | ForEach-Object { [string]$_ }) }
        }
        resources = @($normalizedResources)
        acceptance = @($normalizedAcceptance)
    }

    Assert-AiJsonValueMatchesSchema -Value $acceptedLock -SchemaPath $script:LockSchemaPath -Label 'AI environment accepted lock'

    $stagingLockPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ai-env-lock-approve-$PID-$([guid]::NewGuid().ToString('N')).json")
    try {
        Write-AiJsonFileAtomic -Path $stagingLockPath -Value $acceptedLock
        $candidateState = Get-AiEnvironmentState -ProfilePath $ProfilePath -LockPath $stagingLockPath
        $verification = Test-AiEnvironment -State $candidateState
    }
    finally {
        if (Test-Path -LiteralPath $stagingLockPath -PathType Leaf) {
            Remove-Item -LiteralPath $stagingLockPath -Force
        }
    }

    $eligible = [bool]$candidateState.Source.WorktreeClean -and
        [bool]$candidateState.Source.HeadMatchesLock -and
        [bool]$candidateState.Source.Reproducible -and
        [string]$candidateState.Status -ceq 'CURRENT' -and
        [bool]$verification.Passed -and
        @($candidateState.Reasons).Count -eq 0
    if (-not $eligible) {
        $reasonCodes = @($candidateState.Reasons | Select-Object -ExpandProperty Code -Unique)
        $reasonText = if ($reasonCodes.Count -gt 0) { $reasonCodes -join ',' } else { 'UNREPRODUCIBLE_SOURCE' }
        throw "AI environment lock is not eligible for promotion (status=$($candidateState.Status); reasons=$reasonText)."
    }

    if ($PSCmdlet.ShouldProcess($resolvedLockPath, 'Promote AI environment lock to accepted')) {
        Assert-AiControllerIdentity `
            -ExpectedMachineId ([string]$profile.machine.id) `
            -ExpectedInstanceId ([string]$profile.machine.instanceId) `
            -TargetPath $resolvedLockPath `
            -VerifierPath $VerifierPath
        Write-AiJsonFileAtomic -Path $resolvedLockPath -Value $acceptedLock
    }

    if ($PassThru) {
        return (($acceptedLock | ConvertTo-Json -Depth 100) | ConvertFrom-Json -Depth 100)
    }
    return [pscustomobject][ordered]@{
        Schema = 'ai-skills/ai-environment-lock-receipt/v1'
        Path = $resolvedLockPath
        ProfileId = [string]$profile.id
        State = 'accepted'
        Commit = [string]$acceptedLock.source.commit
        Status = 'CURRENT'
    }
}

Export-ModuleMember -Function @(
    'Approve-AiEnvironmentLock',
    'Get-AiEnvironmentState',
    'New-AiEnvironmentPlan',
    'Save-AiEnvironmentState',
    'Test-AiEnvironment',
    'Update-AiEnvironmentLock'
)
