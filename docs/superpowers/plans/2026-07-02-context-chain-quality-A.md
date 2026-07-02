# Context-Chain Quality (Plan A: private-infra side) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a fresh Claude session boot with correct, self-maintaining shared context by fixing the live machine-naming drift and making the shared CLAUDE.md's volatile facts generated + drift-checkable.

**Architecture:** Non-generated surfaces (machine-tier CLAUDE.md, auto-memory) are hand-fixed once. The shared-tier CLAUDE.md gets three marker-delimited blocks rendered by a new idempotent PowerShell generator from the declared sources of truth (`machines.json`, the Ai-Skills repo). The generator's `-CheckOnly` flag is the drift-check primitive, wired into a docs-sync surface config and the qa cadence.

**Tech Stack:** PowerShell 7+ (pwsh), Pester 5.8 for tests, JSON sources (`machines.json`, `install-manifest.json`).

## Global Constraints

- Target shell is PowerShell 7+ (pwsh). Scripts must be idempotent — safe to re-run at any time.
- `machines.json` (`C:\Users\Sev\OneDrive\common\common_dev\machines.json`) is the single source of truth for machine facts (name, alias, endpoint, user, role).
- Canonical machine identifiers come from `machines.json`: machine=`SND-DESK`, alias=`maindesk`. The literal token `MAINDESK` is invalid and must not appear anywhere.
- Files under `C:\Users\Sev\OneDrive\common\common_dev\` and `D:\DevHome\state\claude\` are **not** git repositories. There are no `git commit` steps in this plan; a task's deliverable is durable once the file is saved (OneDrive/local disk). Each task ends with a **Checkpoint** (a verification command) instead of a commit.
- The generator only ever *reads* `D:\Development\Ai-Skills` (the repo is read-only for Claude). It must degrade gracefully when that path is absent (non-SND-DESK machines).
- File writes use UTF-8 without BOM (`-Encoding utf8` in pwsh) and preserve the target file's existing newline style.
- This plan does not touch the Ai-Skills git repo. Repo-side work (agents pipeline) is Plan B.

---

## File Structure

| Path | Responsibility | Change |
|---|---|---|
| `D:\DevHome\state\claude\CLAUDE.md` | Machine-tier identity | Modify (fix machine name) |
| `C:\Users\Sev\.claude\projects\D--Development-Ai-Skills\memory\ai-skills-devhome-vs-development.md` | Auto-memory | Modify (MAINDESK→SND-DESK) |
| `C:\Users\Sev\.claude\projects\D--Development-Ai-Skills\memory\ai-skills-share-topology.md` | Auto-memory | Modify (MAINDESK→SND-DESK) |
| `C:\Users\Sev\OneDrive\common\common_dev\machines.json` | Machine source of truth | Modify (add `role` field) |
| `C:\Users\Sev\OneDrive\common\common_dev\CLAUDE.md` | Shared-tier context | Modify (wrap 3 regions in markers; regenerated) |
| `C:\Users\Sev\OneDrive\common\common_dev\Update-SharedContext.ps1` | The generator + `-CheckOnly` drift primitive | Create |
| `C:\Users\Sev\OneDrive\common\common_dev\Update-SharedContext.Tests.ps1` | Pester tests for the generator | Create |
| `C:\Users\Sev\OneDrive\common\common_dev\.claude\skills\project.toml` | docs-sync surface config for the context chain | Create |

---

## Phase 1 — Fix the live drift (non-generated surfaces)

### Task 1: Correct the machine-tier CLAUDE.md identity

**Files:**
- Modify: `D:\DevHome\state\claude\CLAUDE.md`

**Interfaces:**
- Consumes: nothing.
- Produces: a machine-tier file whose `**Machine**:` value equals the `machine` field for this host in `machines.json` (`SND-DESK`).

- [ ] **Step 1: Verify the current wrong value is present**

Run:
```bash
grep -n 'MAINDESK' 'D:\DevHome\state\claude\CLAUDE.md'
```
Expected: one hit — `- **Machine**: MAINDESK`.

- [ ] **Step 2: Fix the machine name**

Replace the line
```markdown
- **Machine**: MAINDESK
```
with
```markdown
- **Machine**: SND-DESK
```
(Leave `- **SSH alias**: maindesk` unchanged — it already matches `machines.json`.)

- [ ] **Step 3: Checkpoint — assert the token is gone and the source-of-truth name is present**

Run:
```bash
grep -c 'MAINDESK' 'D:\DevHome\state\claude\CLAUDE.md'; grep -n 'Machine.*SND-DESK' 'D:\DevHome\state\claude\CLAUDE.md'
```
Expected: count `0`, then a line showing `**Machine**: SND-DESK`.

---

### Task 2: Correct the auto-memory files

**Files:**
- Modify: `C:\Users\Sev\.claude\projects\D--Development-Ai-Skills\memory\ai-skills-devhome-vs-development.md`
- Modify: `C:\Users\Sev\.claude\projects\D--Development-Ai-Skills\memory\ai-skills-share-topology.md`

**Interfaces:**
- Consumes: nothing.
- Produces: memory bodies that name the machine as `SND-DESK`, so recalled memories stop reinforcing the wrong name.

- [ ] **Step 1: Locate the occurrences**

Run:
```bash
grep -n 'MAINDESK' 'C:\Users\Sev\.claude\projects\D--Development-Ai-Skills\memory\ai-skills-devhome-vs-development.md' 'C:\Users\Sev\.claude\projects\D--Development-Ai-Skills\memory\ai-skills-share-topology.md'
```
Expected: `on MAINDESK` in each file (prose, not frontmatter).

- [ ] **Step 2: Replace each `MAINDESK` with `SND-DESK`**

In both files, change the phrase `on MAINDESK` to `on SND-DESK`. Do not alter frontmatter, `name:`, or `originSessionId`. Preserve all other text.

- [ ] **Step 3: Checkpoint — no MAINDESK remains in the memory store**

Run:
```bash
grep -rc 'MAINDESK' 'C:\Users\Sev\.claude\projects\D--Development-Ai-Skills\memory\' | grep -v ':0' || echo 'clean'
```
Expected: `clean`.

---

## Phase 2 — Generate the shared-tier volatile facts

### Task 3: Add the `role` field to machines.json

**Files:**
- Modify: `C:\Users\Sev\OneDrive\common\common_dev\machines.json`

**Interfaces:**
- Consumes: nothing.
- Produces: each machine object gains a string `role`, so the generator can source the Role column instead of hand-gluing it. Values: `SND-DESK`→`Primary workstation`, `SND-HOST`→`Secondary workstation`, `REMOTE`→`Remote`.

- [ ] **Step 1: Add `role` to each of the three machine objects**

For the `SND-DESK` object add `"role": "Primary workstation",`; for `SND-HOST` add `"role": "Secondary workstation",`; for `REMOTE` add `"role": "Remote",`. Place the key adjacent to `displayName`. Preserve every existing field (tunnelId, extraIngress, lastBootstrap, etc.).

- [ ] **Step 2: Checkpoint — JSON is valid and roles are present**

Run:
```bash
pwsh -NoProfile -Command "\$m = Get-Content -Raw 'C:\Users\Sev\OneDrive\common\common_dev\machines.json' | ConvertFrom-Json; \$m | ForEach-Object { \$_.machine + ' => ' + \$_.role }"
```
Expected:
```
SND-DESK => Primary workstation
SND-HOST => Secondary workstation
REMOTE => Remote
```

---

### Task 4: Wrap the three regenerable regions of the shared CLAUDE.md in markers

**Files:**
- Modify: `C:\Users\Sev\OneDrive\common\common_dev\CLAUDE.md`

**Interfaces:**
- Consumes: nothing.
- Produces: the shared CLAUDE.md now contains three marker pairs with names `machines`, `provider-targets`, `shared-set-count`. The generator (Task 6) fills them; this task only inserts the boundaries around the existing content.

- [ ] **Step 1: Wrap the machine table + Connect line**

Find the existing block (currently in the `## Machines` section):
```markdown
| Machine | Alias | Endpoint | User | Role |
|---------|-------|----------|------|------|
| SND-DESK | SND-DESK | ssh.seviq.org | Sev | Primary workstation |
| SND-HOST | host | ssh2.seviq.org | Dev | Secondary workstation |
| REMOTE | remote | ssh-remote.seviq.org | Espen | Remote |

Connect: `ssh SND-DESK`, `ssh host`, `ssh remote`
```
Wrap it exactly as:
```markdown
<!-- BEGIN GENERATED: machines (source: machines.json; regen: Update-SharedContext.ps1) -->
| Machine | Alias | Endpoint | User | Role |
|---------|-------|----------|------|------|
| SND-DESK | SND-DESK | ssh.seviq.org | Sev | Primary workstation |
| SND-HOST | host | ssh2.seviq.org | Dev | Secondary workstation |
| REMOTE | remote | ssh-remote.seviq.org | Espen | Remote |

Connect: `ssh SND-DESK`, `ssh host`, `ssh remote`
<!-- END GENERATED: machines -->
```
(The wrong alias/connect values stay for now; Task 6 regenerates them correctly.)

