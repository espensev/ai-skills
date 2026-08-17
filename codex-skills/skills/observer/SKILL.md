---
name: observer
description: "Maintain passive project intelligence by observing, noting, querying, scanning, and synthesizing patterns over time without interfering. Use when the user wants durable project intelligence, passive observation, drift notes, or repo health synthesis."
---

# Observer — Passive Project Intelligence

A non-interfering observation system that accumulates project knowledge over
time. Records decisions, spots patterns, flags drift, and synthesizes a living
intelligence document — without interrupting active work.

The observer never runs automatically. It only acts when you invoke it.
This is not the user's cross-workspace memory store — durable personal
memory belongs to `$memory-management`.

## Scope

- Prefer this skill for passive observation and project-health summaries.
- Prefer `$discover` when the goal is bounded pre-change research for
  one question set.
- Prefer `$qa` when the user wants test execution or failure triage.
- Prefer `$review` when the goal is diff review, not longitudinal
  observation.
- Prefer `verification-loop` when the goal is release-readiness validation,
  not longitudinal observation.

**Storage:** File-based JSONL at `data/observations.jsonl` by default. Repos with
a richer backend (e.g., SQLite campaign DB) can configure `[observer].backend`
in `project.toml` to use backend-specific commands instead.

## Invocation

The installed skill name is `observer`. Invoke it as `$observer <subcommand>`
with the subcommands and arguments shown below.

### Human Commands

```
$observer note <category> <summary>      # record an observation
$observer review                          # scan context, suggest observations
$observer list [--category X] [--status X]  # query observations
$observer resolve <id> [--detail "..."]   # mark an observation resolved
$observer stale [--days 14]               # auto-mark old observations stale
$observer scan [--auto]                   # run probes, emit threshold observations
$observer synthesize                      # update project-intelligence.md
$observer status                          # show observation counts
$observer cycle [--auto]                  # compound: scan → stale → synthesize
```

### Agent Commands

These commands produce structured JSON output for machine consumption.
Agents and other skills should use these exclusively.

```
$observer briefing --format json          # project state snapshot for agents
$observer check --format json             # pre-flight gate (pass/fail)
$observer list --format json              # query observations as JSON array
$observer note ... --format json          # record and return confirmation JSON
$observer scan --auto --format json       # scan and return results as JSON
$observer cycle --auto --format json      # full cycle, return summary JSON
```

---

## Observation Schema

Every observation has these fields:

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `ts` | ISO 8601 timestamp | now | When recorded |
| `cat` | string | required | Category (see below) |
| `summary` | string | required | One-line description |
| `detail` | string | `""` | Expanded context |
| `files` | string[] | `[]` | Related file paths |
| `plan` | string | `null` | Linked plan ID |
| `agent` | string | `null` | Linked agent ID |
| `confidence` | float | `0.5` | Certainty (0.0–1.0) |
| `status` | string | `"open"` | `open`, `resolved`, or `stale` |
| `severity` | string | `"info"` | `info`, `warning`, or `critical` |
| `actor` | string | `"observer"` | Who recorded this |
| `resolved_at` | timestamp | `null` | When resolved |
| `resolved_detail` | string | `null` | Resolution notes |

**Severity levels:**

| Level | Meaning | When to Use |
|-------|---------|-------------|
| `info` | Routine finding | Default for manual notes and patterns |
| `warning` | Needs attention | Drift, soft threshold crossings, growing debt |
| `critical` | Blocks progress | Build failures, enforcement breaches, regressions |

For machine-sensitive observations, also capture `machine_scope`, the verified
`controller_machine_id`, explicit `target_machine_ids`, and `transport`. Never
infer a machine from paths, repository history, or peer snapshot filenames.
Stop before writing a machine-sensitive observation if the controller or any
target identity cannot be verified. Do not substitute a hostname, alias,
username, path, or prose mention for a verified machine ID. Use `unknown` only
for clearly labelled legacy data.

---

## Feedback Prioritization

Prefer recording these signals, in this order:

