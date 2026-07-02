# Release Readiness

This repository contains multiple package shapes. Not every package is shipped
the same way, so release readiness is tracked explicitly.

## Ready Packages

| Package | Status | Delivery | Notes |
|---|---|---|---|
| `codex-skills` | Ready | Portable runtime package | Ships skill docs, contracts, and Python runtime modules. |
| `claude-skills` | Ready | Portable runtime package | Ships skill docs, contracts, and Python runtime modules. |
| `antigravity-skills` | Ready | Antigravity adapter package | Ships Agent Skills, workflows, bootstrap script, and guardrails. |

## Not Part Of Skill Export

| Package | Status | Notes |
|---|---|---|
| `gemini-skills` | Legacy source package | Retained for Gemini CLI enterprise/API-key compatibility and historical review; not exported by default. |
| `wt-cli` | Source package only | Useful tooling for worktree orchestration, but not part of the model skill export bundle. |
| `telemetry-live-ops` | Source-only machine-local skill | Kept under provider skill trees for this workstation's live `ollama-telemetry` deployment; intentionally excluded from install manifests and ready exports. |

## Release Checklist

Run the full local release gate before shipping:

```powershell
.\scripts\Test-ReleaseReadiness.ps1
```

The wrapper runs ready-package validation, README manifest count checks, Codex
and Claude contract tests, provider parity reporting, and git whitespace checks.
Use `-IncludeLiveRootCompare` after syncing local Codex and Claude skill roots.

Individual checks are also available when narrowing a failure:

```powershell
.\scripts\Update-ReadmePackageCounts.ps1 -Check
.\scripts\Compare-ProviderSkillParity.ps1 -MaxRows 20
```

## Export Flow

Validate the ready-package manifests, source-only exclusions, README counts,
Antigravity workflow targets, export smoke, installer smoke, and Antigravity
bootstrap smoke first:

```powershell
.\scripts\Test-ReadyPackages.ps1
```

Use the root export script to gather the ready packages into one destination:

```powershell
.\scripts\export-ready-skill-packages.ps1 -TargetDir ".\dist\ai-skills-ready-packages" -Force
```

The script reads `release-manifest.json` and exports only packages whose status
is `ready`. If `-TargetDir` is omitted, the script falls back to the manifest
default export location.

## Local Root Compare

After running `Install-AgentSkills.ps1`, compare installed Codex and Claude
skill roots against manifest-listed source files:

```powershell
.\scripts\Compare-AgentSkillRoots.ps1 -Provider Both -FailOnMissingOrStale
```

Pass `-IncludeExtra` when you intentionally want to list unrelated local skills
that are present in an agent root but not managed by these packages.
