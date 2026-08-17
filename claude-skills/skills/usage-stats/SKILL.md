---
name: usage-stats
description: "Track token consumption, cost, budgets, and rate-limit forecasts; analyze session tool/agent/timeline activity; and report agent and campaign performance — telemetry-first (measured) with heuristic fallback (estimated). Use when reviewing session cost or usage, setting budgets, forecasting rate-limit pressure, summarizing or comparing sessions, or evaluating agent efficiency and model selection."
argument-hint: "<summary|cost|breakdown|budget|forecast|history|tools|agents|timeline|compare|efficiency|trends|export> — usage, cost & agent analytics"
allowed-tools: Read, Glob, Grep, Bash, Edit, Write
user-invocable: true
disable-model-invocation: true
extracted-from: Ai-Skills
portable-since: 2026-08-17
---

# Usage Stats — Usage, Cost & Agent Analytics

Unified analytics over token consumption, session activity, and agent
performance — the former `token-audit`, `session-stats`, and `agent-report`
skills merged over a single shared data layer.
Complements claude-lens (real-time quota display) with analytical depth and
historical tracking.

**All commands run to completion autonomously.**

**Config:** `.claude/skills/project.toml` — `[usage-stats]` and `[pricing]` sections (optional)

---

## Commands

Three routed groups. Default to `summary` if no command given.

**Token & cost intelligence** (formerly token-audit):

| Command | Usage | Purpose |
|---------|-------|---------|
| `cost` | `/usage-stats cost` | Current token position, burn rate, budget check |
| `breakdown` | `/usage-stats breakdown` | Per-tool and per-turn token cost attribution |
| `budget` | `/usage-stats budget [set <N>\|check\|reset]` | Session or daily budget management |
| `forecast` | `/usage-stats forecast` | Rate-limit proximity and depletion forecast |
| `history` | `/usage-stats history [N]` | Usage trends across last N sessions (default 7) |

**Session analytics** (formerly session-stats):

| Command | Usage | Purpose |
|---------|-------|---------|
| `summary` | `/usage-stats` or `/usage-stats summary` | Quick session overview |
| `tools` | `/usage-stats tools` | Tool usage breakdown with counts and patterns |
| `timeline` | `/usage-stats timeline` | Activity timeline with phases |
| `compare` | `/usage-stats compare [N]` | Compare last N sessions (default 5) |
| `export` | `/usage-stats export` | Export session metrics as JSON |

**Agent performance** (formerly agent-report):

| Command | Usage | Purpose |
|---------|-------|---------|
| `agents` | `/usage-stats agents [agent-id]` | Agent overview, or deep dive on one agent |
| `efficiency` | `/usage-stats efficiency` | Model selection cost analysis |
| `trends` | `/usage-stats trends [N]` | Cross-campaign performance trends (default 5) |

---

## Setup: Discover Data Sources

Before any command, locate data sources. They form a strict **precedence
ladder** — always prefer a higher tier, and always report WHICH tier produced
the numbers:

- **Tier 1 — Telemetry HTTP API (measured, authoritative):** real,
  hook-captured token/cost/tool data from the local ollama-telemetry service.
- **Tier 2 — Hooks JSONL log / conversation transcript (semi-measured):**
  tool call metadata with timestamps; sizing derived from logged inputs/outputs.
- **Tier 3 — Character heuristic (estimated ~approximate):** last-resort
  ~4-chars/token estimate from transcript/log text.

Numbers are labelled **measured** when sourced from Tier 1 and
**estimated ~approximate** when derived from Tier 3 — never present heuristic
numbers as exact.

