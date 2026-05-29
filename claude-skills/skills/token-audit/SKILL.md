---
name: token-audit
description: "Track token consumption, cost attribution, budget management, and rate-limit forecasting across sessions."
argument-hint: "<status|breakdown|budget|forecast|history> — token & cost intelligence"
allowed-tools: Read, Glob, Grep, Bash, Edit, Write
user-invocable: true
extracted-from: Ai-Skills
portable-since: 2026-03-28
---

# Token Audit — Token & Cost Intelligence

Deep-dive into token consumption patterns across sessions. Tracks per-turn
token estimates, cost attribution by tool type, budget management, and
rate-limit forecasting. Complements claude-lens (real-time quota display)
with analytical depth and historical tracking.

**All commands run to completion autonomously.**

**Config:** `.claude/skills/project.toml` — `[token-audit]` and `[pricing]` sections (optional)

---

## Commands

| Command | Usage | Purpose |
|---------|-------|---------|
| `status` | `/token-audit` or `/token-audit status` | Current token position and burn rate |
| `breakdown` | `/token-audit breakdown` | Per-tool and per-turn token cost attribution |
| `budget` | `/token-audit budget [set <N>|check|reset]` | Session or daily budget management |
| `forecast` | `/token-audit forecast` | Rate-limit proximity and depletion forecast |
| `history` | `/token-audit history [N]` | Usage trends across last N sessions (default 7) |

Default to `status` if no command given.

---

## Setup: Discover Token Data

Before any command, locate token-relevant data sources. They form a strict
**precedence ladder** — always prefer a higher tier and report which tier
produced the numbers:

- **Tier 1 — Telemetry HTTP API (measured, authoritative):** real,
  hook-captured token/cost data from the local ollama-telemetry service.
- **Tier 2 — Hooks JSONL log (semi-measured):** tool call metadata with
  timestamps; sizing derived from logged tool inputs/outputs.
- **Tier 3 — Character heuristic (estimated ~approximate):** last-resort
  ~4-chars/token estimate from transcript/log text.

Always report WHICH tier produced the numbers.

0. **Telemetry HTTP API** (Tier 1 — preferred when reachable). A local
   telemetry service (the ollama-telemetry repo) may expose real, hook-captured
   token/cost data over HTTP. The base URL is configurable via
   `[token-audit].telemetry_url` (default `http://127.0.0.1:8099`). It is
   **optional** — probe it, never hard-require it:
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
   never read it from responses.) Numbers from this tier are **measured** and
   should be labelled as such; they supersede the character heuristic below.

1. **Conversation transcripts** (Tier 2/3 input for per-message sizing):
   ```bash
   # macOS / Linux
   ls -t ~/.claude/projects/*/conversations/*.jsonl 2>/dev/null | head -5
   # Windows
   ls -t "$USERPROFILE/.claude/projects/"*/conversations/*.jsonl 2>/dev/null | head -5
   ```
   Find the latest file matching the current project directory hash.

2. **Hooks JSONL log** (Tier 2 — tool call metadata with timestamps):
   ```bash
   ls .claude/hooks/logs/hooks-log.jsonl 2>/dev/null
   ```

3. **Claude Code rate-limit cache** (if lens or similar is active):
   ```bash
   ls /tmp/claude-sl-usage 2>/dev/null    # Unix lens cache
   ```

4. **Budget file** (managed by this skill):
   ```bash
   ls data/token-budget.json 2>/dev/null
   ```

5. **Historical snapshots** (managed by this skill):
   ```bash
   ls data/token-history.jsonl 2>/dev/null
   ```

6. **Pricing config** in project.toml `[pricing]` section (falls back to
   module defaults if absent).

---

## Token Estimation Method

When the telemetry HTTP API (Tier 1) is reachable, prefer its **measured**
totals — that retires the limitation below. Claude Code transcripts do not
expose exact per-message token counts, so when telemetry is **not** reachable
fall back to this estimation pipeline (Tier 2/3):

1. **Character-based heuristic** (Tier 3, last resort): ~4 characters = 1 token
   for English text. For code-heavy content: ~3.5 characters = 1 token (symbols
   are often individual tokens). Configurable via
   `[token-audit].chars_per_token`. Label these numbers as
   **estimated ~approximate**.

2. **Message role weighting**:
   - User messages: count as input tokens
   - Assistant messages: count as output tokens
   - Tool results returned to the model: count as input tokens
   - System messages and CLAUDE.md: count as input tokens (amortize across turns)