- [ ] **Step 2: Wrap the provider-targets list**

Find the four-line provider list under `## AI Skills Repo` (`- \`claude-skills/\` — …` through the `gemini-skills/` line) and wrap it:
```markdown
<!-- BEGIN GENERATED: provider-targets (source: Ai-Skills release-manifest.json + package manifests; regen: Update-SharedContext.ps1) -->
- `claude-skills/` — 20 install-ready skills for Claude Code (24 in source)
- `codex-skills/` — 32 install-ready skills for OpenAI Codex (33 in source)
- `antigravity-skills/` — 29 adapter skills + workflows for Google Antigravity
- `gemini-skills/` — legacy Gemini CLI adapter, source-only (not exported by default)
<!-- END GENERATED: provider-targets -->
```

- [ ] **Step 3: Wrap the shared-set count sentence**

In the `## Shared Skills` section, find the sentence stating the shared set holds "40+ skills" and replace that sentence with a marker pair holding a single generated sentence:
```markdown
<!-- BEGIN GENERATED: shared-set-count (source: OneDrive .claude/skills dir count; regen: Update-SharedContext.ps1) -->
The shared set holds **40+ skills** in total.
<!-- END GENERATED: shared-set-count -->
```

- [ ] **Step 4: Checkpoint — exactly three balanced marker pairs exist**

