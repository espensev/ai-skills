# Review - Skill Upgrade Pass

**Date:** 2026-06-26
**Surface:** ready-package skill upgrade batch
**Spec source:** user request to seek upgrades across skills if needed
**Verdict:** PASS WITH NOTES

## Current Update

The Gemini wrapper drift noted below is now legacy-package hygiene, not a
default ready-export warning. The active Google-facing package is
`antigravity-skills`, which exports manifest-listed workflows instead of
Gemini command wrappers.

## Findings

### High

- None.

### Medium

- None.

### Low

- [axis: standards] `gemini-skills/.gemini/commands/continuous-learning.toml`, `tdd.toml`, and `telemetry-live-ops.toml` are tracked command wrappers but remain outside `gemini-skills/package/install-manifest.json`.
  Evidence: `scripts/Test-ReadyPackages.ps1` reports the three files as extra wrappers.
  Impact: ready-package exports are still correct because export/bootstrap are manifest-driven, but the source command folder is not a clean mirror of the shipping manifest.
  Recommendation: either move source-only wrappers out of `.gemini/commands/`, promote their target skills deliberately, or keep them with an explicit source-only policy.

## Changes Made

- Added `scripts/Test-ReadyPackages.ps1` as the root ready-package validation and export-smoke gate.
- Promoted `diagnosing-bugs` across:
  - `claude-skills/skills/diagnosing-bugs/SKILL.md`
  - `codex-skills/skills/diagnosing-bugs/SKILL.md`
  - `gemini-skills/skills/diagnosing-bugs/SKILL.md`
  - `gemini-skills/.gemini/commands/diagnosing-bugs.toml`
- Updated manifests so the shipped counts are now Claude 20, Codex 32, Gemini 29, total 81.
- Updated root/provider READMEs, release readiness docs, discovery notes, and package contract tests.

## Verification

- `.\scripts\Test-ReadyPackages.ps1` - pass, with the known extra-wrapper warning.
- `python -m pytest tests/test_skill_docs_contract.py -q` in `claude-skills/` - pass, 9 passed.
- `python -m pytest tests/test_skill_docs_contract.py -q` in `codex-skills/` - pass, 9 passed.
- `git diff --check` - pass; only CRLF conversion warnings were emitted.

## Coverage Notes

- Deep-reviewed and changed the ready-package shipping path only: manifests, provider READMEs, the promoted skill bodies, Gemini wrapper, root validation, and docs.
- Did not bulk-promote the imported top-level `skills/` tree or the large Gemini/ECC import. Those remain reference material until individual skills are adapted and manifest-listed.
