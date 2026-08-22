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

Export-ModuleMember -Function @(
    'Get-AiEnvironmentState',
    'New-AiEnvironmentPlan',
    'Test-AiEnvironment'
)