Run:
```bash
pwsh -NoProfile -Command "\$t = Get-Content -Raw 'C:\Users\Sev\OneDrive\common\common_dev\CLAUDE.md'; 'BEGIN=' + ([regex]::Matches(\$t,'BEGIN GENERATED:')).Count + ' END=' + ([regex]::Matches(\$t,'END GENERATED:')).Count"
```
Expected: `BEGIN=3 END=3`.

---

### Task 5: Write the failing Pester tests for the generator

**Files:**
- Create: `C:\Users\Sev\OneDrive\common\common_dev\Update-SharedContext.Tests.ps1`

**Interfaces:**
- Consumes (from Task 6): `Update-SharedContext.ps1`, invoked with `-ContextFile`, `-MachinesFile`, `-RepoRoot`, `-SkillsDir`, `-CheckOnly`. On drift in `-CheckOnly` mode it exits non-zero; otherwise it rewrites the marker blocks in `-ContextFile` in place and is idempotent. Malformed markers cause a terminating error.
- Produces: the test suite that gates Task 6.

- [ ] **Step 1: Write the test file**

```powershell
# Update-SharedContext.Tests.ps1 — Pester 5 tests for the shared-context generator.
BeforeAll {
    $script:Gen = Join-Path $PSScriptRoot 'Update-SharedContext.ps1'

    function New-Fixture {
        # Builds an isolated temp workspace: a CLAUDE.md with 3 marker pairs,
        # a machines.json, a fake shared-skills dir, and a fake repo.
        $root = Join-Path ([System.IO.Path]::GetTempPath()) ("usc-" + [guid]::NewGuid().ToString("N"))
        New-Item -ItemType Directory -Path $root -Force | Out-Null

        $machines = @(
            [ordered]@{ machine='SND-DESK'; alias='maindesk'; hostname='ssh.seviq.org'; user='Sev';   role='Primary workstation' }
            [ordered]@{ machine='HOST';     alias='host';     hostname='ssh2.seviq.org'; user='Dev';   role='Secondary workstation' }
        )
        ($machines | ConvertTo-Json -Depth 5) | Set-Content -LiteralPath (Join-Path $root 'machines.json') -Encoding utf8

        # Fake shared-skills dir with 3 skill subdirs.
        $skills = Join-Path $root 'skills'
        1..3 | ForEach-Object { New-Item -ItemType Directory -Path (Join-Path $skills "skill$_") -Force | Out-Null }

        # Fake repo: claude-skills/skills (2 dirs) + package manifest (default 1 + optional 1 = 2 ready).
        $repo = Join-Path $root 'repo'
        1..2 | ForEach-Object { New-Item -ItemType Directory -Path (Join-Path $repo "claude-skills\skills\c$_") -Force | Out-Null }
        1..4 | ForEach-Object { New-Item -ItemType Directory -Path (Join-Path $repo "codex-skills\skills\x$_") -Force | Out-Null }
        1..5 | ForEach-Object { New-Item -ItemType Directory -Path (Join-Path $repo "antigravity-skills\skills\a$_") -Force | Out-Null }
        New-Item -ItemType Directory -Path (Join-Path $repo 'claude-skills\package') -Force | Out-Null
        (@{ default_skills=@('c1'); optional_skills=@('c2') } | ConvertTo-Json) | Set-Content -LiteralPath (Join-Path $repo 'claude-skills\package\install-manifest.json') -Encoding utf8
        New-Item -ItemType Directory -Path (Join-Path $repo 'codex-skills\package') -Force | Out-Null
        (@{ default_skills=@('x1','x2'); optional_skills=@('x3') } | ConvertTo-Json) | Set-Content -LiteralPath (Join-Path $repo 'codex-skills\package\install-manifest.json') -Encoding utf8

        $md = @'
# Ctx
<!-- BEGIN GENERATED: machines (source: machines.json; regen: Update-SharedContext.ps1) -->
STALE
<!-- END GENERATED: machines -->

<!-- BEGIN GENERATED: provider-targets (source: x; regen: Update-SharedContext.ps1) -->
STALE
<!-- END GENERATED: provider-targets -->

<!-- BEGIN GENERATED: shared-set-count (source: x; regen: Update-SharedContext.ps1) -->
STALE
<!-- END GENERATED: shared-set-count -->
'@
        Set-Content -LiteralPath (Join-Path $root 'CLAUDE.md') -Value $md -Encoding utf8

        return [pscustomobject]@{
            Root = $root
            Ctx  = Join-Path $root 'CLAUDE.md'
            Mach = Join-Path $root 'machines.json'
            Repo = $repo
            Skills = $skills
        }
    }

    function Invoke-Gen {
        param($Fx, [switch]$CheckOnly)
        $p = @{
            ContextFile  = $Fx.Ctx
            MachinesFile = $Fx.Mach
            RepoRoot     = $Fx.Repo
            SkillsDir    = $Fx.Skills
        }
        if ($CheckOnly) { $p['CheckOnly'] = $true }
        & pwsh -NoProfile -File $script:Gen @p 2>&1 | Out-Null
        return $LASTEXITCODE
    }
}

Describe 'Update-SharedContext' {
    It 'renders the machines block from machines.json' {
        $fx = New-Fixture
        Invoke-Gen -Fx $fx | Should -Be 0
        $out = Get-Content -Raw $fx.Ctx
        $out | Should -Match '\| SND-DESK \| maindesk \| ssh\.seviq\.org \| Sev \| Primary workstation \|'
        $out | Should -Match 'Connect: `ssh maindesk`, `ssh host`'
        $out | Should -Not -Match 'STALE'
    }

    It 'renders provider counts from the fake repo' {
        $fx = New-Fixture
        Invoke-Gen -Fx $fx | Should -Be 0
        $out = Get-Content -Raw $fx.Ctx
        $out | Should -Match 'claude-skills/` — 2 install-ready skills for Claude Code \(2 in source\)'
        $out | Should -Match 'codex-skills/` — 3 install-ready skills for OpenAI Codex \(4 in source\)'
        $out | Should -Match 'antigravity-skills/` — 5 adapter skills'
    }

    It 'renders the shared-set count (no volatile date)' {
        $fx = New-Fixture
        Invoke-Gen -Fx $fx | Should -Be 0
        (Get-Content -Raw $fx.Ctx) | Should -Match 'The shared set holds \*\*3 skills\*\*'
    }

    It 'is idempotent — a second run makes no change' {
        $fx = New-Fixture
        Invoke-Gen -Fx $fx | Should -Be 0
        $first = Get-Content -Raw $fx.Ctx
        Invoke-Gen -Fx $fx | Should -Be 0
        (Get-Content -Raw $fx.Ctx) | Should -BeExactly $first
    }

    It 'CheckOnly returns 1 on stale input and 0 once regenerated' {
        $fx = New-Fixture
        (Invoke-Gen -Fx $fx -CheckOnly) | Should -Be 1
        Invoke-Gen -Fx $fx | Should -Be 0
        (Invoke-Gen -Fx $fx -CheckOnly) | Should -Be 0
    }

    It 'skips provider-targets (no throw) when the repo is absent' {
        $fx = New-Fixture
        $fx.Repo = Join-Path $fx.Root 'no-such-repo'
        Invoke-Gen -Fx $fx | Should -Be 0
        (Get-Content -Raw $fx.Ctx) | Should -Match 'The shared set holds \*\*3 skills\*\*'
    }

    It 'throws on an unbalanced marker pair' {
        $fx = New-Fixture
        $broken = (Get-Content -Raw $fx.Ctx) -replace '<!-- END GENERATED: machines -->', ''
        Set-Content -LiteralPath $fx.Ctx -Value $broken -Encoding utf8
        (Invoke-Gen -Fx $fx) | Should -Not -Be 0
    }
}
```

- [ ] **Step 2: Run the tests to confirm they fail (generator does not exist yet)**

Run:
```bash
pwsh -NoProfile -Command "Invoke-Pester -Path 'C:\Users\Sev\OneDrive\common\common_dev\Update-SharedContext.Tests.ps1' -Output Detailed"
```
Expected: failures — the run errors because `Update-SharedContext.ps1` is missing (every `Invoke-Gen` returns a non-zero/`$null` exit code, so assertions fail). This confirms the harness runs and the tests are red.

---

### Task 6: Implement the generator

**Files:**
- Create: `C:\Users\Sev\OneDrive\common\common_dev\Update-SharedContext.ps1`

**Interfaces:**
- Consumes: `machines.json`, the Ai-Skills repo package manifests + skill dirs, the shared-skills dir.
- Produces: `Update-SharedContext.ps1` with the parameter and behavior contract asserted in Task 5. Later consumed by Task 7 (`-CheckOnly`).

- [ ] **Step 1: Write the generator**

```powershell
#───────────────────────────────────────────────────────────────
#  Update-SharedContext.ps1 — regenerate marker-delimited blocks
#  in the shared CLAUDE.md from declared sources of truth.
#  Idempotent. -CheckOnly reports drift (exit 1) without writing.
#───────────────────────────────────────────────────────────────
[CmdletBinding()]
param(
    [switch]$CheckOnly,
    [string]$ContextFile  = (Join-Path $PSScriptRoot 'CLAUDE.md'),
    [string]$MachinesFile = (Join-Path $PSScriptRoot 'machines.json'),
    [string]$RepoRoot     = 'D:\Development\Ai-Skills',
    [string]$SkillsDir    = (Join-Path $PSScriptRoot '.claude\skills')
)
$ErrorActionPreference = 'Stop'

