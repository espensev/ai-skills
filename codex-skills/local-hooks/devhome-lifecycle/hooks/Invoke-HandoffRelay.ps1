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
        elseif (-not [string]::IsNullOrWhiteSpace([string] $Payload.cwd)) {
            try {
                $workspace = Resolve-NormalizedPath -Path ([string] $Payload.cwd)
            }
            catch {
                $workspace = '<unknown>'
            }
        }
        else {
            $workspace = '<unknown>'
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

    foreach ($path in @($Paths.Root, $Paths.State, $Paths.Draft, $Paths.Lock)) {
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

function Limit-WordCount {
    param(
        [Parameter(Mandatory)][string] $Text,
        [Parameter(Mandatory)][int] $Maximum
    )

    $words = @([regex]::Matches($Text, '\S+') | ForEach-Object { $_.Value })
    if ($words.Count -le $Maximum) {
        return [pscustomobject]@{ Text = $Text; Truncated = $false }
    }

    return [pscustomobject]@{
        Text = (($words[0..($Maximum - 1)] -join ' ') + ' ...')
        Truncated = $true
    }
}

function Limit-TextExtent {
    param(
        [Parameter(Mandatory)][string] $Text,
        [Parameter(Mandatory)][int] $MaximumCharacters,
        [Parameter(Mandatory)][int] $MaximumUtf8Bytes
    )

    $elementOffsets = [System.Globalization.StringInfo]::ParseCombiningCharacters($Text)
    $utf8Bytes = $script:Utf8NoBom.GetByteCount($Text)
    if (
        $elementOffsets.Count -le $MaximumCharacters -and
        $utf8Bytes -le $MaximumUtf8Bytes
    ) {
        return [pscustomobject]@{ Text = $Text; Truncated = $false }
    }

    $suffix = ' ...'
    $suffixCharacters = [System.Globalization.StringInfo]::ParseCombiningCharacters($suffix).Count
    $maximumBodyCharacters = $MaximumCharacters - $suffixCharacters
    $maximumBodyBytes = $MaximumUtf8Bytes - $script:Utf8NoBom.GetByteCount($suffix)
    $builder = [System.Text.StringBuilder]::new()
    $bodyBytes = 0
    for ($index = 0; $index -lt $elementOffsets.Count; $index++) {
        if ($index -ge $maximumBodyCharacters) {
            break
        }

        $offset = $elementOffsets[$index]
        $length = if ($index + 1 -lt $elementOffsets.Count) {
            $elementOffsets[$index + 1] - $offset
        }
        else {
            $Text.Length - $offset
        }
        $element = $Text.Substring($offset, $length)
        $elementBytes = $script:Utf8NoBom.GetByteCount($element)
        if ($bodyBytes + $elementBytes -gt $maximumBodyBytes) {
            break
        }

        $null = $builder.Append($element)
        $bodyBytes += $elementBytes
    }

    return [pscustomobject]@{
        Text = $builder.ToString().TrimEnd() + $suffix
        Truncated = $true
    }
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

function ConvertTo-CleanHandoff {
    param([Parameter(Mandatory)][string] $Draft)

    $specs = [ordered]@{
        'Summary' = @{ MaxItems = 2; MaxWords = 45; MaxItemWords = 26; FilterFacts = $true }
        'Outcome' = @{ MaxItems = 3; MaxWords = 60; MaxItemWords = 26; FilterFacts = $true }
        'Verified state' = @{ MaxItems = 4; MaxWords = 100; MaxItemWords = 34; FilterFacts = $true }
        'Changed surfaces' = @{ MaxItems = 4; MaxWords = 60; MaxItemWords = 24; FilterFacts = $true }
        'Verification' = @{ MaxItems = 4; MaxWords = 70; MaxItemWords = 26; FilterFacts = $true }
        'Open risks' = @{ MaxItems = 3; MaxWords = 55; MaxItemWords = 26; FilterFacts = $false }
        'Next gate' = @{ MaxItems = 2; MaxWords = 40; MaxItemWords = 24; FilterFacts = $false }
    }
    $items = [ordered]@{}
    $seen = @{}
    foreach ($section in $specs.Keys) {
        $items[$section] = [System.Collections.Generic.List[string]]::new()
        $seen[$section] = [System.Collections.Generic.HashSet[string]]::new(
            [System.StringComparer]::OrdinalIgnoreCase
        )
    }

    $droppedItems = 0
    $truncatedItems = 0
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
        if ($items[$currentSection].Count -ge [int] $spec.MaxItems) {
            $droppedItems++
            continue
        }

        $limitedWords = Limit-WordCount -Text $text -Maximum ([int] $spec.MaxItemWords)
        $limitedExtent = Limit-TextExtent `
            -Text $limitedWords.Text `
            -MaximumCharacters $MaxItemCharacters `
            -MaximumUtf8Bytes $MaxItemUtf8Bytes
        $text = $limitedExtent.Text
        if ($limitedWords.Truncated -or $limitedExtent.Truncated) {
            $truncatedItems++
        }
        if (-not (Test-SectionItemContract -Section $currentSection -Text $text)) {
            $droppedItems++
            continue
        }
        $sectionWords = @($items[$currentSection] | ForEach-Object { Get-WordCount -Text $_ } |
            Measure-Object -Sum).Sum
        if ($null -eq $sectionWords) {
            $sectionWords = 0
        }
        $remainingWords = [int] $spec.MaxWords - [int] $sectionWords
        if ($remainingWords -lt 5) {
            $droppedItems++
            continue
        }
        if ((Get-WordCount -Text $text) -gt $remainingWords) {
            $limited = Limit-WordCount -Text $text -Maximum $remainingWords
            $text = $limited.Text
            $truncatedItems++
            if (-not (Test-SectionItemContract -Section $currentSection -Text $text)) {
                $droppedItems++
                continue
            }
        }
        if (-not $seen[$currentSection].Add($text)) {
            $droppedItems++
            continue
        }
        $items[$currentSection].Add($text)
    }

    $missingSections = @($specs.Keys | Where-Object { $items[$_].Count -eq 0 })
    $publishedWords = 0
    foreach ($section in $specs.Keys) {
        foreach ($item in $items[$section]) {
            $publishedWords += Get-WordCount -Text $item
        }
    }
    if ($publishedWords -gt $MaxPublishedWords) {
        return [pscustomobject]@{
            Valid = $false
            Code = 'word-limit-exceeded'
            MissingSections = $missingSections
            Items = $items
            Cleaning = [pscustomobject]@{
                droppedItems = $droppedItems
                truncatedItems = $truncatedItems
                ignoredLines = $ignoredLines
                publishedWords = $publishedWords
            }
        }
    }

    return [pscustomobject]@{
        Valid = $missingSections.Count -eq 0
        Code = if ($missingSections.Count -eq 0) { 'clean' } else { 'required-section-empty' }
        MissingSections = $missingSections
        Items = $items
        Cleaning = [pscustomobject]@{
            droppedItems = $droppedItems
            truncatedItems = $truncatedItems
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

function Initialize-HandoffDraft {
    param(
        [Parameter(Mandatory)][object] $Context,
        [Parameter(Mandatory)][object] $Paths
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
        Write-AtomicJson -Path $Paths.State -Value $state
    }
    finally {
        $lock.Dispose()
    }
    Write-HealthRecord `
        -Status PREPARED `
        -Code 'awaiting-draft' `
        -Details @{ quarantinedDrafts = $quarantinedDrafts }

    $instruction = @"
Handoff Relay: prepare the concise next-session handoff before finishing.

Canonical: $($Context.Target)
Workspace: $($Context.Workspace)
Draft: $($Paths.Draft)

Write the handoff to the file at Draft with a file-editing tool; do not edit the canonical file. The relay will clean, validate, hash-check, lock, and atomically publish it on the next Stop pass. This is bounded Remember project state, not Codex native memory.

Do not answer with only the draft path. After the draft write succeeds, repeat the substantive user-facing closeout you had already provided and add one final sentence: `Handoff prepared for automatic publication.` Do not claim publication from the draft write; the relay will surface the publication result separately.

Before the file edit, keep any commentary to a single line: use exactly ``Preparing handoff.`` Do not describe the proposed handoff contents, verification, or outcome in commentary.

Use these exact Markdown headings in this order: `## Summary`, `## Outcome`, `## Verified state`, `## Changed surfaces`, `## Verification`, `## Open risks`, `## Next gate`. Use bullets only. Summary has at most 2 bullets. Verified-state bullets use `[verified] ... Evidence: ...`. Risk bullets use `[risk] ... Basis: ...`, or `None.`. Do not include guesses, speculation, unsupported claims, process narration, code fences, or extra prose. Keep each bullet under 30 words where practical. Current verified state outranks the old handoff.
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
        [Parameter(Mandatory)][object] $Paths
    )

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
        $state = Read-SharedText -Path $Paths.State |
            ConvertFrom-Json -Depth 20 -ErrorAction Stop
    }
    catch {
        Move-AttemptToArchive -Paths $Paths -Kind failed
        Write-HealthRecord -Status FAILED -Code 'state-invalid'
        Write-HandoffFailureResult -Code 'state-invalid'
    }

    $expectedDraft = Resolve-NormalizedPath -Path $Paths.Draft
    $stateTarget = [string] $state.target
    $stateDraft = [string] $state.draft
    $stateWorkspace = [string] $state.workspace
    $stateIsValid =
        [string] $state.schema -ceq 'handoff-relay-state.v1' -and
        [string] $state.phase -ceq 'awaiting-draft' -and
        [string] $state.provider -ceq $Provider.ToLowerInvariant() -and
        [string] $state.sessionKey -ceq $script:SessionKey -and
        -not [string]::IsNullOrWhiteSpace($stateTarget) -and
        -not [string]::IsNullOrWhiteSpace($stateDraft) -and
        -not [string]::IsNullOrWhiteSpace($stateWorkspace) -and
        (Test-SamePath -Left $stateTarget -Right $Context.Target) -and
        (Test-SamePath -Left $stateDraft -Right $expectedDraft) -and
        [string]::Equals(
            $stateWorkspace,
            [string] $Context.Workspace,
            [System.StringComparison]::OrdinalIgnoreCase
        ) -and
        [string] $state.project -ceq [string] $Context.ProjectSlug -and
        [string] $state.baselineHash -match '^(?:<absent>|[A-F0-9]{64})$'
    if (-not $stateIsValid) {
        Move-AttemptToArchive -Paths $Paths -Kind failed
        Write-HealthRecord -Status FAILED -Code 'state-contract-mismatch'
        Write-HandoffFailureResult -Code 'state-contract-mismatch'
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
        Move-AttemptToArchive -Paths $Paths -Kind failed
        Write-HealthRecord `
            -Status FAILED `
            -Code 'draft-invalid' `
            -Cleaning $cleaned.Cleaning `
            -Details @{ missingSections = ($cleaned.MissingSections -join ',') }
        Write-HandoffFailureResult -Code 'draft-invalid'
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
        Remove-Item -LiteralPath $Paths.State,$Paths.Draft -Force -ErrorAction SilentlyContinue
        Write-HealthRecord `
            -Status PUBLISHED `
            -Code 'published' `
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

    if ([string] $payload.hook_event_name -cne 'Stop') {
        Write-NeutralHookResult
    }

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

    $projectRoot = Split-Path -Parent $context.Target
    $paths = Get-AttemptPathSet -ProjectRoot $projectRoot -SessionKey $script:SessionKey
    $stopHookActive = $payload.stop_hook_active -eq $true -or
        [string] $payload.stop_hook_active -eq 'true'
    if ($stopHookActive) {
        $script:Stage = 'complete'
        Complete-HandoffDraft -Context $context -Paths $paths
    }

    $script:Stage = 'prepare'
    Initialize-HandoffDraft -Context $context -Paths $paths
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
