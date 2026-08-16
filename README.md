# AI Skills

**Manifest-driven skill packages for AI coding agents — ready-to-export bundles for Claude Code and Codex, plus the shared contracts and validation tooling that support them.**

This repo curates reusable workflows for planning, testing, review, shipping,
multi-agent worktree orchestration, lightweight Codex sidecar routing,
docs/schema drift checks, telemetry-aware token and cost analysis, and local
Ollama delegation. The shipping surface is
deliberately explicit: `release-manifest.json` selects ready packages, and each
package's `package/install-manifest.json` selects the skills, runtime files,
contracts, workflows, and wrappers that are exported.

59 install-ready skills ship across two provider-specific packages:

| Package | Skills | What it adds |
|---|:---:|---|
| **claude-skills** | 23 | Core campaign orchestration plus deep runtime audit, skill authoring, review/debug workflows, shared ops/analytics, and worktree guardrails for Claude Code |
| **codex-skills** | 36 | Extended toolkit for Codex: API/engineering patterns, gated audits, deep research, Playwright e2e, skill authoring, lightweight parallel sidecar routing, review/debug workflows, and the full ops/analytics and verification suite |

> Counts reflect each ready package's `package/install-manifest.json`.
> Explicit `source_only_skills` entries and unmanifested imported material stay as
> reference surfaces and do not ship in ready-package exports.

## Quick Start

**Run the release checklist**:

```powershell
.\scripts\Test-ReleaseReadiness.ps1
```

**Validate ready packages** with manifest, export, and installer smoke checks:

```powershell
.\scripts\Test-ReadyPackages.ps1
```

**Export all ready packages** into a target folder:

```powershell
.\scripts\export-ready-skill-packages.ps1 -TargetDir ".\dist\ai-skills-ready-packages" -Force
```

**Make Codex and Claude skills available locally** from this workstation's
agent skill roots:

```powershell
.\scripts\Install-AgentSkills.ps1 -Provider Both -Force
```

Compare the installed Codex and Claude roots against the manifests:

```powershell
.\scripts\Compare-AgentSkillRoots.ps1 -Provider Both -FailOnMissingOrStale
```

## What's Inside

### Core campaign skills (shared across packages)

| Skill | Purpose |
|---|---|
| **planner** | Design structured multi-agent campaign plans with work decomposition and dependency mapping |
| **manager** | Orchestrate parallel agents in worktrees — launch, merge, verify builds |
| **discover** | Research a codebase before planning — map dependencies, assess feasibility, identify constraints |
| **qa** | Run tests, check coverage, triage failures, smoke-test a configured app (HTTP or desktop/GUI), generate regression tests |
| **diagnosing-bugs** | Build a tight red-capable feedback loop, reproduce/minimize the symptom, fix, and verify hard bugs or performance regressions |
| **review** | Review branch, staged, or working-tree diffs against standards, specs, and regression risk, writing durable findings under `docs/reviews/` |
| **ship** | Stage, commit, push validated work with campaign-aware commit grouping |
| **observer** | Passive project intelligence — observe patterns over time without interfering |
| **loop** | Run focused work loops with repeated inspect-edit-verify cycles |

### Ops & analytics suite (shared across packages)

| Skill | Purpose |
|---|---|
| **build-gate** | Validate multi-target build chains, artifact freshness, source-list drift, and target tests before merge |
| **campaign-health** | Find stuck plans, orphaned agents, and stale worktrees, each with an actionable recovery command |
| **smart-test** | Map changed files to the minimal useful test subset instead of the full suite (default-branch aware) |
| **schema-validator** | Validate a schema is consumed correctly across data → API → test layers; report drift |
| **truthpack-drift** | Detect drift between declared reusable "truth" facts and the current source |
| **docs-sync** | Detect and fix drift between docs and code (versions, paths, conflict markers) |
| **session-stats** | Session tool/agent/timeline analytics, with a telemetry-first measured tier |
| **deep-audit** | Run evidence-backed, resumable runtime-efficiency audits with explicit safety and evidence boundaries |
| **skill-authoring** | Create or revise Agent Skills with focused discovery metadata, progressive disclosure, support files, and package wiring |
| **token-audit** | Token/cost/budget/forecast intelligence — uses real telemetry data when available, heuristic otherwise |
| **agent-report** | Structured agent handoff and performance/cost reports |
| **worktree-preflight** | Pre-launch conflict gate over branch/worktree/file-ownership (unified OK / WARNING / CONFLICT contract) |

