---
name: session-stats
description: Analyze session tool usage, agent activity, and timing from available data sources (telemetry API, hooks log, campaign state, git activity, observer data) for cross-session comparisons or end-of-session summaries
---

# Session Stats Protocol

## Core Mandate
On-demand analytics dashboard for the current session. Parse available data sources to produce tool-usage breakdowns, agent activity metrics, activity timelines, and cross-session comparisons. All commands run to completion autonomously.

## Execution Rules
1. **Light guardrails:** Follow the global guardrails in GEMINI.md. This is a read-only ops/analytics skill — do not gate it on the planning workflow.
2. **Read-only:** Never modify logs, conversations, or state files.
3. **Degrade gracefully:** Adapt to available data sources; never hard-fail. Report which sources were found and which data tier produced each number.
4. **Evidence over intuition:** Label telemetry numbers as **measured**, hooks/transcript numbers as tier 2, and character-heuristic numbers as **estimated ~approximate**.

## Config
Optional `[session-stats]` section in project.toml:
```toml
[session-stats]
# telemetry_url = "http://127.0.0.1:8099"
# hooks_log = ".gemini/hooks/logs/hooks-log.jsonl"
# history_sessions = 10
# phase_idle_threshold_min = 5
```

## Data Sources (precedence order)
Discover sources before any command. The first reachable tier is authoritative; lower tiers fill gaps it does not cover. Always report WHICH tier produced the numbers.

1. **Telemetry HTTP API** (tier 1 — authoritative, real hook-captured measurements). A local telemetry service (the ollama-telemetry repo) optionally exposes real per-session token/cost/tool data over HTTP. **Optional** — probe first, never hard-require:
   ```bash
   # Reachability probe gates the whole API path (2s budget):
   curl -s --max-time 2 http://127.0.0.1:8099/health >/dev/null && echo REACHABLE
   ```
   Base URL is configurable via `[session-stats].telemetry_url` (default `http://127.0.0.1:8099`). If reachable, prefer it over the char/heuristic and git-only paths:
   ```bash
   curl -s --max-time 2 "http://127.0.0.1:8099/api/llm/overview?hours=8"
   curl -s --max-time 2 "http://127.0.0.1:8099/api/llm/recent?limit=200"
   curl -s --max-time 2 "http://127.0.0.1:8099/api/llm/sessions/<sessionId>"
   ```
   Response JSON is **camelCase**: `totalInputTokens`, `totalOutputTokens`, `totalCostUsd`, `cacheReadTokens`, plus session-level totals. (snake_case like `cache_read_tokens` is ONLY the `/api/llm/ingest` request body — never read it from responses.) Label all tier-1 numbers as **measured**. If port 8099 is unreachable, fall through **silently** to tier 2/3 — never hard-fail and never block on it.

2. **Hooks JSONL log** (tier 2 — richest local source for tool events): `ls -la .gemini/hooks/logs/hooks-log.jsonl 2>/dev/null`. If present, contains timestamped tool events with session_id, tool_name, tool_input, agent_id.

3. **Git activity** (code-level metrics for the session window): `git log --oneline --since="8 hours ago" --format="%H %ai %s"`.

4. **Observer data** (if observer skill is active): `ls data/observations.jsonl 2>/dev/null`.

5. **Campaign state** (if campaign skills are active): `ls data/tasks.json data/plans/*.json 2>/dev/null`.

If **no sources found**, report clearly and suggest: install hooks for tool-level tracking, enable observer for project-level metrics, or run after some session activity has accumulated.

## Commands
- `/session-stats` or `/session-stats summary` — quick session overview (default)
- `/session-stats tools` — tool usage breakdown with counts and patterns
- `/session-stats agents` — subagent spawning, types, and outcomes
- `/session-stats timeline` — activity timeline with phases
- `/session-stats compare [N]` — compare last N sessions (default 5)
- `/session-stats export` — export session metrics as JSON

Default to `summary` if no command given.