- explicit user corrections or rejections
- failing build, lint, typecheck, smoke-test, or verification commands with
  concrete output
- repeated workarounds or repeated reviewer findings
- drift that changes how the next agent should plan or verify
- successful fixes that closed a real regression

Do not turn a one-off weak signal into durable project memory unless it is
evidence-backed and likely to change future behavior.

---

## Output Contracts

Every command supports `--format json` for machine-readable output. When
`--format json` is passed, the command outputs **only** a single JSON object
to stdout — no preamble, no markdown, no commentary.

### Note Output

```json
{
  "action": "note",
  "recorded": true,
  "observation": {
    "ts": "2026-03-21T14:30:00Z",
    "cat": "risk",
    "summary": "no tests for payment module",
    "severity": "warning",
    "status": "open",
    "confidence": 0.5
  }
}
```

If deduplicated (skipped):
```json
{
  "action": "note",
  "recorded": false,
  "reason": "duplicate",
  "existing": {"cat": "risk", "summary": "no tests for payment module"}
}
```

### List Output

```json
{
  "action": "list",
  "count": 3,
  "filters": {"category": "risk", "status": "open"},
  "observations": [
    {"ts": "2026-03-21T09:15:00Z", "cat": "risk", "summary": "no tests for payment module", "severity": "warning", "status": "open", "confidence": 0.8, "files": ["src/payment.py"]},
    {"ts": "2026-03-21T14:30:00Z", "cat": "risk", "summary": "API keys in env without rotation", "severity": "critical", "status": "open", "confidence": 0.9, "files": []}
  ]
}
```

### Status Output

```json
{
  "action": "status",
  "total": 23,
  "by_status": {"open": 18, "resolved": 3, "stale": 2},
  "by_severity": {"info": 18, "warning": 4, "critical": 1},
  "by_category": {
    "decision": {"open": 3, "resolved": 1, "stale": 1},
    "risk": {"open": 3, "resolved": 1, "stale": 0}
  },
  "last_observation": "2026-03-21T14:30:00Z",
  "last_synthesis": "2026-03-20T10:00:00Z",
  "metrics_tracked": 3
}
```

### Scan Output

```json
{
  "action": "scan",
  "probes_run": 5,
  "metrics_updated": [
    {"key": "dirty_file_count", "value": 5, "previous": 3, "delta": 2},
    {"key": "todo_count", "value": 42, "previous": 38, "delta": 4}
  ],
  "observations_emitted": [
    {"cat": "drift", "summary": "TODO count increased by 4 (now 42)", "severity": "warning", "recorded": true}
  ],
  "observations_resolved": [
    {"cat": "risk", "summary": "dirty file count above threshold", "reason": "metric recovered"}
  ]
}
```

### Briefing Output

```json
{
  "action": "briefing",
  "status": "warning",
  "health": "degraded",
  "summary": "2 warnings, 0 critical — 15 open observations",
  "critical": [],
  "warnings": [
    {"cat": "risk", "summary": "no tests for payment module", "files": ["src/payment.py"]},
    {"cat": "drift", "summary": "auth module untouched for 3 weeks", "files": ["src/auth/"]}
  ],
  "metrics": {
    "dirty_file_count": 3,
    "todo_count": 42,
    "plans_executing": 1
  },
  "open_count": 15,
  "next_actions": [
    "Add test coverage for payment module",
    "Review auth module for staleness"
  ]
}
```

`health` values: `healthy` (0 critical, 0 warning), `degraded` (warnings only),
`unhealthy` (any critical).

### Check Output

```json
{
  "action": "check",
  "gate": "pass",
  "blockers": [],
  "warnings": ["no tests for payment module"],
  "open_critical": 0,
  "open_blockers": 0,
  "open_regressions": 0
}
```

Exit code: `0` if gate=pass, `1` if gate=fail.

### Cycle Output

