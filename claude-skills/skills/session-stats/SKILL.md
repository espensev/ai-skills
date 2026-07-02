---
name: session-stats
description: "Analyze session tool usage, agent activity, timing, and cost metrics from conversation transcripts, hooks logs, and telemetry where available. Use for cross-session comparisons or end-of-session summaries."
argument-hint: "<summary|tools|agents|timeline|compare|export> — session usage analytics"
allowed-tools: Read, Glob, Grep, Bash
user-invocable: true
extracted-from: Ai-Skills
portable-since: 2026-03-28
---

# Session Stats — Session Usage Analytics

On-demand analytics dashboard for Claude Code sessions. Parses conversation
transcripts and hooks logs to provide tool usage breakdown, agent activity
metrics, cost tracking, and cross-session comparisons.

Complements claude-lens (real-time statusline) with deeper, historical analysis.

**All commands run to completion autonomously.**

**Config:** `.claude/skills/project.toml` — `[session-stats]` section (optional)

---

## Commands

| Command | Usage | Purpose |
|---------|-------|---------|
| `summary` | `/session-stats` or `/session-stats summary` | Quick session overview |
| `tools` | `/session-stats tools` | Tool usage breakdown with counts and patterns |
| `agents` | `/session-stats agents` | Subagent spawning, types, and outcomes |
| `timeline` | `/session-stats timeline` | Activity timeline with phases |
| `compare` | `/session-stats compare [N]` | Compare last N sessions (default 5) |
| `export` | `/session-stats export` | Export session metrics as JSON |

Default to `summary` if no command given.

---

## Setup: Discover Data Sources

Before any command, discover available data sources in **precedence order**.
The first reachable tier is authoritative; lower tiers fill gaps it does not
cover. Always report WHICH tier produced the numbers.

1. **Telemetry HTTP API** (tier 1 — authoritative, real hook-captured
   measurements). A local telemetry service (the ollama-telemetry repo)
   optionally exposes real per-session token/cost/tool data over HTTP.
   This tier is **optional**: probe it first, but never hard-require it.
   ```bash
   # Reachability probe gates the whole API path (2s budget):
   curl -s --max-time 2 http://127.0.0.1:8099/health >/dev/null && echo REACHABLE
   ```
   Base URL is configurable via `[session-stats].telemetry_url` in project.toml
   (default `http://127.0.0.1:8099`). If reachable, prefer it over the
   char/heuristic and git-only paths:
   ```bash
   # Session-window overview (camelCase response fields):
   curl -s --max-time 2 "http://127.0.0.1:8099/api/llm/overview?hours=8"
   # Recent events (filterable by provider/type/machineId):
   curl -s --max-time 2 "http://127.0.0.1:8099/api/llm/recent?limit=200"
   # Per-session totals once a sessionId is known:
   curl -s --max-time 2 "http://127.0.0.1:8099/api/llm/sessions/<sessionId>"
   ```
   Response JSON is **camelCase**: `totalInputTokens`, `totalOutputTokens`,
   `totalCostUsd`, `cacheReadTokens`, plus session-level totals. (snake_case
   like `cache_read_tokens` is ONLY the `/api/llm/ingest` request body — never
   read it from responses.) Label all numbers from this tier as **measured**.
   If port 8099 is unreachable, fall through **silently** to tier 2/3 — never
   hard-fail and never block on it.

2. **Hooks JSONL log** (tier 2 — richest local source for tool events):
   ```bash
   ls -la .claude/hooks/logs/hooks-log.jsonl 2>/dev/null
   ```
   If exists: contains timestamped tool events with session_id, tool_name,
   tool_input, agent_id. Parse with jq or python3 json module.

3. **Claude Code conversations** (per-message detail):
   Locate the project conversation directory:
   ```bash
   # macOS / Linux
   ls ~/.claude/projects/*/conversations/*.jsonl 2>/dev/null | tail -5
   # Windows
   ls "$USERPROFILE/.claude/projects/"*/conversations/*.jsonl 2>/dev/null | tail -5
   ```
   Find the most recent conversation file for the current project.

4. **Git activity** (code-level metrics for the session window):
   ```bash
   git log --oneline --since="8 hours ago" --format="%H %ai %s"
   ```

