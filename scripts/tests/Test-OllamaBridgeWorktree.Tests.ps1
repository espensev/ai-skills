#Requires -Version 7.0
$ErrorActionPreference = 'Stop'
$repoSource = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$bridge = Join-Path $repoSource 'codex-skills/examples/ollama-bridge.ps1'
$tokens = $null; $parseErrors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile($bridge, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count) { throw 'Bridge failed to parse.' }
foreach ($name in @('Invoke-External', 'Invoke-Required', 'Get-RepoRelativePath', 'Ensure-AgentWorktree')) {
    $definition = $ast.FindAll({ param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] }, $true) | Where-Object Name -eq $name
    . ([scriptblock]::Create($definition.Extent.Text))
}
$tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$sandbox = Join-Path $tempRoot ('ai-skills-worktree-placement-' + [guid]::NewGuid().ToString('N'))
$savedCodeRoot = $env:MACHINE_CODE_ROOT
try {
    $script:RepoRoot = Join-Path $sandbox 'project'
    $script:WorktreeBaseRoot = ''
    $env:MACHINE_CODE_ROOT = $sandbox
    New-Item -ItemType Directory -Path $script:RepoRoot -Force | Out-Null
    & git -C $script:RepoRoot init -b main | Out-Null
    & git -C $script:RepoRoot config user.name Test
    & git -C $script:RepoRoot config user.email test@example.invalid
    Set-Content -LiteralPath (Join-Path $script:RepoRoot 'file.txt') -Value 'content'
    & git -C $script:RepoRoot add file.txt
    & git -C $script:RepoRoot commit -m fixture | Out-Null
    if ($LASTEXITCODE) { throw 'Fixture creation failed.' }
    $agent = [pscustomobject]@{ id = 'a'; name = 'example' }
    $lane = Ensure-AgentWorktree -Agent $agent
    $expected = Join-Path $sandbox 'DevHome/worktrees/project/agent-a-example'
    if ($lane.Path -ne $expected -or -not (Test-Path (Join-Path $expected 'file.txt'))) { throw 'Creation escaped the central project namespace.' }
    if (Test-Path (Join-Path $script:RepoRoot '.worktrees')) { throw 'Project-local worktrees were created.' }
    $mainRepo = $script:RepoRoot
    $script:RepoRoot = $lane.Path
    if ((Ensure-AgentWorktree -Agent $agent).Path -ne $expected) { throw 'Linked invocation changed the project namespace.' }
    $script:RepoRoot = $mainRepo
    & git -C $mainRepo worktree remove $lane.Path
    if ($LASTEXITCODE) { throw 'Fixture lane removal failed.' }
    if ((Ensure-AgentWorktree -Agent $agent).Path -ne $expected) { throw 'Existing branch reattachment escaped the central namespace.' }
    Write-Output 'PASS: Ollama bridge central creation, linked invocation and branch reattachment'
}
finally {
    $env:MACHINE_CODE_ROOT = $savedCodeRoot
    $full = [IO.Path]::GetFullPath($sandbox)
    if (-not $full.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase) -or
        [IO.Path]::GetFileName($full) -notlike 'ai-skills-worktree-placement-*') { throw 'Unsafe fixture cleanup path.' }
    Remove-Item -LiteralPath $full -Recurse -Force -ErrorAction SilentlyContinue
}
