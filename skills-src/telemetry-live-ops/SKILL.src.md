---
name: telemetry-live-ops
description: "MACHINE-LOCAL ops skill (not a portable skill): start, verify, and inspect the live ollama-telemetry deployment spanning observer_hub on MAINDESK and host_agent on snd-host. Retarget it with the OLLAMA_TELEMETRY_* env overrides. Use when tasks mention snd-host, observer_hub, MachineTelemetryHostStack, live telemetry deployment, remote telemetry health, or machine-wide telemetry verification."
{{#claude}}
argument-hint: "[verify|start|status] — live telemetry operations for MAINDESK and snd-host"
allowed-tools: Read, Glob, Grep, Bash
user-invocable: true
agent-invocable: true
{{/claude}}
---

# Telemetry Live Ops

**This is a MACHINE-LOCAL ops skill, not a portable skill.** It drives the live
{{#claude}}
ollama-telemetry deployment on this specific machine over SSH. The command
surface and config are stable, but the targets it points at are personal
{{/claude}}
{{#codex}}
ollama-telemetry stack on this specific machine over SSH. The command surface
and config are stable, but the targets it points at are personal
{{/codex}}
infrastructure. Retarget it for another machine with the environment overrides
below — never edit hardcoded values into the skill.

## Retargeting (environment overrides)

The bundled scripts read these environment variables first and fall back to the
documented defaults below:

| Env override | Targets | Documented default |
|---|---|---|
| `OLLAMA_TELEMETRY_REPO` | telemetry repo root | `D:\Development\AI-data-handling\ollama-telemetry` |
| `OLLAMA_TELEMETRY_REMOTE_HOST` | SSH host alias | `snd-host` |
| `OLLAMA_TELEMETRY_REMOTE_URL` | remote API | `http://192.168.2.5:43217` |
| `OLLAMA_TELEMETRY_OBSERVER_URL` | local observer API | `http://127.0.0.1:43191` |

{{#claude}}
## Commands
{{/claude}}
{{#codex}}
Bundled commands:
{{/codex}}

{{#claude}}
### `/telemetry-live-ops verify`
{{/claude}}
{{#codex}}
- `scripts/telemetry-live-start.ps1`
- `scripts/telemetry-live-verify.ps1`
{{/codex}}

{{#claude}}
Run:
{{/claude}}
{{#codex}}
## Workflow
{{/codex}}

{{#claude}}
```powershell
pwsh ./scripts/telemetry-live-verify.ps1
```
{{/claude}}
{{#codex}}
1. If the task is to assess or review live deployment health, run:
   `pwsh ./scripts/telemetry-live-verify.ps1`
2. If the task is to restart or recover `snd-host`, run:
   `pwsh ./scripts/telemetry-live-start.ps1`
3. If the task is to restart and then validate end to end, run:
   `pwsh ./scripts/telemetry-live-start.ps1 -RunVerification`
{{/codex}}

{{#claude}}
Use this for review, health checks, and before/after deployment validation.

### `/telemetry-live-ops start`

Run:

```powershell
pwsh ./scripts/telemetry-live-start.ps1
```

Use this when `snd-host` needs to be restarted from MAINDESK over SSH.

### `/telemetry-live-ops start --verify`

Run:

```powershell
pwsh ./scripts/telemetry-live-start.ps1 -RunVerification
```

Use this for a full restart and end-to-end validation pass.

### `/telemetry-live-ops status`

Run a fast check:

```powershell
pwsh ./scripts/telemetry-live-verify.ps1 -DirectIterations 1 -ObserverIterations 1 -SensorLimit 5
```

## Healthy Output
{{/claude}}
{{#codex}}
## What Good Looks Like
{{/codex}}

- direct `snd-host` `/v1/status` returns a non-zero `sensor_count`
{{#claude}}
- direct `snd-host` `/v1/snapshot` returns sensors successfully
{{/claude}}
{{#codex}}
- direct `snd-host` `/v1/snapshot` returns the expected sensor array
{{/codex}}
- observer `/v1/machines` reports `reachable_count = 2` and `partial = false`
- observer `/v1/sensors` reports `reachable_count = 2` and `partial = false`
- observer `/v1/overview` reports `machines.partial = false` and `live_partial = false`

{{#claude}}
Treat `truncated = true` on live sensor views as expected when low limits are
requested. That is not a deployment failure.
{{/claude}}
{{#codex}}
Treat `truncated = true` on `/v1/sensors` or `/v1/overview.live_sensors` as
expected when a low `limit` is requested. That is not a reachability failure.
{{/codex}}

{{#claude}}
If the wrapper reports a missing repo path, missing SSH alias, or missing repo
script, surface that as a machine-global prerequisite issue.
{{/claude}}
{{#codex}}
## Failure Handling
{{/codex}}

{{#codex}}
- If the wrapper reports a missing repo path, missing SSH alias, or missing repo
  script, surface that as a machine-global prerequisite problem.
- If direct `snd-host` calls fail but local observer is healthy, report both
  separately instead of collapsing them into one failure.
- If the remote restart succeeds but verification still fails, prefer reporting
  exact endpoint timings and partial flags over generic summaries.

{{/codex}}