5. **Observer data** (if observer skill is active):
   ```bash
   ls data/observations.jsonl 2>/dev/null
   ```

6. **Campaign state** (if campaign skills are active):
   ```bash
   ls data/tasks.json data/plans/*.json 2>/dev/null
   ```

Report which sources were found, and which tier produced each number.
Commands adapt to available data — more sources produce richer analysis.

If **no data sources found**, report clearly and suggest:
- Install hooks for tool-level tracking
- Enable observer for project-level metrics
- Or run the command after some session activity has accumulated

---

## Command: `summary` — Quick Session Overview

### Steps

0. **Telemetry first (tier 1)**: If the telemetry API is reachable (health
   probe above), prefer it for token/tool/session totals. Pull
   `/api/llm/overview?hours=8` and, once a sessionId is known,
   `/api/llm/sessions/<sessionId>` for per-session tool/token data. Use these
   **measured** numbers in place of the char/heuristic and git-only paths. If
   unreachable, skip silently and use the tiers below exactly as today.

1. **Identify current session**: Find the most recent session_id from telemetry
   (tier 1) or the hooks log, or the latest conversation file.

2. **Count tool calls** by type — from telemetry per-session data when tier 1
   is available; otherwise from hooks log PreToolUse events:
   ```bash
   python3 -c "
   import sys, json
   from collections import Counter
   c = Counter()
   for line in open('.claude/hooks/logs/hooks-log.jsonl'):
       try:
           e = json.loads(line)
           if e.get('event') == 'PreToolUse':
               c[e.get('tool_name', 'unknown')] += 1
       except: pass
   for k, v in c.most_common():
       print(f'  {k}: {v}')
   print(f'  Total: {sum(c.values())}')
   "
   ```
   If hooks log unavailable, parse conversation transcript for tool_use blocks.

3. **Count agent spawns** (SubagentStart/SubagentStop events):
   ```bash
   grep -c '"SubagentStart"' .claude/hooks/logs/hooks-log.jsonl 2>/dev/null
   ```

4. **Session duration**: Derive from first to last event timestamp within the
   current session_id.

5. **Git activity during session**: Commits, files changed, insertions/deletions.
   ```bash
   git log --since="8 hours ago" --format="%H" | wc -l
   git diff --stat HEAD~3 2>/dev/null | tail -1
   ```

6. **Rate limit position**: Read from Claude Code statusline cache if accessible
   (e.g., `/tmp/claude-sl-usage` on Unix).

### Report

```
Session Stats — Summary

  Session:     abc123 (started 2h 15m ago)
  Duration:    2h 15m active

  Tool Calls:  47 total
    Read:      18 (38%)
    Edit:      12 (26%)
    Bash:       8 (17%)
    Grep:       5 (11%)
    Write:      3 (6%)
    Agent:      1 (2%)

  Agents:      1 spawned (1 completed)

  Git:         3 commits, 8 files, +142/-37 lines

  Rate Limit:  5h: 32% used | 7d: 15% used
```

---

## Command: `tools` — Tool Usage Breakdown

### Steps

0. **Telemetry first (tier 1)**: If the telemetry API is reachable, prefer its
   real per-session tool data (`/api/llm/recent` filtered to the session, and
   `/api/llm/sessions/<sessionId>`) over the char/heuristic and git-only paths.
   Label counts **measured**. If unreachable, skip silently and use tier 2/3.

1. **Load all tool events** from telemetry (tier 1) or, if unavailable, from
   hooks log or conversation transcript.

2. **Group by tool name** — count calls per tool:
   - Core: Read, Edit, Write, Bash, Grep, Glob, Agent
   - Extended: MCP tools (mcp__*), WebFetch, WebSearch, NotebookEdit
   - Any other tool types discovered

3. **Success/failure ratio**: Cross-reference PreToolUse with PostToolUse vs
   PostToolUseFailure for each tool.

4. **Tool sequences** — identify common two-tool patterns:
   - Read then Edit (read-before-modify)
   - Grep then Read (search-then-read)
   - Edit then Bash (edit-then-test)
   Count the top 5 most frequent two-tool sequences by scanning consecutive
   PreToolUse events.

