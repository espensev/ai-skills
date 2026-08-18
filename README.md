# AI Skills

**Manifest-driven skill packages for AI coding agents — ready-to-export bundles for Claude Code and Codex, plus the shared contracts and validation tooling that support them.**

This repo curates reusable workflows for planning, testing, review, shipping,
multi-agent worktree orchestration, lightweight Codex sidecar routing,
docs/schema drift checks, telemetry-aware token and cost analysis, and local
Ollama delegation. The shipping surface is
deliberately explicit: `release-manifest.json` selects ready packages, and each
package's `package/install-manifest.json` selects the skills, runtime files,
contracts, workflows, and wrappers that are exported.

40 install-ready skills ship across two provider-specific packages:

| Package | Skills | What it adds |
|---|:---:|---|
| **claude-skills** | 16 | Core campaign orchestration plus deep runtime audit, skill authoring, review/debug workflows, shared ops/analytics, and worktree guardrails for Claude Code |
| **codex-skills** | 24 | Extended toolkit for Codex: repository-first API/backend/frontend/E2E/research guidance, gated audits, skill authoring, lightweight parallel sidecar routing, review/debug workflows, and the full ops/analytics and verification suite |

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

Package installs also prune retired standalone skill directories. The one
authoritative retirement registry, including each replacement route, is
[`scripts/retired-skills.json`](scripts/retired-skills.json); both the installer
and root comparator consume it directly.

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

`repo-conventions` (codex-skills only) starts from the target repository's own
rules, then supplies fallback playbooks for APIs, backend/frontend structure,
Playwright E2E, current research, and bounded inspect-edit-verify cycles.

### Ops & analytics suite (shared across packages)

| Skill | Purpose |
|---|---|
| **smart-test** | Map changed files to the minimal useful test subset instead of the full suite (default-branch aware) |
| **docs-sync** | Detect and fix drift between docs and code (versions, paths, conflict markers) |
| **usage-stats** | Token/cost/budget/forecast intelligence, session tool/agent/timeline analytics, and agent performance/cost reports — telemetry-first with heuristic fallback |
| **deep-audit** | Run evidence-backed, resumable runtime-efficiency audits with explicit safety and evidence boundaries |
| **skill-authoring** | Create or revise Agent Skills with focused discovery metadata, progressive disclosure, support files, and package wiring |

### DevHome browser control

`browser-control` routes all agent browser automation on this workstation to
the isolated Opera Developer CDP endpoints managed by `devbrowser`. The rich
Chrome DevTools MCP path is accepted only when its effective command includes
the DevHome `--browser-url`; otherwise agents must use the bundled direct-CDP
helper. Tool visibility alone is not attachment proof. The installed Codex
skill includes the complete preflight, configuration boundary, fallback, and
attended acceptance procedure in
[`CODEX-INTEGRATION.md`](codex-skills/skills/browser-control/CODEX-INTEGRATION.md).

### Lightweight Codex parallelism

| Skill | Purpose |
|---|---|
| **parallel-agents-light** | Route Codex work between the local controller loop, bounded sidecar subagents, split implementation, and full `$manager` campaigns. Use it for Claude-style parallel subagent requests when the full campaign runtime would be too heavy. |

### Local-model delegation (new)

| Skill | Purpose |
|---|---|
| **delegate** | Decide whether a narrow, well-scoped sub-task should go to a **local Ollama model** vs stay with the controller, and route it if so. Grounded in the local `ollama-telemetry` MCP delegation tools (`ollama_readiness` / `ollama_delegate` / `ollama_batch_delegate`), with a static-guidance fallback when the MCP server is unavailable. The controller always verifies the result. |
| **delegation-eval** | Evaluate whether local model routing is worth keeping. Uses `ollama-telemetry` eval runs, judge packets, usage metrics, and `dispatch_recommendations` to compare helper models and propose reviewed `dispatch-rules.json` changes. |

`usage-stats` also has a **telemetry-first data tier**: when a local `ollama-telemetry` API is reachable (`http://127.0.0.1:8099`), it reads real measured token/cost data instead of character-heuristic estimates, falling back silently when it is not.

Telemetry integration is deliberately split by portability:

- `delegate`, `delegation-eval`, and `usage-stats` are portable and depend on API/MCP contracts.
- `telemetry-live-ops` is machine-local, points at a personal live deployment, and is not exported.
- Deprecated Claude-only aliases `refactor-planner`, `observer-test`, and
  `worktree-manager` were removed; their behavior is covered by
  `planner --mode refactor` and `manager` with its task runtime.