```json
{
  "action": "cycle",
  "scan": {"probes_run": 5, "metrics_updated": 3, "observations_emitted": 1},
  "stale": {"marked": 2},
  "synthesize": {"file": "docs/observer/project-intelligence.md", "sections": 9},
  "status": {"total": 23, "open": 16, "critical": 0, "warning": 3}
}
```

### Resolve Output

```json
{
  "action": "resolve",
  "id": "2026-03-21T09:15:00Z:risk:no tests for payment module",
  "status": "resolved",
  "resolved_at": "2026-03-22T10:00:00Z",
  "resolved_detail": "Added pytest coverage in test_payment.py"
}
```

---

## Commands

### `$observer note <category> <summary>`

Record a single observation. **Deduplication:** skip silently if an identical
open observation already exists (same category + summary).

Category must be one of:

| Category | What It Captures |
|----------|-----------------|
| `decision` | Architectural or design choices made |
| `pattern` | Recurring code or workflow patterns |
| `drift` | Divergence from plans or attention imbalance |
| `risk` | Potential problems spotted |
| `progress` | Milestones and completions |
| `question` | Unresolved design questions |
| `debt` | Technical debt accumulating |

**Execution-scoped categories** (used by worktree-local observation sessions,
promoted after merge):

| Category | What It Captures |
|----------|-----------------|
| `test-pass` | Test suite success with counts |
| `test-fail` | Test failure with root cause |
| `build-error` | Compilation or link failure |
| `regression` | Previously passing test now fails |
| `churn` | File edited 3+ times (design instability) |
| `blocker` | Agent could not proceed — missing dependency |
| `workaround` | Agent used a hack to proceed |

All categories write to the same observation store and appear in
`$observer synthesize` output.

Optional flags:
- `--detail "longer explanation"` — expanded context
- `--files "file1.c,file2.h"` — related files (comma-separated)
- `--plan-id <plan-id>` — link to a campaign plan
- `--agent-id <agent-id>` — link to a campaign agent
- `--confidence 0.8` — certainty level (0.0–1.0, default 0.5)
- `--severity warning` — override default `info` level
- `--actor <name>` — who recorded this (default: `observer`)
- `--format json` — return JSON confirmation instead of text

**How to record (JSONL backend):**

1. Get current timestamp:
   ```bash
   date -u +"%Y-%m-%dT%H:%M:%SZ"
   ```

2. Check for duplicates — skip if open observation with same cat+summary exists:
   ```bash
   grep -c '"cat":"decision","summary":"chose JSONL"' data/observations.jsonl 2>/dev/null
   ```

3. Build the JSON observation object:
   ```jsonl
   {"ts":"2026-03-21T14:30:00Z","cat":"decision","summary":"chose JSONL over SQLite for portability","status":"open","severity":"info","detail":"...","files":["src/storage.py"],"plan":null,"agent":null,"confidence":0.5,"actor":"observer"}
   ```

4. Append to `data/observations.jsonl`:
   ```bash
   echo '{"ts":"...","cat":"...","summary":"...","status":"open","severity":"info"}' >> data/observations.jsonl
   ```

5. If `--format json`, output the Note Output contract (see Output Contracts).

### `$observer list [--category X] [--status X] [--since DATE] [--format json]`

Query observations with optional filters.

**Pipeline:**

1. Read all observations from `data/observations.jsonl`
2. Apply filters:
   - `--category risk` — show only risk observations
   - `--status open` — show only open observations
   - `--since 2026-03-15` — show observations after this date
   - `--severity critical` — show only critical observations
3. Output as formatted table (default) or List Output contract (`--format json`)

**Human output:**
```
#  Timestamp             Cat       Sev      Status  Summary
1  2026-03-20T10:00:00Z  decision  info     open    chose event sourcing for audit trail
3  2026-03-21T09:15:00Z  risk      warning  open    no tests for payment module
5  2026-03-21T14:30:00Z  drift     info     open    auth module untouched for 3 weeks
```

### `$observer resolve <id> [--detail "resolution notes"]`

Mark an observation as resolved while preserving its history.

**Pipeline:**

