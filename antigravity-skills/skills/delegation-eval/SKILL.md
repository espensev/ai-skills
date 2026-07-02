---
name: delegation-eval
description: Evaluate and tune local Ollama delegation using ollama-telemetry eval runs, judge packets, usage metrics, and dispatch recommendations. Use when comparing local models for bounded helper tasks, running no-interference or controller-assistant evals, judging outputs, reviewing dispatch-rule drift, or deciding whether /delegate routing should change
---

# Delegation Eval Protocol

## Core Mandate
Measure whether local Ollama models are useful as bounded helpers under a
stronger controller. This is not live routing. Use `/delegate` for one bounded
task; use `/delegation-eval` to decide which models and task mappings deserve
to stay in dispatch rules.

The source of truth is the `ollama-telemetry` repo and its API/MCP surfaces.
Do not duplicate its scripts into this adapter.

## Execution Rules
1. **Resolve repo first:** Use `OLLAMA_TELEMETRY_REPO`, then
   `[delegation-eval].telemetry_repo`, then a sibling `ollama-telemetry` or
   `AI-data-handling/ollama-telemetry` checkout. If not found, stop and ask for
   `OLLAMA_TELEMETRY_REPO`.
2. **API is optional until running evals:** Probe `OLLAMA_TELEMETRY_URL` or
   `http://127.0.0.1:8099`. If unavailable, status/recommend may degrade to
   docs and existing logs. For `run`, start the API with
   `pwsh ./start-telemetry.ps1` only because the user asked to run evals.
3. **Controller judges:** Never use local Ollama models to judge local Ollama
   trustworthiness.
4. **Do not silently mutate routing:** `update-rules` proposes or applies a
   reviewed patch only after recommendations meet evidence thresholds.

## Commands
- `/delegation-eval status` - repo/API/recent-runs/dispatch snapshot.
- `/delegation-eval run [no-interference|controller-assistant] [candidates]` -
  run an eval pack from the telemetry repo.
- `/delegation-eval judge <run-id>` - export judge packet, score with the
  controller, and apply judgments.
- `/delegation-eval recommend` - aggregate judged evals into task_type -> model
  recommendations.
- `/delegation-eval update-rules` - propose a minimal dispatch-rules patch.

Default to `status`.

## Data Sources
Read only what the command needs:
- `docs/ollama-task-map.md`
- `docs/dispatch-rules.md`
- `ollama-testing/README.md`
- `agents/ollama-mcp-server/dispatch-rules.json`
- API: `/health`, `/api/evals/runs`, `/api/evals/runs/{runId}`,
  `/api/llm/overview`, `/api/llm/ollama/inference`
- MCP when available: `dispatch_recommendations`, `ollama_readiness`,
  `llm_usage_overview`, `ollama_inference_history`

## Status Workflow
Report telemetry repo path and dirty/clean status, API reachability, the latest
eval runs, current task mappings, and any recommendation drift. If MCP is
available, call `dispatch_recommendations`; otherwise say MCP unavailable.

## Run Workflow
Run evals from the telemetry repo only when requested:

```powershell
pwsh ./ollama-testing/invoke-no-interference-eval.ps1
```

or:

```powershell
pwsh ./ollama-testing/invoke-controller-assistant-eval.ps1 `
  -Candidates 'machine=model','machine=model'
```

Capture run id, candidates, error count, and output path. Do not judge the run
unless the user asked for `run + judge`.

## Judge Workflow
Export the judge packet, score it with the controller model, write judgments in
the template shape, then apply them:

```powershell
pwsh ./ollama-testing/export-controller-assistant-judge-packet.ps1 `
  -RunId '<run-id>' `
  -OutputPath '.\tmp\judge-packet-<run-id>.json'

pwsh ./ollama-testing/apply-controller-assistant-judgments.ps1 `
  -RunId '<run-id>' `
  -JudgmentsPath '.\tmp\controller-assistant-judgments-<run-id>.json'
```

Score factual preservation, strict-format compliance, escalation/refusal,
compactness, and whether the result should be delegated again.

## Recommendation Rules
Prefer MCP `dispatch_recommendations`. If unavailable, aggregate recent eval
run details by task type and model. Recommend a mapping change only with at
least 3 judged samples, average score >= 0.6, error rate <= 20%, acceptable
no-interference behavior, and compact controller-verifiable output. Never
recommend enabling `transform`.

## Integration
- `/delegate` routes live bounded work.
- `/delegation-eval` measures whether routing should change.
- `/session-stats` and `/token-audit` consume usage/cost telemetry.
- `telemetry-live-ops` is machine-local and excluded from portable manifests.