function Set-Block {
    param([string]$Text, [string]$Name, [string]$Inner, [string]$Newline)
    $begin = [regex]::Escape("BEGIN GENERATED: $Name")
    $end   = [regex]::Escape("END GENERATED: $Name")
    $pattern = "(?s)(<!-- $begin[^>]*-->)(.*?)(<!-- $end -->)"
    $matches = [regex]::Matches($Text, $pattern)
    if ($matches.Count -ne 1) {
        throw "Expected exactly one '$Name' block, found $($matches.Count). Refusing to write."
    }
    $replacement = '${1}' + $Newline + $Inner + $Newline + '${3}'
    return [regex]::Replace($Text, $pattern, $replacement)
}

function Count-Dirs {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return 0 }
    return @(Get-ChildItem -LiteralPath $Path -Directory -ErrorAction SilentlyContinue).Count
}

function Get-ReadyCount {
    param([string]$ManifestPath)
    if (-not (Test-Path $ManifestPath)) { return 0 }
    $m = Get-Content -Raw $ManifestPath | ConvertFrom-Json
    return (@($m.default_skills).Count + @($m.optional_skills).Count)
}

if (-not (Test-Path $ContextFile))  { throw "Context file not found: $ContextFile" }
if (-not (Test-Path $MachinesFile)) { throw "Machines file not found: $MachinesFile" }

