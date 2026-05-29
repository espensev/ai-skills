---
name: telemetry-live-ops
description: "MACHINE-LOCAL ops skill (not a portable skill): start, verify, and inspect the live ollama-telemetry deployment spanning observer_hub on MAINDESK and host_agent on snd-host. Retarget it with the OLLAMA_TELEMETRY_* env overrides. Use when tasks mention snd-host, observer_hub, MachineTelemetryHostStack, live telemetry deployment, remote telemetry health, or machine-wide telemetry verification."
argument-hint: "[verify|start|status] — live telemetry operations for MAINDESK and snd-host"
allowed-tools: Read, Glob, Grep, Bash
user-invocable: true
agent-invocable: true
---

# Telemetry Live Ops

**This is a MACHINE-LOCAL ops skill, not a portable skill.** It drives the live
ollama-telemetry deployment on this specific machine over SSH. The command
surface and config are stable, but the targets it points at are personal
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

## Commands

### `/telemetry-live-ops verify`

Run:

```powershell
pwsh ./scripts/telemetry-live-verify.ps1
```

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

- direct `snd-host` `/v1/status` returns a non-zero `sensor_count`
- direct `snd-host` `/v1/snapshot` returns sensors successfully
- observer `/v1/machines` reports `reachable_count = 2` and `partial = false`
- observer `/v1/sensors` reports `reachable_count = 2` and `partial = false`
- observer `/v1/overview` reports `machines.partial = false` and `live_partial = false`

Treat `truncated = true` on live sensor views as expected when low limits are
requested. That is not a deployment failure.

If the wrapper reports a missing repo path, missing SSH alias, or missing repo
script, surface that as a machine-global prerequisite issue.
