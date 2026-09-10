[CmdletBinding()]
[Diagnostics.CodeAnalysis.SuppressMessageAttribute(
    'PSReviewUnusedParameter',
    '',
    Justification = 'Script parameters are consumed by script-scoped helper functions.'
)]
param(
    [Parameter(Mandatory = $false)]
    [string] $RememberProjectsRoot = 'D:\DevHome\state\remember\projects',

    [Parameter(Mandatory = $false)]
    [ValidateSet('Codex', 'Claude')]
    [string] $Provider = 'Codex',

    [Parameter(Mandatory = $false)]
    [string] $VerifierPath = $(
        Join-Path `
            ([Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData)) `
            'common_dev\v2\Test-LocalMachineIdentity.ps1'
    ),

    [Parameter(Mandatory = $false)]
    [string] $ExpectedMachineId = 'snd-desk',

    [Parameter(Mandatory = $false)]
    [string] $ExpectedInstallationId = 'ca96d510-7d87-4cec-8e1a-bd8fc3866903',

    [Parameter(Mandatory = $false)]
    [ValidateRange(4096, 1048576)]
    [int] $MaxDraftBytes = 131072,

    [Parameter(Mandatory = $false)]
    [ValidateRange(200, 1000)]
    [int] $MaxPublishedWords = 450,

    [Parameter(Mandatory = $false)]
    [ValidateRange(64, 4096)]
    [int] $MaxItemCharacters = 512,

    [Parameter(Mandatory = $false)]
    [ValidateRange(128, 16384)]
    [int] $MaxItemUtf8Bytes = 1024,

    [Parameter(Mandatory = $false)]
    [ValidateRange(512, 262144)]
    [int] $MaxPublishedBytes = 32768,

    [Parameter(Mandatory = $false)]
    [ValidateRange(20, 400)]
    [int] $PublishLockAttempts = 20
)

$ErrorActionPreference = 'Stop'
$script:ResolvedProjectsRoot = $null
$script:IdentityVerified = $false
$script:HealthTargetSafe = $false
$script:SessionKey = $null
$script:ProjectSlug = $null
$script:Stage = 'startup'
$script:Utf8NoBom = [System.Text.UTF8Encoding]::new($false)

function Write-NeutralHookResult {
    param(
        [Parameter(Mandatory = $false)]
        [string] $SystemMessage
    )

    if ([string]::IsNullOrWhiteSpace($SystemMessage)) {
        Write-Output '{}'
    }
    else {
        [ordered]@{
            systemMessage = $SystemMessage
        } | ConvertTo-Json -Compress | Write-Output
    }
    exit 0
}

function Write-HandoffFailureResult {
    param([Parameter(Mandatory)][string] $Code)

    if ($Code -eq 'draft-budget-exceeded') {
        Write-NeutralHookResult -SystemMessage (
            'Handoff Relay: draft exceeds the stated limits; previous context kept. Use a shorter draft next turn.'
        )
    }
    Write-NeutralHookResult -SystemMessage (
        'Handoff Relay: automatic context refresh needs another try.'
    )
}

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

function Test-PathTraversalIsReparseFree {
    param([Parameter(Mandatory)][string] $Path)

    try {
        $resolved = Resolve-NormalizedPath -Path $Path
        $pathRoot = [System.IO.Path]::GetPathRoot($resolved)
        if ([string]::IsNullOrWhiteSpace($pathRoot)) {
            return $false
        }

        $pathsToInspect = [System.Collections.Generic.List[string]]::new()
        $pathsToInspect.Add($pathRoot)
        $relativePath = $resolved.Substring($pathRoot.Length)
        $current = $pathRoot
        foreach ($part in @($relativePath.Split(
            [char[]] @([char] '\', [char] '/'),
            [System.StringSplitOptions]::RemoveEmptyEntries
        ))) {
            $current = Join-Path $current $part
            $pathsToInspect.Add($current)
        }

        foreach ($candidate in $pathsToInspect) {
            try {
                $item = Get-Item -LiteralPath $candidate -Force -ErrorAction Stop
            }
            catch [System.Management.Automation.ItemNotFoundException] {
                break
            }
            catch {
                return $false
            }

            if (
                ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0
            ) {
                return $false
            }
        }

        return $true
    }
    catch {
        return $false
    }
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

function Write-AtomicText {
    param(
        [Parameter(Mandatory)][string] $Path,
        [Parameter(Mandatory)][AllowEmptyString()][string] $Content
    )

    $parent = Split-Path -Parent $Path
    $null = New-Item -ItemType Directory -Path $parent -Force
    $tempPath = Join-Path $parent ('.{0}.{1}.{2}.tmp' -f (
        [System.IO.Path]::GetFileName($Path),
        $PID,
        [guid]::NewGuid().ToString('N')
    ))
    try {
        [System.IO.File]::WriteAllText($tempPath, $Content, $script:Utf8NoBom)
        [System.IO.File]::Move($tempPath, $Path, $true)
    }
    finally {
        if (Test-Path -LiteralPath $tempPath -PathType Leaf) {
            Remove-Item -LiteralPath $tempPath -Force
        }
    }
}

function Write-AtomicJson {
    param(
        [Parameter(Mandatory)][string] $Path,
        [Parameter(Mandatory)][object] $Value
    )

    $rendered = ($Value | ConvertTo-Json -Depth 20 -Compress) + [Environment]::NewLine
    Write-AtomicText -Path $Path -Content $rendered
}

function Get-ShortHash {
    param(
        [Parameter(Mandatory)][string] $Text,
        [Parameter(Mandatory = $false)][int] $Length = 32
    )

    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = $script:Utf8NoBom.GetBytes($Text)
        $hash = [System.Convert]::ToHexString($sha.ComputeHash($bytes)).ToLowerInvariant()
        return $hash.Substring(0, [Math]::Min($Length, $hash.Length))
    }
    finally {
        $sha.Dispose()
    }
}

function Get-SharedFileHash {
    param([Parameter(Mandatory)][string] $Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return '<absent>'
    }

    $stream = [System.IO.FileStream]::new(
        $Path,
        [System.IO.FileMode]::Open,
        [System.IO.FileAccess]::Read,
        [System.IO.FileShare]::ReadWrite -bor [System.IO.FileShare]::Delete
    )
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        return [System.Convert]::ToHexString($sha.ComputeHash($stream))
    }
    finally {
        $sha.Dispose()
        $stream.Dispose()
    }
}

function Read-SharedText {
    param([Parameter(Mandatory)][string] $Path)

    $stream = [System.IO.FileStream]::new(
        $Path,
        [System.IO.FileMode]::Open,
        [System.IO.FileAccess]::Read,
        [System.IO.FileShare]::ReadWrite -bor [System.IO.FileShare]::Delete
    )
    $reader = [System.IO.StreamReader]::new($stream, [System.Text.Encoding]::UTF8, $true)
    try {
        return $reader.ReadToEnd()
    }
    finally {
        $reader.Dispose()
    }
}

function Assert-VerifiedMachine {
    if (-not (Test-Path -LiteralPath $VerifierPath -PathType Leaf)) {
        throw "Machine verifier is missing: $VerifierPath"
    }

    $identity = @(& $VerifierPath)[-1]
    if (
        $null -eq $identity -or
        $identity.status -cne 'VERIFIED' -or
        $identity.machineId -cne $ExpectedMachineId -or
        $identity.instanceId -cne $ExpectedInstallationId
    ) {
        throw "Machine identity mismatch. Expected VERIFIED $ExpectedMachineId/$ExpectedInstallationId."
    }

    $script:IdentityVerified = $true
    return $identity
}

function Write-HealthRecord {
    param(
        [Parameter(Mandatory)][ValidateSet('PREPARED', 'PUBLISHED', 'SKIPPED', 'FAILED', 'CONFLICT')]
        [string] $Status,

        [Parameter(Mandatory)][string] $Code,

        [Parameter(Mandatory = $false)][object] $Cleaning,

        [Parameter(Mandatory = $false)][hashtable] $Details = @{}
    )

    if (
        -not $script:IdentityVerified -or
        -not $script:HealthTargetSafe -or
        [string]::IsNullOrWhiteSpace($script:ResolvedProjectsRoot)
    ) {
        return
    }

    try {
        $healthRoot = Join-Path (Split-Path -Parent $script:ResolvedProjectsRoot) 'handoff-relay'
        if (-not (Test-PathTraversalIsReparseFree -Path $healthRoot)) {
            return
        }
        $null = New-Item -ItemType Directory -Path $healthRoot -Force
        if (-not (Test-PathTraversalIsReparseFree -Path $healthRoot)) {
            return
        }
        $healthPath = Join-Path $healthRoot 'latest-status.json'
        if (-not (Test-PathTraversalIsReparseFree -Path $healthPath)) {
            return
        }
        $safeDetails = [ordered]@{}
        foreach ($key in @($Details.Keys | Sort-Object)) {
            $safeDetails[[string] $key] = [string] $Details[$key]
        }
        $record = [ordered]@{
            schema = 'handoff-relay-health.v1'
            updatedUtc = [DateTime]::UtcNow.ToString('o')
            status = $Status
            code = $Code
            provider = $Provider.ToLowerInvariant()
            sessionKey = if ([string]::IsNullOrWhiteSpace($script:SessionKey)) {
                $null
            }
            else {
                $script:SessionKey.Substring(0, [Math]::Min(16, $script:SessionKey.Length))
            }
            project = $script:ProjectSlug
            controller = "$ExpectedMachineId/$ExpectedInstallationId"
            cleaning = $Cleaning
            details = [pscustomobject] $safeDetails
        }
        Write-AtomicJson -Path $healthPath -Value $record
    }
    catch {
        # Shutdown remains fail-open even if the bounded health record cannot be updated.
        return
    }
}

