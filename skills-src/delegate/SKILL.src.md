---
name: delegate
{{#claude}}
description: "Decide whether a narrow, well-scoped sub-task should go to a LOCAL Ollama model vs stay with the controller, and route it if so. Grounded in the ollama-telemetry MCP delegation tools, with a static-guidance fallback when the MCP server is unavailable. Use when offloading a bounded transform (summarize/classify/extract/rewrite/review/draft) on material the controller already fetched."
argument-hint: "<command|task> — guidance | check | batch | <task description>"
allowed-tools: Read, Glob, Grep, mcp__ollama-delegate__ollama_usage_guidance, mcp__ollama-delegate__ollama_readiness, mcp__ollama-delegate__ollama_delegate, mcp__ollama-delegate__ollama_batch_delegate, mcp__ollama-delegate__ollama_fleet_status
user-invocable: true
agent-invocable: true
{{/claude}}
{{#codex}}
description: "Decide whether a narrow, well-scoped sub-task should go to a LOCAL Ollama model vs stay with the controller, and route it if so. Grounded in the ollama-telemetry MCP delegation tools with a static-guidance fallback. Use when offloading a bounded transform (summarize/classify/extract/rewrite/review/draft) on material the controller already fetched."
{{/codex}}
---

# Delegate {{dash}} Route Bounded Sub-Tasks to a Local Ollama Model

Help a controller agent decide whether to hand a **narrow, well-scoped, reviewable**
sub-task to a LOCAL Ollama model, or keep it with the controller {{dash}} then route it when
appropriate. Local delegation is for cheap, bounded transforms on material the
controller **has already fetched**. The controller always stays in charge and always
verifies the result.

This skill is **MCP-aware but MCP-optional**. The active-routing path depends on the
`ollama-telemetry` MCP server (server name `ollama-delegate`) being registered in this
host. When it is not registered, or when the fleet is degraded, the skill falls back to
**static guidance** and tells the controller to do the task itself.

**MCP tools used (when registered):** `ollama_usage_guidance`, `ollama_readiness`,
`ollama_delegate`, `ollama_batch_delegate`, and optionally `ollama_fleet_status`.

---

## The Delegation Philosophy

Use Ollama as a **bounded local helper**, not as the agent in charge. The normal loop:

1. Controller decides what to inspect or fetch.
2. Controller gathers the files, logs, API output, or web results.
3. Ollama performs one narrow transformation on that material.
4. Controller **verifies** the result and makes the real decision.

`fetch`, `plan`, and `decide` always stay with the controller. Local delegation is never
for architecture, security, deployment, rollback, arithmetic, code tracing, or
multi-step reasoning.

---

## Commands

| Command | Usage | Purpose |
|---------|-------|---------|
| `guidance` | `{{cmd}}delegate guidance` | Show the static safe-task split + client compatibility. Works with NO fleet and even when the MCP server is absent. |
| `check` | `{{cmd}}delegate check` | Report whether local delegation is usable right now (`delegation_usable` / `degraded`). |
| `<task>` | `{{cmd}}delegate <task description>` | Classify the task, refuse if it is a non-delegatable category, else route it and surface the verify hint and savings. |
| `batch` | `{{cmd}}delegate batch` | Route 3+ similar independent items in parallel. |

Default to `guidance` if no command is given and no task is described.

---

## Task Classification (the gate)

A task is **delegatable** only if it maps to one of these bounded task types:

| task_type | Good for | Default model* |
|-----------|----------|----------------|
| `summarize` | log bursts, build/test output, diffs, notes | qwen3:8b |
| `classify` | fixed-label routing, severity/commit buckets | qwen3-coder:30b |
| `extract` | env var names, routes, TODOs, counts, IPs | qwen3-coder:30b |
| `rewrite` | rough notes {{arrow}} cleaner factual text | qwen3:8b |
| `review` | first-pass spotting of OBVIOUS issues only | qwen3:8b |
| `draft` | compact controller-ready snippets | qwen3:8b |

*Model selection is owned by the MCP server's `dispatch-rules.json`. The table above is
the current default mapping; do not hardcode it as a routing decision {{dash}} pass the
`task_type` and let the server resolve the model.

### Non-delegatable {{dash}} REFUSE and keep with controller

Refuse to delegate (route nothing; tell the controller to handle it) when the task is:

- **`transform`** {{dash}} the one task type hard-blocked in `dispatch-rules.json`
  (`blocked_tasks`). Local models fail on data-processing pipelines.
- **Architecture / migration decisions** (e.g. Redis vs RabbitMQ, schema design).
- **Deployment, rollback, or release approval.**
- **Security-sensitive work** {{dash}} secrets review, credential analysis, raw PII.
- **Multi-step planning or reasoning chains** (deploy strategy, migration plan).
- **Arithmetic or code tracing** ("what does this loop compute?").
- **Deciding what to fetch / what to do next** {{dash}} controller-only judgment.
- **Ambiguous scope** with multiple valid interpretations, or missing context.
- Any task where **refusal quality matters more than processing quality**.

When refusing, say plainly: *"Keep this with the controller {{dash}} <reason>."* Do not call
any MCP tool for a refused task.

---

## Hard Safety / Fallback Rules (the spine)

These rules are absolute and override every command below.

1. **MCP server not registered.** If the `ollama_*` tools are absent from this host,
   do **not** error. Fall back to static guidance (the table and rules above), and
   instruct the controller to do the task itself ("stay with controller"). You may still
   answer `{{cmd}}delegate guidance` and classify tasks from this document alone.
2. **Registered but degraded.** If `ollama_readiness` reports `status: "degraded"` or
   `delegation_usable: false` (telemetry API unreachable, or no reachable fleet
   machines), **stay with the controller**. Report the readiness reason; do not route.
3. **Controller owns the output.** Local delegation is for narrow, reviewable sub-tasks
   under supervision. The controller MUST verify the local model's output using the
   returned `verify_hint` before using it. Never delegate architecture, security, or
   destructive work {{dash}} see the refuse list above.
4. **Escalation is honored.** If a delegation returns `status: "escalate"`, treat it as
   "the local model declined" {{dash}} the controller takes the task back.

---

## Command: `guidance` {{dash}} Static Safe-Task Split

Goal: show when to delegate, when not to, and which path is available {{dash}} without touching
the telemetry API.

### Steps

1. If the MCP server is registered, call `ollama_usage_guidance` (no arguments; works
   without the telemetry API) and surface its safe-task split + client compatibility.
2. If the MCP server is **not** registered, present the static split from the
   **Task Classification** section above and note that active routing is unavailable
   here {{dash}} the controller should do bounded tasks itself.

### Report

```
Delegate {{dash}} Guidance

  Delegatable : summarize, classify, extract, rewrite, review (verified), draft
  Refuse      : transform, architecture, security, deploy/rollback, arithmetic,
                code-tracing, planning, ambiguous, fetch/plan/decide
  Routing     : MCP active | static-only (server not registered)
  Rule        : controller fetches {{arrow}} local transforms {{arrow}} controller verifies
```

---

## Command: `check` {{dash}} Is Delegation Usable Now?

Goal: a fast "should I reach for local delegation at all?" answer.

### Steps

1. If the MCP server is not registered {{arrow}} report `routing: static-only`, advise
   stay-with-controller, and stop. (No error.)
2. Otherwise call `ollama_readiness`. Read `delegation_usable`, `status`, and the
   `telemetry_api` / `fleet` fields.
3. Optionally call `ollama_fleet_status` for deeper per-machine detail only if the
   controller asked for it.

### Report

```
Delegate {{dash}} Readiness

  delegation_usable : true | false
  status            : ok | degraded
  telemetry_api     : <base_url> reachable=<bool>
  fleet             : <reachable>/<machine_count> machines, batch_max=<n>
  Verdict           : ROUTE-OK | STAY-WITH-CONTROLLER (<reason>)
```

If `delegation_usable` is false, the verdict is always STAY-WITH-CONTROLLER.

---

## Command: `<task description>` {{dash}} Classify, then Route or Refuse

Goal: decide one task and act on it.

### Steps

1. **Classify** the described task against the **Task Classification** table.
   - If it is a non-delegatable category {{arrow}} **REFUSE**: tell the controller to handle it
     and why. Stop. Do not call any MCP tool.
   - Else pick the matching `task_type` (summarize / classify / extract / rewrite /
     review / draft).
2. **Bounds check.** Confirm the controller has already fetched the source material and
   the task is a single bounded transformation on it. If the material is missing or the
   ask requires deciding what to fetch, refuse and keep it with the controller.
3. **Availability check.**
   - MCP not registered {{arrow}} fall back to static guidance, stay with controller.
   - Else call `ollama_readiness`; if not `delegation_usable` {{arrow}} stay with controller.
4. **Route** via `ollama_delegate` with:
   - `task_type` (from step 1),
   - `prompt` (the bounded instruction + the already-fetched material),
   - `require_json: true` only when a strict machine-readable shape is needed,
   - optional `verify_hint` describing what the controller should check.
5. **Handle the result:**
   - `status: "ok"` {{arrow}} surface the response, the returned `verify_hint`, and the savings
     from `metrics.sonnet_equivalent_cost_usd` / `session_totals.sonnet_equivalent_saved_usd`.
   - `status: "escalate"` {{arrow}} the local model declined; controller takes it back.
   - `status: "error"` (including blocked task_type) {{arrow}} report the error and keep the
     task with the controller.
6. **Always** remind the controller to verify the output against the source using the
   `verify_hint` before acting on it.

### Report

```
Delegate {{dash}} Route

  Task type   : extract
  Decision    : ROUTED to local model (qwen3-coder:30b)
  Status      : ok
  Verify      : <verify_hint {{dash}} what the controller must confirm>
  Savings     : ~$<sonnet_equivalent_saved_usd> vs Sonnet this session

  --- model output ---
  <response>
```

For a refusal:

```
Delegate {{dash}} Route

  Task type   : (architecture decision)
  Decision    : STAY WITH CONTROLLER
  Reason      : architecture/migration choices are never delegated to local models
```

---

## Command: `batch` {{dash}} 3+ Similar Independent Items

Goal: route multiple bounded transformations in parallel.

### When to use

Prefer `batch` over a loop of single delegations when you have **3+ similar,
independent** items (e.g. summarize 12 log files, classify 20 issues). Tasks must be
independent of each other.

### Steps

1. Classify the batch's task type. If any item is a non-delegatable category, drop those
   items and keep them with the controller; route only the rest.
2. Availability check (registration + `ollama_readiness`), same as a single route.
3. Call `ollama_batch_delegate` with a `tasks` array; each task carries `id`,
   `task_type`, `prompt`, and optional `require_json` / `verify_hint`. Submit the full
   set {{dash}} the server auto-chunks to the fleet's parallel width (`batch_max`); do not
   pre-split.
4. Surface per-item results plus the `summary` (succeeded/failed, savings) and remind
   the controller to verify each output. Honor `status: "escalate"` per item and
   `status: "partial"` on chunk failure (route the failed remainder to the controller).

### Report

```
Delegate {{dash}} Batch

  Items       : 12 (12 delegatable, 0 refused)
  Status      : ok (12 succeeded, 0 failed)  | partial
  Savings     : ~$<sonnet_equivalent_cost_usd> vs Sonnet
  Verify      : <per-task verify hints {{dash}} controller confirms each>
```

---

## Conventions

- **MCP-optional:** never error because the MCP server is absent {{dash}} fall back to static
  guidance and stay with the controller.
- **Refuse early:** classify before touching any MCP tool; never route a non-delegatable
  category.
- **Controller verifies:** every routed result must carry a verify hint and a reminder
  that the controller owns the final decision.
- **No machine-specific paths:** model and machine selection live in the MCP server's
  `dispatch-rules.json`; pass `task_type` and let the server resolve. Do not hardcode
  machine names or endpoints in this skill.
- **Read-only on the source:** delegation transforms fetched material; it never decides
  what to fetch or what to do next.
- Default command is `guidance`, not a route {{dash}} classify before acting.
