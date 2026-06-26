---
name: agent-report
description: "Analyze agent and subagent performance: tool usage per agent, duration, success rates, model efficiency, and cross-campaign trends. Use when reviewing how a campaign performed or planning model selection for the next one."
---

# Agent Report - Agent Performance Metrics

Deep analytics on agent and subagent performance across sessions and campaigns.
Tracks per-agent tool usage, duration, success rates, model selection efficiency,
and cross-campaign optimization trends.

Works with campaign agents (from `$manager` orchestration). Complements
`$campaign-health` (state and stuck detection) with performance-focused metrics.

**All commands run to completion autonomously.**

**Config:** `.codex/skills/project.toml` - uses `[paths]` for campaign state

---

## Commands

| Command | Usage | Purpose |
|---------|-------|---------|
| `summary` | `$agent-report` or `$agent-report summary` | Agent overview across recent activity |
| `detail` | `$agent-report detail <agent-id>` | Deep metrics for a specific agent |
| `efficiency` | `$agent-report efficiency` | Model selection cost analysis |
| `trends` | `$agent-report trends [N]` | Cross-campaign performance trends (default 5) |

Default to `summary` if no command given.

---

## Setup: Discover Agent Data

Before any command, locate agent-relevant data sources:

1. **Campaign state** (orchestrated agents - primary source):
   Read `[paths].state` from project.toml (default: `data/tasks.json`).
   ```bash
   python3 -c "
   import json
   d = json.load(open('data/tasks.json'))
   agents = d.get('agents', [])
   print(f'{len(agents)} campaign agents')
   for a in agents:
       print(f'  {a[\"name\"]}: model={a.get(\"model\",\"?\")}, status={a.get(\"status\",\"?\")}')
   " 2>/dev/null
   ```

2. **Plan files** (agent assignments, complexity tiers, file ownership):
   ```bash
   ls data/plans/*.json 2>/dev/null
   ```

3. **Agent spec files** (scope and instructions):
   ```bash
   ls agents/agent-*.md 2>/dev/null
   ```

4. **Git log** (per-agent commits via worktree branches):
   ```bash
   git log --all --format="%H %ai %s" | grep -i "agent\|worktree\|wt-" | head -20
   ```

5. **Observer data** (agent-linked observations):
   ```bash
   grep '"agent"' data/observations.jsonl 2>/dev/null | head -5
   ```

6. **Hooks JSONL log** (optional - if hooks instrumentation is configured for
   this Codex installation; falls back gracefully if missing):
   ```bash
   ls .codex/hooks/logs/hooks-log.jsonl 2>/dev/null
   ```

Report which sources were found. Adapt analysis to available data.

---

## Command: `summary` - Agent Overview

### Steps

1. **Collect campaign agents** from tasks.json (if exists):
   - Agent name, model, status (pending/running/done/failed), complexity tier
   - Files owned, dependency relationships
   - Start and completion timestamps

2. **Per-agent tool usage** (if hooks log available):
   - Filter PreToolUse/PostToolUse events by agent_id
   - Count tools per agent
   - Track PostToolUseFailure events for per-agent error rates

3. **Compute aggregates**:
   - Total agents in active and recent plans
   - Completion rate: done / (done + failed)
   - Average duration per agent
   - Model distribution across agents

### Report

```
Agent Report - Summary

  Campaign Agents (active campaign):
    Total:       6 agents across 1 plan
    Status:      4 done, 1 running, 1 pending

    Agent            Model    Status   Files  Complexity
    ------------------------------------------------------
    A-contracts      mini     done       3    low
    B-core-refactor  standard done       5    medium
    C-migration      standard done       4    medium
    D-integration    max      done       2    high
    E-tests          mini     running    3    low
    F-docs           mini     pending    2    low
```

If hooks instrumentation is active, include a Tool Usage section per agent.

---

## Command: `detail` - Single Agent Deep Dive

### Steps

1. **Identify agent** by ID. Accept:
   - Campaign agent name (e.g., `B-core-refactor`)
   - Positional reference (e.g., `#2` for the second agent in the plan)

2. **Tool breakdown** (from hooks log if available, else from git log):
   Count each tool type used by this agent. Track the chronological tool
   sequence from first call to last.

3. **File activity** (from git log filtered to agent's worktree branch, or
   from campaign state files_owned list):
   - Files read (from Read tool calls)
   - Files modified (from Edit/Write tool calls or git diff)
   - Lines changed (insertions + deletions)

4. **Timeline**: Chronological list of tool calls with relative timestamps.

5. **Cost estimate**: Based on estimated tokens and model pricing.

### Report

