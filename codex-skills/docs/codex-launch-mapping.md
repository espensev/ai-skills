# Codex Launch Mapping

This package keeps the backend model contract portable:

- `mini`
- `standard`
- `max`

Those values are launch tiers, not provider-specific model IDs. On Codex, map
them at agent-launch time.

## Recommended Codex Mapping

Use this default when you want more delegated work to land on
`GPT-5.3-Codex-Spark` and preserve the stronger models for integration-heavy
work:

| Tier | Recommended Codex model | Use for |
|---|---|---|
| `mini` | `gpt-5.3-codex-spark` | bounded sidecar tasks, docs, tests, narrow code edits, repo exploration |
| `standard` | inherit your normal general-purpose coding model | most implementation tasks |
| `max` | inherit your strongest available coding model | ambiguous, integration-heavy, or recovery work |

If `gpt-5.3-codex-spark` is unavailable, fall back to the closest stronger
available coding model instead of blocking the launch.

## Launch Rules

1. Honor the backend `agents[].model` value from `python scripts/task_manager.py run ... --json`.
2. Treat `mini` as an explicit routing signal for Spark-class delegated work.
3. Keep low-risk worker scopes small enough that they genuinely fit the `mini` tier.
4. Do not up-tier work just because it is parallel. Up-tier only for ambiguity, coupling, or integration risk.

## Example: `run --json` to `spawn_agent`

If the backend emits:

```json
{
  "id": "b",
  "name": "add-tests",
  "model": "mini",
  "isolation": "worktree",
  "background": true,
  "prompt": "..."
}
```

Launch the subagent with Spark when available:

```json
{
  "agent_type": "worker",
  "model": "gpt-5.3-codex-spark",
  "reasoning_effort": "high",
  "fork_context": true,
  "message": "..."
}
```

For `standard` or `max`, keep using your normal provider policy:

```text
mini      -> gpt-5.3-codex-spark
standard  -> default general-purpose coding model
max       -> strongest available coding model
```

## Example Splits That Fit Spark

Good `mini` / Spark candidates:

- add or update focused tests in owned test files
- write docs for an already-decided change
- make a narrow refactor inside one module
- inspect a bounded codepath and report findings
- implement a small adapter with a clear interface and disjoint write set

Bad `mini` / Spark candidates:

- merging overlapping edits across workers
- redesigning architecture under uncertainty
- debugging unclear production failures
- multi-surface refactors with shared entry points
- recovery from failing integration or verification

## Planning Guidance

If you want more work to route to `GPT-5.3-Codex-Spark`, shape the plan so some
agents are explicitly:

- low-complexity
- bounded to one concern
- assigned a disjoint write set
- unlikely to need design escalation mid-flight

That is the main practical lever. The backend already emits `mini`,
`standard`, and `max`; the launcher decides how to map those tiers to Codex
models.
