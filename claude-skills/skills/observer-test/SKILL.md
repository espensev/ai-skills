---
name: observer-test
description: "Short-lived worktree observer — capture test results, build errors, and agent behavior during execution"
argument-hint: "/observe-test [start|note|report|export] — worktree observation during agent runs"
allowed-tools: Read, Glob, Grep, Bash, Edit, Write
user-invocable: true
agent-invocable: true
---

# Observer Test — Worktree Execution Observer

A short-lived observer that runs inside worktrees during agent execution.
Captures test results, build errors, file churn, blockers, and workarounds —
then exports observations for promotion to the main project observation log
after merge.

Key difference from `/observe`: this skill is **scoped to a single worktree
run** and its data lives and dies with the worktree (after promotion).

## Invocation

### Human Commands

```
/observe-test start                              # initialize in this worktree
/observe-test note <category> <summary>          # record an observation
/observe-test report                             # summarize this worktree's observations
/observe-test export                             # output JSON for promotion to main log
```

### Agent Commands

Agents running in worktrees should use these. All produce structured JSON
when `--format json` is passed.

```
/observe-test start --format json                # init and return session JSON
/observe-test note <cat> <summary> --format json # record and return confirmation
/observe-test report --format json               # structured session summary
/observe-test export                             # always outputs JSON array
```

---

## Output Contracts

Every command supports `--format json` for machine-readable output. When
`--format json` is passed, the command outputs **only** a single JSON object
to stdout — no preamble, no markdown, no commentary.

### Start Output

```json
{
  "action": "start",
  "session": {
    "worktree": "/path/to/worktree",
    "agent": "agent-a-db-layer",
    "started_at": "2026-03-21T14:30:00Z",
    "observations_file": "/path/to/worktree/observations.jsonl"
  }
}
```

### Note Output

```json
{
  "action": "note",
  "recorded": true,
  "observation": {
    "ts": "2026-03-21T14:35:00Z",
    "cat": "test-fail",
    "summary": "test_db_query NULL deref",
    "severity": "warning",
    "detail": "sqlite3_column_text on empty result set",
    "files": ["native/src/db.c", "tests/test_db.c"],
    "agent": "agent-a-db-layer"
  }
}
```

If deduplicated (skipped):
```json
{
  "action": "note",
  "recorded": false,
  "reason": "duplicate",
  "existing": {"cat": "test-fail", "summary": "test_db_query NULL deref"}
}
```

### Report Output

```json
{
  "action": "report",
  "session": {
    "agent": "agent-a-db-layer",
    "started_at": "2026-03-21T14:30:00Z",
    "ended_at": "2026-03-21T15:45:00Z",
    "worktree": "/path/to/worktree"
  },
  "total": 7,
  "by_severity": {"info": 3, "warning": 2, "critical": 2},
  "by_category": {
    "test-pass": 3,
    "test-fail": 2,
    "build-error": 1,
    "progress": 1
  },
  "flagged": [
    {"cat": "test-fail", "severity": "warning", "summary": "test_db_query NULL deref on empty result"},
    {"cat": "test-fail", "severity": "warning", "summary": "test_cache_evict segfault after double-free"},
    {"cat": "build-error", "severity": "critical", "summary": "undefined reference to cov_store_compact"}
  ],
  "has_blockers": false,
  "has_regressions": false,
  "has_critical": true
}
```

`flagged` includes any observation with severity `warning` or `critical`, or
category `blocker`, `regression`, or `workaround`.

### Export Output

Always outputs a JSON array (no `--format json` flag needed):

```json
[
  {
    "ts": "2026-03-21T14:30:00Z",
    "cat": "progress",
    "summary": "observation session started",
    "severity": "info",
    "agent": "agent-a-db-layer"
  },
  {
    "ts": "2026-03-21T14:35:00Z",
    "cat": "test-fail",
    "summary": "test_db_query NULL deref",
    "severity": "warning",
    "detail": "sqlite3_column_text on empty result set",
    "files": ["native/src/db.c", "tests/test_db.c"],
    "agent": "agent-a-db-layer"
  }
]
```