1. **Telemetry HTTP API** (Tier 1 — preferred when reachable). Base URL is
   configurable via `[usage-stats].telemetry_url` (default
   `http://127.0.0.1:8099`). It is **optional** — probe it, never
   hard-require it:
   ```bash
   # Reachability probe gates the API path (2s budget). If this fails,
   # fall through silently to Tier 2/3 — never block on it.
   curl -s --max-time 2 http://127.0.0.1:8099/health
   ```
   When reachable, read real totals (camelCase JSON under `/api/llm`):
   ```bash
   # Aggregate window totals
   curl -s --max-time 2 "http://127.0.0.1:8099/api/llm/overview?hours=24"
   # Per-session totals (use the current session id when known)
   curl -s --max-time 2 "http://127.0.0.1:8099/api/llm/sessions/<sessionId>"
   # Recent events (optionally filter by provider/type/machineId)
   curl -s --max-time 2 "http://127.0.0.1:8099/api/llm/recent?limit=50"
   ```
   Response fields are camelCase: `totalInputTokens`, `totalOutputTokens`,
   `totalCostUsd`, `cacheReadTokens`, plus session-level totals. (snake_case
   such as `cache_read_tokens` is ONLY the `/api/llm/ingest` request body —
   never read it from responses.)

2. **Hooks JSONL log** (Tier 2 — richest local source for tool events, if
   hooks instrumentation is configured for this installation):
   ```bash
   ls .claude/hooks/logs/hooks-log.jsonl 2>/dev/null
   ```
   Contains timestamped tool events with session_id, tool_name, tool_input,
   agent_id; SubagentStart/SubagentStop events carry agent_type and agent_id.
   Parse with jq or python3's json module.

3. **Conversation transcripts** (Tier 2/3 input for per-message sizing):
   ```bash
   # macOS / Linux
   ls -t ~/.claude/projects/*/conversations/*.jsonl 2>/dev/null | head -5
   # Windows
   ls -t "$USERPROFILE/.claude/projects/"*/conversations/*.jsonl 2>/dev/null | head -5
   ```
   Find the latest file matching the current project directory hash.

4. **Rate-limit cache** (if a statusline or similar surface is active):
   ```bash
   ls /tmp/claude-sl-usage 2>/dev/null    # Unix lens cache
   ```

5. **Campaign and agent state** (primary agent source when hooks are absent):
   read `[paths].state` from project.toml (default `data/tasks.json`) for
   orchestrated agents (name, model, status, complexity, files owned), plus
   `data/plans/*.json` (assignments, complexity tiers) and `agents/agent-*.md`
   (scope and instructions) when present. Per-agent commits are recoverable
   from worktree branches:
   ```bash
   git log --all --format="%H %ai %s" | grep -i "agent\|worktree\|wt-" | head -20
   ```

6. **Git activity** (code-level metrics for the session window):
   ```bash
   git log --oneline --since="8 hours ago" --format="%H %ai %s"
   ```

7. **Observer data** (if observer skill is active): `data/observations.jsonl`,
   including agent-linked observations (`grep '"agent"'`).

8. **Budget and history files** (managed by this skill):
   `data/token-budget.json`, `data/token-history.jsonl`.

9. **Pricing config** in project.toml `[pricing]` (when absent, follow the
   *Model pricing* rule below).

Report which sources were found. Commands adapt to available data — more
sources produce richer analysis. If **no data sources found**, report clearly
and suggest: install hooks for tool-level tracking, enable observer for
project-level metrics, or re-run after some session activity has accumulated.

---

## Estimation & Pricing Method

When the telemetry API (Tier 1) is reachable, prefer its **measured** totals.
Claude Code transcripts do not expose exact per-message token counts, so when
telemetry is **not** reachable fall back to this estimation pipeline:

1. **Character-based heuristic** (Tier 3, last resort): ~4 characters = 1 token
   for English text; ~3.5 for code-heavy content (symbols are often individual
   tokens). Configurable via `[usage-stats].chars_per_token`. Label these
   numbers as **estimated ~approximate**.

2. **Message role weighting**: user messages, tool results returned to the
   model, and system/CLAUDE.md content count as input tokens (amortize
   system content across turns); assistant messages and tool call parameters
   count as output tokens.