1. Read `data/observations.jsonl`, find observation by ID (line number or
   matching timestamp + category + summary)
2. Set `status` to `"resolved"`, add `resolved_at` timestamp
3. If `--detail` provided, set `resolved_detail`
4. Rewrite the JSONL file with the updated entry
5. If `--format json`, output the Resolve Output contract
6. Otherwise print confirmation with observation summary

### `$observer stale [--days 14]`

Auto-mark observations older than N days (default 14) as stale.

**Pipeline:**

1. Read all open observations from `data/observations.jsonl`
2. For each open observation where `ts` is older than `--days` threshold:
   - Set `status` to `"stale"`
3. Rewrite the JSONL file
4. Print count: "Marked N observations as stale"

### `$observer scan [--auto] [--format json]`

Run probes against project state, update metrics, and emit threshold
observations. This is the primary way to collect structured project health data.

**Probes** (all git/file-based, no build toolchain dependencies):

| Probe | What It Checks | Metric Key |
|-------|---------------|------------|
| Git state | Uncommitted files via `git status --porcelain` | `dirty_file_count` |
| TODO markers | `git grep -c 'TODO\|FIXME\|HACK\|XXX'` across source files | `todo_count` |
| File churn | Files changed 3+ times in last 10 commits via `git log --name-only` | (emits churn observation) |
| Plan state | Parse tracker file for executing/approved plan counts | `plans_executing`, `plans_approved` |
| Recent activity | `git log --oneline -10` to detect stalled areas | (emits drift observation) |

**Metrics storage:** `data/metrics.jsonl` — each line is a gauge:
```jsonl
{"key":"dirty_file_count","value":5,"previous":3,"unit":"files","ts":"2026-03-21T14:30:00Z"}
```

**Threshold-driven observations:** When a metric crosses a threshold, emit an
observation automatically:

| Metric | Threshold | Severity | Observation |
|--------|-----------|----------|-------------|
| `dirty_file_count` | >= 10 | warning | "N uncommitted files — possible merge risk" |
| `todo_count` | > 10% delta from previous | warning | "TODO count changed by N (now M total)" |
| `plans_executing` | > 0 but no recent commits | warning | "Plan executing but no activity in N days" |

**Auto-resolution:** When a metric recovers below its threshold, automatically
resolve the matching open observation.

**`--auto` flag:** Skip user confirmation for threshold-driven observations.
Without `--auto`, each suggested observation is presented for approval.

**`--format json`:** Return the Scan Output contract (see Output Contracts).

**Consumer extension point:** Repos with build toolchains can add probes for
`dotnet build`, `cmake`, test runners, enforcement hooks, etc. by extending the
scan pipeline in their backend. The portable skill covers git-only probes.

### `$observer review`

A **skill-level workflow** (not a backend command) that reads the current
project context and suggests new observations. This is the primary way to
build up qualitative observations over time.

**Pipeline:**

1. Load existing observations from `data/observations.jsonl`:
   ```bash
   cat data/observations.jsonl 2>/dev/null | wc -l
   ```
   Parse JSON lines to understand what has already been recorded.

2. Read recent context:
   - `git log --oneline -20` — recent commits
   - `git diff --stat HEAD~5` — recent file changes
   - Read tracker file from `[paths].tracker` — current campaign state
   - `docs/observer/project-intelligence.md` — last synthesis (if exists)

3. Analyze for:
   - **Decisions** made in recent commits or sessions
   - **Patterns** — files changing together, repeated error types
   - **Drift** — areas with no recent activity vs. active areas
   - **Risks** — missing tests, growing complexity, unresolved TODOs
   - **Questions** — ambiguities in recent work, undecided design choices
   - **Debt** — TODO/FIXME/HACK comments, workarounds

4. For each candidate observation:
   - Check deduplication (same category + summary already open -> skip)
   - Assign severity based on impact (info/warning/critical)
   - Present to the user for approval
   - On approval, record via append to `data/observations.jsonl`

5. Summarize: how many new observations recorded, category breakdown