```
Agent Report - Detail: B-core-refactor

  Type:        Campaign agent (Plan: plan-012)
  Model:       standard
  Complexity:  medium
  Status:      done
  Duration:    12m 45s

  Files Touched:
    Modified: src/core/engine.py (+45/-12), src/core/config.py (+8/-3)
              src/core/types.py (+22/-0), tests/test_engine.py (+38/-5)
    Read-only: src/utils.py, src/api/handler.py, docs/architecture.md

  Estimated Cost: $0.42 (input ~35K, output ~8K at standard-tier rates)

  Timeline (if hooks log available):
    00:00  Read src/core/engine.py (full file)
    00:15  Grep for usage of old interface
    00:30  Read 3 dependent files
    01:45  Edit src/core/types.py (add new type)
    03:20  Edit src/core/engine.py (4 sequential edits)
    08:00  Bash: run tests
    11:00  Bash: run tests (all pass)
    12:45  DONE
```

---

## Command: `efficiency` - Model Selection Analysis

### Steps

1. **Load campaign agents** with their model assignments and complexity tiers
   from tasks.json and plan files.

2. **Calculate cost scenarios**:
   - Tiered cost (actual model assignments)
   - All-max cost (what if every agent used the strongest tier)
   - All-mini cost (what if every agent used the lowest-cost tier)
   - Savings from tiered selection vs all-max

3. **Evaluate model-task fit**:
   - Did high-complexity tasks assigned to `max` succeed without retries?
   - Did low-complexity tasks assigned to `mini` succeed?
   - Any failures suggesting the assigned model was underpowered?
   - Any successes suggesting the model was overpowered (could downgrade)?

4. **Per-model tool efficiency**: Compare average tool calls per agent across
   model tiers. More capable models may need fewer tool calls to achieve the
   same outcome.

### Report

```
Agent Report - Model Efficiency

  Campaign: plan-012 (6 agents)

  Cost Comparison:
    Tiered (actual):  $1.85
    All-max:          $3.40
    All-mini:         $0.68
    Savings vs max:   $1.55 (45.6%)

  Model Distribution:
    mini:     3 agents (low complexity)    - $0.21 avg, 100% success
    standard: 2 agents (medium complexity) - $0.42 avg, 100% success
    max:      1 agent  (high complexity)   - $0.38 avg, 100% success

  Model-Task Fit:
    All agents completed successfully with assigned models.
    No retries or failures suggesting underpowered model selection.

  Recommendation: Current tiered selection is efficient.
```

---

## Command: `trends` - Cross-Campaign Trends

### Steps

1. **Find historical campaigns**: Scan `data/plans/` for plan JSON files.
   Sort by creation timestamp. Take the last N (default 5).

2. **Extract per-campaign metrics**:
   - Agent count and model breakdown
   - Completion rate (done / total) and failure rate
   - Estimated total cost
   - Campaign duration (plan approval to verify completion)

3. **Compute trends over time**:
   - Are campaigns growing larger (more agents per campaign)?
   - Is cost per agent increasing or decreasing?
   - Is the success rate improving?
   - Is model selection becoming more aggressive (shifting toward `mini`)?

4. **Generate actionable recommendations**:
   - Rising failure rate: suggest more conservative model selection or smaller scope
   - Rising cost: suggest scope reduction or more aggressive tiering
   - Stable 100% success: suggest trying more aggressive downtiering
   - Decreasing duration: positive signal, note what changed

### Report

```
Agent Report - Trends (last 5 campaigns)

  Campaign          Date      Agents  Success  Cost    Avg Cost/Agent
  ----------------------------------------------------------------------
  plan-012          Mar 28      6      100%    $1.85      $0.31
  plan-011          Mar 25      4      100%    $1.52      $0.38
  plan-010          Mar 22      5       80%    $2.10      $0.42
  plan-009          Mar 18      3      100%    $0.95      $0.32
  plan-008          Mar 14      8       88%    $3.20      $0.40

  Trends (5-campaign window):
    Success rate:    improving (88% -> 100%)
    Cost/agent:      decreasing ($0.40 -> $0.31, -22%)
    Agents/campaign: stable (5.2 avg)
    Mini usage:      increasing (25% -> 50%)

  Recommendations:
    Success rate is strong. Consider:
    - Moving more medium-complexity tasks to `mini` for further savings
    - Current tiered strategy saves ~45% vs all-max
```

---

## Integration

| Skill | How Agent Report Helps |
|-------|------------------------|
| `$campaign-health` | Agent-report adds performance dimension to health checks |
| `$planner` | Trend data informs model selection for future campaign planning |
| `$manager verify` | Include agent efficiency in campaign verification checks |
| `$observer` | Record efficiency findings as project-level observations |

---

## Conventions

- Read-only: never modify campaign state, plans, or agent specs
- Adapt to available data - campaign agents from tasks.json are the primary surface;
  hooks log is optional enrichment
- Report clearly which data sources were found and used
- Cost estimates use `[pricing]` config when available, else module defaults
- When comparing models, normalize by complexity tier (do not compare `mini` on easy tasks against `max` on hard tasks)
