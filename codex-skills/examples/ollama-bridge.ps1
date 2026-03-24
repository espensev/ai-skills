[CmdletBinding()]
param(
    [string]$RepoRoot = (Get-Location).Path,
    [string]$PlanId = "",
    [ValidateSet("tasks", "campaign")]
    [string]$LaunchMode = "tasks",
    [string]$OllamaUrl = "http://127.0.0.1:11434",
    [string]$DefaultModel = "",
    [string]$HaikuModel = "",
    [string]$SonnetModel = "",
    [string]$OpusModel = "",
    [double]$Temperature = 0.1,
    [int]$NumCtx = 16384,
    [int]$MaxConventionChars = 12000,
    [int]$MaxFileChars = 24000,
    [int]$MaxIterations = 24,
    [switch]$SkipMerge,
    [switch]$SkipVerification
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Utf8File {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$Content
    )

    $parent = Split-Path -Parent $Path
    if ($parent) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }

    $encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Content, $encoding)
}

function Invoke-External {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Executable,
        [Parameter()]
        [string[]]$Arguments = @(),
        [Parameter()]
        [string]$WorkingDirectory = ""
    )

    $output = ""
    $exitCode = 0
    $location = if ($WorkingDirectory) { $WorkingDirectory } else { (Get-Location).Path }

    Push-Location $location
    try {
        $raw = & $Executable @Arguments 2>&1
        $exitCode = $LASTEXITCODE
        $output = ($raw | Out-String).Trim()
    }
    finally {
        Pop-Location
    }

    [pscustomobject]@{
        ExitCode = $exitCode
        Output = $output
        Command = ($Executable + " " + ($Arguments -join " ")).Trim()
    }
}

function Invoke-Required {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Executable,
        [Parameter()]
        [string[]]$Arguments = @(),
        [Parameter()]
        [string]$WorkingDirectory = "",
        [Parameter()]
        [string]$FailureLabel = "Command failed"
    )

    $result = Invoke-External -Executable $Executable -Arguments $Arguments -WorkingDirectory $WorkingDirectory
    if ($result.ExitCode -ne 0) {
        $detail = if ($result.Output) { $result.Output } else { "(no output)" }
        throw "$FailureLabel`nCommand: $($result.Command)`n$detail"
    }
    return $result
}

function Get-RepoRelativePath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BasePath,
        [Parameter(Mandatory = $true)]
        [string]$TargetPath
    )

    [System.IO.Path]::GetRelativePath($BasePath, $TargetPath).Replace("\", "/")
}

function Get-ConsumerTaskManagerPath {
    param([string]$BasePath)

    $candidate = Join-Path $BasePath "scripts/task_manager.py"
    if (-not (Test-Path -LiteralPath $candidate)) {
        throw "Expected an installed runtime at $candidate. Copy this example into a consumer repo that already has scripts/task_manager.py."
    }
    return (Resolve-Path -LiteralPath $candidate).Path
}

function Invoke-TaskManagerJson {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $taskManagerArgs = @($script:TaskManagerPath) + $Arguments
    $result = Invoke-Required -Executable "python" -Arguments $taskManagerArgs -WorkingDirectory $script:RepoRoot -FailureLabel "task_manager.py failed"
    try {
        return $result.Output | ConvertFrom-Json -Depth 100
    }
    catch {
        throw "task_manager.py did not return valid JSON for arguments: $($Arguments -join ' ')`n$($result.Output)"
    }
}

function Get-OllamaModels {
    if ($script:InstalledOllamaModels) {
        return $script:InstalledOllamaModels
    }

    try {
        $response = Invoke-RestMethod -Method Get -Uri ($script:OllamaUrl.TrimEnd("/") + "/api/tags")
        $names = @($response.models | ForEach-Object { [string]$_.name } | Where-Object { $_ })
    }
    catch {
        throw "Unable to query Ollama at $($script:OllamaUrl). Make sure the server is running and reachable. $($_.Exception.Message)"
    }

    if (-not $names) {
        throw "Ollama is reachable at $($script:OllamaUrl), but no local models are installed."
    }

    $script:InstalledOllamaModels = $names
    return $script:InstalledOllamaModels
}