This array is the input contract for `/observe note --format json` batch
promotion and `/manager merge` observation promotion.

---

## Observation Schema

Worktree observations use a lighter schema than project-level observations.
Fields are added during promotion to the main store.

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `ts` | ISO 8601 timestamp | now | When recorded |
| `cat` | string | required | Category (see below) |
| `summary` | string | required | One-line description |
| `detail` | string | `""` | Expanded context |
| `files` | string[] | `[]` | Related file paths |
| `agent` | string | auto-detected | Agent identity |
| `severity` | string | `"info"` | `info`, `warning`, or `critical` |

**Severity assignment guidelines:**

| Severity | When to Use |
|----------|-------------|
| `info` | Test passes, progress milestones, routine findings |
| `warning` | Test failures, file churn, workarounds |
| `critical` | Build errors, regressions, blockers |

---

## Commands

### `/observe-test start [--format json]`

Initialize observation tracking for the current worktree.

1. Determine worktree root:
   ```bash
   git rev-parse --show-toplevel
   ```

2. Create `observations.jsonl` in the worktree root (or cwd if not in a
   worktree):
   ```bash
   touch observations.jsonl
   ```

3. Determine agent identity from:
   - Git branch name (often contains agent letter)
   - Environment variable `AGENT_ID` if set
   - Worktree directory name as fallback

4. Record a start observation:
   ```jsonl
   {"ts":"...","cat":"progress","summary":"observation session started","agent":"...","severity":"info"}
   ```

5. If `--format json`, output Start Output contract. Otherwise print
   confirmation with the observation file path.

### `/observe-test note <category> <summary> [--format json]`

Append a single observation to the local `observations.jsonl`.

**Deduplication:** Skip silently if an identical observation already exists
in this session (same `cat` + `summary`). When `--format json` is used,
returns `recorded: false` with reason instead of silent skip.

**Categories** (test/build scoped):

| Category | What It Captures | Default Severity |
|----------|-----------------|------------------|
| `test-pass` | Test suite success with counts | info |
| `test-fail` | Test failure with root cause detail | warning |
| `build-error` | Compilation or link failure | critical |
| `regression` | Previously passing test now fails | critical |
| `churn` | File edited 3+ times (design instability signal) | warning |
| `blocker` | Agent could not complete — missing dependency or API | critical |
| `workaround` | Agent used a hack to proceed | warning |
| `progress` | Milestone reached within the agent's scope | info |

Optional flags:
- `--detail "longer explanation"` — expanded context
- `--files "file1.c,file2.h"` — related files (comma-separated)
- `--severity warning` — override default severity for the category
- `--format json` — return Note Output contract instead of text

**How to record:**

1. Get current timestamp:
   ```bash
   date -u +"%Y-%m-%dT%H:%M:%SZ"
   ```

2. Check deduplication — skip if same cat+summary already in file:
   ```bash
   grep -c '"cat":"test-fail","summary":"test_db_query NULL deref"' observations.jsonl 2>/dev/null
   ```

3. Append JSON line to `observations.jsonl` in the worktree root.

4. If `--format json`, output Note Output contract (see Output Contracts).

### `/observe-test report [--format json]`

Summarize all observations collected in this worktree session.

**Pipeline:**

1. Read `observations.jsonl` from worktree root
2. Count by category and severity
3. Identify flagged items (warning/critical severity, blocker/regression/workaround)
4. If `--format json`, output Report Output contract
5. Otherwise print human-readable summary:

**Human output:**
```
Worktree Observer Report
========================
Session: 2026-03-21 14:30 — 15:45
Agent: agent-a-db-layer
Observations: 7 (2 critical, 2 warning, 3 info)

  test-pass:    3
  test-fail:    2  <- review (warning)
  build-error:  1  <- review (critical)
  progress:     1

Flagged:
  #2 [test-fail] [warning] test_db_query NULL deref on empty result
  #4 [test-fail] [warning] test_cache_evict segfault after double-free
  #5 [build-error] [critical] undefined reference to cov_store_compact
```