### `summary`
0. **Telemetry first (tier 1):** If the API is reachable, prefer it for token/tool/session totals — `/api/llm/overview?hours=8` and `/api/llm/sessions/<sessionId>` once a sessionId is known. Use these **measured** numbers in place of the char/heuristic and git-only paths. If unreachable, skip silently and use the tiers below exactly as today.
1. Identify current session — most recent session_id from telemetry (tier 1) or hooks log, else the current working window.
2. Count tool calls by type — from telemetry per-session data when tier 1 is available; otherwise from hooks log PreToolUse events. If no hooks log, fall back to git log + observer data for a coarser picture.
3. Count agent spawns (SubagentStart/SubagentStop) if available.
4. Session duration — first to last event timestamp within the session, else first/last commit in the session window.
5. Git activity — commits, files changed, insertions/deletions (`git log --since="8 hours ago" --format="%H" | wc -l`; `git diff --stat HEAD~3 | tail -1`).

Report tool calls, agents, git metrics. Omit tool/agent sections if only git data is available.

### `tools`
0. **Telemetry first (tier 1):** If reachable, prefer real per-session tool data (`/api/llm/recent` filtered to the session, and `/api/llm/sessions/<sessionId>`) over the char/heuristic and git-only paths. Label counts **measured**. If unreachable, skip silently and use tier 2/3.
1. Load all tool events from telemetry (tier 1) or, if unavailable, the hooks log.
2. Group by tool name (core: Read, Edit, Write, Bash, Grep, Glob, Agent; extended: MCP tools, WebFetch, WebSearch; plus any others discovered).
3. Success/failure ratio — cross-reference PreToolUse with PostToolUse vs PostToolUseFailure.
4. Tool sequences — top two-tool patterns (Read→Edit, Grep→Read, Edit→Bash).
5. Tool input sizes — estimate per-call data volume.
6. Hourly distribution — bucket calls per clock hour when the session spans more than one hour.

If neither the telemetry API (tier 1) nor the hooks log (tier 2) is available, report that telemetry or hooks instrumentation is required and exit with guidance.

### `agents`
0. **Telemetry first (tier 1):** If reachable, prefer real per-session agent/tool records (`/api/llm/recent`, `/api/llm/sessions/<sessionId>`) over the char/heuristic and git-only paths. Label counts **measured**. If unreachable, skip silently and use tier 2/3.
1. Load agent events from telemetry (tier 1), or from hooks log (SubagentStart, SubagentStop) or `data/tasks.json` for orchestrated campaign agents.
2. Per-agent metrics: type, duration, tool calls within agent context, outcome (completed/error/timeout).
3. Agent type distribution: count by type, average duration per type.
4. Campaign cross-reference (if `data/tasks.json` exists): files owned, model selection, complexity tier.

### `timeline`
1. Build an event timeline from telemetry, hooks log, or git log, ordered by timestamp.
2. Identify phases by clustering consecutive tool calls — Research (Read/Grep/Glob), Implementation (Edit/Write), Testing (Bash with test/pytest/npm-test patterns), Review (Read with small Edits).
3. Mark milestones: git commits, agent completions, plan state transitions.
4. Calculate idle gaps — periods longer than `[session-stats].phase_idle_threshold_min` minutes (default 5) without tool activity.

### `compare [N]`
1. Find recent sessions — group telemetry/hooks events by session_id, or list git activity by day.
2. Extract per-session metrics: tool count, agent count, duration, dominant tool, top-tool percentage.
3. Compute deltas against the running average and identify trends (tool usage, agent reliance, session length over time).

### `export`
Run the same collection pipeline as `summary` + `tools` + `agents`. Output a single JSON object — no markdown, no commentary:
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
  "agents": {"total": 1, "completed": 1, "failed": 0},
  "git": {"commits": 3, "files_changed": 8, "insertions": 142, "deletions": 37},
  "data_sources": ["telemetry_api", "hooks_log", "git"],
  "data_tier": "measured"
}
```
`data_tier` reflects the highest tier that produced the numbers: `measured` (telemetry API), `hooks` (tier 2 log / transcript), or `estimated` (tier 3 character heuristic).

## Output Contract
- Use plain text for reports (no ANSI colors — terminal-portable).
- Report which data sources were found and which tier produced each number, in every report.
- Session boundaries: use session_id from telemetry/hooks, else git activity windows.

## Integration
| Skill | How Session Stats Helps |
|-------|------------------------|
| `/observer` | Feed tool patterns as observations for project intelligence |
| `/campaign-health` | Supplement campaign metrics with session-level tool detail |
| `/token-audit` | Session-stats provides tool counts; token-audit adds cost analysis |
| `/agent-report` | Agent counts from session-stats feed agent performance analytics |
| `/ship` | Include session summary in commit messages or PR descriptions |