3. **Per-tool estimation** (from hooks log tool_input or transcript content):
   - Read: file content returned as tool result -> input tokens (bytes / 3.5)
   - Bash: command output returned -> input tokens (output bytes / 4)
   - Edit: old_string + new_string -> small output token count
   - Agent: full prompt -> output tokens; agent result -> input tokens
   - Grep/Glob: result set -> input tokens
   - Write: file content -> output tokens

4. **Model pricing** from the `[pricing]` config. Never price from memory:
   when `[pricing]` is absent, prefer Tier 1 telemetry cost totals (already
   priced at ingestion time); otherwise look up the provider's current
   published rates and label the source. If neither is available, report token
   counts without dollar figures rather than inventing prices.

All estimates are clearly labelled as approximate. Actual API billing may
differ due to caching, batching, and prompt caching discounts.

---

## Command: `cost` — Current Token Position

1. **Size session tokens (follow the ladder)**: Tier 1 — GET
   `/api/llm/sessions/<sessionId>` (and/or `/api/llm/overview?hours=N`) and
   read `totalInputTokens`, `totalOutputTokens`, `totalCostUsd`,
   `cacheReadTokens`; report as **measured**. Tier 2/3 — parse the transcript
   or hooks log and apply the character heuristic; sum input (user messages +
   tool results) and output (assistant messages + tool call parameters).

2. **Session cost**: Tier 1 uses `totalCostUsd` directly; Tier 2/3 multiplies
   token estimates by model pricing. If session totals expose a cache-read or
   savings figure (e.g. `cacheReadTokens`), add a "real cost avoided" note —
   do not invent field names beyond the verified contract.

3. **Rate limit position** (if rate-limit data available): 5-hour and 7-day
   windows — used percentage, time remaining, effective burn rate (tokens/hour).

4. **Budget check**: if `data/token-budget.json` exists, compare current usage
   against the configured limits.

```
Usage Stats — Cost

  Data tier: Tier 1 — telemetry API (measured)
             [or: Tier 3 — character heuristic (estimated ~approximate)]

  Session Tokens (measured):
    Input 285K ($1.43) | Output 42K ($1.05) | Total 327K ($2.48 measured)
    Cache reads: 180K tokens (real cost avoided)

  Burn Rate:   current ~145K tokens/hour, sustained ~120K tokens/hour
  Rate Limits: 5h window 32% used (3h 28m left) | 7d window 15% used
  Budget:      Daily $2.48 / $10.00 (24.8%)  ON TRACK
```

---

## Command: `breakdown` — Cost Attribution

1. **Anchor totals to the best tier**: with Tier 1 reachable, pull session
   totals from `/api/llm/sessions/<sessionId>` as the **measured** ground
   truth. Per-tool attribution is still derived from the hooks log /
   transcript, but reconcile it — scale the heuristic per-tool shares so they
   sum to the measured total. Without telemetry, the whole breakdown is
   **estimated ~approximate**. Report which tier anchored the totals.

2. **Group by tool type**: per tool call, estimate output tokens (the call:
   tool name + parameters) and input tokens (the result returned to the model).

3. **Group by conversation turn**: track turn number, user input size,
   assistant output size, tools invoked.

4. **Identify heavy operations** — flag the top 3-5 most token-expensive
   turns: large file reads (> 500 lines), verbose bash outputs, agent spawns
   (full prompt + returned result), compaction events.

5. **Compute overhead**: system prompt, conversation history, and CLAUDE.md
   content sent with every request but not attributable to a single tool.

```
Usage Stats — Breakdown

  By Tool (estimated tokens consumed):
    Tool       Calls  Input Tokens  Output Tokens  Est. Cost
    ──────────────────────────────────────────────────────────
    Read         18     180K            0.5K        $0.90
    Bash          8      45K            2K          $0.28
    Edit         12       2K           18K          $0.46
    ──────────────────────────────────────────────────────────
    Subtool      47     264K           37K          $2.24
    Overhead*                                       $0.24
    Total                                           $2.48

  * Overhead: system prompts, CLAUDE.md, conversation history

  Heaviest Turns:
    Turn 5:  ~45K tokens (large file read: src/engine.py, 1200 lines)
    Turn 12: ~38K tokens (agent spawn: codebase research)

  Optimization Tips:
    - Use offset/limit on Read for large files (only read the part you need)
    - Pipe bash output through head/tail to limit result size
    - Prefer Explore agent for multi-file searches over sequential reads
```