See [docs/ollama-telemetry-integration.md](docs/ollama-telemetry-integration.md) for the integration boundary.

### Machine-local ops

| Skill | Purpose |
|---|---|
| **telemetry-live-ops** | Machine-local skill that starts/verifies a live `ollama-telemetry` deployment over SSH. Retarget via `OLLAMA_TELEMETRY_*` env vars; not a portable skill. |

`telemetry-live-ops` is kept in this source repo for this workstation only. It is intentionally excluded from the install manifests and ready-package export.

### Machine-local Codex lifecycle hooks

The source authority for the DevHome safety and Remember-compatibility hooks is
[`codex-skills/local-hooks/devhome-lifecycle`](codex-skills/local-hooks/devhome-lifecycle/README.md).
It remains outside the portable ready-package manifests and is available as the
`devhome-lifecycle` choice in the repository's local **AI Skills** Codex
marketplace. Its sync-only plugin hook keeps the verified
`D:\DevHome\state\codex` projection current once it is enabled and trusted,
without registering the safety or Remember behavior twice.

```powershell
.\scripts\Install-AgentSkills.ps1 -Provider Codex -CodexLocalPlugin DevHomeLifecycle
```

Use `-Provider Both` with the same `-CodexLocalPlugin` choice when the Claude
package roots should be refreshed in the same run. Re-run the command after
updating this checkout; it hash-checks the materialized plugin cache and
refreshes it only when needed, while `-Force` requests an explicit reinstall.
Source acquisition is deliberately separate, so the synchronizer never pulls,
cleans, or otherwise changes Git state.
This machine-specific choice pins its Codex state to
`D:\DevHome\state\codex`; an alternate `CODEX_HOME` does not relocate the
lifecycle plugin or its runtime hook projection. Plugin enablement and hook
trust remain user-controlled Codex state. After first installation or a hook
command change, restart Codex, confirm the plugin is enabled, and review the
reconciliation hook in `/hooks`.

Current review blocker: the Remember adapter's generated mirrors, locks,
checkpoints, and logs still derive from ambient `CODEX_HOME`. Until that path is
pinned too, the broader no-AppData lifecycle requirement is not complete. See
the [full lifecycle feature review](docs/reviews/review-2026-08-16-devhome-lifecycle-feature.md).

## Architecture

Each ready package follows a **contract-first, read-all write-scoped** design:

- Skills reference shared contracts (`planning-contract.md`) that define required plan elements and agent specs
- Agents read the full repo for context but only write to explicitly scoped files
- All material claims require source evidence (file path, line number, or command output)
- Shared skills keep an **equivalent workflow contract across Claude and Codex** while provider metadata, invocation surfaces, and narrow runtime details may differ. The one exception is `telemetry-live-ops`, a machine-local ops skill that intentionally keeps per-provider presentations. A one-sided obligation is allowed only when the mechanism exists on one side only.

The export script reads `release-manifest.json` to determine which packages are
ready and applies the `portable-runtime` strategy to Claude and Codex.

## Repository Layout

```
codex-skills/       Codex package — skills, contracts, Python runtime
claude-skills/      Claude package — skills, contracts, Python runtime
skills-src/         Single-source canon for shared skills (generated into both packages)
scripts/            Export automation
docs/               Release notes and readiness tracking
```

Shared skills are single-sourced. Every skill listed under `generated_skills` in
`skills-src/manifest.json` is authored once in `skills-src/<skill>/SKILL.src.md`
and regenerated into both provider packages by
`scripts/Build-ProviderSkillPackages.ps1`; the generated `SKILL.md` files remain
committed build outputs. Provider differences live in explicit `{{#claude}}` /
`{{#codex}}` conditional blocks and `{{token}}` substitutions inside the canon,
so parity for those pairs is enforced by the generator rather than by authoring
discipline — `Build-ProviderSkillPackages.ps1 -Check` byte-verifies both copies
in the release gate. Support files ship verbatim from
`skills-src/<skill>/files/` (both providers) or
`skills-src/<skill>/files-claude/` and `skills-src/<skill>/files-codex/` (one
provider). `telemetry-live-ops` is the only remaining
`provider_owned_shared_skills` entry: it is a declared whole-document fork,
recorded with its reason in `declared_provider_forks`. Every shared pair that is
neither generated nor declared fails the release gate:
`scripts/Compare-ProviderSkillParity.ps1 -FailOnUndeclaredFork` exits non-zero
on an undeclared fork, and on a generated pair whose `description:` diverges
without a `{{#claude}}` / `{{#codex}}` block in the canon declaring it.

## License

[MIT](LICENSE) - Espen Severinsen