### `/observe-test export`

Output all observations as JSON array for promotion to the main project
observation log. Always outputs JSON (no `--format` flag needed).

```bash
# Parse JSONL to JSON array
python3 -c "
import json, sys
obs = [json.loads(line) for line in open('observations.jsonl') if line.strip()]
json.dump(obs, sys.stdout, indent=2)
"
```

See Export Output contract for the schema.

**Promotion via `/manager merge`:**

For each observation in the exported array, the manager calls:
```
/observe note <cat> "<summary>" --files "<files>" --agent-id "<agent>" --severity <severity> --format json
```

**Field mapping for promotion:**

| Worktree field | Project field | Notes |
|----------------|--------------|-------|
| `ts` | `ts` | Preserved from worktree recording |
| `cat` | `cat` | Category name |
| `summary` | `summary` | Observation text |
| `detail` | `detail` | Optional expanded context |
| `files` | `files` | File path array |
| `agent` | `agent` | Agent letter/ID -> maps to `--agent-id` |
| `severity` | `severity` | Preserved from worktree recording |
| (not set) | `status` | Set to `"open"` during promotion |
| (not set) | `confidence` | Set to `0.5` during promotion |
| (not set) | `plan` | Set from active plan context during promotion |
| (not set) | `actor` | Set to `"observe-test"` during promotion |

---

## Agent Integration

### When Agents Should Call Observer-Test

| Lifecycle Point | Command | Why |
|----------------|---------|-----|
| **Worktree start** | `/observe-test start --format json` | Initialize session, get agent identity |
| **After test run** | `/observe-test note test-pass/test-fail ... --format json` | Capture test results |
| **After build** | `/observe-test note build-error ... --format json` | Capture build failures |
| **When blocked** | `/observe-test note blocker ... --format json` | Signal dependency issue |
| **When using workaround** | `/observe-test note workaround ... --format json` | Flag tech debt |
| **On milestone** | `/observe-test note progress ... --format json` | Track completion |
| **Before session end** | `/observe-test report --format json` | Get session summary |

### Agent Workflow Pattern

An agent running in a worktree should follow this pattern:

```
1. /observe-test start --format json
   -> Store session.agent and session.worktree from response

2. Do agent work (edit files, run tests, build)
   After each significant event:
   /observe-test note <cat> "<summary>" --files "..." --format json
   -> Check recorded == true to confirm

3. Before completing:
   /observe-test report --format json
   -> Parse response:
      - If has_blockers or has_regressions: include in AGENT_RESULT_JSON.issues[]
      - Use by_category counts for AGENT_RESULT_JSON.tests_passed/tests_failed
      - Use flagged[] for AGENT_RESULT_JSON.summary context
```

### Mapping to AGENT_RESULT_JSON

The report output maps directly to the agent result contract:

| Report field | AGENT_RESULT_JSON field | Mapping |
|-------------|----------------------|---------|
| `by_category.test-pass` | `tests_passed` | Direct count |
| `by_category.test-fail` | `tests_failed` | Direct count |
| `flagged[]` where severity=critical | `issues[]` | Map each to issue string |
| `has_blockers` | `status` | If true, status = "blocked" |
| `total` | (context) | Include in `summary` |
| `session.agent` | `id` / `name` | Agent identity |

Example agent result incorporating observer-test data:

```json
{
  "id": "a",
  "name": "db-layer",
  "status": "done",
  "files_modified": ["native/src/db.c", "tests/test_db.c"],
  "tests_passed": 3,
  "tests_failed": 2,
  "issues": [
    "build-error: undefined reference to cov_store_compact",
    "test-fail: test_db_query NULL deref on empty result"
  ],
  "summary": "7 observations: 3 test-pass, 2 test-fail, 1 build-error, 1 progress"
}
```

---

## Automatic Observation Suggestions