**Non-interference contract:**
- Never auto-records without user approval during review
- Never modifies code or plans
- Only reads project state and suggests observations

### `$observer synthesize`

Read all observations and produce the living intelligence document at
`docs/observer/project-intelligence.md`.

**Pipeline:**

1. Read all observations from `data/observations.jsonl`:
   ```bash
   cat data/observations.jsonl
   ```

2. Cluster observations by theme:
   - Group by category
   - Within categories, cluster by related files or topics
   - Count recurrence (similar observations = stronger signal)

3. Write `docs/observer/project-intelligence.md` with sections:
   - **Active Themes** — top patterns by frequency, sorted by confidence (max 5)
   - **Decisions Log** — category: decision, reverse chronological
   - **Drift & Risks** — unresolved drift + risk observations, severity-sorted
   - **Emerging Patterns** — category: pattern, with occurrence count
   - **Test & Build Observations** — execution-scoped categories promoted from worktrees
   - **Open Questions** — category: question, unresolved
   - **Technical Debt** — category: debt, unresolved
   - **Recently Resolved** — last 10 resolved observations with timestamps
   - **Stats** — count table by category and status

4. Do not mirror the synthesis into native memory —
   `docs/observer/project-intelligence.md` is the durable summary surface.
   Native Codex memory stays governed by `$memory-management`.

### `$observer status [--format json]`

Show observation counts by category, status, and severity.

**Human output:**

```
Observations: 23 total (18 open, 3 resolved, 2 stale)
Severity: 1 critical, 4 warning, 18 info

  decision:  5 (3 open)
  pattern:   4 (4 open)
  drift:     3 (2 open, 1 stale)
  risk:      4 (3 open, 1 resolved)
  progress:  3 (2 open, 1 resolved)
  question:  2 (2 open)
  debt:      2 (2 open, 1 stale)

Last observation: 2026-03-21
Last synthesis:   2026-03-20
Metrics: 3 tracked (dirty_file_count, todo_count, plans_executing)
```

**`--format json`:** Return the Status Output contract (see Output Contracts).

### `$observer briefing [--format json]`

Agent-facing project state snapshot. Returns a compact summary designed for
consumption by other skills and agents, not for human reading.

**Pipeline:**

1. Read open observations, current metrics from storage
2. Determine overall status:
   - `critical` — any critical-severity open observation exists
   - `warning` — any warning-severity open observation exists
   - `ok` — only info-severity observations
3. Determine health: `healthy` (0 critical, 0 warning), `degraded` (warnings),
   `unhealthy` (any critical)
4. Build next_actions from open critical/warning observations
5. Output the Briefing Output contract (see Output Contracts)

**Used by:** `$discover` (pre-research context), `$planner` (risk check before
planning), `$manager` (pre-flight before launching agents), any agent
(start-of-session context).

### `$observer check [--format json]`

Pre-flight gate for agents. Returns exit code 0 (clear) or 1 (blocked).

**Pipeline:**

1. Read open observations
2. Check for blockers:
   - Any `critical` severity open observation -> exit 1
   - Any `blocker` category open observation -> exit 1
   - Any `regression` category open observation -> exit 1
3. Return the Check Output contract (see Output Contracts)

Exit code: `0` if gate=pass, `1` if gate=fail.

**Used by:** `$manager run` (pre-launch check), `$manager verify` (readiness gate).

### `$observer cycle [--auto] [--format json]`

Compound command that runs the full observation cycle in one invocation.

**Pipeline:**

1. **Scan** — run all probes, emit threshold observations
2. **Stale** — auto-mark observations older than 14 days
3. **Synthesize** — regenerate `project-intelligence.md`
4. **Status** — collect final summary

With `--auto`, threshold observations are recorded without user confirmation.
Without it, each suggested observation requires approval before proceeding to
the next step.

**`--format json`:** Return the Cycle Output contract (see Output Contracts).

This is the recommended single command for periodic project health checks.

---

## Agent Integration

### When to Call Observer

