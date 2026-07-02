# Antigravity Skills

A docs-first adapter for the shared AI Skills workflow stack on Google
Antigravity and Antigravity CLI.

This package ships Agent Skills plus Antigravity workflows. It replaces the
consumer-facing Gemini CLI package path while keeping the same manifest-driven
export boundary: only entries listed in `package/install-manifest.json` are
installed or exported.

## Current Scope

- install packaged skills into `.agents/skills/`
- install workflow entrypoints into `.agent/workflows/`
- inject shared project guardrails into `AGENTS.md`
- keep the package adapter-first until a neutral shared runtime exists

## Included Skills

| Skill | Purpose |
|---|---|
| `discover` | Produce repository findings from read-only analysis |
| `planner` | Produce planning-contract artifacts from discovery context |
| `brief` | Extract exact context needed for a specific task |
| `manager` | Coordinate campaign execution and verification |
| `review` | Review branch, staged, or working-tree diffs against standards, specs, and regression risk |
| `diagnosing-bugs` | Build a red-capable feedback loop, reproduce/minimize the symptom, fix, and verify regressions |
| `qa` | Evaluate completed work against plans, tests, coverage, and smoke checks |
| `ship` | Stage, commit, and prepare validated changes |
| `loop` | Execute focused inspect-edit-verify loops |
| `loop-master` | Supervise larger loop/campaign lifecycle |
| `agent-report` | Produce structured agent handoff and performance reports |
| `build-gate` | Validate build chains, artifact freshness, and target tests |
| `campaign-health` | Find stale plans, orphaned agents, and stuck worktrees |
| `delegate` | Route bounded helper tasks to local Ollama when telemetry readiness allows it |
| `delegation-eval` | Evaluate helper-model routing with telemetry evals and judge packets |
| `docs-sync` | Detect drift between docs and code-facing facts |
| `schema-validator` | Validate schema usage across data, API, and tests |
| `session-stats` | Summarize session/tool activity from measured telemetry where available |
| `smart-test` | Map changes to the smallest useful test subset |
| `token-audit` | Analyze token, cost, and budget usage |
| `truthpack-drift` | Detect drift in reusable truth facts |
| `worktree-preflight` | Check branch, worktree, and file ownership conflicts before launch |
| `epic-refactor` | Execute repo-scale migrations under a strict refactor report |
| `forensic-debugger` | Produce incident RCA and patch proposals from large artifacts |
| `ui-test-engineer` | Triage and fix visual regressions from multimodal evidence |
| `doc-weaver` | Synchronize architecture docs and code-facing docs |
| `guardrails` | Scan the repo for rule violations without editing files |
| `edit` | Apply scoped, surgical file edits |
| `rules-distill` | Distill repeated project conventions into durable rules |
| `memory-management` | Govern durable memory: typed write schema, locality routing, and index budget for AGENTS.md and rule files |

## Package Layout

| Path | Purpose |
|---|---|
| `README.md` | Package overview and scope |
| `AGENTS.md` | Maintainer guidance and installable guardrails |
| `skills/` | Source Agent Skill folders |
| `.agent/workflows/` | Source Antigravity workflow entrypoints |
| `scripts/bootstrap.ps1` | Installer for skills, workflows, and guardrails |
| `package/install-manifest.json` | Shipping metadata |
| `docs/skill-portability-notes.md` | Adapter rules and migration notes |

## Installation

From this package root:

```powershell
.\scripts\bootstrap.ps1 -TargetDir "C:\path\to\target-repo"
```

The bootstrap script creates `.agents/skills/` and `.agent/workflows/`, copies
manifest-listed entries only, and appends the global guardrails to `AGENTS.md`.

## Status

- **Ready:** 30 curated skills and 30 workflows are manifest-listed.
- **Legacy path:** `gemini-skills` remains in this repo for Gemini CLI
  compatibility and historical review, but it is no longer the active
  consumer-facing Google package.
- **Export boundary:** the root export script reads `release-manifest.json` and
  this package's install manifest. Imported ECC reference material is not
  exported unless explicitly manifest-listed.
