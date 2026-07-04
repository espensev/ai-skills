# AI Skills

**Manifest-driven skill packages for AI coding agents — ready-to-export bundles for Claude Code, Codex, and Google Antigravity — plus the shared contracts, docs, and `wt-cli` worktree tooling that support them.**

This repo curates reusable workflows for planning, testing, review, shipping,
multi-agent worktree orchestration, lightweight Codex sidecar routing,
docs/schema drift checks, telemetry-aware token and cost analysis, and local
Ollama delegation. The shipping surface is
deliberately explicit: `release-manifest.json` selects ready packages, and each
package's `package/install-manifest.json` selects the skills, runtime files,
contracts, workflows, and wrappers that are exported.

85 install-ready skills ship across three provider-specific packages:

| Package | Skills | What it adds |
|---|:---:|---|
| **claude-skills** | 21 | Core campaign orchestration plus review/debug workflows, shared ops/analytics (build gates, health, docs sync, schema/truth validation, memory hygiene, session & token analytics), and worktree guardrails for Claude Code |
| **codex-skills** | 34 | Extended toolkit for Codex: API/engineering patterns, deep research, Playwright e2e, lightweight parallel sidecar routing, review/debug workflows, plus the full ops/analytics and verification suite |
| **antigravity-skills** | 30 | Antigravity adapter: Agent Skills, workflows, guardrails, the ops/analytics suite, and editor/refactor helpers |
| **wt-cli** | — | TypeScript CLI for cross-platform worktree orchestration in parallel agent flows |

> Counts reflect each package's `package/install-manifest.json`. The legacy
> `gemini-skills` adapter remains in source for Gemini CLI enterprise/API-key
> compatibility, but the ready Google-facing export is now `antigravity-skills`.
> Imported or source-only skills that are not manifest-listed stay as reference
> material and do not ship in ready-package exports.

## Quick Start

**Run the release checklist**:

```powershell
.\scripts\Test-ReleaseReadiness.ps1
```

**Validate ready packages** with export, installer, and Antigravity bootstrap
smoke checks:

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

**Bootstrap Antigravity skills** into another repo:

```powershell
.\antigravity-skills\scripts\bootstrap.ps1 -TargetDir "C:\path\to\target-repo"
```

The bootstrap script creates `.agents/skills/` and `.agent/workflows/`, copies
manifest-listed skills and workflows, and injects multi-agent guardrails into
`AGENTS.md`.

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
- Deprecated/duplicative Claude-only skills (`refactor-planner`, `observer-test`, `worktree-manager`) remain in source for compatibility but are no longer in the curated install manifest.

See [docs/ollama-telemetry-integration.md](docs/ollama-telemetry-integration.md) for the integration boundary.

### Machine-local ops

| Skill | Purpose |
|---|---|
| **telemetry-live-ops** | Machine-local skill that starts/verifies a live `ollama-telemetry` deployment over SSH. Retarget via `OLLAMA_TELEMETRY_*` env vars; not a portable skill. |

`telemetry-live-ops` is kept in this source repo for this workstation only. It is intentionally excluded from the install manifests and ready-package export.

### Antigravity adapter extras

`brief`, `edit`, `epic-refactor`, `forensic-debugger`, `guardrails`, `ui-test-engineer`, `doc-weaver` — plus the core campaign workflow and the shared ops/analytics suite above. Imported domain-specific skills are kept out of the installable adapter set so the adapter stays maintainable.

## Architecture

Each package follows a **contract-first, read-all write-scoped** design:

- Skills reference shared contracts (`planning-contract.md`) that define required plan elements and agent specs
- Agents read the full repo for context but only write to explicitly scoped files
- All material claims require source evidence (file path, line number, or command output)
- Each skill keeps an **equivalent workflow contract across Claude, Codex, and Antigravity** — Claude and Codex ship the full portable runtime while Antigravity ships adapter skills plus workflows, so provider metadata, runtime wiring, invocation surface, and wording differ per package

The export script reads `release-manifest.json` to determine which packages are
ready and applies the correct export strategy: `portable-runtime` for
Claude/Codex and `antigravity-adapter` for the active Google package. The
`gemini-adapter` strategy remains available for the legacy Gemini source
package but is not part of the default ready export.

## Repository Layout

```
codex-skills/       Codex package — skills, contracts, Python runtime
claude-skills/      Claude package — skills, contracts, Python runtime
antigravity-skills/ Antigravity package — skills, workflows, bootstrap, guardrails
gemini-skills/      Legacy Gemini package — skills, commands, bootstrap, guardrails
wt-cli/             Worktree orchestration CLI (TypeScript)
scripts/            Export automation
docs/               Release notes and readiness tracking
```

## License

[MIT](LICENSE) - Espen Severinsen
