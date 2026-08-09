# Review - Skill Metadata and DevHome Sync

**Date:** 2026-06-27
**Surface:** ready skill packages, legacy Gemini adapter, and local Codex/Claude skill roots
**Verdict:** PASS

> **Historical record.** The Gemini surface described below was removed on
> 2026-08-09. Findings remain valid only for the June audit state.

## Findings

### High

- None.

### Medium

- None.

### Low

- [axis: skill-discovery] Several manifest-listed skills had useful trigger guidance only in the body or implicit in terse descriptions.
  Evidence: the new `scripts/Test-ReadyPackages.ps1` description check initially failed on `codex-skills/skills/worktree-preflight/SKILL.md` and `claude-skills/skills/worktree-preflight/SKILL.md`.
  Impact: a model-invoked skill can be missed if its `description` does not expose when it should trigger.
  Resolution: updated ready-package frontmatter descriptions to include explicit `Use when`, `Use for`, or `Use before` trigger phrasing. The same cleanup was applied to the legacy Gemini adapter for parity.

## Changes Made

- Added a ready-package validation check that fails manifest-listed skills when `SKILL.md` frontmatter lacks a discoverable trigger phrase.
- Refined Codex and Claude frontmatter for `manager`, `ship`, `observer`, `worktree-preflight`, and related shared ops skills where triggers were implicit.
- Refined Antigravity adapter frontmatter so the active Google-facing package exposes trigger phrases for workflow discovery.
- Refined legacy Gemini adapter frontmatter for parity, while keeping Gemini marked legacy and outside default ready export.
- Refreshed local skill roots with `.\scripts\Install-AgentSkills.ps1 -Provider Both -Force`:
  - `C:\Users\Sev\.codex\skills`
  - `D:\DevHome\state\codex\skills`
  - `C:\Users\Sev\.claude\skills`
  - `D:\DevHome\state\claude\skills`

## Verification

- `.\scripts\Test-ReadyPackages.ps1` - pass, including export smoke.
- `python -m unittest codex-skills.tests.test_skill_docs_contract claude-skills.tests.test_skill_docs_contract` - pass, 18 tests.
- `git diff --check` - pass; only CRLF conversion warnings were emitted.
- Spot-checked copied frontmatter in both DevHome and user-home live skill roots after sync.

## Notes

- `D:\DevHome\state\agents\skills` remains a broader shared provider inventory; this pass did not overwrite that tree because the repo installer targets Codex and Claude package roots specifically.
- `quick_validate.py` under DevHome could not run in this shell because `PyYAML` is not installed in the active Python environment. The repo-owned ready-package gate covers the package/export contracts used for this pass.
