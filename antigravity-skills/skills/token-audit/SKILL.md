---
name: token-audit
description: "Track token consumption, cost attribution, budget management, and rate-limit forecasting across sessions. Use when reviewing session cost, setting budgets, or forecasting rate-limit pressure."
---

# Token Audit Protocol

## Core Mandate
Deep-dive into token consumption patterns across sessions. Track per-turn token
sizing, cost attribution by tool type, budget management, and rate-limit
forecasting. Prefer real **measured** telemetry over heuristic estimates, and
always report which data tier produced the numbers.

## Execution Rules
1. **Follow the global guardrails in AGENTS.md.** (This is an ops/analytics
   skill — it does not require the planning workflow to run.)
2. **Run to completion autonomously.** All commands finish without prompts.
3. **Read globally, write narrowly:** only `data/token-budget.json` and
   `data/token-history.jsonl` may be written. Never modify conversation
   transcripts or hooks logs.
4. **Label every number by tier.** Telemetry numbers are **measured**; heuristic
   numbers are **estimated ~approximate**. Never present heuristic numbers as
   exact.

**Config:** `.agents/skills/project.toml` — `[token-audit]` and `[pricing]`
sections (optional).

## Commands
- `/token-audit status` — current token position and burn rate (default action)
- `/token-audit breakdown` — per-tool and per-turn token cost attribution
- `/token-audit budget [set <N>|check|reset]` — session or daily budget management
- `/token-audit forecast` — rate-limit proximity and depletion forecast
- `/token-audit history [N]` — usage trends across last N sessions (default 7)

Default to `status` if no command is given.

## Data-Source Precedence Ladder
Discover token data in strict precedence order and always report WHICH tier
produced the numbers:

- **Tier 1 — Telemetry HTTP API (measured, authoritative).** A local telemetry
  service (the ollama-telemetry repo) may expose real, hook-captured token/cost
  data over HTTP. Base URL configurable via `[token-audit].telemetry_url`
  (default `http://127.0.0.1:8099`). It is **optional** — probe, never
  hard-require:
  ```bash
  # 2s reachability probe gates the API path. On failure, fall through
  # silently to Tier 2/3 — never block on it.
  curl -s --max-time 2 http://127.0.0.1:8099/health
  ```
  When reachable, read real totals (camelCase JSON under `/api/llm`):
  ```bash
  curl -s --max-time 2 "http://127.0.0.1:8099/api/llm/overview?hours=24"
  curl -s --max-time 2 "http://127.0.0.1:8099/api/llm/sessions/<sessionId>"
  curl -s --max-time 2 "http://127.0.0.1:8099/api/llm/recent?limit=50"
  ```
  Response fields are camelCase: `totalInputTokens`, `totalOutputTokens`,
  `totalCostUsd`, `cacheReadTokens`, plus session-level totals. (snake_case such
  as `cache_read_tokens` is ONLY the `/api/llm/ingest` request body — never read
  it from responses.) These numbers are **measured** and supersede the heuristic.

- **Tier 2 — Hooks JSONL log (semi-measured):** tool call metadata with
  timestamps. `ls .agent/hooks/logs/hooks-log.jsonl 2>/dev/null`

- **Tier 3 — Character heuristic (estimated ~approximate, last resort):** size
  text at ~4 chars = 1 token (English) / ~3.5 chars = 1 token (code-heavy),
  configurable via `[token-audit].chars_per_token`.

Other sources used by Tier 2/3 sizing and by budget/history:
- Conversation transcripts (per-message sizing; location varies by install —
  degrade gracefully if not found).
- Rate-limit cache (if an Antigravity statusline or similar surface is active).
- Budget file `data/token-budget.json` (managed by this skill).
- Historical snapshots `data/token-history.jsonl` (managed by this skill).

## Token Estimation Method (Tier 2/3 fallback)
When the telemetry API is reachable, prefer its **measured** totals — that
retires the "exact per-message counts not exposed" limitation. When telemetry is
**not** reachable, fall back to:
1. **Character heuristic** (Tier 3): ratios above, labelled estimated ~approximate.
2. **Message role weighting:** user messages + tool results → input tokens;
   assistant messages + tool-call parameters → output tokens; system messages and
   AGENTS.md → input tokens (amortize across turns).
