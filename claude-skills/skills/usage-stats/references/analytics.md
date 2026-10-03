# Usage Stats: Command Details

Use the entry's routing table and read only the selected command section.
Source collection, estimation, pricing, and config are in
[sources-and-methods.md](sources-and-methods.md). Commands are read-only unless
the user explicitly requests `budget set`, `budget reset`, or history
persistence. Automatic skill selection adds no permission to write.

## `summary` — quick session overview

1. Identify the session unambiguously. Use native counters first, then optional
   telemetry per-session totals, then logs/transcripts. A telemetry overview
   (for example, `hours=8`) is only a labelled window fallback.
2. Count tool calls by actual name from telemetry, hook PreToolUse events, or
   transcript tool-call records. Count agent spawns/completions from supported
   records, including SubagentStart/SubagentStop when present.
3. Measure session duration from its first to last timestamp. Include bounded
   git activity (commits, files, insertions/deletions) and rate-limit position
   when exposed. Do not call elapsed session time active working time.
4. Report ID, duration, tool distribution, agents, git activity, and quota
   position as available. With git-only evidence, omit unobservable tool and
   agent counts. With transcripts but no hooks, retain supported counts.

## `cost` — current token position

1. Report input/output/total from the best source. Use telemetry fields
   `totalInputTokens`, `totalOutputTokens`, `totalCostUsd`, and `cacheReadTokens`
   only where exposed; otherwise use the documented estimation method.
2. Include measured cost or a labelled calculation with verified pricing.
   Report cache reads and supported avoided-cost calculations separately.
3. Show five-hour and seven-day quota positions, remaining window time, and
   current/sustained burn rates when supported. Keep measured percentages
   separate from estimated tokens per hour.
4. If a budget exists, compare supported session and daily totals to their
   respective limits; do not compare one session's spend as if it were a day.

## `breakdown` — tool and turn attribution

1. Anchor totals to native counters or telemetry when available. Group estimated
   input (returned results) and output (calls/parameters) by tool and turn.
2. Reconcile estimated shares to the measured anchor. Account for system
   prompts, replayed conversation, and project instructions as overhead where
   observable; identify any residual or allocation assumption. A normalized
   tool share remains estimated even when it sums to a measured total.
3. Show tool, calls, input, output, and cost if pricing is available. Flag the
   top three to five expensive turns: large reads (for example, over 500 lines),
   verbose command outputs, agent prompts/results, or compaction events.
4. Recommend bounded reads, bounded command output, or batched searches only
   where the measured pattern supports it. Do not assume spawning an agent
   saves tokens without including its prompt, results, and child usage.

## `budget [set <amount>|check|reset]` — budget management

Default to `check`. Read `data/token-budget.json` and compare independently
covered session/daily costs with the corresponding limits. Report `ON TRACK`,
`WARNING` at or above `alert_threshold_pct`, or `EXCEEDED` at/above the limit.
Give depletion estimates only when a defensible spend rate exists. Missing
cost or daily coverage is unavailable, not zero.

For an explicit `budget set` request, accept `$10`, `10.00`, or
`session:5 daily:10`; use user context to select session/daily scope and clarify
only if it cannot be determined. Create/update this file while preserving
unrelated fields and unspecified limits:

```json
{
  "daily_budget_usd": 10.0,
  "session_budget_usd": 5.0,
  "set_at": "2026-03-28T14:00:00Z",
  "alert_threshold_pct": 80
}
```

Confirm the resulting limits. For an explicit `budget reset` request, keep
limits and clear only accumulated daily spend tracking in the budget file.
Never alter provider counters, logs, transcripts, or history to reset a budget.

## `forecast` — rate-limit forecast

1. Read actual quota position/window boundaries from available rate-limit data.
   Hook event frequency or transcript growth may estimate activity/burn but
   cannot establish quota capacity or percentage by themselves.
2. Calculate time to depletion as remaining capacity divided by a compatible
   hourly/daily burn rate; compare with window expiry. If capacity is unknown,
   report burn trends without inventing a depletion time.
3. Compare with history when available. Suggest reduced effort, bounded reads,
   batching, or a lower-cost eligible model when the observed workload permits;
   model choice still follows the user's constraints and normal agent policy.
   Otherwise report available headroom. These are recommendations, not changes.

## `history [N]` — session trends

Default to seven sessions, or `[usage-stats].history_sessions` when configured.
Read the configured history file (default `data/token-history.jsonl`). If it is
absent, derive a report in memory from native counters, per-session telemetry,
hooks, or transcripts. A window overview alone cannot supply per-session rows.

Report per-session date, ID, duration, tokens, cost when available, and tools;
calculate daily averages and per-session averages. Preserve each metric's source
tier, because rows can mix measured totals with estimated attribution. Flag
costs more than two standard deviations above the mean when the sample supports
that comparison; show sample size and missing coverage.

Only when the user explicitly requests building/saving history, write the
derived snapshots and append the current session if absent. Deduplicate by
`session_id`; preserve existing rows and source labels. Read-only `history`
does not auto-snapshot. Existing estimated rows may use this legacy shape:

```json
{"session_id":"abc123","date":"2026-03-28","duration_min":135,"est_input_tokens":285000,"est_output_tokens":42000,"est_cost_usd":2.48,"tool_calls":47,"agents":1,"source_tier":"estimated"}
```

Keep measured and estimated fields distinguishable; record coverage and source
when persisting new metrics. Do not store measured totals as unlabelled estimates.

## `tools` — usage patterns

1. Collect complete session tool events from telemetry, hooks, or transcripts;
   report paging/coverage limits. If none are available, explain the missing
   instrumentation without installing it.
2. Group actual core, MCP, and other tool names. Match pre/post/failure records
   where available to compute success/failure counts; unmatched calls are
   unknown or pending, not presumed successes.
3. Count the top five consecutive two-tool patterns (such as search → read or
   edit → test). Estimate per-call data sizes from available call/results, and
   state whether the size is input, result, or combined.
4. For sessions over an hour, bucket calls by clock hour. Report tool totals,
   success/failure/unknown, average size, common sequences, and hourly activity.

## `timeline` — activity phases

Order hooks, transcript, and git events by timestamp. Cluster tool sequences
into Research (reads/searches), Implementation (edits/writes), Testing (test
commands), and Review where supported; label phases as inferred. Mark commits,
agent completions, and plan transitions. Show idle gaps longer than five
minutes, configurable by `[usage-stats].phase_idle_threshold_min`. Gaps show
missing activity, not proof that the person or model was idle.

## `compare [N]` — cross-session comparison

Default to five sessions. Group records by session ID or verified transcript
boundaries; a git-by-day fallback is labelled daily activity, not sessions.
Extract duration, tool/agent counts, dominant tool and share. Show per-session
values, averages, and deltas, with source/scope differences visible before
claiming trends in tool usage, agent reliance, or duration.

## `export` — JSON output

Collect the supported `summary`, `tools`, and `agents` metrics and return one
JSON object without Markdown or commentary. Omit unavailable metrics or use
null; do not invent zeroes. Preserve the existing field families:

```json
{
  "session_id": "abc123",
  "started_at": "2026-03-28T14:02:00Z",
  "duration_minutes": 135,
  "tool_calls": {"total": 47, "by_tool": {"Read": 18}, "success_rate": 0.957, "failed": 2},
  "agents": {"total": 1, "by_type": {"general-purpose": 1}, "completed": 1, "failed": 0},
  "git": {"commits": 3, "files_changed": 8, "insertions": 142, "deletions": 37},
  "data_sources": ["telemetry_api", "hooks_log", "git"],
  "data_tier": "measured"
}
```

`data_tier` is the highest available tier (`measured`, `hooks`, or `estimated`).
For mixed-source metrics add per-field source/tier and coverage so this top-level
label cannot imply every field is measured. Export prints JSON; writing a file
requires an explicit destination request and ordinary workspace authorization.

## `agents [agent-id]` — agent overview or detail

Combine optional session subagent records with campaign state. Pair
SubagentStart/SubagentStop by agent ID and tool events by the same ID. Collect
campaign names, model, status, complexity, files, dependencies, and timestamps.
Correlate differing hook/campaign IDs by supported timing/worktree evidence;
report uncertain matches instead of silently merging them.

Overview: show total, completion rate `done / (done + failed)`, pending/running,
mean duration and tools, model distribution, and nesting depth where exposed.
An empty completed denominator is unavailable. Campaign state remains the
primary campaign source even when hook events are absent.

Detail accepts a hook ID, campaign name, or positional `#2` reference resolved
against the displayed list. Show tool counts/sequences, files read/modified and
line deltas, relative timeline, model and complexity, outcome/retries, and
measured tokens/cost or a labelled estimate. File ownership is planned scope;
git/transcript evidence establishes actual file activity.

## `efficiency` — model selection

Read campaign model assignments and complexity from task/plan state. Where the
package exposes it, use `estimate_campaign_savings()` in
`scripts/task_runtime/telemetry.py`, or equivalent documented calculations, to
compare actual tiered assignments with all-high-tier and all-low-tier scenarios.
Resolve this helper relative to the installed provider package, not this skill
directory; verify its API before calling it. Scenario costs are estimates,
even if actual spend is measured.

Compare outcomes, retries, average tools, and cost within the same complexity
and task class. Report plausible upgrade/downgrade candidates with their evidence
and sample size; cheap easy tasks versus expensive hard tasks do not establish
model efficiency. Do not treat hypothetical savings as proven equal-quality
outcomes or change model assignments automatically.

## `trends [N]` — cross-campaign trends

Default to five campaigns from `data/plans/`, ordered by creation time. Extract
agent/model counts, success/failure, supported duration and costs. Compare
campaign size, cost per agent, outcomes, and lower-tier model share while noting
complexity changes and missing data. Rising failures can support smaller scope
or stronger model choices; rising costs can support scope/tier adjustments.
Stable success may justify a bounded lower-tier experiment, not a claim that
downgrading will preserve quality. Explain changes behind duration trends where
the records support them.