3. **Per-tool estimation** (from hooks log tool_input or transcript content):
   - Read: file content returned as tool result -> input tokens (bytes / 3.5)
   - Bash: command output returned -> input tokens (output bytes / 4)
   - Edit: old_string + new_string -> small output token count
   - Agent: full prompt -> output tokens; agent result -> input tokens
   - Grep/Glob: result set -> input tokens
   - Write: file content -> output tokens

4. **Model pricing** from `[pricing]` config or defaults:

   | Model | Input ($/1M tokens) | Output ($/1M tokens) |
   |-------|---------------------|----------------------|
   | Haiku | $1.00 | $5.00 |
   | Sonnet | $3.00 | $15.00 |
   | Opus | $5.00 | $25.00 |

All estimates are clearly labelled as approximate. Actual API billing may differ
due to caching, batching, and prompt caching discounts.

---

## Command: `status` — Current Token Position

### Steps

1. **Size session tokens (follow the precedence ladder)**:
   - **Tier 1 (preferred):** if the telemetry probe succeeded, GET
     `/api/llm/sessions/<sessionId>` for the current session (and/or
     `/api/llm/overview?hours=N`) and read `totalInputTokens`,
     `totalOutputTokens`, `totalCostUsd`, `cacheReadTokens`. Report these as
     **measured**.
   - **Tier 2/3 (fallback):** if telemetry is unreachable, parse the current
     conversation transcript or hooks log and apply the character heuristic.
     Sum input tokens (user messages + tool results) and output tokens
     (assistant messages + tool call parameters); total = input + output.
     Report as **estimated ~approximate**.

2. **Calculate session cost**: Tier 1 uses `totalCostUsd` directly (measured);
   Tier 2/3 multiplies token estimates by model pricing (estimated). If the
   session totals expose a cache-read or savings figure (e.g. `cacheReadTokens`
   / a session-level savings total), add a "real cost avoided" note — do not
   invent field names beyond the verified contract.

3. **Rate limit position** (if rate-limit data available):
   - 5-hour window: used percentage, time remaining
   - 7-day window: used percentage, time remaining
   - Effective burn rate: estimated tokens per hour

4. **Budget check**: If `data/token-budget.json` exists, compare current
   estimated usage against the configured limit.

### Report

```
Token Audit — Status

  Data tier: Tier 1 — telemetry API (measured)
             [or: Tier 3 — character heuristic (estimated ~approximate)]

  Session Tokens (measured):
    Input:     285K tokens   ($1.43)
    Output:    42K tokens    ($1.05)
    Total:     327K tokens   ($2.48 measured)
    Cache reads: 180K tokens (real cost avoided)

  Burn Rate:
    Current:   ~145K tokens/hour
    Sustained: ~120K tokens/hour (session average)

  Rate Limits:
    5h window: 32% used, 3h 28m remaining
    7d window: 15% used, 6d 2h remaining

  Budget:
    Daily: $2.48 / $10.00 (24.8%)
    Status: ON TRACK
```

---

## Command: `breakdown` — Cost Attribution

### Steps

0. **Anchor totals to the best tier**: if the telemetry API (Tier 1) is
   reachable, pull session totals (`totalInputTokens`, `totalOutputTokens`,
   `totalCostUsd`, `cacheReadTokens`) from `/api/llm/sessions/<sessionId>` and
   treat them as the **measured** ground-truth total. Per-tool attribution
   below is still derived from the hooks log / transcript, but reconcile it to
   the measured total (scale the heuristic per-tool shares so they sum to the
   measured total). If telemetry is unreachable, the whole breakdown is
   **estimated ~approximate**. Report which tier anchored the totals.

1. **Group token consumption by tool type**: For each tool call, estimate the
   output tokens consumed (the call itself: tool name + parameters) and the
   input tokens consumed (the tool result returned to the model).

2. **Group by conversation turn**: Each user-to-assistant exchange is a "turn".
   Track: turn number, user input size, assistant output size, tools invoked.

3. **Identify heavy operations**: Flag the top 3-5 most token-expensive turns:
   - Large file reads (> 500 lines)
   - Verbose bash outputs
   - Agent spawns (full prompt + returned result)
   - Compaction events (context reduction)

4. **Compute overhead**: Estimate system prompt, conversation history, and
   CLAUDE.md content that is sent with every request but not attributable to
   a single tool.

