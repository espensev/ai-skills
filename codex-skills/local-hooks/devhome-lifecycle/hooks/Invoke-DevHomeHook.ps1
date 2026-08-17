[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateSet('PreToolUse', 'UserPromptSubmit')]
    [string] $Event
)

$ErrorActionPreference = 'Stop'

try {
    $rawInput = [Console]::In.ReadToEnd()
    $payload = $rawInput | ConvertFrom-Json -Depth 20
}
catch {
    Write-Output '{}'
    exit 0
}

if ($Event -eq 'PreToolUse') {
    $toolName = [string] $payload.tool_name
    $command = [string] $payload.tool_input.command
    if ([string]::IsNullOrWhiteSpace($command)) {
        $command = $payload.tool_input | ConvertTo-Json -Depth 20 -Compress
    }

    $normalized = ($command -replace '\\', '/').ToLowerInvariant()
    $reason = $null

    $generatedMemoryPattern = '(?:^|[/\\\s])(?:memory\.md|raw_memories\.md)(?:$|[/\\\s])|(?:^|[/\\\s])memories[/\\]memory_summary\.md(?:$|[/\\\s])|(?:^|[/\\\s])rollout_summaries(?:$|[/\\])|(?:^|[/\\\s])\.memory(?:$|[/\\])'
    $sevnetRuntimePattern = '(?:appdata[/\\]local|\$env:localappdata|%localappdata%)[/\\]sevnet(?:$|[/\\])'
    $mutationPattern = '(?i)\b(?:remove-item|set-content|add-content|out-file|move-item|copy-item|rename-item|new-item|clear-content|rm|del|rmdir|mv|cp|tee|truncate)\b|(?:^|\s)>{1,2}(?:\s|$)'

    $isWriteTool = $toolName -match '^(?:apply_patch|Edit|Write)$'
    $isMutation = $isWriteTool -or $command -match $mutationPattern

    if ($isMutation -and $normalized -match $generatedMemoryPattern) {
        $reason = 'Direct changes to generated memory are blocked. Submit an explicitly authorized memory note through memories\extensions\ad_hoc\notes instead.'
    }
    elseif ($isMutation -and $normalized -match $sevnetRuntimePattern) {
        $reason = 'Direct mutation of the ACL-protected Sevnet runtime is blocked. Use the documented medium-integrity shim workflow.'
    }
    else {
        $recursiveDelete = $command -match '(?i)\bremove-item\b[^\r\n]*(?:-recurse|-r\b)' -or
            $command -match '(?i)(?:^|[;&|]\s*)rm\s+-[a-z]*r[a-z]*\b'
        $broadTarget = $normalized -match '(?:^|[\s''"])(?:d:/devhome|c:/users/sev|\$home|\$env:userprofile|\$env:codex_home|%userprofile%)(?:[/\\]?)(?:[\s''"]|$)'

        if ($recursiveDelete -and $broadTarget) {
            $reason = 'A broad recursive delete targeting DevHome or the user profile is blocked by the local safety hook.'
        }
    }

    if ($reason) {
        [ordered]@{
            hookSpecificOutput = [ordered]@{
                hookEventName = 'PreToolUse'
                permissionDecision = 'deny'
                permissionDecisionReason = $reason
            }
        } | ConvertTo-Json -Depth 5 -Compress | Write-Output
        exit 0
    }

    Write-Output '{}'
    exit 0
}

$prompt = [string] $payload.prompt
$secretPatterns = @(
    '-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
    '\bsk-(?:proj-|ant-api\d{2}-)?[A-Za-z0-9_-]{20,}\b',
    '\bgh[pousr]_[A-Za-z0-9]{30,}\b',
    '\bgithub_pat_[A-Za-z0-9_]{40,}\b',
    '\bAKIA[0-9A-Z]{16}\b',
    '\bxox[baprs]-[A-Za-z0-9-]{20,}\b'
)

foreach ($pattern in $secretPatterns) {
    if ($prompt -cmatch $pattern) {
        [ordered]@{
            decision = 'block'
            reason = 'The prompt appears to contain a secret or private key. Remove or redact it before submitting.'
        } | ConvertTo-Json -Compress | Write-Output
        exit 0
    }
}

Write-Output '{}'
exit 0