---

## Command: `budget` — Budget Management

#### `/usage-stats budget set <amount>`

Set a session or daily budget in USD. Create or update
`data/token-budget.json`:
```json
{
  "daily_budget_usd": 10.00,
  "session_budget_usd": 5.00,
  "set_at": "2026-03-28T14:00:00Z",
  "alert_threshold_pct": 80
}
```
Parse the amount from the argument — accept formats like `$10`, `10.00`,
`session:5 daily:10`. Confirm: "Budget set to $X.XX per session / $Y.YY per day".

#### `/usage-stats budget check`

Read `data/token-budget.json`, estimate current session cost (same method as
`cost`), compare against limits, and report ON TRACK / WARNING (>= alert
threshold) / EXCEEDED:

```
Usage Stats — Budget Check

  Session:  $2.48 / $5.00 (49.6%)  ON TRACK
  Daily:    $7.23 / $10.00 (72.3%) WARNING — approaching 80% threshold
  At current burn rate: session budget exhausts in ~1h 45m, daily in ~1h 15m
```

#### `/usage-stats budget reset`

Reset daily usage counters — keep the budget limits, clear the accumulated
spend tracking.

---

## Command: `forecast` — Rate Limit Forecast

1. **Current rate limit position**: parse from any available rate-limit cache,
   hooks log event frequency, or transcript size growth.

2. **Depletion time**: at the current burn rate, when does each window hit
   100%? (remaining capacity / current hourly or daily burn)

3. **Pace adjustments**: if burning faster than sustainable, recommend
   reduced effort level (effort=default instead of high), Read with
   offset/limit instead of full-file reads, batching related questions into
   fewer turns, and `haiku`-tier agents for research tasks; if
   well ahead of pace, report available headroom.

4. **Historical comparison**: if `data/token-history.jsonl` exists, compare
   current burn rate against the historical average.

```
Usage Stats — Forecast

  5-Hour Window:
    Used: 32% | Remaining: 3h 28m | Burn rate: 9.5%/hour
    At this rate: hits 100% in 7h 10m (2h 42m of headroom)
    Pace: COMFORTABLE

  7-Day Window:
    Used: 15% | Remaining: 6d 2h | Burn rate: 2.1%/day
    Pace: COMFORTABLE

  Recommendations:
    (none — usage is well within limits; otherwise list pace adjustments)
```

---

## Command: `history` — Usage Trends

1. **Load historical snapshots** from `data/token-history.jsonl`:
   ```json
   {"session_id": "abc123", "date": "2026-03-28", "duration_min": 135, "est_input_tokens": 285000, "est_output_tokens": 42000, "est_cost_usd": 2.48, "tool_calls": 47, "agents": 1}
   ```

2. **If no history file exists**, retroactively build it: Tier 1 — scan
   `/api/llm/overview?hours=N` (widen N to cover the window) and/or
   `/api/llm/sessions/<sessionId>` per known session for **measured**
   per-session totals; Tier 2/3 — scan the hooks log for distinct session_id
   values and apply the character heuristic. Write results to
   `data/token-history.jsonl`, tagging each row's source tier so measured and
   estimated sessions stay distinguishable.

3. **Compute trends**: daily average cost, tokens/cost/tools per session.
   Report which tier produced each number (mixed rows are possible).

4. **Identify anomalies**: sessions more than 2 standard deviations above the
   mean cost.

```
Usage Stats — History (last 7 sessions)

  Date        Session    Duration  Tokens   Cost    Tools
  ─────────────────────────────────────────────────────────
  Mar 28      abc123     2h 15m    ~327K    $2.48     47
  Mar 27      def456     1h 40m    ~210K    $1.62     32

  7-Session Averages:  306K tokens, $2.31, 42.8 tools, 2h 03m
  Trend: Cost stable ($2.31 avg, +/- $0.87 std dev)
```