function Resolve-OllamaModel {
    param([string]$Tier)

    $normalizedTier = ([string]$Tier).Trim().ToLowerInvariant()
    switch ($normalizedTier) {
        "mini" { if ($script:HaikuModel) { return $script:HaikuModel } }
        "standard" { if ($script:SonnetModel) { return $script:SonnetModel } }
        "max" { if ($script:OpusModel) { return $script:OpusModel } }
    }

    if ($script:DefaultModel) {
        return $script:DefaultModel
    }

    $models = @(Get-OllamaModels)
    $preferred = @(
        "qwen2.5-coder",
        "qwen3-coder",
        "deepseek-coder",
        "codellama",
        "starcoder"
    )

    foreach ($hint in $preferred) {
        $match = $models | Where-Object { $_ -like "*$hint*" } | Select-Object -First 1
        if ($match) {
            return $match
        }
    }

    return $models[0]
}

function Ensure-ArtifactRoot {
    $path = Join-Path $script:RepoRoot ".codex/ollama"
    New-Item -ItemType Directory -Path $path -Force | Out-Null
    return $path
}

function Ensure-AgentWorktree {
    param(
        [Parameter(Mandatory = $true)]
        [pscustomobject]$Agent
    )

    $worktreeRoot = Join-Path $script:RepoRoot ".worktrees"
    New-Item -ItemType Directory -Path $worktreeRoot -Force | Out-Null

    $leaf = "agent-{0}-{1}" -f ([string]$Agent.id).ToLowerInvariant(), ([string]$Agent.name).ToLowerInvariant()
    $branch = "agent/{0}-{1}" -f ([string]$Agent.id).ToLowerInvariant(), ([string]$Agent.name).ToLowerInvariant()
    $worktreePath = Join-Path $worktreeRoot $leaf

    if (Test-Path -LiteralPath $worktreePath) {
        $status = Invoke-Required -Executable "git" -Arguments @("-C", $worktreePath, "status", "--porcelain") -FailureLabel "Unable to inspect existing worktree"
        if ($status.Output) {
            throw "Existing worktree is dirty: $worktreePath. Clean it manually before rerunning the bridge."
        }
    }
    else {
        $branchCheck = Invoke-Required -Executable "git" -Arguments @("-C", $script:RepoRoot, "branch", "--list", $branch) -FailureLabel "Unable to inspect git branches"
        if ($branchCheck.Output) {
            Invoke-Required -Executable "git" -Arguments @("-C", $script:RepoRoot, "worktree", "add", $worktreePath, $branch) -FailureLabel "Unable to attach existing branch as worktree"
        }
        else {
            Invoke-Required -Executable "git" -Arguments @("-C", $script:RepoRoot, "worktree", "add", "-b", $branch, $worktreePath, "HEAD") -FailureLabel "Unable to create agent worktree"
        }
    }

    [pscustomobject]@{
        Path = $worktreePath
        RelativePath = Get-RepoRelativePath -BasePath $script:RepoRoot -TargetPath $worktreePath
        Branch = $branch
    }
}