### Report

```
Token Audit — Breakdown

  By Tool (estimated tokens consumed):
    Tool       Calls  Input Tokens  Output Tokens  Est. Cost
    ──────────────────────────────────────────────────────────
    Read         18     180K            0.5K        $0.90
    Bash          8      45K            2K          $0.28
    Agent         1      25K            8K          $0.33
    Edit         12       2K           18K          $0.46
    Grep          5      12K            0.3K        $0.06
    Write         3       0.2K          8K          $0.20
    ──────────────────────────────────────────────────────────
    Subtool      47     264K           37K          $2.24
    Overhead*                                       $0.24
    Total                                           $2.48

  * Overhead: system prompts, CLAUDE.md, conversation history

  Heaviest Turns:
    Turn 5:  ~45K tokens (large file read: src/engine.py, 1200 lines)
    Turn 12: ~38K tokens (agent spawn: Explore codebase)
    Turn 8:  ~22K tokens (bash: full test suite output)

  Optimization Tips:
    - Use offset/limit on Read for large files (only read the part you need)
    - Pipe bash output through head/tail to limit result size
    - Prefer Explore agent for multi-file searches over sequential reads
```

---

## Command: `budget` — Budget Management

### Subcommands

#### `/token-audit budget set <amount>`

Set a session or daily budget in USD.

1. Create or update `data/token-budget.json`:
   ```json
   {
     "daily_budget_usd": 10.00,
     "session_budget_usd": 5.00,
     "set_at": "2026-03-28T14:00:00Z",
     "alert_threshold_pct": 80
   }
   ```
   Parse the amount from the argument. Accept formats like `$10`, `10.00`,
   `session:5 daily:10`.

2. Confirm: "Budget set to $X.XX per session / $Y.YY per day"

#### `/token-audit budget check`

Check current estimated spend against configured budget.

1. Read `data/token-budget.json`
2. Estimate current session cost (same method as `status`)
3. Compare against limits
4. Report: ON TRACK / WARNING (>= alert threshold) / EXCEEDED

```
Token Audit — Budget Check

  Session:  $2.48 / $5.00 (49.6%)  ON TRACK
  Daily:    $7.23 / $10.00 (72.3%) WARNING — approaching 80% threshold

  At current burn rate:
    Session budget exhausts in: ~1h 45m
    Daily budget exhausts in: ~1h 15m
```

#### `/token-audit budget reset`

Reset daily usage counters. Keeps the budget limits, clears the accumulated
spend tracking.

---

## Command: `forecast` — Rate Limit Forecast

### Steps

1. **Current rate limit position**: Parse from Claude Code statusline cache,
   hooks log event frequency, or conversation transcript size growth.

2. **Calculate depletion time**: At the current burn rate, when does each
   window hit 100%?
   - 5-hour window: remaining capacity / current hourly burn
   - 7-day window: remaining capacity / current daily burn

3. **Suggest pace adjustments**:
   - If burning faster than sustainable: suggest effort reduction, smaller
     reads, fewer agent spawns, or switching to a lighter model
   - If well ahead of pace: report available headroom

4. **Historical comparison**: If `data/token-history.jsonl` exists, compare
   current burn rate against the historical average.

### Report

```
Token Audit — Forecast

  5-Hour Window:
    Used: 32% | Remaining: 3h 28m
    Burn rate: 9.5%/hour
    At this rate: hits 100% in 7h 10m (2h 42m of headroom)
    Pace: COMFORTABLE

  7-Day Window:
    Used: 15% | Remaining: 6d 2h
    Burn rate: 2.1%/day
    At this rate: hits 100% in 7d 3h (1d 1h of headroom)
    Pace: COMFORTABLE

  Recommendations:
    (none — usage is well within limits)
```

If pace is tight:
```
  Recommendations:
    - Reduce effort level (effort=default instead of high)
    - Use Read with offset/limit to avoid full-file reads
    - Batch related questions into fewer turns
    - Prefer Haiku agents for research tasks
```

---

## Command: `history` — Usage Trends

### Steps

1. **Load historical snapshots** from `data/token-history.jsonl`:
   ```json
   {"session_id": "abc123", "date": "2026-03-28", "duration_min": 135, "est_input_tokens": 285000, "est_output_tokens": 42000, "est_cost_usd": 2.48, "tool_calls": 47, "agents": 1}
   ```