**Auto-snapshot**: at the end of each `history` command, append the current
session's metrics to `data/token-history.jsonl` if not already present (keyed
by session_id to prevent duplicates).

---

## Command: `summary` — Quick Session Overview

1. **Telemetry first**: with Tier 1 reachable, pull `/api/llm/overview?hours=8`
   and, once a sessionId is known, `/api/llm/sessions/<sessionId>` for
   **measured** token/tool/session totals. Otherwise use the tiers below.

2. **Identify current session**: most recent session_id from telemetry or the
   hooks log, or the latest conversation file.

3. **Count tool calls** by type — from telemetry per-session data when
   available, else from hooks log PreToolUse events (parse the JSONL with
   python3/jq, count by tool_name); failing that, parse the transcript for
   tool_use blocks, then fall back to git log + observer data for a coarser
   picture.

4. **Count agent spawns**: SubagentStart/SubagentStop events when hooks
   instrumentation is active.

5. **Session duration**: first to last event timestamp within the session_id.

6. **Git activity during session**: commits, files changed,
   insertions/deletions (`git log --since`, `git diff --stat`).

7. **Rate limit position**: read from any accessible rate-limit cache
   (e.g., `/tmp/claude-sl-usage` on Unix).

```
Usage Stats — Summary

  Session:     abc123 (started 2h 15m ago), 2h 15m active
  Tool Calls:  47 total — Read 18 (38%), Edit 12 (26%), Bash 8 (17%),
               Grep 5 (11%), Write 3 (6%), Agent 1 (2%)
  Agents:      1 spawned (1 completed)
  Git:         3 commits, 8 files, +142/-37 lines
  Rate Limit:  5h: 32% used | 7d: 15% used   (if available)
```

If the hooks log is missing, omit the Tool Calls and Agents sections and
report only the git-derived metrics.

---

## Command: `tools` — Tool Usage Breakdown

1. **Load all tool events** from telemetry (Tier 1 — `/api/llm/recent`
   filtered to the session, `/api/llm/sessions/<sessionId>`; label counts
   **measured**), else the hooks log or transcript. If none exists, report
   that telemetry or hooks instrumentation is required and exit with guidance.

2. **Group by tool name**: core (Read, Edit, Write, Bash, Grep, Glob, Agent),
   extended (MCP tools `mcp__*`, WebFetch, WebSearch, NotebookEdit), and any
   other tool types discovered.

3. **Success/failure ratio**: cross-reference PreToolUse with PostToolUse vs
   PostToolUseFailure per tool.

4. **Tool sequences**: count the top 5 two-tool patterns from consecutive
   PreToolUse events — e.g. Read->Edit (read-before-modify), Grep->Read
   (search-then-read), Edit->Bash (edit-then-test).

5. **Tool input sizes**: estimate per-call data volume (Bash command length,
   Read result size, Edit old+new length, Agent prompt length, Grep/Glob
   result set size).

6. **Hourly distribution**: if the session spans more than one hour, bucket
   tool calls per clock hour to show activity waves.

```
Usage Stats — Tool Usage

  Tool          Calls  Success  Failed  Avg Input Size
  ──────────────────────────────────────────────────────
  Read            18      18       0     2.1 KB
  Edit            12      11       1     1.4 KB
  ──────────────────────────────────────────────────────
  Total           47      45       2     1.6 KB avg

  Common Sequences:
    Read -> Edit   8x (read-modify)     Grep -> Read   4x (search-read)

  Hourly Distribution:
    14:00  ============ 18
    15:00  ================ 22
```

---

## Command: `timeline` — Activity Timeline

1. **Build event timeline** from hooks log, transcript, or git log, ordered by
   timestamp.