3. **Per-tool sizing** from hooks log / transcript: Read → file bytes / 3.5
   (input); Bash → output bytes / 4 (input); Edit → old+new string (small output);
   Agent → prompt (output) + result (input); Grep/Glob → result set (input);
   Write → file content (output).
4. **Model pricing** from `[pricing]` or defaults (see Config).

## Command: `status`
1. **Size session tokens (precedence ladder):**
   - Tier 1 (preferred): GET `/api/llm/sessions/<sessionId>` (and/or
     `/api/llm/overview?hours=N`); read `totalInputTokens`, `totalOutputTokens`,
     `totalCostUsd`, `cacheReadTokens` → **measured**.
   - Tier 2/3 (fallback): size transcript/hooks log via the heuristic →
     **estimated ~approximate**.
2. **Session cost:** Tier 1 uses `totalCostUsd` directly; Tier 2/3 multiplies
   tokens by model pricing. If session totals expose a cache-read or savings
   figure (e.g. `cacheReadTokens` / a session-level savings total), add a "real
   cost avoided" note — do not invent field names beyond the verified contract.
3. **Rate-limit position** (if data available): 5h and 7d windows — used %, time
   remaining, effective burn rate.
4. **Budget check:** compare against `data/token-budget.json` if present.

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

  Rate Limits (if available):
    5h window: 32% used, 3h 28m remaining
    7d window: 15% used, 6d 2h remaining

  Budget:
    Daily: $2.48 / $10.00 (24.8%)
    Status: ON TRACK
```

## Command: `breakdown`
0. **Anchor totals to the best tier:** if Tier 1 is reachable, pull session
   totals (`totalInputTokens`, `totalOutputTokens`, `totalCostUsd`,
   `cacheReadTokens`) from `/api/llm/sessions/<sessionId>` as the **measured**
   ground-truth total, then reconcile per-tool shares (derived from hooks
   log / transcript) so they sum to that total. If telemetry is unreachable, the
   whole breakdown is **estimated ~approximate**. Report which tier anchored it.
1. **Group by tool type:** per call, estimate output tokens (call name +
   parameters) and input tokens (tool result returned to the model).
2. **Group by turn:** turn number, user input size, assistant output size, tools
   invoked.
3. **Identify heavy operations:** top 3–5 token-expensive turns (large reads,
   verbose bash output, agent spawns, compaction events).
4. **Compute overhead:** system prompt, conversation history, and AGENTS.md sent
   every request but not attributable to one tool.

```
Token Audit — Breakdown

  Anchored to: Tier 1 — telemetry API (measured)

  By Tool (tokens consumed):
    Tool       Calls  Input Tokens  Output Tokens  Cost
    ----------------------------------------------------------
    Read         18     180K            0.5K        $0.90
    Bash          8      45K            2K          $0.28
    Agent         1      25K            8K          $0.33
    Edit         12       2K           18K          $0.46
    Grep          5      12K            0.3K        $0.06
    Write         3       0.2K          8K          $0.20
    ----------------------------------------------------------
    Subtool      47     264K           37K          $2.24
    Overhead*                                       $0.24
    Total                                           $2.48

  * Overhead: system prompts, AGENTS.md, conversation history

  Heaviest Turns:
    Turn 5:  ~45K tokens (large file read: src/engine.py, 1200 lines)
    Turn 12: ~38K tokens (agent spawn: research codebase)
    Turn 8:  ~22K tokens (bash: full test suite output)

  Optimization Tips:
    - Use offset/limit on Read for large files (read only the part you need)
    - Pipe bash output through head/tail to limit result size
    - Prefer agent spawns over sequential reads for multi-file searches
```

## Command: `budget`
### `/token-audit budget set <amount>`
Set a session or daily budget in USD. Create or update `data/token-budget.json`:
```json
{
  "daily_budget_usd": 10.00,
  "session_budget_usd": 5.00,
  "set_at": "2026-03-28T14:00:00Z",
  "alert_threshold_pct": 80
}
```
Accept formats like `$10`, `10.00`, `session:5 daily:10`. Confirm:
"Budget set to $X.XX per session / $Y.YY per day".

### `/token-audit budget check`
Read `data/token-budget.json`, estimate current session cost (same method as
`status` — measured when Tier 1 is up), compare against limits, report
ON TRACK / WARNING (>= alert threshold) / EXCEEDED.
```
Token Audit — Budget Check

  Session:  $2.48 / $5.00 (49.6%)  ON TRACK
  Daily:    $7.23 / $10.00 (72.3%) WARNING — approaching 80% threshold

  At current burn rate:
    Session budget exhausts in: ~1h 45m
    Daily budget exhausts in: ~1h 15m