function Get-RecordMessageText {
    param([Parameter(Mandatory)][object] $Record)

    $content = if ($null -ne $Record.payload -and $null -ne $Record.payload.content) {
        $Record.payload.content
    }
    elseif ($null -ne $Record.message -and $null -ne $Record.message.content) {
        $Record.message.content
    }
    else {
        $null
    }

    $textParts = [System.Collections.Generic.List[string]]::new()
    foreach ($part in @($content)) {
        if ($part -is [string]) {
            $textParts.Add([string] $part)
            continue
        }

        if ($null -ne $part.text) {
            $textParts.Add([string] $part.text)
        }
    }

    return ($textParts -join "`n")
}

function Get-DeveloperDeclaredTarget {
    param([Parameter(Mandatory)][string] $TranscriptPath)

    $result = [ordered]@{
        Found = $false
        Target = $null
    }
    if (-not (Test-Path -LiteralPath $TranscriptPath -PathType Leaf)) {
        return [pscustomobject] $result
    }

    $targetPattern = '(?im)^[ \t]*Write[ \t]+next[ \t]+handoff[ \t]+to:[ \t]*(?<path>[^\r\n]+?)[ \t]*$'
    $stream = $null
    $reader = $null
    try {
        $stream = [System.IO.FileStream]::new(
            $TranscriptPath,
            [System.IO.FileMode]::Open,
            [System.IO.FileAccess]::Read,
            [System.IO.FileShare]::ReadWrite -bor [System.IO.FileShare]::Delete
        )
        $reader = [System.IO.StreamReader]::new($stream, [System.Text.Encoding]::UTF8, $true)
        while ($null -ne ($line = $reader.ReadLine())) {
            if ($line.IndexOf('Write next handoff to:', [System.StringComparison]::OrdinalIgnoreCase) -lt 0) {
                continue
            }

            try {
                $record = $line | ConvertFrom-Json -Depth 100 -ErrorAction Stop
            }
            catch {
                continue
            }

            $role = if ($null -ne $record.payload -and $null -ne $record.payload.role) {
                [string] $record.payload.role
            }
            elseif ($null -ne $record.message -and $null -ne $record.message.role) {
                [string] $record.message.role
            }
            else {
                ''
            }
            if ($role -notin @('developer', 'system')) {
                continue
            }

            $messageText = Get-RecordMessageText -Record $record
            foreach ($match in [regex]::Matches($messageText, $targetPattern)) {
                $candidate = $match.Groups['path'].Value.Trim()
                $candidate = $candidate.Trim([char[]] @([char] 0x60, [char] 0x22, [char] 0x27))
                $result.Found = $true
                $result.Target = $candidate
            }
        }
    }
    finally {
        if ($null -ne $reader) {
            $reader.Dispose()
        }
        elseif ($null -ne $stream) {
            $stream.Dispose()
        }
    }

    return [pscustomobject] $result
}

function Get-SessionKind {
    param([Parameter(Mandatory)][object] $Payload)

    # Classifies the hook's session as interactive, sdk (Claude Agent SDK),
    # exec (codex exec) or subagent (a Codex team thread: session_meta.source
    # carries a subagent object, or session_meta.session_id names a root thread
    # other than the rollout's own id). Only interactive sessions own a next-session
    # handoff. Unknown or unreadable shapes stay interactive so recovery keeps
    # working for transcript formats this relay has not seen.
    $transcriptPath = [string] $Payload.transcript_path
    if ($Provider -ceq 'Claude') {
        $entrypoint = [string] [Environment]::GetEnvironmentVariable('CLAUDE_CODE_ENTRYPOINT')
        if ($entrypoint.StartsWith('sdk', [System.StringComparison]::OrdinalIgnoreCase)) {
            return 'sdk'
        }
    }
    if (
        [string]::IsNullOrWhiteSpace($transcriptPath) -or
        -not (Test-Path -LiteralPath $transcriptPath -PathType Leaf)
    ) {
        return 'interactive'
    }

    $stream = $null
    $reader = $null
    try {
        $stream = [System.IO.FileStream]::new(
            $transcriptPath,
            [System.IO.FileMode]::Open,
            [System.IO.FileAccess]::Read,
            [System.IO.FileShare]::ReadWrite -bor [System.IO.FileShare]::Delete
        )
        $reader = [System.IO.StreamReader]::new($stream, [System.Text.Encoding]::UTF8, $true)
        $inspected = 0
        while ($inspected -lt 32 -and $null -ne ($line = $reader.ReadLine())) {
            if ([string]::IsNullOrWhiteSpace($line)) { continue }
            $inspected++
            try {
                $record = $line | ConvertFrom-Json -Depth 100 -ErrorAction Stop
            }
            catch {
                continue
            }
            if ($null -eq $record) { continue }

            if ($Provider -ceq 'Claude') {
                # Claude Code stamps every user/assistant record with the
                # launching entrypoint: cli, claude-desktop, sdk-cli, sdk-py...
                $property = $record.PSObject.Properties['entrypoint']
                if ($null -eq $property -or [string]::IsNullOrWhiteSpace([string] $property.Value)) {
                    continue
                }
                if (([string] $property.Value).StartsWith('sdk', [System.StringComparison]::OrdinalIgnoreCase)) {
                    return 'sdk'
                }
                return 'interactive'
            }

            if ([string] $record.type -cne 'session_meta') { continue }
            $meta = $record.payload
            if ($null -eq $meta) { return 'interactive' }
            # A spawned thread writes its own rollout (payload.id equals the
            # filename UUID) but keeps the root thread in payload.session_id and
            # describes the spawn under payload.source.subagent. The root thread
            # has id and session_id equal and a string source such as 'cli'.
            $ownId = [string] $meta.id
            $rootId = [string] $meta.session_id
            $sourceValue = $meta.source
            $sourceIsObject = $null -ne $sourceValue -and $sourceValue -isnot [string]
            if ($sourceIsObject -and $null -ne $sourceValue.PSObject.Properties['subagent']) {
                return 'subagent'
            }
            if (
                -not [string]::IsNullOrWhiteSpace($rootId) -and
                -not [string]::IsNullOrWhiteSpace($ownId) -and
                $rootId -ine $ownId
            ) {
                return 'subagent'
            }
            if ([string]::IsNullOrWhiteSpace($ownId) -and -not [string]::IsNullOrWhiteSpace($rootId)) {
                $fileId = [regex]::Match(
                    [System.IO.Path]::GetFileNameWithoutExtension($transcriptPath),
                    '[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}'
                )
                if ($fileId.Success -and $fileId.Value -ine $rootId) {
                    return 'subagent'
                }
            }
            if (-not $sourceIsObject -and ([string] $sourceValue -ceq 'exec' -or [string] $meta.originator -ceq 'codex_exec')) {
                return 'exec'
            }
            return 'interactive'
        }
    }
    catch {
        return 'interactive'
    }
    finally {
        if ($null -ne $reader) {
            $reader.Dispose()
        }
        elseif ($null -ne $stream) {
            $stream.Dispose()
        }
    }

    return 'interactive'
}

