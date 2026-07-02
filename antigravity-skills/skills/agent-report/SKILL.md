---
name: agent-report
description: "Analyze agent and subagent performance: tool usage per agent, duration, success rates, model efficiency, and cross-campaign trends. Use when reviewing how a campaign performed, comparing agents, or planning model selection for future work."
---

# Agent Report Protocol

## Core Mandate
Produce structured performance analytics on campaign agents and ad-hoc subagents. Track per-agent tool usage, duration, success rates, model selection efficiency, and cross-campaign optimization trends so the next plan can pick better models for the same work.

## Execution Rules
1. **Adhere to the Contract:** Follow the 13-element Planning Contract and the global guardrails in AGENTS.md.
2. **Read-only:** Agent-report never modifies campaign state, plans, or agent specs. Output is reports and recommendations only.
3. **Evidence Over Intuition:** Every metric must cite its data source (tasks.json, plan file, hooks log, observer file, git log).
4. **Adapt to available data:** Campaign agents from `data/tasks.json` are the primary surface. Hooks log and conversation transcripts are optional enrichment. Degrade gracefully when sources are missing.

## Data Sources (priority order)
1. **Campaign state** — `data/tasks.json` (default; configurable via `[paths].state`)
2. **Plan files** — `data/plans/*.json` (agent assignments, complexity tiers, file ownership)
3. **Agent spec files** — `agents/agent-*.md`
4. **Git log** — per-agent commits via worktree branches
5. **Observer data** — `data/observations.jsonl` filtered to agent context
6. **Hooks JSONL** (optional, varies by install) — `.agent/hooks/logs/hooks-log.jsonl` for tool-level events

## Commands
- `/agent-report summary` — overview across recent campaign activity (default)
- `/agent-report detail <agent-id>` — deep metrics for one agent (tool breakdown, file activity, timeline, cost)
- `/agent-report efficiency` — model selection cost analysis (tiered vs all-Opus vs all-Haiku, model-task fit)
- `/agent-report trends [N]` — cross-campaign performance trends (default last 5 campaigns)

## Cost Estimation
Use `[pricing]` config in project.toml when present. Defaults match Anthropic public list pricing:

| Model | Input ($/1M tokens) | Output ($/1M tokens) |
|-------|---------------------|----------------------|
| Haiku | $1.00 | $5.00 |
| Sonnet | $3.00 | $15.00 |
| Opus | $5.00 | $25.00 |

Always label estimates as approximate.

## Output Contract
For each command, emit a structured report that:
- Names every data source consulted (and which ones were missing)
- Reports counts and rates with exact numbers, not adjectives
- For `efficiency`, compares actual vs hypothetical model assignments
- For `trends`, identifies direction (improving/stable/declining) per metric
- Closes with explicit recommendations or "current strategy is efficient — no change recommended"

Never compare models on tasks of different complexity tiers — normalize before recommending.