```

### `/token-audit budget reset`
Reset daily usage counters. Keep budget limits; clear accumulated spend tracking.

## Command: `forecast`
1. **Current rate-limit position:** parse from any available rate-limit cache,
   hooks log event frequency, or transcript size growth.
2. **Depletion time:** at current burn rate, when does each window hit 100%?
   (5h: remaining / hourly burn; 7d: remaining / daily burn).
3. **Pace adjustments:** if burning too fast, suggest effort reduction, smaller
   reads, fewer agent spawns, or a lighter model; if ahead of pace, report
   headroom.
4. **Historical comparison:** if `data/token-history.jsonl` exists, compare
   current burn rate against the historical average.

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
If pace is tight, recommend: reduce effort level; use Read with offset/limit;
batch related questions into fewer turns; prefer lighter agents for research.

## Command: `history`
1. **Load snapshots** from `data/token-history.jsonl`:
   ```json
   {"session_id": "abc123", "date": "2026-03-28", "duration_min": 135, "est_input_tokens": 285000, "est_output_tokens": 42000, "est_cost_usd": 2.48, "tool_calls": 47, "agents": 1, "source_tier": 1}
   ```
2. **If no history file exists**, retroactively build it:
   - Tier 1 (preferred): scan `/api/llm/overview?hours=N` (widen N to cover the
     window) and/or `/api/llm/sessions/<sessionId>` per known session for
     **measured** per-session `totalInputTokens` / `totalOutputTokens` /
     `totalCostUsd`.
   - Tier 2/3 (fallback): scan hooks log for distinct session_id values and
     compute per-session metrics via the heuristic.
   - Write to `data/token-history.jsonl`; tag each row's source tier so measured
     and estimated sessions are distinguishable.
3. **Compute trends:** daily average cost, tokens/cost/tools per session. Report
   which tier produced the numbers (mixed rows are possible — note measured vs
   estimated).
4. **Identify anomalies:** sessions whose cost is > 2 std dev above the mean.

```
Token Audit — History (last 7 sessions)

  Date        Session    Duration  Tokens   Cost    Tools  Tier
  ------------------------------------------------------------------
  Mar 28      abc123     2h 15m    327K     $2.48     47   measured
  Mar 27      def456     1h 40m    ~210K    $1.62     32   estimated
  Mar 26      ghi789     3h 05m    ~520K    $3.89     68   estimated
  Mar 25      jkl012     0h 45m    ~95K     $0.71     15   estimated
  Mar 24      mno345     2h 30m    ~380K    $2.85     52   estimated

  7-Session Averages:
    Tokens/session:  306K
    Cost/session:    $2.31
    Tools/session:   42.8
    Duration:        2h 03m

  Trend: Cost stable ($2.31 avg, +/- $0.87 std dev)
```
**Auto-snapshot:** at the end of each `history` run, append the current
session's metrics to `data/token-history.jsonl` if not already present (keyed by
session_id to prevent duplicates).

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

Default pricing if absent (per 1M tokens): mini/haiku $1.00 in / $5.00 out;
standard/sonnet $3.00 in / $15.00 out; max/opus $5.00 in / $25.00 out. Override
with current prices for the models your installation uses.

## Integration
- `/session-stats` — token-audit adds the cost dimension to tool analytics
- `/campaign-health` — token costs feed campaign efficiency metrics
- `/agent-report` — per-agent cost data feeds agent efficiency analysis

## Output Contract
- Report which data tier (1/2/3) produced the numbers in every command.
- Telemetry numbers are **measured**; heuristic numbers are **estimated
  ~approximate** — never present the latter as exact.
- The telemetry API is optional: probe with a 2s budget, fall through silently
  to Tier 2/3 if unreachable, never hard-fail or block on it.
- Report which data sources were found.
- Use conservative (round-up) estimates when tracking against budgets.