Agents and skills should call observer at specific lifecycle points:

| Lifecycle Point | Command | Why |
|----------------|---------|-----|
| **Agent start** | `$observer briefing --format json` | Get project context, check for known risks |
| **Before launching agents** | `$observer check --format json` | Gate: don't launch if critical blockers exist |
| **After agent completes** | `$observer note ... --format json` | Record decisions, patterns, risks discovered |
| **Before merge** | `$observer check --format json` | Verify no regressions before merging |
| **After merge** | `$observer cycle --auto --format json` | Full health check on merged state |
| **Before planning** | `$observer briefing --format json` | Incorporate risks/drift into plan |
| **Periodic health check** | `$observer cycle --auto --format json` | Keep intelligence current |

### How Agents Consume Observer Output

**Pattern 1: Pre-flight gate** — agent reads `check` output and aborts if blocked:
```
1. Call $observer check --format json
2. Parse JSON: if gate == "fail", report blockers and stop
3. If gate == "pass", proceed with agent work
4. Optionally log warnings to agent context
```

**Pattern 2: Context enrichment** — agent reads `briefing` to inform decisions:
```
1. Call $observer briefing --format json
2. Parse JSON: extract warnings[], metrics{}, next_actions[]
3. Use warnings to avoid known problem areas
4. Use metrics to understand current project state
5. Use next_actions to prioritize work
```

**Pattern 3: Record findings** — agent writes observations during work:
```
1. During work, when agent discovers a decision/risk/pattern:
   Call $observer note <cat> "<summary>" --agent-id <self> --format json
2. Parse JSON: confirm recorded == true
3. At end of session, optionally call $observer scan --auto --format json
```

**Pattern 4: Batch promotion** — manager promotes worktree observations:
```
1. After worktree merge, read worktree observations.jsonl
2. For each observation:
   Call $observer note <cat> "<summary>" --files "..." --agent-id "..." --format json
3. Parse JSON: count recorded vs deduplicated
4. Report: "Promoted N observations, M deduplicated"
```

### Agent Result Integration

When an agent produces an `AGENT_RESULT_JSON` block, the manager can extract
observation-worthy signals and record them:

| AGENT_RESULT_JSON field | Observer category | When |
|------------------------|-------------------|------|
| `tests_failed > 0` | `test-fail` | Always record |
| `tests_passed > 0 && tests_failed == 0` | `test-pass` | Record on completion |
| `issues[]` non-empty | `risk` or `blocker` | Per issue |
| `status == "done"` | `progress` | Record milestone |
| `files_modified[]` | (context) | Attach as `--files` to other observations |

---

## Observation Lifecycle

```
note/review/scan  ->  open  ->  resolved
                       |
                       +--- stale
                         (auto after 14d via $observer stale)
```

- **open** — newly recorded, active
- **resolved** — addressed via `$observer resolve`, keeps history
- **stale** — auto-marked after 14 days unresolved via `$observer stale`

**Deduplication:** Before recording any observation, check if an identical open
observation already exists (same `cat` + `summary`). If so, skip silently.
This applies to `$observer note`, `$observer review`, and `$observer scan`.

---

## Metrics

Metrics are numeric gauges that track project health over time. Unlike
observations (qualitative, append-only events), metrics are key-value pairs
that update in place and record their previous value for delta tracking.

**Storage:** `data/metrics.jsonl` — one line per metric key, upserted on scan.

```jsonl
{"key":"dirty_file_count","value":5,"previous":3,"unit":"files","ts":"2026-03-21T14:30:00Z"}
{"key":"todo_count","value":42,"previous":38,"unit":"markers","ts":"2026-03-21T14:30:00Z"}
{"key":"plans_executing","value":1,"previous":0,"unit":"plans","ts":"2026-03-21T14:30:00Z"}
```

Metrics are collected by `$observer scan` and reported by `$observer status` and
`$observer briefing`. They feed the threshold-driven observation system — when a
metric crosses a threshold, an observation is emitted automatically.

