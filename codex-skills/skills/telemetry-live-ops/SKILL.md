---
name: telemetry-live-ops
description: "MACHINE-LOCAL ops skill (not a portable skill): start, verify, and inspect the live ollama-telemetry deployment spanning observer_hub on MAINDESK and host_agent on snd-host. Retarget it with the OLLAMA_TELEMETRY_* env overrides. Use when tasks mention snd-host, observer_hub, MachineTelemetryHostStack, live telemetry deployment, remote telemetry health, or machine-wide telemetry verification."
---

# Telemetry Live Ops

**This is a MACHINE-LOCAL ops skill, not a portable skill.** It drives the live
ollama-telemetry stack on this specific machine over SSH. The command surface
and config are stable, but the targets it points at are personal
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

Bundled commands:

- `scripts/telemetry-live-start.ps1`
- `scripts/telemetry-live-verify.ps1`

## Workflow

1. If the task is to assess or review live deployment health, run:
   `pwsh ./scripts/telemetry-live-verify.ps1`
2. If the task is to restart or recover `snd-host`, run:
   `pwsh ./scripts/telemetry-live-start.ps1`
3. If the task is to restart and then validate end to end, run:
   `pwsh ./scripts/telemetry-live-start.ps1 -RunVerification`

## What Good Looks Like

- direct `snd-host` `/v1/status` returns a non-zero `sensor_count`
- direct `snd-host` `/v1/snapshot` returns the expected sensor array
- observer `/v1/machines` reports `reachable_count = 2` and `partial = false`
- observer `/v1/sensors` reports `reachable_count = 2` and `partial = false`
- observer `/v1/overview` reports `machines.partial = false` and `live_partial = false`

Treat `truncated = true` on `/v1/sensors` or `/v1/overview.live_sensors` as
expected when a low `limit` is requested. That is not a reachability failure.

## Failure Handling

- If the wrapper reports a missing repo path, missing SSH alias, or missing repo
  script, surface that as a machine-global prerequisite problem.
- If direct `snd-host` calls fail but local observer is healthy, report both
  separately instead of collapsing them into one failure.
- If the remote restart succeeds but verification still fails, prefer reporting
  exact endpoint timings and partial flags over generic summaries.