5. **Tool input sizes** — estimate per-call data volume:
   - Bash: command string length
   - Read: file content size from tool result
   - Edit: old_string + new_string character count
   - Agent: prompt length
   - Grep/Glob: result set size

6. **Hourly distribution** — if session spans more than one hour, bucket tool
   calls per clock hour to show activity waves.

### Report

```
Session Stats — Tool Usage

  Tool          Calls  Success  Failed  Avg Input Size
  ──────────────────────────────────────────────────────
  Read            18      18       0     2.1 KB
  Edit            12      11       1     1.4 KB
  Bash             8       7       1     0.3 KB
  Grep             5       5       0     0.1 KB
  Write            3       3       0     3.8 KB
  Agent            1       1       0     2.2 KB
  ──────────────────────────────────────────────────────
  Total           47      45       2     1.6 KB avg

  Common Sequences:
    Read -> Edit           8x (read-modify pattern)
    Grep -> Read           4x (search-read pattern)
    Edit -> Bash           3x (edit-test pattern)
    Bash -> Read           2x
    Read -> Read           2x

  Hourly Distribution:
    14:00  ============ 18
    15:00  ================ 22
    16:00  ===== 7
```

---

## Command: `agents` — Subagent Metrics

### Steps

0. **Telemetry first (tier 1)**: If the telemetry API is reachable, prefer its
   real per-session agent/tool records (`/api/llm/recent`,
   `/api/llm/sessions/<sessionId>`) over the char/heuristic and git-only paths.
   Label counts **measured**. If unreachable, skip silently and use tier 2/3.

1. **Load agent events** from telemetry (tier 1), or from hooks log
   (SubagentStart, SubagentStop) or conversation transcript (Agent tool calls).

2. **Per-agent metrics**:
   - Agent type (Explore, Plan, general-purpose, custom)
   - Duration (start timestamp to stop timestamp)
   - Tool calls within agent context (filter by agent_id field in hooks log)
   - Outcome (completed, error, timeout)

3. **Agent type distribution**: Count by type, average duration per type.

4. **Nesting depth**: Detect agents that spawned sub-agents (agent_id present
   on SubagentStart events within another agent context).

5. **Campaign agent cross-reference** (if data/tasks.json exists):
   - Match hook agent events to campaign agent records
   - Report files owned, model selection, complexity tier

### Report

```
Session Stats — Agent Activity

  Total Agents Spawned: 4

  Agent  Type             Duration  Tools  Outcome
  ─────────────────────────────────────────────────
  #1     Explore          0:45      8      completed
  #2     Explore          1:12      12     completed
  #3     general-purpose  3:22      24     completed
  #4     Plan             0:18      3      completed

  By Type:
    Explore:          2 (50%)  avg 0:58
    general-purpose:  1 (25%)  avg 3:22
    Plan:             1 (25%)  avg 0:18

  Nesting: 0 nested spawns (flat)

  Campaign Agents (if active):
    Agent A: 4 files, model=sonnet, status=done
    Agent B: 3 files, model=haiku, status=running
```

---

## Command: `timeline` — Activity Timeline

### Steps

1. **Build event timeline** from hooks log or conversation transcript, ordered
   by timestamp.

2. **Identify phases** by clustering consecutive tool calls:
   - Research: majority Read, Grep, Glob
   - Implementation: majority Edit, Write
   - Testing: Bash calls containing test/pytest/npm test/dotnet test patterns
   - Review: Read with small Edit changes
   A phase boundary occurs when the dominant tool category shifts.

3. **Mark milestones**: git commits (from git log timestamps), agent
   completions, plan state transitions.

4. **Calculate idle gaps**: periods longer than 5 minutes without tool activity
   (configurable via `[session-stats].phase_idle_threshold_min`).

### Report

```
Session Stats — Timeline

  14:02  SESSION START
  14:02  ---- Research Phase (12 min) ----
         Read x8, Grep x3, Glob x2
  14:14  ---- Implementation Phase (28 min) ----
         Edit x6, Write x2, Read x4, Bash x3
  14:20  [commit] fix: resolve auth token refresh bug
  14:42  ---- Agent: Explore (1 min) ----
         Read x5, Grep x3
  14:43  ---- Testing Phase (8 min) ----
         Bash x4 (test runs), Edit x2 (fixes)
  14:51  [commit] test: add regression tests for token refresh
  14:51  ---- idle 12 min ----
  15:03  ---- Review Phase (5 min) ----
         Read x3, Edit x1
  15:08  CURRENT
```

