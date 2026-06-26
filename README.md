# AI Skills

**Portable, production-ready skill packages that give AI coding agents structured workflows for planning, testing, shipping, multi-agent orchestration, and cost-aware local-model delegation.**

78 install-ready skills across three provider-specific packages — each package's install manifest lists exactly what ships. Drop them into any project and your agents gain campaign planning, parallel worktree coordination, QA pipelines, review gates, ops/analytics, and grounded model routing.

| Package | Skills | What it adds |
|---|:---:|---|
| **claude-skills** | 19 | Core campaign orchestration plus review, shared ops/analytics (build gates, health, docs sync, schema/truth validation, session & token analytics), and worktree guardrails for Claude Code |
| **codex-skills** | 31 | Extended toolkit for Codex: API/engineering patterns, deep research, Playwright e2e, review, plus the full ops/analytics and verification suite |
| **gemini-skills** | 28 | Gemini bootstrap adapter: campaign workflow, review, guardrails, the ops/analytics suite, and editor/refactor helpers |
| **wt-cli** | — | TypeScript CLI for cross-platform worktree orchestration in parallel agent flows |

> Counts reflect each package's `package/install-manifest.json`. The Gemini count is the curated adapter set (skills that ship a `.gemini/commands` wrapper); the Gemini tree also carries additional imported domain skills that are not part of the installable adapter.

## Quick Start

**Export all ready packages** into a target folder:

```powershell
.\scripts\export-ready-skill-packages.ps1 -TargetDir ".\dist\ai-skills-ready-packages" -Force
```

**Bootstrap Gemini skills** into another repo:

```powershell
.\gemini-skills\scripts\bootstrap.ps1 -TargetDir "C:\path\to\target-repo"
```

The bootstrap script creates `.gemini/skills/` and `.gemini/commands/`, copies skill wrappers, and injects multi-agent guardrails into `GEMINI.md`.

## What's Inside

### Core campaign skills (shared across packages)

| Skill | Purpose |
|---|---|
| **planner** | Design structured multi-agent campaign plans with work decomposition and dependency mapping |
| **manager** | Orchestrate parallel agents in worktrees — launch, merge, verify builds |
| **discover** | Research a codebase before planning — map dependencies, assess feasibility, identify constraints |
| **qa** | Run tests, check coverage, triage failures, smoke-test endpoints, generate regression tests |
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

### Gemini adapter extras

`brief`, `edit`, `epic-refactor`, `forensic-debugger`, `guardrails`, `ui-test-engineer`, `doc-weaver` — plus the core campaign workflow and the shared ops/analytics suite above. Imported domain-specific skills are kept out of the installable adapter set so the adapter stays maintainable.

## Architecture

Each package follows a **contract-first, read-all write-scoped** design:

- Skills reference shared contracts (`planning-contract.md`) that define required plan elements and agent specs
- Agents read the full repo for context but only write to explicitly scoped files
- All material claims require source evidence (file path, line number, or command output)
- Each skill keeps **identical executable behavior across Claude, Codex, and Gemini** — only frontmatter shape and the command prefix (`/` vs `$`) differ

The export script reads `release-manifest.json` to determine which packages are ready and applies the correct export strategy — `portable-runtime` for Claude/Codex, `gemini-adapter` for Gemini.

## Repository Layout

```
codex-skills/       Codex package — skills, contracts, Python runtime
claude-skills/      Claude package — skills, contracts, Python runtime
gemini-skills/      Gemini package — skills, commands, bootstrap, guardrails
wt-cli/             Worktree orchestration CLI (TypeScript)
scripts/            Export automation
docs/               Release notes and readiness tracking
```

## License

[MIT](LICENSE) - Espen Severinsen