$orig = Get-Content -Raw $ContextFile
$nl   = if ($orig -match "`r`n") { "`r`n" } else { "`n" }
$new  = $orig

# ── machines block ────────────────────────────────────────────
$machines = Get-Content -Raw $MachinesFile | ConvertFrom-Json
$rows = foreach ($x in $machines) {
    "| $($x.machine) | $($x.alias) | $($x.hostname) | $($x.user) | $($x.role) |"
}
$connect = 'Connect: ' + (($machines | ForEach-Object { "``ssh $($_.alias)``" }) -join ', ')
$machinesInner = @(
    '| Machine | Alias | Endpoint | User | Role |'
    '|---------|-------|----------|------|------|'
    $rows
    ''
    $connect
) -join $nl
$new = Set-Block -Text $new -Name 'machines' -Inner $machinesInner -Newline $nl

# ── provider-targets block (repo required; skip if absent) ────
if (Test-Path $RepoRoot) {
    $cReady = Get-ReadyCount (Join-Path $RepoRoot 'claude-skills\package\install-manifest.json')
    $cSrc   = Count-Dirs   (Join-Path $RepoRoot 'claude-skills\skills')
    $xReady = Get-ReadyCount (Join-Path $RepoRoot 'codex-skills\package\install-manifest.json')
    $xSrc   = Count-Dirs   (Join-Path $RepoRoot 'codex-skills\skills')
    $aSrc   = Count-Dirs   (Join-Path $RepoRoot 'antigravity-skills\skills')
    $ptInner = @(
        "- ``claude-skills/`` — $cReady install-ready skills for Claude Code ($cSrc in source)"
        "- ``codex-skills/`` — $xReady install-ready skills for OpenAI Codex ($xSrc in source)"
        "- ``antigravity-skills/`` — $aSrc adapter skills + workflows for Google Antigravity"
        '- `gemini-skills/` — legacy Gemini CLI adapter, source-only (not exported by default)'
    ) -join $nl
    $new = Set-Block -Text $new -Name 'provider-targets' -Inner $ptInner -Newline $nl
} else {
    Write-Warning "RepoRoot '$RepoRoot' not found; leaving provider-targets block unchanged."
}

