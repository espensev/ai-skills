# Ollama Telemetry Integration

This repo should tie into `ollama-telemetry` through stable contracts, not by
copying its implementation.

## Decision

Use three layers:

1. **Live delegation:** `delegate` calls the `ollama-telemetry` MCP tools when
   registered. It falls back to static guidance when the MCP server or fleet is
   unavailable.
2. **Measured analytics:** `usage-stats` prefers the local telemetry API at
   `http://127.0.0.1:8099` for measured usage and cost data, then falls back
   to hooks/transcript estimates.
3. **Evaluation and tuning:** `delegation-eval` uses telemetry eval runs, judge
   packets, and `dispatch_recommendations` to decide whether model/task routing
   should change.

`telemetry-live-ops` remains source-only. It is useful for this machine's live
deployment, but it contains machine-local assumptions and must not ship in the
portable packages.

## Local Checkout

For this workstation, set:

```powershell
$env:OLLAMA_TELEMETRY_REPO = 'D:\Development\AI-data-handling\ollama-telemetry'
```

Portable skills should resolve that env var or a project config value. They
should not hard-code the local path into exported package behavior.

## What Not To Do

- Do not duplicate eval scripts from `ollama-telemetry`.
- Do not let local Ollama models judge their own trustworthiness.
- Do not enable routing changes without judged eval evidence.
- Do not export machine-local live deployment skills.