2. **If no history file exists**, attempt to retroactively build it:
   - **Tier 1 (preferred):** if the telemetry API is reachable, scan
     `/api/llm/overview?hours=N` (widen N to cover the window) and/or
     `/api/llm/sessions/<sessionId>` per known session for **measured**
     per-session `totalInputTokens` / `totalOutputTokens` / `totalCostUsd`.
   - **Tier 2/3 (fallback):** scan hooks log for distinct session_id values
     and compute per-session metrics via the character heuristic.
   - Write results to `data/token-history.jsonl`. Tag each row's source tier so
     measured and estimated sessions are distinguishable.

3. **Compute trends**: daily average cost, tokens per session, cost per
   session, tools per session. Report which tier produced the numbers (mixed
   rows are possible — note when a row is measured vs estimated).

4. **Identify anomalies**: sessions whose cost is more than 2 standard
   deviations above the mean.

### Report

```
Token Audit — History (last 7 sessions)

  Date        Session    Duration  Tokens   Cost    Tools
  ─────────────────────────────────────────────────────────
  Mar 28      abc123     2h 15m    ~327K    $2.48     47
  Mar 27      def456     1h 40m    ~210K    $1.62     32
  Mar 26      ghi789     3h 05m    ~520K    $3.89     68
  Mar 25      jkl012     0h 45m    ~95K     $0.71     15
  Mar 24      mno345     2h 30m    ~380K    $2.85     52

  7-Session Averages:
    Tokens/session:  306K
    Cost/session:    $2.31
    Tools/session:   42.8
    Duration:        2h 03m

  Trend: Cost stable ($2.31 avg, +/- $0.87 std dev)
```

**Auto-snapshot**: At the end of each `history` command, append the current
session's metrics to `data/token-history.jsonl` if not already present (keyed
by session_id to prevent duplicates).

---

## Config (project.toml)

Optional `[token-audit]` section:

```toml
[token-audit]
# telemetry_url = "http://127.0.0.1:8099"   # optional ollama-telemetry API base
# daily_budget_usd = 10.00
# session_budget_usd = 5.00
# alert_threshold_pct = 80
# chars_per_token = 4.0
# history_file = "data/token-history.jsonl"
```

Pricing overrides in `[pricing]` section (shared with telemetry.py).

**Two key families are accepted so a `[pricing]` block authored for any host
works on every host.** The canonical family is the generic runtime tier
(`mini` / `standard` / `max`); the Anthropic-named family
(`haiku` / `sonnet` / `opus`) is accepted as an alias mapped to the same tiers
(haiku→mini, sonnet→standard, opus→max). If both are present for the same tier,
the canonical `*_input` / `*_output` key wins.

```toml
[pricing]
# --- Canonical generic-tier keys ---
# mini_input = 1.00
# mini_output = 5.00
# standard_input = 3.00
# standard_output = 15.00
# max_input = 5.00
# max_output = 25.00
# --- Accepted aliases (haiku→mini, sonnet→standard, opus→max) ---
# haiku_input = 1.00
# haiku_output = 5.00
# sonnet_input = 3.00
# sonnet_output = 15.00
# opus_input = 5.00
# opus_output = 25.00
```

---

## Integration

| Skill | How Token Audit Helps |
|-------|----------------------|
| `/session-stats` | Token-audit adds cost dimension to session tool analytics |
| `/campaign-health` | Token costs feed into campaign efficiency metrics |
| `/planner` | Budget awareness informs agent model selection decisions |
| `/manager` | Cost tracking per campaign validates tiered-model savings |
| `/agent-report` | Per-agent cost data feeds agent efficiency analysis |
| `/observer` | Budget alerts can be recorded as observations |

---

## Conventions

- Token counts are **measured** when sourced from the telemetry API (Tier 1)
  and **estimated ~approximate** when derived from the character heuristic
  (Tier 3) — always label which, and never present heuristic numbers as exact
- The telemetry API is optional: probe with a 2s budget, fall through silently
  to Tier 2/3 if unreachable, and never hard-fail or block on it
- Never modify conversation transcripts or hooks logs
- Write targets limited to: `data/token-budget.json`, `data/token-history.jsonl`
- Always report which data tier (1/2/3) produced the numbers
- Use conservative estimates (round up) when tracking against budgets
- Pricing defaults match Anthropic public list pricing; override in `[pricing]`