# ── shared-set-count block ────────────────────────────────────
$sharedCount = Count-Dirs $SkillsDir
$scInner = "The shared set holds **$sharedCount skills** in total."
$new = Set-Block -Text $new -Name 'shared-set-count' -Inner $scInner -Newline $nl

# ── emit ──────────────────────────────────────────────────────
if ($new -eq $orig) {
    if ($CheckOnly) { Write-Output 'OK: shared context is up to date.'; exit 0 }
    Write-Output 'No change: shared context already current.'; exit 0
}

if ($CheckOnly) {
    Write-Output 'DRIFT: shared context is stale. Run Update-SharedContext.ps1 to regenerate.'
    exit 1
}

$tmp = "$ContextFile.tmp"
Set-Content -LiteralPath $tmp -Value $new -Encoding utf8 -NoNewline
Move-Item -LiteralPath $tmp -Destination $ContextFile -Force
Write-Output "Updated: $ContextFile"
exit 0
```

- [ ] **Step 2: Run the tests to confirm they pass**

Run:
```bash
pwsh -NoProfile -Command "Invoke-Pester -Path 'C:\Users\Sev\OneDrive\common\common_dev\Update-SharedContext.Tests.ps1' -Output Detailed"
```
Expected: `Tests Passed: 7, Failed: 0`.

- [ ] **Step 3: Regenerate the real shared CLAUDE.md**

Run (from a machine where the repo is present — SND-DESK):
```bash
pwsh -NoProfile -File 'C:\Users\Sev\OneDrive\common\common_dev\Update-SharedContext.ps1'
```
Expected: `Updated: ...CLAUDE.md`.

- [ ] **Step 4: Checkpoint — the live drift is fixed and re-running is a no-op**

Run:
```bash
grep -n 'ssh maindesk' 'C:\Users\Sev\OneDrive\common\common_dev\CLAUDE.md'; grep -c 'ssh SND-DESK' 'C:\Users\Sev\OneDrive\common\common_dev\CLAUDE.md'; pwsh -NoProfile -File 'C:\Users\Sev\OneDrive\common\common_dev\Update-SharedContext.ps1'
```
Expected: the Connect line now shows `ssh maindesk`; the `ssh SND-DESK` count is `0`; the second run prints `No change: shared context already current.`

---

## Phase 3 — Wire drift-checking into the qa cadence

### Task 7: Add the docs-sync surface config and document the check

**Files:**
- Create: `C:\Users\Sev\OneDrive\common\common_dev\.claude\skills\project.toml`
- Modify: `C:\Users\Sev\OneDrive\common\common_dev\README.md`

**Interfaces:**
- Consumes: `Update-SharedContext.ps1 -CheckOnly` (the drift primitive from Task 6) and the `/docs-sync` skill's `[docs-sync]` config schema.
- Produces: a discoverable, repeatable drift check over the context chain.

- [ ] **Step 1: Create the docs-sync config**

```toml
# project.toml — config for context-chain hygiene skills run against common_dev.
# Treat the layered CLAUDE.md tiers as documentation surfaces to cross-check.