### Lightweight Codex parallelism

| Skill | Purpose |
|---|---|
| **parallel-agents-light** | Route Codex work between the local controller loop, bounded sidecar subagents, split implementation, and full `$manager` campaigns. Use it for Claude-style parallel subagent requests when the full campaign runtime would be too heavy. |

### Local-model delegation (new)

| Skill | Purpose |
|---|---|
| **delegate** | Decide whether a narrow, well-scoped sub-task should go to a **local Ollama model** vs stay with the controller, and route it if so. Grounded in the local `ollama-telemetry` MCP delegation tools (`ollama_readiness` / `ollama_delegate` / `ollama_batch_delegate`), with a static-guidance fallback when the MCP server is unavailable. The controller always verifies the result. |
| **delegation-eval** | Evaluate whether local model routing is worth keeping. Uses `ollama-telemetry` eval runs, judge packets, usage metrics, and `dispatch_recommendations` to compare helper models and propose reviewed `dispatch-rules.json` changes. |

`token-audit` and `session-stats` also gained a **telemetry-first data tier**: when a local `ollama-telemetry` API is reachable (`http://127.0.0.1:8099`), they read real measured token/cost data instead of character-heuristic estimates, falling back silently when it is not.

Telemetry integration is deliberately split by portability:

- `delegate`, `delegation-eval`, `token-audit`, and `session-stats` are portable and depend on API/MCP contracts.
- `telemetry-live-ops` is machine-local, points at a personal live deployment, and is not exported.
- Deprecated Claude-only aliases `refactor-planner`, `observer-test`, and
  `worktree-manager` were removed; their behavior is covered by
  `planner --mode refactor`, `observer`, and `manager` with its task runtime.

See [docs/ollama-telemetry-integration.md](docs/ollama-telemetry-integration.md) for the integration boundary.

### Machine-local ops

| Skill | Purpose |
|---|---|
| **telemetry-live-ops** | Machine-local skill that starts/verifies a live `ollama-telemetry` deployment over SSH. Retarget via `OLLAMA_TELEMETRY_*` env vars; not a portable skill. |

`telemetry-live-ops` is kept in this source repo for this workstation only. It is intentionally excluded from the install manifests and ready-package export.

### Machine-local Codex lifecycle hooks

The source authority for the DevHome safety and Remember-compatibility hooks is
[`codex-skills/local-hooks/devhome-lifecycle`](codex-skills/local-hooks/devhome-lifecycle/README.md).
It installs explicitly into `D:\DevHome\state\codex`, supports a read-only drift
check, and remains outside the portable ready-package manifests.

## Architecture

Each ready package follows a **contract-first, read-all write-scoped** design:

- Skills reference shared contracts (`planning-contract.md`) that define required plan elements and agent specs
- Agents read the full repo for context but only write to explicitly scoped files
- All material claims require source evidence (file path, line number, or command output)
- Shared skills keep an **equivalent workflow contract across Claude and Codex** while provider metadata, invocation surfaces, and narrow runtime details may differ.

The export script reads `release-manifest.json` to determine which packages are
ready and applies the `portable-runtime` strategy to Claude and Codex.

## Repository Layout

```
codex-skills/       Codex package — skills, contracts, Python runtime
claude-skills/      Claude package — skills, contracts, Python runtime
scripts/            Export automation
docs/               Release notes and readiness tracking
```

## License

[MIT](LICENSE) - Espen Severinsen