function Test-ToolFreeQuestion {
    param([Parameter(Mandatory)][object] $Payload)

    # Only suppress a continuation when the transcript positively identifies a
    # current user turn without tools. Missing/unknown formats keep recovery.
    if ([string]::IsNullOrWhiteSpace([string] $Payload.transcript_path)) {
        return $false
    }
    $reader = $null
    $stream = $null
    $knownTurn = $false
    $hasTools = $false
    $handoffMentioned = $false
    $hasCodexTurnBoundary = $false
    $userText = ''
    $assistantCharacters = 0
    try {
        $stream = [System.IO.FileStream]::new(
            [string] $Payload.transcript_path,
            [System.IO.FileMode]::Open,
            [System.IO.FileAccess]::Read,
            [System.IO.FileShare]::ReadWrite -bor [System.IO.FileShare]::Delete
        )
        $reader = [System.IO.StreamReader]::new($stream, [System.Text.Encoding]::UTF8, $true)
        while ($null -ne ($line = $reader.ReadLine())) {
            if ([string]::IsNullOrWhiteSpace($line)) { continue }
            $record = $line | ConvertFrom-Json -Depth 100 -ErrorAction Stop
            if ($record.isSidechain -eq $true) { continue }
            if ($record.type -ceq 'event_msg' -and $record.payload.type -ceq 'task_started') {
                $hasCodexTurnBoundary = $true
                $knownTurn = $false
                $hasTools = $false
                $handoffMentioned = $false
                $userText = ''
                $assistantCharacters = 0
                continue
            }
            $isCodexMessage = $record.type -ceq 'response_item' -and $record.payload.type -ceq 'message'
            $isClaudeUser = $record.type -ceq 'user' -and $record.message.role -ceq 'user'
            $isUser = ($isCodexMessage -and $record.payload.role -ceq 'user') -or $isClaudeUser
            $messageText = if ($isUser) { Get-RecordMessageText -Record $record } else { '' }
            # Claude tool_result records also have role=user; they are not prompts.
            if ($isUser -and -not [string]::IsNullOrWhiteSpace($messageText)) {
                if (-not $hasCodexTurnBoundary) {
                    $hasTools = $false
                    $handoffMentioned = $false
                }
                $knownTurn = $true
                $userText = $messageText.Trim()
                $assistantCharacters = 0
                # Preserve recovery for varied handoff phrasing instead of
                # trying to infer authorization from a narrow command grammar.
                $handoffMentioned = $handoffMentioned -or $messageText -match '(?i)\bhandoff\b'
            }
            if ($record.type -ceq 'response_item' -and $record.payload.type -match '_call(?:_output)?$') {
                $hasTools = $true
            }
            if (($isCodexMessage -and $record.payload.role -ceq 'assistant') -or (
                $record.type -ceq 'assistant' -and $record.message.role -ceq 'assistant'
            )) {
                $reply = Get-RecordMessageText -Record $record
                if (-not [string]::IsNullOrWhiteSpace($reply)) {
                    $assistantCharacters = [Math]::Min(501, $assistantCharacters + $reply.Length)
                }
            }
            if ($record.type -ceq 'assistant' -and $record.message.role -ceq 'assistant') {
                foreach ($part in @($record.message.content)) {
                    if ($part.type -ceq 'tool_use') { $hasTools = $true }
                }
            }
        }
        # Bound this optimization to short Q&A. A tool-free plan or other
        # substantial written deliverable can still deserve a checkpoint.
        return $knownTurn -and -not $hasTools -and -not $handoffMentioned -and
            $userText.EndsWith('?') -and $userText.Length -le 500 -and
            $assistantCharacters -gt 0 -and $assistantCharacters -le 500
    }
    catch {
        return $false
    }
    finally {
        if ($null -ne $reader) { $reader.Dispose() }
        elseif ($null -ne $stream) { $stream.Dispose() }
    }
}