[docs-sync]
files = [
  "CLAUDE.md",
  "../../../../DevHome/state/claude/CLAUDE.md",
]
# The machine table, provider counts, and shared-set count in CLAUDE.md are
# generated by Update-SharedContext.ps1; run its -CheckOnly for authoritative
# drift detection against machines.json and the Ai-Skills repo.
```

- [ ] **Step 2: Document the qa step in the README**

Add a short subsection to `common_dev\README.md` (under whatever maintenance/ops section exists, or a new `## Context hygiene` heading):
```markdown
## Context hygiene

The machine table, provider counts, and shared-set total in `CLAUDE.md` are
generated. To check for drift (run on SND-DESK, where the Ai-Skills repo lives):

    pwsh -NoProfile -File .\Update-SharedContext.ps1 -CheckOnly

Exit code 1 means the shared context is stale — re-run without `-CheckOnly` to
regenerate. Include this check in the periodic qa sweep.
```

- [ ] **Step 3: Checkpoint — the check is green after Phase 2**

Run:
```bash
pwsh -NoProfile -File 'C:\Users\Sev\OneDrive\common\common_dev\Update-SharedContext.ps1' -CheckOnly; echo "exit=$?"
```
Expected: `OK: shared context is up to date.` and `exit=0`.

---

## Self-Review

**Spec coverage (Phases 1–3 of the design):**
- Phase 1 fix-now (machine naming, memory) → Tasks 1–2. ✓
- Phase 2 generator with 3 blocks + `-CheckOnly` + `role` field + graceful repo-absent degradation → Tasks 3–6. ✓
- Phase 3 docs-sync surface config + qa cadence doc → Task 7. ✓
- Phase 4 (agents pipeline) and Phase 5 (promotion) are intentionally **out of scope** for Plan A — Plan B covers Phase 4.

**Deviations from spec (deliberate):**
- The `shared-set-count` block omits the "as-of date" from the spec: a date would make `-CheckOnly` report false drift every day, defeating the primitive. The count alone stays idempotent.
- Machine-tier and repo-tier CLAUDE.mds are drift-*checked* (docs-sync surface), not generated, as the spec specified — Task 7 lists the machine-tier file as a docs-sync surface; deeper machine-tier identity assertion is folded into Plan B's `context-auditor` rather than duplicated here.

**Placeholder scan:** none — every code/step body is complete.

**Type/name consistency:** the generator's parameter names (`-ContextFile`, `-MachinesFile`, `-RepoRoot`, `-SkillsDir`, `-CheckOnly`) are identical in Task 5 (tests), Task 6 (impl), and Task 7 (usage). Block names (`machines`, `provider-targets`, `shared-set-count`) match across Tasks 4, 5, 6.