2. **Identify phases** by clustering consecutive tool calls: Research
   (majority Read/Grep/Glob), Implementation (majority Edit/Write), Testing
   (Bash calls with test/pytest/npm test/dotnet test patterns), Review (Read
   with small Edit changes). A phase boundary occurs when the dominant tool
   category shifts.

3. **Mark milestones**: git commits, agent completions, plan state transitions.

4. **Calculate idle gaps**: periods longer than 5 minutes without tool
   activity (configurable via `[usage-stats].phase_idle_threshold_min`).

```
Usage Stats — Timeline

  14:02  SESSION START
  14:02  ---- Research Phase (12 min) ----      Read x8, Grep x3, Glob x2
  14:14  ---- Implementation Phase (28 min) --  Edit x6, Write x2, Bash x3
  14:20  [commit] fix: resolve auth token refresh bug
  14:43  ---- Testing Phase (8 min) ----        Bash x4 (tests), Edit x2
  14:51  ---- idle 12 min ----
  15:03  ---- Review Phase (5 min) ----
  15:08  CURRENT
```

---

## Command: `compare` — Cross-Session Comparison

1. **Find recent sessions**: group hooks log events by session_id, list
   conversation files by modification time, or fall back to git activity
   grouped by day.

2. **Extract per-session metrics**: tool count, agent count, duration,
   dominant tool and its percentage.

3. **Compute deltas** against the running average, and **identify trends**:
   tool usage, agent reliance, session duration over time.

```
Usage Stats — Comparison (last 5 sessions)

  Session      Date        Duration  Tools  Agents  Top Tool
  ───────────────────────────────────────────────────────────
  abc123 <-    today       2h 15m    47     1       Read (38%)
  def456       yesterday   1h 40m    32     0       Edit (41%)

  Averages:    2h 03m    42.8 tools/session    1.2 agents/session
  This session: +12m      +4.2 tools           -0.2 agents
  Trends: tool usage stable; agent usage decreasing; length stable
```

---

## Command: `export` — Export as JSON

Run the same collection pipeline as `summary` + `tools` + `agents`, then
output a single JSON object — no markdown, no commentary — for external
tooling or downstream skill consumption:

```json
{
  "session_id": "abc123",
  "started_at": "2026-03-28T14:02:00Z",
  "duration_minutes": 135,
  "tool_calls": {"total": 47, "by_tool": {"Read": 18, "Edit": 12, "Bash": 8, "Grep": 5, "Write": 3, "Agent": 1}, "success_rate": 0.957, "failed": 2},
  "agents": {"total": 1, "by_type": {"general-purpose": 1}, "completed": 1, "failed": 0},
  "git": {"commits": 3, "files_changed": 8, "insertions": 142, "deletions": 37},
  "data_sources": ["telemetry_api", "hooks_log", "git"],
  "data_tier": "measured"
}
```

`data_tier` reflects the highest tier that produced the numbers: `measured`
(telemetry API), `hooks` (tier 2 log / transcript), or `estimated` (tier 3
character heuristic).

---

## Command: `agents` — Agent Overview & Deep Dive

Covers session subagents (hooks events) and campaign agents (from
`/manager` orchestration). Complements `/campaign-health` (state
and stuck detection) with performance-focused metrics.

### `/usage-stats agents` — overview

1. **Collect subagent data** from telemetry (Tier 1) or hooks log:
   SubagentStart/SubagentStop pairs matched by agent_id give type, duration,
   and outcome; PreToolUse/PostToolUse events filtered by agent_id give
   per-agent tool counts and error rates. Skip if hooks instrumentation is
   not active.

2. **Collect campaign agents** from tasks.json (if exists): name, model,
   status (pending/running/done/failed), complexity tier, files owned,
   dependency relationships, timestamps.

3. **Merge sources**: correlate hook subagent events with campaign agent
   records by timing window and worktree name where possible.

4. **Compute aggregates**: total agents, completion rate (done / (done +
   failed)), average duration, average tool calls, model distribution,
   nesting depth (agents that spawned sub-agents).