function ConvertTo-RememberProjectSlug {
    param([Parameter(Mandatory)][string] $WorkingDirectory)

    $resolved = Resolve-NormalizedPath -Path $WorkingDirectory
    $builder = [System.Text.StringBuilder]::new($resolved.Length)
    foreach ($character in $resolved.ToCharArray()) {
        if ($character -in @([char] ':', [char] '\', [char] '/')) {
            $null = $builder.Append('-')
        }
        elseif (
            [char]::IsLetterOrDigit($character) -or
            $character -in @([char] '.', [char] '_', [char] '-')
        ) {
            $null = $builder.Append($character)
        }
        else {
            $null = $builder.Append('-')
        }
    }

    $slug = $builder.ToString()
    if ($resolved -match '^[A-Za-z]:') {
        $slug = $slug.Substring(0, 1).ToLowerInvariant() + $slug.Substring(1)
    }

    return $slug
}

function Resolve-SafeHandoffTarget {
    param(
        [Parameter(Mandatory)][string] $Candidate,
        [Parameter(Mandatory)][string] $ResolvedProjectsRoot
    )

    if (
        [string]::IsNullOrWhiteSpace($Candidate) -or
        -not [System.IO.Path]::IsPathFullyQualified($Candidate)
    ) {
        return $null
    }

    try {
        $resolvedCandidate = Resolve-NormalizedPath -Path $Candidate
    }
    catch {
        return $null
    }

    $rootPrefix = $ResolvedProjectsRoot + [System.IO.Path]::DirectorySeparatorChar
    if (-not $resolvedCandidate.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $null
    }

    $relativePath = $resolvedCandidate.Substring($rootPrefix.Length)
    $parts = @($relativePath.Split(
        [char[]] @([char] '\', [char] '/'),
        [System.StringSplitOptions]::RemoveEmptyEntries
    ))
    if (
        $parts.Count -ne 2 -or
        $parts[0] -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]*$' -or
        $parts[1] -cne 'remember.md'
    ) {
        return $null
    }

    $projectRoot = Split-Path -Parent $resolvedCandidate
    if (-not (Test-Path -LiteralPath $projectRoot -PathType Container)) {
        return $null
    }
    if (
        -not (Test-PathTraversalIsReparseFree -Path $ResolvedProjectsRoot) -or
        -not (Test-PathTraversalIsReparseFree -Path $resolvedCandidate)
    ) {
        return $null
    }

    return $resolvedCandidate
}

function Resolve-EnrolledAncestor {
    param(
        [Parameter(Mandatory)][string] $WorkingDirectory,
        [Parameter(Mandatory)][string] $ResolvedProjectsRoot
    )

    try {
        $current = Resolve-NormalizedPath -Path $WorkingDirectory
    }
    catch {
        return $null
    }

    while (-not [string]::IsNullOrWhiteSpace($current)) {
        $slug = ConvertTo-RememberProjectSlug -WorkingDirectory $current
        $projectRoot = Join-Path $ResolvedProjectsRoot $slug
        if (Test-Path -LiteralPath $projectRoot -PathType Container) {
            $candidate = Join-Path $projectRoot 'remember.md'
            $target = Resolve-SafeHandoffTarget `
                -Candidate $candidate `
                -ResolvedProjectsRoot $ResolvedProjectsRoot
            if (-not [string]::IsNullOrWhiteSpace($target)) {
                return [pscustomobject]@{
                    Target = $target
                    Workspace = $current
                    ProjectSlug = $slug
                }
            }
        }

        $parent = [System.IO.Directory]::GetParent($current)
        if ($null -eq $parent) {
            break
        }
        $next = Resolve-NormalizedPath -Path $parent.FullName
        if ([string]::Equals($next, $current, [System.StringComparison]::OrdinalIgnoreCase)) {
            break
        }
        $current = $next
    }

    return $null
}

function Resolve-HandoffContext {
    param(
        [Parameter(Mandatory)][object] $Payload,
        [Parameter(Mandatory)][string] $ResolvedProjectsRoot
    )

    $declared = if (-not [string]::IsNullOrWhiteSpace([string] $Payload.transcript_path)) {
        Get-DeveloperDeclaredTarget -TranscriptPath ([string] $Payload.transcript_path)
    }
    else {
        [pscustomobject]@{ Found = $false; Target = $null }
    }

    if ($declared.Found) {
        $target = Resolve-SafeHandoffTarget `
            -Candidate ([string] $declared.Target) `
            -ResolvedProjectsRoot $ResolvedProjectsRoot
        if ([string]::IsNullOrWhiteSpace($target)) {
            return [pscustomobject]@{ Found = $false; Code = 'invalid-declared-target' }
        }

        $projectRoot = Split-Path -Parent $target
        $workspace = $null
        $ancestor = if (-not [string]::IsNullOrWhiteSpace([string] $Payload.cwd)) {
            Resolve-EnrolledAncestor `
                -WorkingDirectory ([string] $Payload.cwd) `
                -ResolvedProjectsRoot $ResolvedProjectsRoot
        }
        if ($null -ne $ancestor -and (Test-SamePath -Left $ancestor.Target -Right $target)) {
            $workspace = $ancestor.Workspace
        }
        else {
            return [pscustomobject]@{ Found = $false; Code = 'declared-target-workspace-mismatch' }
        }

        return [pscustomobject]@{
            Found = $true
            Code = 'declared-target'
            Target = $target
            Workspace = $workspace
            ProjectSlug = Split-Path -Leaf $projectRoot
        }
    }

    if ([string]::IsNullOrWhiteSpace([string] $Payload.cwd)) {
        return [pscustomobject]@{ Found = $false; Code = 'cwd-missing' }
    }

    $ancestor = Resolve-EnrolledAncestor `
        -WorkingDirectory ([string] $Payload.cwd) `
        -ResolvedProjectsRoot $ResolvedProjectsRoot
    if ($null -eq $ancestor) {
        return [pscustomobject]@{ Found = $false; Code = 'enrolled-ancestor-not-found' }
    }

    return [pscustomobject]@{
        Found = $true
        Code = 'enrolled-ancestor'
        Target = $ancestor.Target
        Workspace = $ancestor.Workspace
        ProjectSlug = $ancestor.ProjectSlug
    }
}

function Get-SessionKey {
    param([Parameter(Mandatory)][object] $Payload)

    $session = [string] $Payload.session_id
    if ([string]::IsNullOrWhiteSpace($session)) {
        $session = [string] $Payload.transcript_path
    }
    if ([string]::IsNullOrWhiteSpace($session)) {
        $session = "legacy:$([string] $Payload.cwd)"
    }

    $turn = [string] $Payload.turn_id
    return Get-ShortHash -Text "$($Provider.ToLowerInvariant())|$session|$turn" -Length 32
}

function Get-AttemptPathSet {
    param(
        [Parameter(Mandatory)][string] $ProjectRoot,
        [Parameter(Mandatory)][string] $SessionKey
    )

    $attemptRoot = Join-Path $ProjectRoot 'tmp\handoff-relay'
    return [pscustomobject]@{
        Root = $attemptRoot
        State = Join-Path $attemptRoot "$SessionKey.state.json"
        Draft = Join-Path $attemptRoot "$SessionKey.draft.md"
        Lock = Join-Path $attemptRoot 'publish.lock'
        Receipt = Join-Path $attemptRoot 'completed.json'
    }
}

function Test-HandoffPathSetIsSafe {
    param(
        [Parameter(Mandatory)][string] $Target,
        [Parameter(Mandatory)][object] $Paths
    )

    $safeTarget = Resolve-SafeHandoffTarget `
        -Candidate $Target `
        -ResolvedProjectsRoot $script:ResolvedProjectsRoot
    if (
        [string]::IsNullOrWhiteSpace($safeTarget) -or
        -not (Test-SamePath -Left $safeTarget -Right $Target)
    ) {
        return $false
    }

    foreach ($path in @($Paths.Root, $Paths.State, $Paths.Draft, $Paths.Lock, $Paths.Receipt)) {
        if (-not (Test-PathTraversalIsReparseFree -Path ([string] $path))) {
            return $false
        }
    }

    return $true
}

function Move-AttemptToArchive {
    param(
        [Parameter(Mandatory)][object] $Paths,
        [Parameter(Mandatory)][ValidateSet('failed', 'conflict', 'orphaned')]
        [string] $Kind
    )

    $timestamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')
    if (Test-Path -LiteralPath $Paths.Draft -PathType Leaf) {
        $draftArchive = Join-Path $Paths.Root "$script:SessionKey.$Kind.$timestamp.draft.md"
        Move-Item -LiteralPath $Paths.Draft -Destination $draftArchive -Force
    }
    if (Test-Path -LiteralPath $Paths.State -PathType Leaf) {
        $stateArchive = Join-Path $Paths.Root "$script:SessionKey.$Kind.$timestamp.state.json"
        Move-Item -LiteralPath $Paths.State -Destination $stateArchive -Force
    }
}

function Move-LooseDraftsToArchive {
    param([Parameter(Mandatory)][object] $Paths)

    if (-not (Test-Path -LiteralPath $Paths.Root -PathType Container)) {
        return 0
    }

    $moved = 0
    foreach ($draft in @(
        Get-ChildItem -LiteralPath $Paths.Root -File -Filter '*.draft.md'
    )) {
        $match = [regex]::Match(
            $draft.Name,
            '^(?<key>[0-9a-f]{32})\.draft\.md$',
            [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
        )
        if (-not $match.Success) {
            continue
        }

        $key = $match.Groups['key'].Value
        $statePath = Join-Path $Paths.Root "$key.state.json"
        if (Test-Path -LiteralPath $statePath -PathType Leaf) {
            continue
        }

        $timestamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')
        $archivePath = Join-Path $Paths.Root "$key.orphaned.$timestamp.draft.md"
        try {
            Move-Item -LiteralPath $draft.FullName -Destination $archivePath
            $moved++
        }
        catch {
            if (Test-Path -LiteralPath $draft.FullName -PathType Leaf) {
                throw
            }
        }
    }

    return $moved
}

function Enter-ProjectPublishLock {
    param([Parameter(Mandatory)][string] $Path)

    for ($attempt = 0; $attempt -lt $PublishLockAttempts; $attempt++) {
        try {
            return [System.IO.FileStream]::new(
                $Path,
                [System.IO.FileMode]::OpenOrCreate,
                [System.IO.FileAccess]::ReadWrite,
                [System.IO.FileShare]::None
            )
        }
        catch [System.IO.IOException] {
            Start-Sleep -Milliseconds 25
        }
    }

    throw 'Timed out acquiring the Handoff Relay project publish lock.'
}

function Get-CanonicalSectionName {
    param([Parameter(Mandatory)][string] $Heading)

    $normalized = $Heading.Trim().TrimEnd(':')
    switch -Regex ($normalized) {
        '^(?i:summary)$' { return 'Summary' }
        '^(?i:outcome)$' { return 'Outcome' }
        '^(?i:verified state)$' { return 'Verified state' }
        '^(?i:changed surfaces|changed source/runtime/remote surfaces)$' { return 'Changed surfaces' }
        '^(?i:verification|verification evidence)$' { return 'Verification' }
        '^(?i:open risks)$' { return 'Open risks' }
        '^(?i:next gate|next actionable gate)$' { return 'Next gate' }
        default { return $null }
    }
}

function Get-WordCount {
    param([Parameter(Mandatory)][AllowEmptyString()][string] $Text)

    return [regex]::Matches($Text, '\S+').Count
}

function Test-SpeculativeFact {
    param([Parameter(Mandatory)][string] $Text)

    $patterns = @(
        '(?i)\[(?:unverified|speculation|inference|guess|assumption)\]',
        '(?i)\b(?:maybe|perhaps|probably|possibly|presumably|apparently|allegedly|reportedly|supposedly|ostensibly|arguably|conceivably|seems?|appears?|likely|unlikely)\b',
        '(?i)\b(?:could|might|may)\s+(?:not\s+)?(?:be|have|need|fail|pass|cause|indicate|mean|show|suggest|remain|require|change|break|work|contain|include|affect|produce|allow|prevent|occur|happen)\b',
        '(?i)\b(?:i|we)\s+(?:think|believe|assume|suspect|guess|expect|estimate)\b',
        '(?i)\b(?:is|are|was|were|has been|have been)\s+(?:thought|believed|assumed|expected|suspected|estimated)\s+to\b',
        '(?i)\b(?:unconfirmed|unproven|unknown|unclear|not\s+(?:yet\s+)?verified|needs?\s+(?:verification|confirmation)|await(?:s|ing)?\s+(?:verification|confirmation))\b'
    )
    foreach ($pattern in $patterns) {
        if ($Text -match $pattern) {
            return $true
        }
    }

    return $false
}

function Test-SectionItemContract {
    param(
        [Parameter(Mandatory)][string] $Section,
        [Parameter(Mandatory)][string] $Text
    )

    if ($Section -eq 'Verified state') {
        return $Text -match '(?i)^\[verified\]\s+\S' -and
            $Text -match '(?i)\bEvidence:\s*\S'
    }
    if ($Section -eq 'Open risks') {
        return $Text -match '(?i)^None\.?$' -or (
            $Text -match '(?i)^\[risk\]\s+\S' -and
            $Text -match '(?i)\bBasis:\s*\S'
        )
    }

    return $true
}

function Get-HandoffSectionSpecs {
    return [ordered]@{
        'Summary' = @{ MaxItems = 2; MaxWords = 45; MaxItemWords = 26; FilterFacts = $true }
        'Outcome' = @{ MaxItems = 3; MaxWords = 60; MaxItemWords = 26; FilterFacts = $true }
        'Verified state' = @{ MaxItems = 4; MaxWords = 100; MaxItemWords = 34; FilterFacts = $true }
        'Changed surfaces' = @{ MaxItems = 4; MaxWords = 60; MaxItemWords = 24; FilterFacts = $true }
        'Verification' = @{ MaxItems = 4; MaxWords = 70; MaxItemWords = 26; FilterFacts = $true }
        'Open risks' = @{ MaxItems = 3; MaxWords = 55; MaxItemWords = 26; FilterFacts = $false }
        'Next gate' = @{ MaxItems = 2; MaxWords = 40; MaxItemWords = 24; FilterFacts = $false }
    }
}

function Get-HandoffBudgetInstruction {
    $specs = Get-HandoffSectionSpecs
    $lines = @('Maximums, including labels and evidence (words are separated by whitespace):')
    foreach ($section in $specs.Keys) {
        $spec = $specs[$section]
        $lines += "- ${section}: $($spec.MaxItems) bullets, $($spec.MaxWords) words total, $($spec.MaxItemWords) words per bullet."
    }
    $lines += "Body: $MaxPublishedWords words total. Each bullet: $MaxItemCharacters Unicode text elements and $MaxItemUtf8Bytes UTF-8 bytes. Over-budget drafts are retained as failures; no facts are clipped to fit. Put the current priority first in Next gate and link a separate note for deferred work."
    return $lines -join "`n"
}

function ConvertTo-CleanHandoff {
    param([Parameter(Mandatory)][string] $Draft)

    $specs = Get-HandoffSectionSpecs
    $items = [ordered]@{}
    $seen = @{}
    $sectionWords = @{}
    foreach ($section in $specs.Keys) {
        $items[$section] = [System.Collections.Generic.List[string]]::new()
        $sectionWords[$section] = 0
        $seen[$section] = [System.Collections.Generic.HashSet[string]]::new(
            [System.StringComparer]::OrdinalIgnoreCase
        )
    }

    $droppedItems = 0
    $budgetExceeded = $false
    $ignoredLines = 0
    $currentSection = $null
    $inFence = $false
    foreach ($line in @($Draft -split '\r?\n')) {
        if ($line -match '^\s*```') {
            $inFence = -not $inFence
            $ignoredLines++
            continue
        }
        if ($inFence) {
            if (-not [string]::IsNullOrWhiteSpace($line)) {
                $ignoredLines++
            }
            continue
        }
        if ($line -match '^\s*#{1,6}\s+(?<heading>.+?)\s*$') {
            $currentSection = Get-CanonicalSectionName -Heading $Matches.heading
            if ($null -eq $currentSection -and $Matches.heading -notmatch '^(?i:Handoff(?:\s+(?:-|\u2014).*)?)$') {
                $ignoredLines++
            }
            continue
        }
        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }
        $plainSection = Get-CanonicalSectionName -Heading $line
        if ($null -ne $plainSection) {
            $currentSection = $plainSection
            continue
        }
        if ($null -eq $currentSection) {
            $ignoredLines++
            continue
        }
        if ($line -notmatch '^\s*(?:[-*+]|\d+[.)])\s+(?<text>\S.*?)\s*$') {
            $ignoredLines++
            continue
        }

        $text = ($Matches.text -replace '[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '')
        $text = ($text -replace '\s+', ' ').Trim()
        $spec = $specs[$currentSection]
        if ([bool] $spec.FilterFacts -and (Test-SpeculativeFact -Text $text)) {
            $droppedItems++
            continue
        }
        if (-not (Test-SectionItemContract -Section $currentSection -Text $text)) {
            $droppedItems++
            continue
        }
        if (-not $seen[$currentSection].Add($text)) {
            $droppedItems++
            continue
        }

        $wordCount = Get-WordCount -Text $text
        if (
            $items[$currentSection].Count -ge [int] $spec.MaxItems -or
            $wordCount -gt [int] $spec.MaxItemWords -or
            $sectionWords[$currentSection] + $wordCount -gt [int] $spec.MaxWords -or
            [System.Globalization.StringInfo]::ParseCombiningCharacters($text).Count -gt $MaxItemCharacters -or
            $script:Utf8NoBom.GetByteCount($text) -gt $MaxItemUtf8Bytes
        ) {
            $budgetExceeded = $true
            continue
        }
        $items[$currentSection].Add($text)
        $sectionWords[$currentSection] += $wordCount
    }

    $missingSections = @($specs.Keys | Where-Object { $items[$_].Count -eq 0 })
    $publishedWords = 0
    foreach ($section in $specs.Keys) {
        foreach ($item in $items[$section]) {
            $publishedWords += Get-WordCount -Text $item
        }
    }
    if ($publishedWords -gt $MaxPublishedWords) {
        $budgetExceeded = $true
    }

    return [pscustomobject]@{
        Valid = -not $budgetExceeded -and $missingSections.Count -eq 0
        Code = if ($budgetExceeded) { 'draft-budget-exceeded' } elseif ($missingSections.Count -eq 0) { 'clean' } else { 'required-section-empty' }
        MissingSections = $missingSections
        Items = $items
        Cleaning = [pscustomobject]@{
            droppedItems = $droppedItems
            truncatedItems = 0
            ignoredLines = $ignoredLines
            publishedWords = $publishedWords
        }
    }
}

function ConvertTo-HandoffDocument {
    param(
        [Parameter(Mandatory)][object] $Cleaned,
        [Parameter(Mandatory)][object] $State
    )

    $workspace = ([string] $State.workspace).Replace('--', '- -').Replace("`r", '').Replace("`n", ' ')
    $lines = [System.Collections.Generic.List[string]]::new()
    $lines.Add('# Handoff')
    $lines.Add('')
    $lines.Add('<!-- handoff-relay:v1')
    $lines.Add("updated_utc: $([DateTime]::UtcNow.ToString('o'))")
    $lines.Add("provider: $($Provider.ToLowerInvariant())")
    $lines.Add("session: $($script:SessionKey.Substring(0, 16))")
    $lines.Add("controller: $ExpectedMachineId/$ExpectedInstallationId")
    $lines.Add("workspace: $workspace")
    $lines.Add("baseline_sha256: $([string] $State.baselineHash)")
    $lines.Add(('cleaning: dropped={0}; truncated={1}; ignored={2}; words={3}' -f
        $Cleaned.Cleaning.droppedItems,
        $Cleaned.Cleaning.truncatedItems,
        $Cleaned.Cleaning.ignoredLines,
        $Cleaned.Cleaning.publishedWords
    ))
    $lines.Add('-->')

    foreach ($section in @(
        'Summary',
        'Outcome',
        'Verified state',
        'Changed surfaces',
        'Verification',
        'Open risks',
        'Next gate'
    )) {
        $lines.Add('')
        $lines.Add("## $section")
        $lines.Add('')
        foreach ($item in $Cleaned.Items[$section]) {
            $lines.Add("- $item")
        }
    }

    return ($lines -join [Environment]::NewLine) + [Environment]::NewLine
}

function Write-ContinuationResult {
    param(
        [Parameter(Mandatory)][string] $Instruction,
        [Parameter(Mandatory)][string] $SystemMessage
    )

    $output = if ($Provider -ceq 'Claude') {
        [ordered]@{
            systemMessage = $SystemMessage
            hookSpecificOutput = [ordered]@{
                hookEventName = 'Stop'
                additionalContext = $Instruction
            }
        }
    }
    else {
        [ordered]@{
            systemMessage = $SystemMessage
            decision = 'block'
            reason = $Instruction
        }
    }

    $output | ConvertTo-Json -Depth 10 -Compress | Write-Output
    exit 0
}

function Get-CompletedAttempts {
    param([Parameter(Mandatory)][object] $Paths)

    # This cache can suppress duplicate work but cannot authorize publication.
    # Losing it must retain capture; a later success rebuilds the bounded cache.
    try {
        if (-not (Test-Path -LiteralPath $Paths.Receipt -PathType Leaf)) { return @() }
        if ((Get-Item -LiteralPath $Paths.Receipt).Length -gt 32768) { return @() }
        $receipt = Read-SharedText -Path $Paths.Receipt | ConvertFrom-Json -ErrorAction Stop
        if ($receipt.schema -cne 'handoff-relay-completed.v1' -or @($receipt.attempts).Count -gt 32) {
            return @()
        }
        foreach ($attempt in @($receipt.attempts)) {
            if ([string] $attempt.key -cnotmatch '^[a-f0-9]{32}$' -or
                [string]::IsNullOrWhiteSpace([string] $attempt.transcript) -or
                ($attempt.offset -isnot [long] -and $attempt.offset -isnot [int]) -or
                [long] $attempt.offset -lt 0) { return @() }
        }
        return @($receipt.attempts)
    }
    catch { return @() }
}

function Test-AttemptCompleted {
    param([object] $Paths, [object] $Payload)

    $attempt = @(Get-CompletedAttempts -Paths $Paths | Where-Object { $_.key -ceq $script:SessionKey } | Select-Object -Last 1)
    if ($attempt.Count -ne 1 -or $null -eq $Payload -or
        [string]::IsNullOrWhiteSpace([string] $Payload.transcript_path)) { return $false }
    $stream = $null
    $reader = $null
    try {
        if (-not (Test-SamePath -Left $attempt[0].transcript -Right $Payload.transcript_path)) { return $false }
        $stream = [System.IO.FileStream]::new($Payload.transcript_path, 'Open', 'Read',
            [System.IO.FileShare]::ReadWrite -bor [System.IO.FileShare]::Delete)
        if ($stream.Length -lt $attempt[0].offset) { return $false }
        $null = $stream.Seek($attempt[0].offset, [System.IO.SeekOrigin]::Begin)
        $reader = [System.IO.StreamReader]::new($stream, [System.Text.Encoding]::UTF8, $true)
        while ($null -ne ($line = $reader.ReadLine())) {
            if ([string]::IsNullOrWhiteSpace($line)) { continue }
            $record = $line | ConvertFrom-Json -Depth 100 -ErrorAction Stop
            if ($record.type -ceq 'token_usage_record') { continue }
            if ($record.type -ceq 'event_msg' -and $record.payload.type -in @('token_count', 'task_complete')) { continue }
            # Any subsequent message, tool, steering or compaction needs capture.
            # This receipt only suppresses an actual repeated Stop with no work.
            return $false
        }
        return $true
    }
    catch { return $false }
    finally {
        if ($null -ne $reader) { $reader.Dispose() }
        elseif ($null -ne $stream) { $stream.Dispose() }
    }
}

function Save-CompletedAttempt {
    param([Parameter(Mandatory)][object] $Paths, [Parameter(Mandatory)][object] $Payload, [long] $TranscriptOffset)

    # Called only under the project lock, after publication or an explicit Q&A skip.
    # One bounded receipt avoids a persistent success-state file for every turn.
    $attempts = @(@(Get-CompletedAttempts -Paths $Paths) | Where-Object { $_.key -cne $script:SessionKey })
    $attempts += @{ key = $script:SessionKey; transcript = [string] $Payload.transcript_path; offset = $TranscriptOffset }
    $receipt = @{
        schema = 'handoff-relay-completed.v1'; attempts = @($attempts | Select-Object -Last 32)
    }
    if ($script:Utf8NoBom.GetByteCount(($receipt | ConvertTo-Json -Depth 10)) -gt 32768) { throw 'Receipt exceeds its bound.' }
    Write-AtomicJson -Path $Paths.Receipt -Value $receipt
}

function Test-HandoffState {
    param([object] $State, [object] $Context, [object] $Paths)

    return $null -ne $State -and
        [string] $State.schema -ceq 'handoff-relay-state.v1' -and
        [string] $State.phase -ceq 'awaiting-draft' -and
        [string] $State.provider -ceq $Provider.ToLowerInvariant() -and
        [string] $State.sessionKey -ceq $script:SessionKey -and
        -not [string]::IsNullOrWhiteSpace([string] $State.target) -and
        -not [string]::IsNullOrWhiteSpace([string] $State.draft) -and
        -not [string]::IsNullOrWhiteSpace([string] $State.workspace) -and
        (Test-SamePath -Left $State.target -Right $Context.Target) -and
        (Test-SamePath -Left $State.draft -Right $Paths.Draft) -and
        (Test-SamePath -Left $State.workspace -Right $Context.Workspace) -and
        [string] $State.project -ceq [string] $Context.ProjectSlug -and
        [string] $State.baselineHash -match '^(?:<absent>|[A-F0-9]{64})$'
}

function Test-DedicatedDraftCall {
    param([object] $Call, [string] $DraftPath)

    $patch = ''
    if ($Call.type -ceq 'custom_tool_call' -and $Call.name -ceq 'apply_patch') {
        $patch = [string] $Call.input
    }
    elseif ($Call.type -ceq 'custom_tool_call' -and $Call.name -ceq 'exec') {
        # Support the observed code-mode wrapper without executing or loosely
        # searching JavaScript. Mixed/nested batches retain the recovery path.
        $match = [regex]::Match([string] $Call.input,
            '^\s*text\(await tools\.apply_patch\((?<json>"(?:[^"\\]|\\.)*")\)\);?\s*$')
        if (-not $match.Success) { return $false }
        $patch = $match.Groups['json'].Value | ConvertFrom-Json -ErrorAction Stop
    }
    else { return $false }
    $files = @([regex]::Matches($patch, '(?m)^\*\*\* (?:Add|Update|Delete) File: (?<path>[^\r\n]+)'))
    return $files.Count -eq 1 -and
        (Test-SamePath -Left $files[0].Groups['path'].Value -Right $DraftPath)
}

function Test-PreparedDraftFresh {
    param([object] $State, [object] $Payload, [object] $Paths)

    $stream = $null
    $reader = $null
    try {
        if ([string] $State.sessionId -cne [string] $Payload.session_id -or
            [string] $State.turnId -cne [string] $Payload.turn_id -or
            -not (Test-SamePath -Left $State.transcript -Right $Payload.transcript_path)) { return $false }
        $stream = [System.IO.FileStream]::new($State.transcript, 'Open', 'Read',
            [System.IO.FileShare]::ReadWrite -bor [System.IO.FileShare]::Delete)
        $offset = [long] $State.transcriptOffset
        if ($offset -lt 0 -or $offset -gt $stream.Length) { return $false }
        $null = $stream.Seek($offset, [System.IO.SeekOrigin]::Begin)
        $reader = [System.IO.StreamReader]::new($stream, [System.Text.Encoding]::UTF8, $true)
        $pending = @{}
        $fresh = $false
        $draftContent = $null
        while ($null -ne ($line = $reader.ReadLine())) {
            if ([string]::IsNullOrWhiteSpace($line)) { continue }
            $record = $line | ConvertFrom-Json -Depth 100 -ErrorAction Stop
            $entry = $record.payload
            if ($record.type -ceq 'response_item') {
                if ($entry.type -match '_call$') {
                    $fresh = $false
                    $pending[[string] $entry.call_id] = Test-DedicatedDraftCall -Call $entry -DraftPath $Paths.Draft
                }
                elseif ($entry.type -match '_call_output$') {
                    if (-not $pending.ContainsKey([string] $entry.call_id)) { $fresh = $false }
                    $pending.Remove([string] $entry.call_id)
                }
                elseif ($entry.type -ceq 'message' -and $entry.role -ceq 'assistant') { }
                elseif ($entry.type -ceq 'reasoning') { }
                else { $fresh = $false }
            }
            elseif ($record.type -ceq 'event_msg') {
                if ($entry.type -ceq 'item_completed') {
                    $item = $entry.item
                    if ($item.type -ceq 'FileChange') {
                        $fresh = $false
                        $changes = @($item.changes.PSObject.Properties)
                        if ($entry.thread_id -ceq $State.sessionId -and $entry.turn_id -ceq $State.turnId -and
                            $item.status -ceq 'completed' -and $pending.Count -eq 1 -and
                            @($pending.Values)[0] -eq $true -and $changes.Count -eq 1 -and
                            (Test-SamePath -Left $changes[0].Name -Right $Paths.Draft) -and
                            $changes[0].Value.type -ceq 'add') {
                            $draftContent = [string] $changes[0].Value.content
                            $fresh = $true
                        }
                    }
                    elseif ($item.type -notin @('AgentMessage', 'Reasoning')) { $fresh = $false }
                }
                elseif ($entry.type -notin @('token_count')) { $fresh = $false }
            }
            elseif ($record.type -cne 'token_usage_record') { $fresh = $false }
        }
        $script:ValidatedTranscriptLength = $stream.Position
        return $fresh -and $pending.Count -eq 0 -and $null -ne $draftContent -and
            $draftContent.Replace("`r`n", "`n") -ceq (Read-SharedText -Path $Paths.Draft).Replace("`r`n", "`n")
    }
    catch { return $false }
    finally {
        if ($null -ne $reader) { $reader.Dispose() }
        elseif ($null -ne $stream) { $stream.Dispose() }
    }
}

function Initialize-HandoffDraft {
    param(
        [Parameter(Mandatory)][object] $Context,
        [Parameter(Mandatory)][object] $Paths,
        [object] $Payload,
        [switch] $BeforeModel
    )

    if (-not (Test-HandoffPathSetIsSafe -Target $Context.Target -Paths $Paths)) {
        Write-HealthRecord -Status FAILED -Code 'unsafe-reparse-traversal'
        Write-NeutralHookResult
    }
    $null = New-Item -ItemType Directory -Path $Paths.Root -Force
    if (-not (Test-HandoffPathSetIsSafe -Target $Context.Target -Paths $Paths)) {
        Write-HealthRecord -Status FAILED -Code 'unsafe-reparse-traversal'
        Write-NeutralHookResult
    }
    $quarantinedDrafts = 0
    $lock = Enter-ProjectPublishLock -Path $Paths.Lock
    try {
        if (-not (Test-HandoffPathSetIsSafe -Target $Context.Target -Paths $Paths)) {
            Write-HealthRecord -Status FAILED -Code 'unsafe-reparse-traversal'
            Write-NeutralHookResult
        }
        if (Test-AttemptCompleted -Paths $Paths -Payload $Payload) {
            Write-NeutralHookResult
        }
        if ($BeforeModel -and (Test-Path -LiteralPath $Paths.State -PathType Leaf)) {
            if ((Get-Item -LiteralPath $Paths.State).Length -gt 8192) { throw 'State exceeds its bound.' }
            $existing = Read-SharedText -Path $Paths.State | ConvertFrom-Json -Depth 20 -ErrorAction Stop
            if (-not (Test-HandoffState -State $existing -Context $Context -Paths $Paths)) {
                Write-NeutralHookResult
            }
            # Never reset a baseline or a Stop recovery on prompt retries/steering.
            if ($existing.preparation -ceq 'prompt') {
                Write-DraftInstruction -Context $Context -Paths $Paths -BeforeModel
            }
            Write-NeutralHookResult
        }
        $quarantinedDrafts = Move-LooseDraftsToArchive -Paths $Paths
        if (
            (Test-Path -LiteralPath $Paths.State -PathType Leaf) -or
            (Test-Path -LiteralPath $Paths.Draft -PathType Leaf)
        ) {
            Move-AttemptToArchive -Paths $Paths -Kind orphaned
        }

        $state = [ordered]@{
            schema = 'handoff-relay-state.v1'
            phase = 'awaiting-draft'
            provider = $Provider.ToLowerInvariant()
            sessionKey = $script:SessionKey
            target = $Context.Target
            workspace = $Context.Workspace
            project = $Context.ProjectSlug
            draft = $Paths.Draft
            baselineHash = Get-SharedFileHash -Path $Context.Target
            createdUtc = [DateTime]::UtcNow.ToString('o')
        }
        if ($BeforeModel) {
            $state.preparation = 'prompt'
            $state.sessionId = [string] $Payload.session_id
            $state.turnId = [string] $Payload.turn_id
            $state.transcript = Resolve-NormalizedPath -Path $Payload.transcript_path
            $state.transcriptOffset = (Get-Item -LiteralPath $Payload.transcript_path).Length
        }
        Write-AtomicJson -Path $Paths.State -Value $state
    }
    finally {
        $lock.Dispose()
    }
    Write-HealthRecord `
        -Status PREPARED `
        -Code 'awaiting-draft' `
        -Details @{ quarantinedDrafts = $quarantinedDrafts }

    Write-DraftInstruction -Context $Context -Paths $Paths -BeforeModel:$BeforeModel -QuarantinedDrafts $quarantinedDrafts
}

function Write-DraftInstruction {
    param([object] $Context, [object] $Paths, [switch] $BeforeModel, [int] $QuarantinedDrafts = 0)

    $budgetInstruction = Get-HandoffBudgetInstruction
    if ($BeforeModel) {
        $instruction = @"
Handoff Relay: an active draft transaction is ready for this turn.

Canonical: $($Context.Target)
Workspace: $($Context.Workspace)
Draft: $($Paths.Draft)

This turn's handoff destination is Draft. The canonical declaration remains routing information; do not also write canonical. This is bounded Remember project state, not Codex native memory.

Complete all requested work and verification first. Immediately before your final answer, write the current handoff using a dedicated apply_patch call that adds only Draft. In code mode use only text(await tools.apply_patch(...)); in that call. Then give the normal useful final answer, including any required Run closeout. Do not shorten the requested deliverable or claim publication: Stop validates, hash-checks and atomically publishes afterward. No preparation tool call is needed.

If more work or user steering arrives after drafting, finish that work; Stop will request a fresh draft. For a short tool-free Q&A ending in a question mark, with question and reply each at most 500 characters and no handoff request, skip drafting. Background work retains the existing bypass. Missing instructions or an uncertain draft retain Stop recovery.

Use these exact headings in order: ## Summary, ## Outcome, ## Verified state, ## Changed surfaces, ## Verification, ## Open risks, ## Next gate. Use bullets only, [verified] ... Evidence: ... for verified facts, and [risk] ... Basis: ... or None. for risks. Each [verified] bullet names a checkable token in backticks: a commit sha, branch, path, or test name; anything you cannot check belongs under Open risks with its basis. Current verified state outranks old notes. Include no speculation, process narration, code fences or unsupported claims.

$budgetInstruction
"@.Trim()
        @{ hookSpecificOutput = @{ hookEventName = 'UserPromptSubmit'; additionalContext = $instruction } } |
            ConvertTo-Json -Depth 10 -Compress | Write-Output
        exit 0
    }

    $instruction = @"
Handoff Relay: prepare the concise next-session handoff before finishing.

Canonical: $($Context.Target)
Workspace: $($Context.Workspace)
Draft: $($Paths.Draft)

Write the handoff to the file at Draft with a file-editing tool; do not edit the canonical file. The relay will clean, validate, hash-check, lock, and atomically publish it on the next Stop pass. This is bounded Remember project state, not Codex native memory.

After the draft write succeeds, finish with 1-2 useful, self-contained sentences: summarize the task's concrete outcome or finding, then give the most relevant suggested next action or unresolved blocker. If the task is complete and no follow-up is needed, say so without inventing work. Never end with only a handoff status or a generic acknowledgement. Condense the earlier answer instead of repeating it in full; do not repeat its Run closeout. Do not claim publication from the draft write; the relay will surface the publication result separately.

Before the file edit, keep any commentary to a single line: use exactly ``Preparing handoff.`` Do not describe the proposed handoff contents, verification, or outcome in commentary.

Use these exact Markdown headings in this order: `## Summary`, `## Outcome`, `## Verified state`, `## Changed surfaces`, `## Verification`, `## Open risks`, `## Next gate`. Use bullets only. Verified-state bullets use `[verified] ... Evidence: ...` and each names a checkable token in backticks: a commit sha, branch, path, or test name; anything you cannot check belongs under Open risks with its basis. Risk bullets use `[risk] ... Basis: ...`, or `None.`. Do not include guesses, speculation, unsupported claims, process narration, code fences, or extra prose. Current verified state outranks the old handoff.

$budgetInstruction
"@.Trim()
    $preparationMessage = 'Preparing handoff.'
    if ($quarantinedDrafts -gt 0) {
        $noun = if ($quarantinedDrafts -eq 1) { 'draft' } else { 'drafts' }
        $preparationMessage += " The relay quarantined $quarantinedDrafts stale $noun."
    }
    Write-ContinuationResult `
        -Instruction $instruction `
        -SystemMessage $preparationMessage
}

function Complete-HandoffDraft {
    param(
        [Parameter(Mandatory)][object] $Context,
        [Parameter(Mandatory)][object] $Paths,
        [object] $Payload,
        [switch] $InitialStop
    )

    $script:ValidatedTranscriptLength = if ($null -ne $Payload -and
        -not [string]::IsNullOrWhiteSpace([string] $Payload.transcript_path) -and
        (Test-Path -LiteralPath $Payload.transcript_path -PathType Leaf)) {
        (Get-Item -LiteralPath $Payload.transcript_path).Length
    } else { 0 }

    if (-not (Test-HandoffPathSetIsSafe -Target $Context.Target -Paths $Paths)) {
        Write-HealthRecord -Status FAILED -Code 'unsafe-reparse-traversal'
        Write-HandoffFailureResult -Code 'unsafe-reparse-traversal'
    }
    if (-not (Test-Path -LiteralPath $Paths.Root -PathType Container)) {
        Write-HealthRecord -Status SKIPPED -Code 'no-active-attempt'
        Write-NeutralHookResult
    }
    $lock = Enter-ProjectPublishLock -Path $Paths.Lock
    try {
        if (-not (Test-HandoffPathSetIsSafe -Target $Context.Target -Paths $Paths)) {
            Write-HealthRecord -Status FAILED -Code 'unsafe-reparse-traversal'
            Write-HandoffFailureResult -Code 'unsafe-reparse-traversal'
        }
        if (-not (Test-Path -LiteralPath $Paths.State -PathType Leaf)) {
        if (Test-Path -LiteralPath $Paths.Draft -PathType Leaf) {
            Move-AttemptToArchive -Paths $Paths -Kind orphaned
            Write-HealthRecord `
                -Status FAILED `
                -Code 'state-missing' `
                -Details @{ draftQuarantined = $true }
            Write-HandoffFailureResult -Code 'state-missing'
        }

        Write-HealthRecord -Status SKIPPED -Code 'no-active-attempt'
        Write-NeutralHookResult
    }

    try {
        if ((Get-Item -LiteralPath $Paths.State).Length -gt 8192) { throw 'State exceeds its bound.' }
        $state = Read-SharedText -Path $Paths.State |
            ConvertFrom-Json -Depth 20 -ErrorAction Stop
    }
    catch {
        Move-AttemptToArchive -Paths $Paths -Kind failed
        Write-HealthRecord -Status FAILED -Code 'state-invalid'
        Write-HandoffFailureResult -Code 'state-invalid'
    }

    $stateIsValid = Test-HandoffState -State $state -Context $Context -Paths $Paths
    if (-not $stateIsValid) {
        Move-AttemptToArchive -Paths $Paths -Kind failed
        Write-HealthRecord -Status FAILED -Code 'state-contract-mismatch'
        Write-HandoffFailureResult -Code 'state-contract-mismatch'
    }

    if ($InitialStop) {
        if ($state.preparation -ceq 'recovery') {
            Write-NeutralHookResult
        }
        if ($state.preparation -cne 'prompt') { return }
    }
    if ($state.preparation -ceq 'prompt') {
        if ($null -eq $Payload -or
            [string] $state.sessionId -cne [string] $Payload.session_id -or
            [string] $state.turnId -cne [string] $Payload.turn_id -or
            [string]::IsNullOrWhiteSpace([string] $state.transcript) -or
            -not (Test-SamePath -Left $state.transcript -Right $Payload.transcript_path)) {
            Move-AttemptToArchive -Paths $Paths -Kind failed
            Write-HealthRecord -Status FAILED -Code 'prepared-ownership-mismatch'
            Write-HandoffFailureResult -Code 'prepared-ownership-mismatch'
        }
        if ($InitialStop -and (Test-ToolFreeQuestion -Payload $Payload)) {
            Save-CompletedAttempt -Paths $Paths -Payload $Payload -TranscriptOffset $script:ValidatedTranscriptLength
            if (Test-Path -LiteralPath $Paths.Draft -PathType Leaf) {
                Move-AttemptToArchive -Paths $Paths -Kind orphaned
            }
            else { Remove-Item -LiteralPath $Paths.State -Force }
            Write-HealthRecord -Status SKIPPED -Code 'tool-free-turn'
            Write-NeutralHookResult
        }
        $hasBoundedDraft = (Test-Path -LiteralPath $Paths.Draft -PathType Leaf) -and
            (Get-Item -LiteralPath $Paths.Draft).Length -le $MaxDraftBytes
        if (-not $hasBoundedDraft -or -not (Test-PreparedDraftFresh -State $state -Payload $Payload -Paths $Paths)) {
            if (-not $InitialStop) {
                Move-AttemptToArchive -Paths $Paths -Kind failed
                Write-HealthRecord -Status FAILED -Code 'prepared-draft-stale'
                Write-HandoffFailureResult -Code 'prepared-draft-stale'
            }
            # Keep the original hash. In particular, do not rebaseline after a
            # concurrent publisher when recovering a missing or stale draft.
            Move-AttemptToArchive -Paths $Paths -Kind orphaned
            $state.preparation = 'recovery'
            Write-AtomicJson -Path $Paths.State -Value $state
            Write-HealthRecord -Status PREPARED -Code 'prepared-draft-recovery'
            Write-DraftInstruction -Context $Context -Paths $Paths
        }
    }

    if (-not (Test-Path -LiteralPath $Paths.Draft -PathType Leaf)) {
        Move-AttemptToArchive -Paths $Paths -Kind failed
        Write-HealthRecord -Status FAILED -Code 'draft-missing'
        Write-HandoffFailureResult -Code 'draft-missing'
    }
    $draftInfo = Get-Item -LiteralPath $Paths.Draft
    if ($draftInfo.Length -gt $MaxDraftBytes) {
        Move-AttemptToArchive -Paths $Paths -Kind failed
        Write-HealthRecord -Status FAILED -Code 'draft-too-large' -Details @{
            maximumBytes = $MaxDraftBytes
        }
        Write-HandoffFailureResult -Code 'draft-too-large'
    }

    $cleaned = ConvertTo-CleanHandoff -Draft (Read-SharedText -Path $Paths.Draft)
    if (-not $cleaned.Valid) {
        $failureCode = if ($cleaned.Code -eq 'draft-budget-exceeded') { $cleaned.Code } else { 'draft-invalid' }
        Move-AttemptToArchive -Paths $Paths -Kind failed
        Write-HealthRecord `
            -Status FAILED `
            -Code $failureCode `
            -Cleaning $cleaned.Cleaning `
            -Details @{ missingSections = ($cleaned.MissingSections -join ',') }
        Write-HandoffFailureResult -Code $failureCode
    }

    $document = ConvertTo-HandoffDocument -Cleaned $cleaned -State $state
    $documentBytes = $script:Utf8NoBom.GetByteCount($document)
    if ($documentBytes -gt $MaxPublishedBytes) {
        Move-AttemptToArchive -Paths $Paths -Kind failed
        Write-HealthRecord `
            -Status FAILED `
            -Code 'document-too-large' `
            -Cleaning $cleaned.Cleaning `
            -Details @{
                actualBytes = $documentBytes
                maximumBytes = $MaxPublishedBytes
            }
        Write-HandoffFailureResult -Code 'document-too-large'
    }

        $currentHash = Get-SharedFileHash -Path $Context.Target
        if ([string] $state.baselineHash -cne $currentHash) {
            Move-AttemptToArchive -Paths $Paths -Kind conflict
            Write-HealthRecord `
                -Status CONFLICT `
                -Code 'canonical-changed' `
                -Cleaning $cleaned.Cleaning
            Write-NeutralHookResult -SystemMessage (
                'Handoff Relay: a newer next-session context already exists; ' +
                'this attempt was saved for review.'
            )
        }

        Write-AtomicText -Path $Context.Target -Content $document
        $receiptSaved = $true
        if ($state.preparation -in @('prompt', 'recovery')) {
            try { Save-CompletedAttempt -Paths $Paths -Payload $Payload -TranscriptOffset $script:ValidatedTranscriptLength }
            catch { $receiptSaved = $false }
        }
        Remove-Item -LiteralPath $Paths.State,$Paths.Draft -Force -ErrorAction SilentlyContinue
        Write-HealthRecord `
            -Status PUBLISHED `
            -Code 'published' `
            -Details @{ completionReceiptSaved = $receiptSaved } `
            -Cleaning $cleaned.Cleaning
    }
    finally {
        $lock.Dispose()
    }

    Write-NeutralHookResult -SystemMessage (
        'Handoff Relay: next-session context refreshed.'
    )
}

try {
    $script:Stage = 'resolve-root'
    $script:ResolvedProjectsRoot = Resolve-NormalizedPath -Path $RememberProjectsRoot
    if (-not (Test-Path -LiteralPath $script:ResolvedProjectsRoot -PathType Container)) {
        Write-NeutralHookResult
    }
    if (-not (Test-PathTraversalIsReparseFree -Path $script:ResolvedProjectsRoot)) {
        Write-NeutralHookResult
    }
    $script:HealthTargetSafe = $true

    $script:Stage = 'verify-identity'
    $null = Assert-VerifiedMachine

    $script:Stage = 'read-input'
    $rawInput = [Console]::In.ReadToEnd()
    $payload = $rawInput | ConvertFrom-Json -Depth 100 -ErrorAction Stop

    $beforeModel = $Provider -ceq 'Codex' -and [string] $payload.hook_event_name -ceq 'UserPromptSubmit'
    if (-not $beforeModel -and [string] $payload.hook_event_name -cne 'Stop') {
        Write-NeutralHookResult
    }
    if ($beforeModel -and (
        [string]::IsNullOrWhiteSpace([string] $payload.session_id) -or
        [string]::IsNullOrWhiteSpace([string] $payload.turn_id) -or
        [string]::IsNullOrWhiteSpace([string] $payload.transcript_path) -or
        -not (Test-Path -LiteralPath ([string] $payload.transcript_path) -PathType Leaf)
    )) { Write-NeutralHookResult }

    $hasBackgroundTasks = $null -ne $payload.PSObject.Properties['background_tasks'] -and
        $null -ne $payload.background_tasks -and
        @($payload.background_tasks).Count -gt 0
    $hasSessionCrons = $null -ne $payload.PSObject.Properties['session_crons'] -and
        $null -ne $payload.session_crons -and
        @($payload.session_crons).Count -gt 0
    if ($hasBackgroundTasks -or $hasSessionCrons) {
        Write-NeutralHookResult
    }

    $script:SessionKey = Get-SessionKey -Payload $payload

    $script:Stage = 'resolve-context'
    $context = Resolve-HandoffContext `
        -Payload $payload `
        -ResolvedProjectsRoot $script:ResolvedProjectsRoot
    if (-not $context.Found) {
        Write-HealthRecord -Status SKIPPED -Code ([string] $context.Code)
        Write-NeutralHookResult
    }
    $script:ProjectSlug = [string] $context.ProjectSlug

    $script:Stage = 'classify-session'
    $sessionKind = Get-SessionKind -Payload $payload
    if ($sessionKind -cne 'interactive') {
        Write-HealthRecord -Status SKIPPED -Code "non-interactive-$sessionKind"
        Write-NeutralHookResult
    }

    $projectRoot = Split-Path -Parent $context.Target
    $paths = Get-AttemptPathSet -ProjectRoot $projectRoot -SessionKey $script:SessionKey
    if ($beforeModel) {
        $script:Stage = 'prepare'
        Initialize-HandoffDraft -Context $context -Paths $paths -Payload $payload -BeforeModel
    }
    $stopHookActive = $payload.stop_hook_active -eq $true -or
        [string] $payload.stop_hook_active -eq 'true'
    if ($stopHookActive) {
        $script:Stage = 'complete'
        Complete-HandoffDraft -Context $context -Paths $paths -Payload $payload
    }

    if ($Provider -ceq 'Codex' -and (Test-Path -LiteralPath $paths.State -PathType Leaf)) {
        $script:Stage = 'complete'
        Complete-HandoffDraft -Context $context -Paths $paths -Payload $payload -InitialStop
    }

    if (Test-ToolFreeQuestion -Payload $payload) {
        Write-HealthRecord -Status SKIPPED -Code 'tool-free-turn'
        Write-NeutralHookResult
    }

    $script:Stage = 'prepare'
    Initialize-HandoffDraft -Context $context -Paths $paths -Payload $payload
}
catch {
    Write-HealthRecord `
        -Status FAILED `
        -Code 'unexpected-error' `
        -Details @{
            stage = $script:Stage
            exceptionType = $_.Exception.GetType().Name
        }
    if ($script:Stage -ceq 'complete') {
        Write-HandoffFailureResult -Code 'unexpected-error'
    }
    if ($script:Stage -ceq 'prepare') {
        Write-HandoffFailureResult -Code 'unexpected-error'
    }
    Write-NeutralHookResult
}
