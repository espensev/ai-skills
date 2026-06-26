---
name: delegate
description: Decide whether a narrow, well-scoped sub-task should go to a LOCAL Ollama model vs stay with the controller, and route it if so — grounded in the ollama-telemetry MCP delegation tools with a static-guidance fallback
---

# Delegate Protocol

## Core Mandate
Help a controller agent decide whether to hand a narrow, well-scoped, reviewable sub-task to a LOCAL Ollama model, or keep it with the controller — then route it when appropriate. Local delegation is for cheap, bounded transforms on material the controller HAS ALREADY FETCHED. The controller always stays in charge and always verifies the result.

This skill is MCP-aware but MCP-optional. The active-routing path depends on the `ollama-telemetry` MCP server (server name `ollama-delegate`) being registered in this host. When it is not registered, or when the fleet is degraded, fall back to static guidance and tell the controller to do the task itself.

MCP tools used (when registered): `ollama_usage_guidance`, `ollama_readiness`, `ollama_delegate`, `ollama_batch_delegate`, and optionally `ollama_fleet_status`.

## Execution Rules
1. **Follow the guardrails:** Operate under the global guardrails in GEMINI.md. This is an ops/routing skill, not a planning skill — no planning-contract gate applies.
2. **Refuse early:** Classify the task before touching any MCP tool. Never route a non-delegatable category.
3. **Controller verifies:** Every routed result must carry a verify hint and a reminder that the controller owns the final decision.
4. **No machine-specific paths:** Model and machine selection live in the MCP server's `dispatch-rules.json` — pass `task_type` and let the server resolve. Never hardcode machine names or endpoints.

## Delegation Loop
Controller decides what to fetch → controller gathers the material → Ollama performs one narrow transformation → controller verifies and decides. `fetch`, `plan`, and `decide` always stay with the controller.

## Commands
- `/delegate guidance` — Show the static safe-task split + client compatibility. Works with NO fleet and even when the MCP server is absent. (Default action.)
- `/delegate check` — Report whether local delegation is usable right now (`delegation_usable` / `degraded`).
- `/delegate <task description>` — Classify the task; refuse if non-delegatable, else route it and surface the verify hint and savings.
- `/delegate batch` — Route 3+ similar independent items in parallel.

Default to `guidance` if no command is given and no task is described.

## Task Classification (the gate)
Delegatable only if it maps to one of these bounded task types. Model selection is owned by the server's `dispatch-rules.json` — this is the current default mapping, not a routing decision to hardcode:

| task_type | Good for | Default model |
|-----------|----------|---------------|
| summarize | log bursts, build/test output, diffs, notes | qwen3:8b |
| classify | fixed-label routing, severity/commit buckets | qwen3-coder:30b |
| extract | env var names, routes, TODOs, counts, IPs | qwen3-coder:30b |
| rewrite | rough notes -> cleaner factual text | qwen3:8b |
| review | first-pass spotting of OBVIOUS issues only | qwen3:8b |
| draft | compact controller-ready snippets | qwen3:8b |

### Non-delegatable — REFUSE and keep with controller
Route nothing and tell the controller to handle it when the task is:
- `transform` — the one task type hard-blocked in `dispatch-rules.json` (`blocked_tasks`).
- Architecture / migration decisions (Redis vs RabbitMQ, schema design).
- Deployment, rollback, or release approval.
- Security-sensitive work — secrets review, credential analysis, raw PII.
- Multi-step planning or reasoning chains.
- Arithmetic or code tracing.
- Deciding what to fetch / what to do next — controller-only judgment.
- Ambiguous scope, multiple valid interpretations, or missing context.
- Any task where refusal quality matters more than processing quality.

When refusing, say plainly: "Keep this with the controller — <reason>." Do not call any MCP tool for a refused task.

## Hard Safety / Fallback Rules (the spine — absolute, override every command)
1. **MCP server not registered:** If the `ollama_*` tools are absent, do NOT error. Fall back to static guidance and instruct the controller to do the task itself ("stay with controller"). `/delegate guidance` and classification still work from this document alone.
2. **Registered but degraded:** If `ollama_readiness` reports `status: "degraded"` or `delegation_usable: false`, stay with the controller. Report the reason; do not route.
3. **Controller owns the output:** Delegation is for narrow, reviewable sub-tasks under supervision. The controller MUST verify the output via `verify_hint` before using it. Never delegate architecture, security, or destructive work.
4. **Escalation is honored:** A `status: "escalate"` result means the local model declined — the controller takes the task back.

## Workflow per command
- **guidance:** If MCP is registered, call `ollama_usage_guidance` (no args; works without the telemetry API) and surface its safe-task split + client compatibility. Otherwise present the static split above and note routing is static-only here.
- **check:** If MCP is not registered → report `routing: static-only`, advise stay-with-controller, stop (no error). Else call `ollama_readiness`; read `delegation_usable`, `status`, `telemetry_api`, `fleet`. If `delegation_usable` is false the verdict is always STAY-WITH-CONTROLLER. Call `ollama_fleet_status` only if deeper detail is requested.
- **`<task>`:** (1) Classify; refuse non-delegatable categories without any MCP call. (2) Bounds check — confirm the controller already fetched the material and the task is one bounded transform. (3) Availability check (registration + `ollama_readiness`); if not usable, stay with controller. (4) Route via `ollama_delegate` with `task_type`, `prompt` (instruction + fetched material), optional `require_json` (only for strict machine-readable output) and `verify_hint`. (5) Handle result: `ok` → surface response + `verify_hint` + savings (`metrics.sonnet_equivalent_cost_usd` / `session_totals.sonnet_equivalent_saved_usd`); `escalate` → controller takes it back; `error` (including blocked task_type) → report and keep with controller. (6) Always remind the controller to verify against the source.
- **batch:** Use for 3+ similar independent items. Classify; drop and keep any non-delegatable items with the controller. Availability check. Call `ollama_batch_delegate` with a `tasks` array (`id`, `task_type`, `prompt`, optional `require_json` / `verify_hint`); submit the full set — the server auto-chunks to the fleet's parallel width (`batch_max`), do not pre-split. Surface per-item results + `summary`, honor per-item `escalate` and chunk-level `partial` (route the failed remainder to the controller), and remind the controller to verify each output.

## Output Contract
For every run emit one of:
- **Guidance:** delegatable set, refuse set, routing path (MCP active | static-only), the fetch→transform→verify rule.
- **Readiness:** `delegation_usable`, `status`, telemetry API reachability, fleet reachable/total + `batch_max`, and a ROUTE-OK | STAY-WITH-CONTROLLER verdict with reason.
- **Route:** task type, decision (ROUTED to <model> | STAY WITH CONTROLLER), status, verify hint, savings, and the model output (when routed).
- **Batch:** item count (delegatable vs refused), overall status (ok | partial, succeeded/failed), savings, and per-task verify hints.
