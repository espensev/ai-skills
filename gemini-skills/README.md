# Gemini Campaign Skills

A docs-first adapter for the generic multi-agent campaign skill stack on Gemini
CLI.

This package stays intentionally thin. It defines the Gemini-facing
instruction surface, command wrappers, and evaluation artifacts without
vendoring a Gemini-specific runtime fork.

## Current Scope

- document the Gemini-specific provider surface
- ship packaged `skills/` and `.gemini/commands/` for the generic campaign
  workflow plus Gemini-native workflows
- harden skill instructions with explicit artifacts, stop conditions, and
  portability guardrails
- provide a starter light-eval case set that reuses the shared scorer pattern
  from the existing provider packages

## Provider Surface

Gemini CLI gives this package two provider-specific integration points:

- `GEMINI.md` for persistent repo guidance and hierarchical context loading
- `.gemini/commands/` for reusable command wrappers
- `.gemini/skills/` for reusable project or user Agent Skills

Those surfaces are enough to expose the Gemini adapter cleanly before
extracting a shared core.

## Included Skills

| Skill | Purpose |
|---|---|
| `discover` | Produce `docs/system-map.md` from read-only repository analysis |
| `planner` | Produce `docs/planning-contract.md` from the discovery artifact |
| `brief` | Extract exact context needed for a specific task-id |
| `manager` | Coordinate the multi-agent loop by parsing the planning contract |
| `ship` | Execute highly specific, tightly scoped coding tasks |
| `qa` | Evaluate the completed work against the planning contract |
| `loop` | Iteratively execute specific assigned sub-tasks |
| `loop-master` | Orchestrate high-level campaign lifecycle and continuous verification |
| `epic-refactor` | Execute repo-scale migrations under a strict refactor report |
| `forensic-debugger` | Produce an incident RCA and patch proposal from large artifacts |
| `ui-test-engineer` | Triage and fix visual regressions from multimodal test evidence |
| `doc-weaver` | Synchronize architecture docs and code-facing docs with source changes |
| `guardrails` | Scan the full repo for rule violations without editing files |
| `edit` | Apply scoped, surgical file edits under contract or user instruction |

## ECC Ported Capabilities

This repository now includes significant capability ports from the `everything-claude-code` ecosystem, mapped to Gemini natively:

- **Domain-Specific Skills:** Dozens of specialized patterns (e.g., `kotlin-patterns`, `django-tdd`, `rust-patterns`, `golang-testing`) to elevate the quality of execution tasks.
- **Continuous Learning & Rule Distillation:** The `continuous-learning-v2` and `rules-distill` tools enable systematic self-improvement workflows.
- **Canonical Session Adapters:** (`docs/SESSION-ADAPTER-CONTRACT.md`) Adapters are ported to unify worker tracking natively.

## Eval

The package now includes a starter light-eval dataset under `eval/`.

- `eval/README.md` describes the current lightweight workflow
- `eval/cases/light-skill-cases.json` contains the starter Gemini cases
- `eval/responses.template.json` is the blank response payload

Until a neutral shared core exists, score Gemini responses with the existing
light scorer from `../codex-skills/` or `../claude-skills/` instead of copying
that script into this package.

## Package Layout

| Path | Purpose |
|---|---|
| `README.md` | Package overview and scope |
| `GEMINI.md` | Maintainer conventions and global guardrails |
| `skills/` | Prototype Agent Skills and their instruction logic |
| `.gemini/commands/` | Gemini command wrapper definitions for the packaged skills |
| `scripts/bootstrap.ps1` | Installer for Gemini skills, commands, and guardrails |
| `package/install-manifest.json` | Shipping metadata for the bootstrap adapter package |
| `docs/skill-portability-notes.md` | Adapter rules and future extraction notes |
| `docs/gemini-context-skills.md` | Concepts for Gemini-native skills |
| `eval/` | Starter light-eval cases and response template |

## Design Direction

The package should stay adapter-first until the shared runtime is extracted.

- **The Lens Strategy (Read-All, Write-Scoped):** Unlike the swarm architecture used by other models, Gemini natively executes the `Plan -> Run -> Verify` lifecycle by leveraging its massive context window for full-repo comprehension while strictly scoping file edits via the 13-element contract.
- shared planning contracts, schemas, runtime modules, and tests should come
  from a provider-neutral core
- Gemini-specific files should stay limited to Agent Skills, instruction
  files, package docs, and lightweight eval artifacts
- no package-local copy of `task_manager.py` or provider-specific runtime
  scripts should be introduced here until that shared-core split exists

## Status

- **v1.0 Ready**: The Gemini CLI multi-agent adapter is fully registered.
- **14 Specialized Skills**: All generic campaign skills and Gemini super-skills are mapped and constrained.
- **Strict Guardrails**: Enforced via `GEMINI.md` and `allowed_tools` to prevent architectural drift.
- **Shared-Core Friendly**: The package stays adapter-first so shared runtime extraction remains possible later.

## Installation

To install these skills and guardrails into a target repository without requiring heavy package managers, you can use the provided PowerShell bootstrap script from the root of this package:

```powershell
# From the gemini-skills repo root
.\scripts\bootstrap.ps1 -TargetDir "C:\path\to\your\target\repo"
```

This script creates the `.gemini/skills/` and `.gemini/commands/`
directories, copies the packaged skills and command wrappers, and injects the global
multi-agent guardrails into the target repository's `GEMINI.md` file.

## References

- Gemini CLI custom commands:
  `https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/custom-commands.md`
- Gemini CLI context files:
  `https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/gemini-md.md`
- Gemini API docs:
  `https://ai.google.dev/gemini-api/docs`
