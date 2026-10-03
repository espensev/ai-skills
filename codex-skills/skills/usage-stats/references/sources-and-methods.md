# Usage Stats: Sources and Methods

Read this only when the selected command needs source discovery, estimates,
pricing, or configuration beyond the entry's native-counter route. Read only
the relevant sections; do not scan all available logs for a routine closeout.

## Source discovery

Keep the entry's precedence: native counters or telemetry (Tier 1), event logs
and transcripts (Tier 2), then character estimates (Tier 3). Report the source,
scope, and coverage of each metric; measured totals do not make estimated
attribution measured. Bind the current session by ID and project/prompt evidence;
the newest file alone is insufficient when sessions overlap.

1. **Telemetry is optional.** Use `[usage-stats].telemetry_url`, default
   `http://127.0.0.1:8099`. Probe `/health` with a two-second timeout only when
   telemetry is needed. An unreachable service is a reason to use local sources,
   never to start, repair, reconfigure, or deploy a service.

   ```bash
   curl -s --max-time 2 http://127.0.0.1:8099/health
   curl -s --max-time 2 "http://127.0.0.1:8099/api/llm/overview?hours=24"
   curl -s --max-time 2 "http://127.0.0.1:8099/api/llm/sessions/<sessionId>"
   curl -s --max-time 2 "http://127.0.0.1:8099/api/llm/recent?limit=50"
   ```

   Responses use camelCase: `totalInputTokens`, `totalOutputTokens`,
   `totalCostUsd`, `cacheReadTokens`, plus session totals. Snake case such as
   `cache_read_tokens` belongs to the `/api/llm/ingest` request body, not these
   responses. Recent events may filter by provider, type, or machine ID; verify
   supported filters and paging before treating a page as complete coverage.
   An overview is a window aggregate, not proof of current-session usage.

2. **Hooks JSONL:** use `[usage-stats].hooks_log` or the provider's installed
   hooks log (commonly `.claude/hooks/logs/hooks-log.jsonl` or
   `.codex/hooks/logs/hooks-log.jsonl`). Fields can include timestamp,
   `session_id`, `tool_name`, `tool_input`, and `agent_id`. SubagentStart and
   SubagentStop include agent type/ID. Parse with Python's JSON module or jq;
   preserve parse errors and incomplete coverage.

3. **Transcripts:** use the active provider home and a verified current-session
   match. Claude installations may expose
   `~/.claude/projects/*/conversations/*.jsonl` (on Windows, below the user's
   `.claude/projects` directory); discover the actual layout rather than
   assuming that path exists. Codex native counters are described in the entry;
   other transcript events support turn, tool, and phase attribution. Tool
   metadata alone does not establish token totals.

4. **Rate limits:** read a configured statusline/cache surface if present;
   `/tmp/claude-sl-usage` is one Claude Unix example. Missing rate-limit data
   means position is unavailable; do not infer quota percentages from file size.

5. **Campaigns and agents:** `[paths].state` in project config defaults to
   `data/tasks.json`. This is the primary campaign source when hooks are absent:
   names, models, status, complexity, ownership, dependencies, and timestamps.
   Enrich from `data/plans/*.json`, `agents/agent-*.md`, and worktree branches.
   Use `git log --all --format="%H %ai %s"` with bounded agent/worktree filters
   where attribution is supported; commit-message matches are candidate evidence.

6. **Other local sources:** bounded `git log --since=<session-start>` and
   `git diff --stat`, optional `data/observations.jsonl`,
   `data/token-budget.json`, and the configured history file (default
   `data/token-history.jsonl`). Git-only activity cannot establish tool counts.

Report sources found and used. If none are usable, say so and suggest adding
instrumentation or retrying after activity accumulates. Do not install hooks
or write observations as part of data discovery.

## Estimation and pricing

- Use measured totals whenever available. Without them, estimate about four
  characters per token for English or 3.5 for code-heavy text, configurable by
  `[usage-stats].chars_per_token`. Label every such result
  **estimated ~approximate** and retain the scope that was sized.
- User messages, returned tool results, and system/project instruction content
  count as input. Assistant messages and tool-call parameters count as output.
  Account for repeated context where observable; an amortized system-content
  estimate does not prove actual replay or cache charges.
- Per-tool sizing: Read content returned is input (roughly characters / 3.5);
  shell output is input (roughly characters / 4); Edit old/new text is output;
  agent prompts are output and returned results are input; search/glob results
  are input; Write content is output. If only byte lengths are available, label
  that approximation separately because bytes and characters can differ.
- Costs use an explicit `[pricing]` override, measured telemetry cost, or current
  published provider rates with a cited source. Never use remembered rates or
  treat package placeholder prices as live. Without verified pricing, report
  tokens without dollars. Token counters alone do not establish billed cost.
- Expose cache reads/savings only when the source supplies them or a stated
  pricing calculation supports them. Caching and batching can change billing.
  Round estimates conservatively when checking a budget.

## Configuration

Read the optional provider project config named in the entry. When
`[usage-stats]` is absent, legacy `[token-audit]` and `[session-stats]` sections
remain fallbacks for their former keys. Respect configured paths.

```toml
[usage-stats]
# telemetry_url = "http://127.0.0.1:8099"
# daily_budget_usd = 10.00
# session_budget_usd = 5.00
# alert_threshold_pct = 80
# chars_per_token = 4.0
# history_file = "data/token-history.jsonl"
# hooks_log = "<provider-hooks-log>"
# history_sessions = 10
# phase_idle_threshold_min = 5
```

`[pricing]` accepts generic tier keys `mini_input`, `mini_output`,
`standard_input`, `standard_output`, `max_input`, and `max_output` in USD per
million tokens. Aliases `haiku_*`, `sonnet_*`, and `opus_*` map to mini,
standard, and max. If both families define a tier, the canonical generic key
wins. These are runtime pricing tiers; use the configured provider/model
mapping rather than assuming that a tier name is a current model identifier.

## Reporting and integrations

Use plain text without ANSI colors, concise tables when helpful, and the actual
tool names exposed by the provider. Never manufacture missing counts or zeroes.
Separate source edits, deployed runtime, and remote publication.

Budget and trend findings can inform planner model selection; campaign costs
and efficiency can inform manager verification; a requested summary can inform
ship's commit or PR text. This skill does not itself publish, edit plans or
observations, change models, or invoke those workflows. Keep analytics advisory.
