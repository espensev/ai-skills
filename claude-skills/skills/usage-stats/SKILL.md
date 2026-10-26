---
name: usage-stats
description: "Use when reviewing token/cost usage, budgets, rate-limit forecasts, session tool or timeline activity, agent/campaign efficiency, or execution closeouts. Prefers measured telemetry with an explicitly estimated fallback. Do not use to operate a live telemetry deployment."
argument-hint: "<summary|window|closeout|cost|breakdown|budget|forecast|history|tools|agents|timeline|compare|efficiency|trends|export> — usage, cost & agent analytics"
user-invocable: true
metadata:
  extracted-from: Ai-Skills
  portable-since: 2026-08-17
---

# Usage Stats

Choose the route that matches the user's question or the required execution
closeout. No explicit skill name is needed. Default an unspecified usage request
to `summary`; routine closeouts use only the closeout and source rules below.
Read only the relevant reference section when the selected route needs it.

Automatic selection grants no additional tool permissions or write authority.
Logs, transcripts, campaign state, plans, and agent specs are read-only. Budget
writes require an explicit `budget set` or `budget reset` request; history writes
require an explicit request to build/save history. `closeout` never writes history
or memory. Do not operate or repair a telemetry deployment.

## Routes

Use `/usage-stats <command>` when an explicit invocation is useful.
All paths below are relative to the installed directory containing this `SKILL.md`.

| Command | Use for | Read next |
|---------|---------|-----------|
| `closeout` | End-of-execution outcome, time, tokens, evidence, risk | Closeout below |
| `window [H]` | Last H hours of usage; default 24 | Window below |
| `summary` | Current session overview; default command | [Analytics](references/analytics.md#summary--quick-session-overview) |
| `cost` | Token position, spend, burn rate, budget | [Analytics](references/analytics.md#cost--current-token-position) |
| `breakdown` | Per-tool and per-turn attribution | [Analytics](references/analytics.md#breakdown--tool-and-turn-attribution) |
| `budget [set <N>\|check\|reset]` | Budget limits and status | [Analytics](references/analytics.md#budget-set-amountcheckreset--budget-management) |
| `forecast` | Quota proximity and depletion | [Analytics](references/analytics.md#forecast--rate-limit-forecast) |
| `history [N]` | Recent usage trends; default 7 sessions | [Analytics](references/analytics.md#history-n--session-trends) |
| `tools` | Counts, failures, sequences, data volume | [Analytics](references/analytics.md#tools--usage-patterns) |
| `timeline` | Activity phases, milestones, gaps | [Analytics](references/analytics.md#timeline--activity-phases) |
| `compare [N]` | Compare sessions; default 5 | [Analytics](references/analytics.md#compare-n--cross-session-comparison) |
| `export` | Metrics as one JSON object | [Analytics](references/analytics.md#export--json-output) |
| `agents [agent-id]` | Agent overview or one agent's activity | [Analytics](references/analytics.md#agents-agent-id--agent-overview-or-detail) |
| `efficiency` | Model selection and cost scenarios | [Analytics](references/analytics.md#efficiency--model-selection) |
| `trends [N]` | Compare campaigns; default 5 | [Analytics](references/analytics.md#trends-n--cross-campaign-trends) |

## Source and reporting rules

Use the best available source for the requested scope; report its tier and coverage:

1. **Tier 1 — measured:** native provider counters first, then optional telemetry
   counters/cost. Native token totals alone do not establish billed cost.
2. **Tier 2 — event evidence:** hooks JSONL or transcripts for timestamps, tools,
   agents, and activity. Tool metadata does not establish exact token totals.
3. **Tier 3 — estimated ~approximate:** character sizing only when measured
   counters are unavailable. Never present heuristic tokens or attribution as exact.

Bind current-session data unambiguously by session ID and project/prompt evidence.
Do not pick the newest session merely because it is newest. Follow the provider's
counter schema before forming totals; normalized telemetry may already include
cache tokens. Reasoning is an output subset where the schema defines it that way.
State missing data as `not exposed`; never invent zeroes. Separate turn, session,
and window scope.
Claude native `input_tokens` excludes `cache_read_input_tokens` and
`cache_creation_input_tokens`. Add those three lanes to form total input, then
show cache reads/writes as subsets of that total. Do not add them again to an
already normalized telemetry input total.

Config is optional: `.claude/skills/project.toml`, `[usage-stats]` and
`[pricing]`. Need alternate sources, pricing, estimates, or legacy config?
Read [Sources and methods](references/sources-and-methods.md). Telemetry defaults
to `http://127.0.0.1:8099`; when needed, probe `/health` with a two-second timeout
and fall through to local sources if unreachable. Do not probe when native data
already answers the question. Price only from configured or verified published
rates, or measured telemetry cost; otherwise omit dollar figures.


## Command: `window` — Rolling Usage

1. Parse H (default 24); reject non-positive values.
2. Use optional telemetry `/api/llm/overview?hours=H`; read
   [Sources and methods](references/sources-and-methods.md#source-discovery) for
   its response contract. Otherwise use logs/transcripts and label token sizing
   **estimated ~approximate**.
3. Report input/output/total, cached/reasoning subsets, exact start/end, source,
   session/completed-step coverage, parse/read errors, and reconciliation delta
   where exposed. Repeat included/excluded scope: native Codex data excludes
   ChatGPT web/app conversations and usage under other Codex homes.

## Command: `closeout` — End-of-Execution Report

Use for turns that materially edit, test, build, publish, deploy, or run a
multi-step operation. Omit for simple answers/read-only lookups unless requested.
Keep six compact fields, using only evidence already available or a bounded
current-session lookup; do not load the analytics reference for a closeout.

1. **Outcome** — `COMPLETE`, `PARTIAL`, or `BLOCKED`, and the result or blocker.
2. **Elapsed** — current user message timestamp to the latest transcript/hook
   event only when they unambiguously bound the current turn. Label session-only
   duration as session time; without reliable boundaries use `not exposed`.
3. **Tokens** — input, cached-input subset, output, reasoning-output subset,
   total when exposed; source tier and timestamp/coverage. State that the final
   response is excluded from a pre-final counter. Label estimates explicitly.
4. **Execution** — completed model steps, tools, failures, approvals/denials,
   and agents only when exposed. Note repeated denials or wasteful retry loops.
5. **Verification** — exact pass/fail/skipped checks and changed source,
   runtime, or remote surfaces. Distinguish edits from deployment/publication.
6. **Remaining** — highest risk or next gate; one efficiency recommendation
   only if evidence makes it actionable.

Use `Run closeout` as the label. Omit unavailable fields or say `not exposed`.
This command is read-only and must not auto-write history or memory.
