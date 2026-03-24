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

```
/observe-test start                              # initialize in this worktree
/observe-test note <category> <summary>          # record an observation
/observe-test report                             # summarize this worktree's observations
/observe-test export                             # output JSON for promotion to main log
```

---

## Commands

### `/observe-test start`

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

3. Record a start observation:
   ```jsonl
   {"ts":"...","cat":"progress","summary":"observation session started","agent":"..."}
   ```

4. Print confirmation with the observation file path.

### `/observe-test note <category> <summary>`

Append a single observation to the local `observations.jsonl`.

**Categories** (test/build scoped):

| Category | What It Captures |
|----------|-----------------|
| `test-pass` | Test suite success with counts |
| `test-fail` | Test failure with root cause detail |
| `build-error` | Compilation or link failure |
| `regression` | Previously passing test now fails |
| `churn` | File edited 3+ times (design instability signal) |
| `blocker` | Agent could not complete — missing dependency or API |
| `workaround` | Agent used a hack to proceed |
| `progress` | Milestone reached within the agent's scope |

**JSONL format:**
```jsonl
{"ts":"2026-03-21T14:30:00Z","cat":"test-fail","summary":"test_db_query NULL deref","detail":"sqlite3_column_text on empty result set","files":["native/src/db.c","tests/test_db.c"],"agent":"agent-a-db-layer"}
```

**How to record:**

1. Get current timestamp:
   ```bash
   date -u +"%Y-%m-%dT%H:%M:%SZ"
   ```

2. Determine agent identity from:
   - Git branch name (often contains agent letter)
   - Environment variable `AGENT_ID` if set
   - Worktree directory name as fallback

3. Append JSON line to `observations.jsonl` in the worktree root.

### `/observe-test report`

Summarize all observations collected in this worktree session.

**Pipeline:**

1. Read `observations.jsonl` from worktree root
2. Count by category
3. List all observations grouped by category
4. Highlight any `blocker`, `regression`, or `workaround` observations (these
   are the most important signals for planning)
5. Print summary to stdout

**Example output:**
```
Worktree Observer Report
========================
Session: 2026-03-21 14:30 — 15:45
Agent: agent-a-db-layer
Observations: 7

  test-pass:    3
  test-fail:    2  <- review
  build-error:  1  <- review
  progress:     1

Flagged:
  #2 [test-fail] test_db_query NULL deref on empty result
  #4 [test-fail] test_cache_evict segfault after double-free
  #5 [build-error] undefined reference to cov_store_compact
```

### `/observe-test export`

Output all observations as JSON array for promotion to the main project
observation log.

```bash
# Parse JSONL to JSON array
python3 -c "
import json, sys
obs = [json.loads(line) for line in open('observations.jsonl') if line.strip()]
json.dump(obs, sys.stdout, indent=2)
"
```

This output is consumed by `/manager merge` or manually appended to the
project-level `data/observations.jsonl` used by `/observe`:

```bash
# Promote worktree observations to project log
cat worktree-path/observations.jsonl >> data/observations.jsonl
```

---

## Automatic Observation Suggestions

During agent work, `/observe-test` can suggest observations based on tool
output. When activated:

1. **After test runs** (Bash output containing `FAIL`, `PASSED`, `ERROR`):
   - Parse pass/fail/skip counts
   - Record `test-pass` or `test-fail` with details

2. **After build commands** (cmake, dotnet build, gcc output):
   - Parse error/warning counts
   - Record `build-error` with compiler message

3. **After repeated edits** to the same file (3+ Edit/Write to same path):
   - Record `churn` observation with file path and edit count

4. **After agent reports a blocker** (can't proceed):
   - Record `blocker` with the missing dependency

These suggestions are **never automatic** — the skill presents them and the
agent (or user) approves each one.

---

## Integration with `/manager`

### During `/manager run`

Each launched agent can invoke `/observe-test start` at the beginning of its
worktree session. Observations accumulate during execution.

### During `/manager merge`

After merging worktrees:

1. Check each merged worktree path for `observations.jsonl`
2. Read and parse the JSONL file
3. Append each observation to the project-level `data/observations.jsonl`
4. Report promoted observation count

### During `/manager verify`

Flag worktree observations that indicate problems:
- Any `blocker` -> verification warning
- Any `regression` -> verification failure
- Any `workaround` -> verification warning (tech debt)

### Feeding `/planner`

When planning the next campaign, `/planner` checks recent observations:
- `churn` observations -> files that need redesign before more work
- `blocker` observations -> dependencies that must be built first
- `workaround` observations -> debt to address in a cleanup campaign

---

## Storage

- **Worktree-local:** `observations.jsonl` in the worktree root
- **Lifetime:** exists only while the worktree exists
- **Promotion:** observations appended to `data/observations.jsonl` via `/observe` after merge
- **No database dependency:** pure file-based, works in any worktree

---

## Non-Interference Contract

1. Observer-test **never** blocks or delays agent execution
2. All observations are appended — never modifies existing entries
3. Observation suggestions require explicit approval
4. File writes are limited to `observations.jsonl` only
5. Does not modify code, tests, builds, or campaign state