During agent work, `/observe-test` can suggest observations based on tool
output. When activated:

1. **After test runs** (Bash output containing `FAIL`, `PASSED`, `ERROR`):
   - Parse pass/fail/skip counts
   - Record `test-pass` (severity: info) or `test-fail` (severity: warning)
   - Record `regression` (severity: critical) if a previously passing test fails

2. **After build commands** (cmake, dotnet build, gcc output):
   - Parse error/warning counts
   - Record `build-error` (severity: critical) with compiler message

3. **After repeated edits** to the same file (3+ Edit/Write to same path):
   - Record `churn` (severity: warning) with file path and edit count

4. **After agent reports a blocker** (can't proceed):
   - Record `blocker` (severity: critical) with the missing dependency

These suggestions are **never automatic** — the skill presents them and the
agent (or user) approves each one.

---

## Integration with `/manager`

### During `/manager run`

Each launched agent can invoke `/observe-test start --format json` at the
beginning of its worktree session. The manager includes this instruction in
the agent launch prompt. Observations accumulate during execution.

### During `/manager merge`

After merging worktrees:

1. Check each merged worktree path for `observations.jsonl`
2. Call `/observe-test export` to get JSON array
3. For each observation in the array:
   ```
   /observe note <cat> "<summary>" --files "..." --agent-id "..." --severity <sev> --format json
   ```
4. Parse each response: count `recorded: true` vs `recorded: false` (dedup)
5. Report: "Promoted N observations (M deduplicated, K critical, J warning)"

### During `/manager verify`

Parse the report output to flag problems:
- `has_blockers == true` -> verification warning
- `has_regressions == true` -> verification failure
- `has_critical == true` -> verification warning
- Any `workaround` in `flagged[]` -> verification warning (tech debt)

### Feeding `/planner`

When planning the next campaign, `/planner` reads promoted observations via
`/observe list --category <cat> --format json`:
- `churn` observations -> files that need redesign before more work
- `blocker` observations -> dependencies that must be built first
- `workaround` observations -> debt to address in a cleanup campaign
- `critical` severity items -> must be resolved before next campaign starts

---

## Storage

- **Worktree-local:** `observations.jsonl` in the worktree root
- **Lifetime:** exists only while the worktree exists
- **Promotion:** observations promoted to `data/observations.jsonl` via `/observe note` after merge
- **No database dependency:** pure file-based, works in any worktree

---

## Hook Integration

When hooks are configured (see `/observe` SKILL.md > Hook Integration), two
hooks record observations directly to `observations.jsonl`:

| Hook | Trigger | Records |
|------|---------|---------|
| `observe_test_output.py` | `PostToolUse:Bash` — after test/build commands | `test-fail`, `test-pass`, or `build-error` |
| `observe_churn.py` | `PostToolUse:Edit\|Write` — after file edits | `churn` when file edited 3+ times |

Hooks write directly to whichever `observations.jsonl` exists (worktree-local
first, then project-level). They tag observations with `actor: "hook:<name>"`
and inject a brief `[observer] Recorded ...` confirmation into context.

**For worktree agents:** These hooks are most valuable here — they catch
test/build/churn signals automatically during execution, so agents don't have
to remember to call `/observe-test note` after every test run.

**Graceful degradation:** If `observations.jsonl` doesn't exist (observer-test
not started), hooks silently exit. No errors, no file creation.

---

## Non-Interference Contract

1. Observer-test **never** blocks or delays agent execution
2. All observations are appended — never modifies existing entries
3. Observation suggestions require explicit approval
4. File writes are limited to `observations.jsonl` only
5. Does not modify code, tests, builds, or campaign state
6. Deduplication is silent in human mode, explicit in JSON mode
7. **Hooks record automatically when configured** — recording hooks write
   directly to `observations.jsonl` with `actor: "hook:<name>"` tag. This
   is opt-in (user installs hook config) and degrades gracefully (no-op if
   `observations.jsonl` doesn't exist)