**Consumer extension:** Repos with richer backends can track additional metrics
(build status, enforcement hooks, per-worktree drift, test counts) by extending
the scan probes. The portable skill tracks git-derived metrics only.

---

## Integration with Other Skills

| Skill | How It Uses Observer | Recommended Command |
|-------|---------------------|---------------------|
| `$discover` | Project context before research | `$observer briefing --format json` |
| `$planner` | Risk/drift check before planning | `$observer briefing --format json` |
| `$manager run` | Pre-launch gate | `$observer check --format json` |
| `$manager merge` | Promotes worktree observations to project store | `$observer note --format json` (batch) |
| `$manager verify` | Readiness gate for merge | `$observer check --format json` |
| `$qa` | Coverage gap prioritization | `$observer list --category pattern --format json` |
| Worktree-local observation sessions | Worktree observations promoted after merge | `$observer note --format json` (batch) |
| Any agent | Start-of-session context | `$observer briefing --format json` |

---

## Storage

- **Observations:** `data/observations.jsonl` — append-only JSONL file
- **Metrics:** `data/metrics.jsonl` — upserted gauge values
- **Living doc:** `docs/observer/project-intelligence.md` — synthesized output

---

## Automation

This package ships no observer hook layer. Do not claim hooks, agents, or
slash commands exist unless they are actually present in the current package.
For periodic collection, run `$observer cycle --auto` manually or via `$loop`
when a recurring pass is wanted.

> This section, and Non-Interference Contract rules 7-8, differ between the
> Claude and Codex packages because the mechanism exists on one side only:
> Claude ships portable observer hook scripts, Codex ships none. The asymmetry
> is defensible only while that stays true. Expiry condition and what to
> revisit: `docs/observer-hook-asymmetry.md` in the Ai-Skills repo.

---

## Non-Interference Contract

1. Observer **never** modifies code, plans, or campaign state
2. Observer **only** reads project state and writes to its own outputs
3. During `$observer review`, every suggested observation requires user approval
4. During `$observer scan` (without `--auto`), threshold observations require approval
5. The observer is purely additive — it records, it does not act
6. Scan probes are read-only — no builds, no test runs, no file modifications

---

## Promotion Rules

- Record one-off incidents as observations when they explain the current state.
- Promote recurring regressions and blockers by keeping them `open` with
  raised severity so `$observer check` gates on them, and surface them in
  `$manager verify` reports.
- Additionally promote them into eval pressure with:
  `python scripts/observe_to_eval.py --merge eval/cases/light-skill-cases.json`
  If `scripts/observe_to_eval.py` is not present in the repo (for example a
  skills-only install without the runtime files), skip this command and record
  the eval-case candidate in the observation entry or report instead.
- Re-rank which skills need attention with:
  `python scripts/skill_feedback_loop.py --out docs/skill-improvement-report.md`
  If `scripts/skill_feedback_loop.py` is not present in the repo (for example a
  skills-only install without the runtime files), skip this command and record
  the skills needing attention in the observation entry or report instead.
- Only turn user preference into a reusable pattern after repetition or an
  explicit request to codify it.

---

## Rules

- Do not invent backend commands that the repo does not implement.
- Do not auto-record speculative observations from weak signals.
- Do not use observer artifacts as a parallel Codex native-memory store.
- Do not replace `$discover`, `$planner`, `$manager`, or
  `$qa`; enrich them.
- When a finding is really a blocking bug or regression, say so explicitly
  rather than burying it in a vague summary.

---

## Package Fit

In `codex-skills`, observer is an optional engineering skill that keeps durable
notes about drift and recurring risks, summarizes cross-session project
health, gives `$discover` and `$planner` richer context when the
user asks for it, and stays file-based and stdlib-friendly. It is not a
guaranteed runtime command surface in `scripts/task_manager.py`.

---

## Output

Default response shape:

1. current observation state or requested synthesis
2. evidence-backed observations to add or update
3. resulting artifacts changed
4. next useful command or follow-up skill