```
Usage Stats — Agents

  Subagents (this session, when hooks instrumentation is active):
    Total: 4 spawned, 4 completed, 0 failed
    Avg duration: 1m 24s   Avg tools: 11.8 per agent
    By type: Explore 2 (avg 0:58, 100%), general 1 (avg 3:22, 100%)

  Campaign Agents (active campaign): 6 agents across 1 plan
    Status: 4 done, 1 running, 1 pending

    Agent            Model    Status   Files  Complexity
    ──────────────────────────────────────────────────────
    A-contracts      haiku    done       3    low
    B-core-refactor  sonnet   done       5    medium
    D-integration    opus     done       2    high
```

### `/usage-stats agents <agent-id>` — deep dive

Accept a subagent ID from the hooks log (e.g. `agent-abc123`), a campaign
agent name (e.g. `B-core-refactor`), or a positional reference (`#2`).

1. **Tool breakdown**: counts per tool type and the chronological tool
   sequence (from hooks log if available, else git log).
2. **File activity**: files read, files modified with line deltas (from the
   agent's worktree branch or the campaign files_owned list).
3. **Timeline**: chronological tool calls with relative timestamps.
4. **Cost estimate**: estimated tokens in/out at the agent's model pricing.

```
Usage Stats — Agent Detail: B-core-refactor

  Type: Campaign agent (Plan: plan-012)   Model: sonnet
  Complexity: medium   Status: done   Duration: 12m 45s

  Tool Usage:  Read 12, Edit 8 (1 failed), Bash 4, Grep 3, Write 1 — 28 total
  Files Touched:
    Modified: src/core/engine.py (+45/-12), tests/test_engine.py (+38/-5)
  Estimated Cost: $0.42 (input ~35K, output ~8K at sonnet rates)
  Timeline (if hooks log available):
    00:00  Read engine.py   03:20  Edit engine.py x4   11:00  tests pass
```

---

## Command: `efficiency` — Model Selection Analysis

1. **Load campaign agents** with model assignments and complexity tiers from
   tasks.json and plan files.

2. **Calculate cost scenarios** using `estimate_campaign_savings()` from
   telemetry.py or equivalent logic: tiered cost (actual assignments),
   all-Opus cost, all-Haiku cost, savings from tiered
   selection vs all-Opus.

3. **Evaluate model-task fit**: did high-complexity tasks on Opus
   succeed without retries? Did low-complexity tasks on Haiku succeed?
   Any failures suggesting an underpowered model, or easy successes suggesting
   a downgrade candidate?

4. **Per-model tool efficiency**: average tool calls per agent across model
   tiers — more capable models may need fewer calls for the same outcome.

```
Usage Stats — Model Efficiency

  Campaign: plan-012 (6 agents)

  Cost Comparison:
    Tiered (actual) $1.85 | All-Opus $3.40 | All-Haiku $0.68
    Savings vs Opus: $1.55 (45.6%)

  Model Distribution:
    haiku:   3 agents (low complexity)   — $0.21 avg, 100% success
    sonnet:  2 agents (medium complexity) — $0.42 avg, 100% success
    opus:    1 agent  (high complexity)   — $0.38 avg, 100% success

  Recommendation: Current tiered selection is efficient.
```

If inefficiencies are detected, name them — e.g. "Agent A-contracts used
opus for a low-complexity task — consider haiku" or
"Agent E-tests failed twice with haiku — upgrade to sonnet".

---

## Command: `trends` — Cross-Campaign Trends

1. **Find historical campaigns**: scan `data/plans/` for plan JSON files,
   sorted by creation timestamp; take the last N (default 5).

2. **Extract per-campaign metrics**: agent count and model breakdown,
   completion/failure rate, estimated total cost, campaign duration.

3. **Compute trends over time**: campaign size, cost per agent, success rate,
   model-selection aggressiveness (share of haiku).

4. **Generate actionable recommendations**: rising failure rate — more
   conservative model selection or smaller scope; rising cost — scope
   reduction or more aggressive tiering; stable 100% success — try more
   aggressive downtiering; decreasing duration — note what changed.

```
Usage Stats — Trends (last 5 campaigns)

  Campaign          Date      Agents  Success  Cost    Avg Cost/Agent
  ──────────────────────────────────────────────────────────────────────
  plan-012          Mar 28      6      100%    $1.85      $0.31
  plan-011          Mar 25      4      100%    $1.52      $0.38

  Trends: success improving (88% -> 100%); cost/agent decreasing
          ($0.40 -> $0.31, -22%); Haiku usage increasing (25% -> 50%)

  Recommendations:
    - Move more medium-complexity tasks to haiku for further savings
    - Current tiered strategy saves ~45% vs all-opus
```

---

## Config (project.toml)

Optional `[usage-stats]` section. Legacy `[token-audit]` and `[session-stats]`
sections are read as fallbacks for their former keys when `[usage-stats]` is
absent.

```toml
[usage-stats]
# telemetry_url = "http://127.0.0.1:8099"   # optional ollama-telemetry API base
# daily_budget_usd = 10.00
# session_budget_usd = 5.00
# alert_threshold_pct = 80
# chars_per_token = 4.0
# history_file = "data/token-history.jsonl"
# hooks_log = ".claude/hooks/logs/hooks-log.jsonl"
# history_sessions = 10
# phase_idle_threshold_min = 5
```

Campaign state paths come from `[paths]` (default `data/tasks.json`).

Pricing overrides live in the `[pricing]` section (shared with telemetry.py).
**Two key families are accepted so a `[pricing]` block authored for any host
works on every host.** The canonical family is the generic runtime tier
(`mini` / `standard` / `max`); the Anthropic-named family
(`haiku` / `sonnet` / `opus`) is accepted as an alias mapped to the same tiers
(haiku→mini, sonnet→standard, opus→max). If both are present for the same
tier, the canonical `*_input` / `*_output` key wins.

```toml
[pricing]
# Canonical generic-tier keys (aliases: haiku_*, sonnet_*, opus_* map to
# mini_*, standard_*, max_* respectively)
# mini_input = 1.00
# mini_output = 5.00
# standard_input = 3.00
# standard_output = 15.00
# max_input = 5.00
# max_output = 25.00
```

---

## Integration

| Skill | How Usage Stats Helps |
|-------|----------------------|
| `/campaign-health` | Token costs and agent performance feed campaign efficiency metrics |
| `/planner` | Budget awareness and trend data inform agent model selection |
| `/manager` | Cost tracking per campaign validates tiered-model savings; include efficiency in `/manager verify` |
| `/observer` | Budget alerts and efficiency findings can be recorded as observations |
| `/ship` | Include session summary in commit messages or PR descriptions |

---

## Conventions

- Token counts are **measured** when sourced from the telemetry API (Tier 1)
  and **estimated ~approximate** when derived from the character heuristic
  (Tier 3) — always label which tier produced every number
- The telemetry API is optional: probe with a 2s budget, fall through
  silently to Tier 2/3 if unreachable, and never hard-fail or block on it
- Read-only toward logs, conversations, campaign state, plans, and agent
  specs; write targets are limited to `data/token-budget.json` and
  `data/token-history.jsonl`
- Adapt to available data sources — degrade gracefully, never hard-fail —
  and report which sources were found and used in every report
- Use conservative estimates (round up) when tracking against budgets; any
  built-in pricing values are package placeholders, not live rates —
  override them in `[pricing]` with current published rates
- Use plain text for reports (no ANSI colors — terminal-portable); session
  boundaries come from hooks session_id, conversation file boundaries, or
  git activity windows
- Agent IDs from hooks may not match campaign agent names — correlate by
  timing and worktree; campaign agents from tasks.json are the primary agent
  surface, hook-captured subagent events are optional enrichment
- When comparing models, normalize by complexity tier (don't compare
  haiku on easy tasks against opus on hard tasks)
- Tool names use Claude Code canonical names (Read, Edit, Write, Bash, Grep, Glob, Agent)
