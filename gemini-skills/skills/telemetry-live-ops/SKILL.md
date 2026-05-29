---
name: telemetry-live-ops
description: "MACHINE-LOCAL ops skill (not a portable skill): start, verify, and inspect the live ollama-telemetry deployment spanning observer_hub on MAINDESK and host_agent on snd-host. Retarget it with the OLLAMA_TELEMETRY_* env overrides."
---

# Telemetry Live Ops Protocol

## Core Mandate
**This is a MACHINE-LOCAL ops skill, not a portable skill.** It drives the live
ollama-telemetry deployment on this specific machine over SSH from a single
entry point: restart the remote scheduled task, verify both endpoints, and
report exact endpoint timings and partial flags rather than collapsing failures
into generic summaries. The targets are personal infrastructure — retarget with
the `OLLAMA_TELEMETRY_*` env overrides, never by editing hardcoded values.

## Retargeting (environment overrides)
The repo scripts read these environment variables first and fall back to the
documented defaults below:

| Env override | Targets | Documented default |
|---|---|---|
| `OLLAMA_TELEMETRY_REPO` | telemetry repo root | `D:\Development\AI-data-handling\ollama-telemetry` |
| `OLLAMA_TELEMETRY_REMOTE_HOST` | SSH host alias | `snd-host` |
| `OLLAMA_TELEMETRY_REMOTE_URL` | remote API | `http://192.168.2.5:43217` |
| `OLLAMA_TELEMETRY_OBSERVER_URL` | local observer API | `http://127.0.0.1:43191` |

## Execution Rules
1. **Resolve scripts from the telemetry repo, not from this skill.** This Gemini
   adapter ships NO co-located `scripts/` folder. The runtime scripts live in
   the telemetry repo and are reached via `OLLAMA_TELEMETRY_REPO` (default
   `D:\Development\AI-data-handling\ollama-telemetry`). Never invoke a
   co-located `./scripts/...` path.
2. **Use the repo scripts:** Always prefer the repo's own
   `native\scripts\verify-live-deployment.ps1` and
   `native\scripts\start-remote-host-stack.ps1` over ad-hoc curl or SSH commands.
3. **Read globally, write nothing:** This skill orchestrates deployment scripts
   and reports their output. Do not modify the telemetry codebase from this skill.
4. **Evidence Over Intuition:** Report exact HTTP status codes, response timings,
   sensor counts, and partial/truncated flags. Never paraphrase.
5. Follow the global guardrails in GEMINI.md.

## Workflow
Resolve the repo root and targets from the environment, then call the repo
scripts (PowerShell shown; values fall back to the documented defaults):

```powershell
$repo       = if ($env:OLLAMA_TELEMETRY_REPO) { $env:OLLAMA_TELEMETRY_REPO } else { 'D:\Development\AI-data-handling\ollama-telemetry' }
$remoteHost = if ($env:OLLAMA_TELEMETRY_REMOTE_HOST) { $env:OLLAMA_TELEMETRY_REMOTE_HOST } else { 'snd-host' }
$remote     = if ($env:OLLAMA_TELEMETRY_REMOTE_URL) { $env:OLLAMA_TELEMETRY_REMOTE_URL } else { 'http://192.168.2.5:43217' }
$observer   = if ($env:OLLAMA_TELEMETRY_OBSERVER_URL) { $env:OLLAMA_TELEMETRY_OBSERVER_URL } else { 'http://127.0.0.1:43191' }
$remoteUri  = [Uri]$remote
```

1. **Health check only** — run the repo verifier:

   ```powershell
   pwsh "$repo\native\scripts\verify-live-deployment.ps1" `
     -RemoteBaseUrl $remote -ObserverBaseUrl $observer -RemoteTargetName $remoteHost `
     -DirectIterations 5 -ObserverIterations 3 -SensorLimit 10
   ```

   Fast variant (matches the Claude/Codex `status` action):

   ```powershell
   pwsh "$repo\native\scripts\verify-live-deployment.ps1" `
     -RemoteBaseUrl $remote -ObserverBaseUrl $observer -RemoteTargetName $remoteHost `
     -DirectIterations 1 -ObserverIterations 1 -SensorLimit 5
   ```

2. **Restart snd-host** — run the repo restart script:

   ```powershell
   pwsh "$repo\native\scripts\start-remote-host-stack.ps1" `
     -SshHost $remoteHost -ApiHost $remoteUri.Host -ApiPort $remoteUri.Port `
     -ObserverBaseUrl $observer
   ```

3. **Restart and verify end-to-end** — add `-RunVerification`:

   ```powershell
   pwsh "$repo\native\scripts\start-remote-host-stack.ps1" `
     -SshHost $remoteHost -ApiHost $remoteUri.Host -ApiPort $remoteUri.Port `
     -ObserverBaseUrl $observer -RunVerification
   ```

## What Good Looks Like
- Direct `snd-host` `/v1/status` returns a non-zero `sensor_count`
- Direct `snd-host` `/v1/snapshot` returns the expected sensor array
- Observer `/v1/machines` reports `reachable_count = 2` and `partial = false`
- Observer `/v1/sensors` reports `reachable_count = 2` and `partial = false`
- Observer `/v1/overview` reports `machines.partial = false` and `live_partial = false`

`truncated = true` on `/v1/sensors` or `/v1/overview.live_sensors` is expected when a low `limit` is requested — that is NOT a reachability failure.

## Failure Handling
- If a script reports a missing repo path, missing SSH alias, or missing repo script: surface as a machine-global prerequisite problem.
- If direct `snd-host` calls fail but the local observer is healthy: report both separately, not as a single failure.
- If the remote restart succeeds but verification still fails: prefer reporting exact endpoint timings and partial flags over generic summaries.

## Output Contract
For every run, emit:
- The script invoked and its exit code
- Per-endpoint result table: URL, HTTP status, response time, key fields (`sensor_count`, `reachable_count`, `partial`, `truncated`)
- A final PASS / DEGRADED / FAIL verdict with the specific endpoint that drove the verdict