---

## Command: `compare` — Cross-Session Comparison

### Steps

1. **Find recent sessions**: Group hooks log events by session_id, or list
   conversation files sorted by modification time.

2. **Extract per-session metrics**: tool count, agent count, duration, dominant
   tool, top tool percentage.

3. **Compute deltas**: Compare current session against the running average.

4. **Identify trends**: increasing or decreasing tool usage, agent reliance,
   session duration over time.

### Report

```
Session Stats — Comparison (last 5 sessions)

  Session      Date        Duration  Tools  Agents  Top Tool
  ───────────────────────────────────────────────────────────
  abc123 <-    today       2h 15m    47     1       Read (38%)
  def456       yesterday   1h 40m    32     0       Edit (41%)
  ghi789       2 days ago  3h 05m    68     3       Read (35%)
  jkl012       3 days ago  0h 45m    15     0       Bash (47%)
  mno345       4 days ago  2h 30m    52     2       Read (40%)

  Averages:    2h 03m    42.8 tools/session    1.2 agents/session
  This session: +12m      +4.2 tools           -0.2 agents

  Trends:
    Tool usage: stable (+/- 10%)
    Agent usage: decreasing (-40% over 5 sessions)
    Session length: stable
```

---

## Command: `export` — Export as JSON

Export all session metrics as a single JSON object for external tooling or
downstream skill consumption.

### Steps

1. Run the same collection pipeline as `summary` + `tools` + `agents`.
2. Output as a single JSON object — no markdown, no commentary.

### Output

```json
{
  "session_id": "abc123",
  "started_at": "2026-03-28T14:02:00Z",
  "duration_minutes": 135,
  "tool_calls": {
    "total": 47,
    "by_tool": {"Read": 18, "Edit": 12, "Bash": 8, "Grep": 5, "Write": 3, "Agent": 1},
    "success_rate": 0.957,
    "failed": 2
  },
  "agents": {
    "total": 1,
    "by_type": {"Explore": 0, "general-purpose": 1, "Plan": 0},
    "completed": 1,
    "failed": 0
  },
  "git": {
    "commits": 3,
    "files_changed": 8,
    "insertions": 142,
    "deletions": 37
  },
  "data_sources": ["telemetry_api", "hooks_log", "git"],
  "data_tier": "measured"
}
```

`data_tier` reflects the highest tier that produced the numbers:
`measured` (telemetry API), `hooks` (tier 2 log / transcript), or
`estimated` (tier 3 character heuristic).

---

## Config (project.toml)

Optional `[session-stats]` section:

```toml
[session-stats]
# telemetry_url = "http://127.0.0.1:8099"
# hooks_log = ".claude/hooks/logs/hooks-log.jsonl"
# history_sessions = 10
# phase_idle_threshold_min = 5
```

---

## Integration

| Skill | How Session Stats Helps |
|-------|------------------------|
| `/observer` | Feed tool patterns as observations for project intelligence |
| `/campaign-health` | Supplement campaign metrics with session-level tool detail |
| `/token-audit` | Session-stats provides tool counts; token-audit adds cost analysis |
| `/agent-report` | Agent counts from session-stats feed agent performance analytics |
| `/ship` | Include session summary in commit messages or PR descriptions |

---

## Conventions

- Read-only: never modify logs, conversations, or state files
- Adapt to available data sources — degrade gracefully, never hard-fail
- Data-tier precedence: (1) telemetry HTTP API → label **measured**;
  (2) hooks JSONL log / conversation transcript → tier 2; (3) character
  heuristic → label **estimated ~approximate**. The telemetry service is
  optional; a 2s `/health` probe gates it and an unreachable port falls
  through silently to tier 2/3.
- Report which data sources were found and used in every report
- Use plain text for reports (no ANSI colors — terminal-portable)
- Session boundaries: use session_id from hooks, or conversation file boundaries
- Tool names use Claude Code canonical names (Read, Edit, Write, Bash, Grep, Glob, Agent)
