# Release Readiness

This repository contains multiple package shapes. Not every package is shipped
the same way, so release readiness is tracked explicitly.

## Ready Packages

| Package | Status | Delivery | Notes |
|---|---|---|---|
| `codex-skills` | Ready | Portable runtime package | Ships skill docs, contracts, and Python runtime modules. |
| `claude-skills` | Ready | Portable runtime package | Ships skill docs, contracts, and Python runtime modules. |
| `gemini-skills` | Ready | Bootstrap adapter package | Ships Gemini skills, Gemini command wrappers, bootstrap script, and guardrails. |

## Not Part Of Skill Export

| Package | Status | Notes |
|---|---|---|
| `wt-cli` | Source package only | Useful tooling for worktree orchestration, but not part of the model skill export bundle. |
| `telemetry-live-ops` | Source-only machine-local skill | Kept under provider skill trees for this workstation's live `ollama-telemetry` deployment; intentionally excluded from install manifests and ready exports. |

## Export Flow

Use the root export script to gather the ready packages into one destination:

```powershell
.\scripts\export-ready-skill-packages.ps1 -TargetDir ".\dist\ai-skills-ready-packages" -Force
```

The script reads `release-manifest.json` and exports only packages whose status
is `ready`. If `-TargetDir` is omitted, the script falls back to the manifest
default export location.