function Get-ConventionsPathFromPrompt {
    param([string]$PromptText)

    $match = [regex]::Match($PromptText, "Read\s+(.+?)\s+first\s+for project conventions\.", [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
    if (-not $match.Success) {
        return ""
    }
    return $match.Groups[1].Value.Trim()
}

function Get-OwnedFilesFromSpec {
    param([string]$SpecText)

    $match = [regex]::Match($SpecText, "\*\*Output files?:\*\*\s*(.+?)(?:\r?\n|$)", [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
    if (-not $match.Success) {
        return @()
    }

    $raw = $match.Groups[1].Value.Trim()
    if (-not $raw) {
        return @()
    }

    $normalized = $raw.Trim('`').Trim()
    if ($normalized -match "^(none|\(none\)|-|no explicit files assigned\.)$") {
        return @()
    }

    @(
        $raw.Split(",") |
            ForEach-Object { $_.Trim().Trim('`') } |
            Where-Object { $_ -and $_ -notmatch "^(none|\(none\)|-)$" }
    )
}

function Get-VerificationCommandsFromSpec {
    param([string]$SpecText)

    $match = [regex]::Match(
        $SpecText,
        '## Verification\s*```(?:powershell)?\s*(.*?)```',
        [System.Text.RegularExpressions.RegexOptions]::Singleline -bor [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
    )

    if (-not $match.Success) {
        return @()
    }

    @(
        $match.Groups[1].Value -split "\r?\n" |
            ForEach-Object { $_.Trim() } |
            Where-Object { $_ -and -not $_.StartsWith("#") }
    )
}

function Get-ContextBlock {
    param(
        [string]$Title,
        [string]$Content,
        [int]$CharLimit
    )

    $body = if ($Content.Length -gt $CharLimit) {
        $Content.Substring(0, $CharLimit) + "`n`n[TRUNCATED]"
    }
    else {
        $Content
    }

    return @"
=== $Title ===
$body
"@
}

function Build-ContextBundle {
    param(
        [string]$PromptText,
        [string]$SpecText,
        [string[]]$OwnedFiles
    )

    $sections = New-Object System.Collections.Generic.List[string]

    $conventionsPath = Get-ConventionsPathFromPrompt -PromptText $PromptText
    if ($conventionsPath) {
        $absoluteConventions = Join-Path $script:RepoRoot $conventionsPath
        if (Test-Path -LiteralPath $absoluteConventions) {
            $content = Get-Content -LiteralPath $absoluteConventions -Raw
            $sections.Add((Get-ContextBlock -Title ("Conventions: " + $conventionsPath) -Content $content -CharLimit $script:MaxConventionChars))
        }
    }

    foreach ($file in $OwnedFiles) {
        $absolute = Join-Path $script:RepoRoot $file
        if (Test-Path -LiteralPath $absolute) {
            $content = Get-Content -LiteralPath $absolute -Raw
            $sections.Add((Get-ContextBlock -Title ("File: " + $file) -Content $content -CharLimit $script:MaxFileChars))
        }
        else {
            $sections.Add((Get-ContextBlock -Title ("File: " + $file) -Content "[File does not exist yet. Create it only if the scope requires it.]" -CharLimit 512))
        }
    }

    $sections.Add((Get-ContextBlock -Title "Agent Spec" -Content $SpecText -CharLimit ($script:MaxFileChars * 2)))
    return ($sections -join "`n`n")
}

function Build-OllamaPrompt {
    param(
        [pscustomobject]$Agent,
        [string]$SpecText,
        [string[]]$OwnedFiles,
        [string]$ContextBundle
    )

    $ownedList = if ($OwnedFiles) { ($OwnedFiles -join ", ") } else { "(no explicit owned files listed in the spec)" }

    @"
You are operating as a git patch generator for a task-manager agent.
You cannot edit files directly. You must return a patch that can be applied with `git apply`.

Return exactly two blocks and nothing else:

<agent_result>
{
  "id": "$(([string]$Agent.id).ToUpperInvariant())",
  "name": "$([string]$Agent.name)",
  "status": "done",
  "files_modified": ["relative/path.ext"],
  "tests_passed": 0,
  "tests_failed": 0,
  "issues": [],
  "summary": "1-2 sentence summary"
}
</agent_result>
<patch>
diff --git a/path.ext b/path.ext
...
</patch>

Rules:
- Output only those two tagged blocks.
- The patch must use repo-relative paths.
- Only touch files inside this ownership list: $ownedList
- If you cannot produce a safe patch, set `"status"` to `"failed"`, explain why in `"issues"`, and leave `<patch>` empty.
- Keep the patch minimal and preserve existing behavior outside the spec scope.

Backend launch prompt:
$([string]$Agent.prompt)

Additional project context:
$ContextBundle
"@
}

function Invoke-OllamaGenerate {
    param(
        [string]$Model,
        [string]$Prompt
    )

    $body = @{
        model = $Model
        prompt = $Prompt
        stream = $false
        options = @{
            temperature = $script:Temperature
            num_ctx = $script:NumCtx
        }
    } | ConvertTo-Json -Depth 8

    try {
        return Invoke-RestMethod -Method Post -Uri ($script:OllamaUrl.TrimEnd("/") + "/api/generate") -ContentType "application/json" -Body $body
    }
    catch {
        throw "Ollama generate call failed for model '$Model'. $($_.Exception.Message)"
    }
}

function Parse-OllamaEnvelope {
    param([string]$ResponseText)

    $resultMatch = [regex]::Match(
        $ResponseText,
        "<agent_result>\s*(.*?)\s*</agent_result>",
        [System.Text.RegularExpressions.RegexOptions]::Singleline -bor [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
    )
    $patchMatch = [regex]::Match(
        $ResponseText,
        "<patch>\s*(.*?)\s*</patch>",
        [System.Text.RegularExpressions.RegexOptions]::Singleline -bor [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
    )

    if (-not $resultMatch.Success) {
        throw "Ollama response did not include an <agent_result> block."
    }

    $agentResultText = $resultMatch.Groups[1].Value.Trim()
    try {
        $agentResult = $agentResultText | ConvertFrom-Json -Depth 16
    }
    catch {
        throw "Ollama <agent_result> block was not valid JSON.`n$agentResultText"
    }

    [pscustomobject]@{
        AgentResult = $agentResult
        Patch = if ($patchMatch.Success) { $patchMatch.Groups[1].Value.Trim() } else { "" }
    }
}

function Invoke-Verification {
    param(
        [string]$WorktreePath,
        [string[]]$Commands,
        [string]$LogPrefix
    )

    if ($script:SkipVerification -or -not $Commands) {
        return [pscustomobject]@{
            TestsPassed = 0
            TestsFailed = 0
            Issues = @()
        }
    }

    $issues = New-Object System.Collections.Generic.List[string]
    $shellCommand = Get-Command pwsh -ErrorAction SilentlyContinue
    if (-not $shellCommand) {
        $shellCommand = Get-Command powershell -ErrorAction SilentlyContinue
    }
    if (-not $shellCommand) {
        throw "Neither 'pwsh' nor 'powershell' is available to run verification commands."
    }

    $passed = 0
    $failed = 0
    $escapedWorktree = $WorktreePath.Replace("'", "''")

    for ($index = 0; $index -lt $Commands.Count; $index++) {
        $commandText = $Commands[$index]
        $fullCommand = "Set-Location -LiteralPath '$escapedWorktree'; $commandText"
        $result = Invoke-External -Executable $shellCommand.Source -Arguments @("-NoProfile", "-Command", $fullCommand) -WorkingDirectory $script:RepoRoot

        $logPath = "{0}-{1:00}.log" -f $LogPrefix, ($index + 1)
        Write-Utf8File -Path $logPath -Content $result.Output

        if ($result.ExitCode -eq 0) {
            $passed += 1
        }
        else {
            $failed += 1
            $issues.Add("Verification failed: $commandText")
        }
    }

    [pscustomobject]@{
        TestsPassed = $passed
        TestsFailed = $failed
        Issues = @($issues)
    }
}

function Get-ChangedFiles {
    param([string]$WorktreePath)

    $result = Invoke-Required -Executable "git" -Arguments @("-C", $WorktreePath, "diff", "--name-only") -FailureLabel "Unable to inspect git diff after patch apply"
    if (-not $result.Output) {
        return @()
    }

    @(
        $result.Output -split "\r?\n" |
            ForEach-Object { $_.Trim().Replace("\", "/") } |
            Where-Object { $_ }
    )
}

function Apply-AgentPatch {
    param(
        [string]$WorktreePath,
        [string]$PatchText,
        [string]$PatchPath
    )

    if (-not $PatchText) {
        return [pscustomobject]@{
            Applied = $false
            Error = "Model returned an empty patch."
        }
    }

    $normalized = $PatchText -replace "`r`n", "`n"
    Write-Utf8File -Path $PatchPath -Content $normalized

    $result = Invoke-External -Executable "git" -Arguments @("-C", $WorktreePath, "apply", "--whitespace=nowarn", "--recount", $PatchPath) -WorkingDirectory $script:RepoRoot
    if ($result.ExitCode -ne 0) {
        return [pscustomobject]@{
            Applied = $false
            Error = if ($result.Output) { $result.Output } else { "git apply failed." }
        }
    }

    [pscustomobject]@{
        Applied = $true
        Error = ""
    }
}

function Merge-Issues {
    param(
        [object[]]$Values
    )

    @(
        $Values |
            ForEach-Object {
                if ($_ -is [System.Collections.IEnumerable] -and -not ($_ -is [string])) {
                    $_
                }
                else {
                    @($_)
                }
            } |
            ForEach-Object { $_ } |
            ForEach-Object { [string]$_ } |
            Where-Object { $_ } |
            Select-Object -Unique
    )
}

function Process-Agent {
    param(
        [pscustomobject]$Agent,
        [string]$ArtifactRoot
    )

    $agentId = ([string]$Agent.id).ToLowerInvariant()
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $agentPrefix = Join-Path $ArtifactRoot ("agent-{0}-{1}" -f $agentId, $stamp)

    Write-Host ("Launching agent {0} ({1})" -f $agentId.ToUpperInvariant(), [string]$Agent.name)

    $worktree = Ensure-AgentWorktree -Agent $Agent
    Invoke-TaskManagerJson -Arguments @("attach", $agentId, "--worktree-path", $worktree.RelativePath, "--branch", $worktree.Branch, "--json") | Out-Null

    $specPath = Join-Path $script:RepoRoot ([string]$Agent.spec_file)
    if (-not (Test-Path -LiteralPath $specPath)) {
        throw "Spec file not found for agent ${agentId}: $specPath"
    }

    $specText = Get-Content -LiteralPath $specPath -Raw
    $ownedFiles = @(Get-OwnedFilesFromSpec -SpecText $specText)
    $verificationCommands = @(Get-VerificationCommandsFromSpec -SpecText $specText)
    $contextBundle = Build-ContextBundle -PromptText ([string]$Agent.prompt) -SpecText $specText -OwnedFiles $ownedFiles

    $tier = [string]$Agent.model
    $resolvedModel = Resolve-OllamaModel -Tier $tier
    $prompt = Build-OllamaPrompt -Agent $Agent -SpecText $specText -OwnedFiles $ownedFiles -ContextBundle $contextBundle

    Write-Host ("  model: {0} (tier {1})" -f $resolvedModel, $tier)

    $ollamaResponse = Invoke-OllamaGenerate -Model $resolvedModel -Prompt $prompt
    $responseText = [string]$ollamaResponse.response
    Write-Utf8File -Path ($agentPrefix + "-response.txt") -Content $responseText

    $parsed = Parse-OllamaEnvelope -ResponseText $responseText
    $patchPath = $agentPrefix + ".patch"
    $applyResult = Apply-AgentPatch -WorktreePath $worktree.Path -PatchText ([string]$parsed.Patch) -PatchPath $patchPath

    $verificationPrefix = $agentPrefix + "-verify"
    $changedFiles = @()
    if ($applyResult.Applied) {
        $verification = Invoke-Verification -WorktreePath $worktree.Path -Commands $verificationCommands -LogPrefix $verificationPrefix
        $changedFiles = @(Get-ChangedFiles -WorktreePath $worktree.Path)
    }
    else {
        $verification = [pscustomobject]@{
            TestsPassed = 0
            TestsFailed = 0
            Issues = @()
        }
    }

    $reportedIssues = @()
    if ($parsed.AgentResult.PSObject.Properties.Name -contains "issues") {
        $reportedIssues = @($parsed.AgentResult.issues)
    }

    $issues = Merge-Issues -Values @(
        $reportedIssues,
        $verification.Issues,
        $(if (-not $applyResult.Applied) { @($applyResult.Error) } else { @() }),
        $(if ($applyResult.Applied -and -not $changedFiles) { @("No files changed after applying the Ollama patch.") } else { @() })
    )

    $status = "done"
    if ($issues) {
        $status = "failed"
    }
    if ($parsed.AgentResult.PSObject.Properties.Name -contains "status") {
        $reportedStatus = ([string]$parsed.AgentResult.status).Trim().ToLowerInvariant()
        if ($reportedStatus -eq "failed") {
            $status = "failed"
        }
    }

    $summary = if ($parsed.AgentResult.PSObject.Properties.Name -contains "summary" -and [string]$parsed.AgentResult.summary) {
        [string]$parsed.AgentResult.summary
    }
    elseif ($status -eq "done") {
        "Applied Ollama-generated patch for agent $($agentId.ToUpperInvariant())."
    }
    else {
        "Ollama bridge could not complete agent $($agentId.ToUpperInvariant())."
    }

    $payload = @{
        id = $agentId
        name = [string]$Agent.name
        status = $status
        files_modified = $changedFiles
        tests_passed = [int]$verification.TestsPassed
        tests_failed = [int]$verification.TestsFailed
        issues = $issues
        summary = $summary
        worktree_path = $worktree.RelativePath
        branch = $worktree.Branch
    }

    $payloadPath = $agentPrefix + "-result.json"
    Write-Utf8File -Path $payloadPath -Content ($payload | ConvertTo-Json -Depth 16)

    $recorded = Invoke-TaskManagerJson -Arguments @("result", $agentId, "--payload-file", $payloadPath, "--json")
    Write-Host ("  recorded status: {0}" -f ([string]$recorded.status))
}

$script:RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
$script:TaskManagerPath = Get-ConsumerTaskManagerPath -BasePath $script:RepoRoot
$script:OllamaUrl = $OllamaUrl
$script:LaunchMode = $LaunchMode
$script:DefaultModel = $DefaultModel
$script:HaikuModel = $HaikuModel
$script:SonnetModel = $SonnetModel
$script:OpusModel = $OpusModel
$script:Temperature = $Temperature
$script:NumCtx = $NumCtx
$script:MaxConventionChars = $MaxConventionChars
$script:MaxFileChars = $MaxFileChars
$script:InstalledOllamaModels = @()

$artifactRoot = Ensure-ArtifactRoot

if ($script:LaunchMode -eq "campaign") {
    for ($iteration = 1; $iteration -le $MaxIterations; $iteration++) {
        $goArgs = @("go")
        if ($PlanId) {
            $goArgs += $PlanId
        }
        $goArgs += "--json"

        $payload = Invoke-TaskManagerJson -Arguments $goArgs
        $status = [string]$payload.status

        Write-Host ("Lifecycle status: {0}" -f $status)

        if ($status -eq "awaiting_results") {
            $agents = @()
            if ($payload.PSObject.Properties.Name -contains "launch" -and $payload.launch -and $payload.launch.PSObject.Properties.Name -contains "agents") {
                $agents = @($payload.launch.agents)
            }

            if (-not $agents) {
                $running = @()
                if ($payload.PSObject.Properties.Name -contains "running_agents") {
                    $running = @($payload.running_agents)
                }
                if ($running) {
                    throw "Backend reports running agents but no new launch payloads. Resolve or recover those worktrees before rerunning."
                }
                throw "Backend reported awaiting_results without any launchable agents."
            }

            foreach ($agent in $agents) {
                Process-Agent -Agent $agent -ArtifactRoot $artifactRoot
            }
            continue
        }

        if ($status -eq "blocked") {
            Write-Warning "Lifecycle is blocked. Inspect failed or blocked agents in task_manager status."
            break
        }

        if ($status -in @("verified", "verification_failed", "merge_conflicts")) {
            Write-Host ("Lifecycle finished with status: {0}" -f $status)
            break
        }

        Write-Host "No launch payload returned. Exiting."
        break
    }
}
else {
    for ($iteration = 1; $iteration -le $MaxIterations; $iteration++) {
        $launch = Invoke-TaskManagerJson -Arguments @("run", "ready", "--json")
        $agents = @()
        if ($launch.PSObject.Properties.Name -contains "agents") {
            $agents = @($launch.agents)
        }

        if ($agents) {
            Write-Host ("Launching {0} ready agent(s) from existing task state." -f $agents.Count)
            foreach ($agent in $agents) {
                Process-Agent -Agent $agent -ArtifactRoot $artifactRoot
            }
            continue
        }

        $statusPayload = Invoke-TaskManagerJson -Arguments @("status", "--json")
        $counts = $statusPayload.counts
        $readyCount = [int]$counts.ready
        $runningCount = [int]$counts.running
        $doneCount = [int]$counts.done
        $failedCount = [int]$counts.failed
        $blockedCount = [int]$counts.blocked
        $pendingCount = [int]$counts.pending

        Write-Host (
            "Task status: ready={0} running={1} done={2} failed={3} blocked={4} pending={5}" -f
            $readyCount, $runningCount, $doneCount, $failedCount, $blockedCount, $pendingCount
        )

        if ($runningCount -gt 0) {
            throw "Backend still shows running tasks. Resolve or recover them before rerunning the bridge."
        }

        if ($readyCount -gt 0) {
            $skippedSummary = ""
            if ($launch.PSObject.Properties.Name -contains "skipped") {
                $skippedEntries = @($launch.skipped | ForEach-Object { "{0}:{1}" -f ([string]$_.id), ([string]$_.reason) })
                if ($skippedEntries) {
                    $skippedSummary = " Skipped: " + ($skippedEntries -join ", ")
                }
            }
            throw ("Ready tasks exist but `run ready` returned no launchable agents." + $skippedSummary)
        }

        if ($blockedCount -gt 0 -or $pendingCount -gt 0) {
            Write-Warning "No more ready tasks. Remaining blocked or pending tasks need manual review."
            break
        }

        if ($doneCount -eq 0 -and $failedCount -eq 0) {
            Write-Host "No task state requires work."
            break
        }

        break
    }

    if (-not $SkipMerge) {
        $mergePayload = Invoke-TaskManagerJson -Arguments @("merge", "--json")
        $mergedCount = @($mergePayload.merged).Count
        $conflictCount = @($mergePayload.conflicts).Count
        $skippedCount = @($mergePayload.skipped).Count
        Write-Host ("Merge summary: merged={0} conflicts={1} skipped={2}" -f $mergedCount, $conflictCount, $skippedCount)
    }
    else {
        Write-Host "Skipping merge because -SkipMerge was provided."
    }

    if ($PlanId) {
        $verifyPayload = Invoke-TaskManagerJson -Arguments @("verify", $PlanId, "--json")
        Write-Host ("Verify status: {0}" -f ([string]$verifyPayload.status))
    }
    else {
        Write-Host "Skipping lifecycle verify because no -PlanId was provided."
    }
}
