# AI Skills

**Portable, production-ready skill packages that give AI coding agents structured workflows for planning, testing, shipping, and multi-agent orchestration.**

65 skills across three provider-specific packages — drop them into any project and your agents gain campaign planning, parallel worktree coordination, QA pipelines, and more.

| Package | Skills | What it adds |
|---|:---:|---|
| **claude-skills** | 9 | Core campaign orchestration for Claude Code — planning, multi-agent management, QA, shipping |
| **codex-skills** | 18 | Extended toolkit for Codex — adds API design, research, e2e testing, frontend/backend patterns |
| **gemini-skills** | 38 | Full Gemini adapter with bootstrap installer, guardrails, and 30+ domain-specific skills |
| **wt-cli** | — | TypeScript CLI for cross-platform worktree orchestration in parallel agent flows |

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

### Core Skills (shared across packages)

| Skill | Purpose |
|---|---|
| **planner** | Design structured multi-agent campaign plans with work decomposition and dependency mapping |
| **manager** | Orchestrate parallel agents in worktrees — launch, merge, verify builds |
| **discover** | Research a codebase before planning — map dependencies, assess feasibility, identify constraints |
| **qa** | Run tests, check coverage, triage failures, smoke-test endpoints, generate regression tests |
| **ship** | Stage, commit, push validated work with campaign-aware commit grouping |
| **observer** | Passive project intelligence — observe patterns over time without interfering |
| **loop** | Run focused work loops with repeated inspect-edit-verify cycles |

### Codex Extras

API design, backend/frontend patterns, deep research, Playwright e2e testing, documentation lookup, MCP server patterns, and more.

### Gemini Extras

Architecture decision records, codebase onboarding, forensic debugger, epic refactor, Django TDD, Rust/Go/Kotlin/C# patterns, security scanning, doc weaver, and a full guardrail system enforcing contract-first execution and scoped writes.

## Architecture

Each package follows a **contract-first, read-all write-scoped** design:

- Skills reference shared contracts (`planning-contract.md`, `system-map.md`) that define required plan elements and agent specs
- Agents read the full repo for context but only write to explicitly scoped files
- All material claims require source evidence (file path, line number, or command output)

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

[MIT](LICENSE) — Espen Severinsen
