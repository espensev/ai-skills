# Review - Skill Runtime Sync and Subagent Audit

**Date:** 2026-07-02
**Surface:** Codex and Claude ready packages, local skill-root sync
**Method:** Main-thread verification plus three read-only subagent audit lanes
**Verdict:** PASS

## Findings

### High

- None.

### Medium

- [axis: packaging] `scripts/Install-AgentSkills.ps1` copied manifest-listed
  skills and support files, but not manifest-listed runtime files or runtime
  directories.
  Evidence: both Codex and Claude manifests declare runtime files and
  directories, but the installer only copied contracts and skills before this
  pass. All four live roots were missing `scripts/task_manager.py`.
  Impact: local Codex and Claude roots could discover the skills but lacked the
  runtime helpers the skills document.
  Resolution: the installer now syncs `runtime_files` and
  `runtime_directories` as well as skills and support files.

- [axis: packaging] Manifest-listed skills referenced helper scripts that were
  not shipped by the relevant install manifests.
  Evidence: Codex `observer`, `manager`, and `verification-loop` referenced
  `scripts/observe_to_eval.py`; Codex `observer` also referenced
  `scripts/skill_feedback_loop.py`. Claude `observer` referenced
  `scripts/hooks/`.
  Impact: exported or locally synced skills could instruct agents to run files
  absent from the installed package.
  Resolution: Codex now lists `scripts/observe_to_eval.py` and
  `scripts/skill_feedback_loop.py` in `runtime_files`; Claude now lists
  `scripts/hooks` in `runtime_directories`.

### Low

- [axis: validation] The ready-package validator did not check script paths
  referenced by manifest-listed skill bodies.
  Resolution: `scripts/Test-ReadyPackages.ps1` now fails portable-runtime
  packages when manifest-listed skills reference `scripts/...` paths that are
  not bundled by `runtime_files` or `runtime_directories`.

- [axis: validation] Source-only skill directories remain in the portable
  package source trees.
  Evidence: Codex has `telemetry-live-ops`; Claude has `observer-test`,
  `refactor-planner`, `telemetry-live-ops`, and `worktree-manager`.
  Impact: this is intentional source retention, but it can obscure what ships.
  Resolution: the validator now reports these as warnings by default and can
  fail them with `-StrictSkillManifest`.

- [axis: skill-docs] Claude `discover` still handed off to `/refactor-planner`,
  which is no longer manifest-listed.
  Resolution: replaced those handoffs with `/planner --mode refactor`.

- [axis: skill-docs] Claude `observer` contained hard references to the
  source-only `/observe-test` skill.
  Resolution: changed those references to worktree-local observation sessions
  and added a note that `observer` is the installed skill name while `/observe`
  is this package's command-style invocation.

## Changes Made

- Updated `scripts/Install-AgentSkills.ps1` to copy manifest runtime files and
  runtime directories into each selected local skill root.
- Updated `scripts/Test-ReadyPackages.ps1` with:
  - script-reference validation for manifest-listed portable skills,
  - warning/strict reporting for extra portable skill directories.
- Updated Codex and Claude install manifests for referenced runtime helpers.
- Updated Codex and Claude README package-layout tables.
- Updated Codex and Claude package contract tests for the new runtime manifest
  entries.
- Refined Claude `discover` and `observer` skill text to avoid non-manifest
  handoffs.
- Synced live roots with `.\scripts\Install-AgentSkills.ps1 -Provider Both -Force`.

## Live Root Verification

Verified after sync:

- `C:\Users\Sev\.codex\skills\scripts\task_manager.py`
- `C:\Users\Sev\.codex\skills\scripts\observe_to_eval.py`
- `C:\Users\Sev\.codex\skills\scripts\skill_feedback_loop.py`
- `D:\DevHome\state\codex\skills\scripts\task_manager.py`
- `D:\DevHome\state\codex\skills\scripts\observe_to_eval.py`
- `D:\DevHome\state\codex\skills\scripts\skill_feedback_loop.py`
- `C:\Users\Sev\.claude\skills\scripts\task_manager.py`
- `C:\Users\Sev\.claude\skills\scripts\hooks\settings-hooks.template.json`
- `C:\Users\Sev\.claude\skills\scripts\hooks\observe_test_output.py`
- `D:\DevHome\state\claude\skills\scripts\task_manager.py`
- `D:\DevHome\state\claude\skills\scripts\hooks\settings-hooks.template.json`
- `D:\DevHome\state\claude\skills\scripts\hooks\observe_test_output.py`

## Verification

- `.\scripts\Test-ReadyPackages.ps1` - pass, including export smoke.
- `python -m unittest codex-skills.tests.test_skill_docs_contract claude-skills.tests.test_skill_docs_contract` - pass, 18 tests.
- `git diff --check` - pass; only CRLF conversion warnings were emitted.
- `.\scripts\Install-AgentSkills.ps1 -Provider Both -Force` - pass.

## Notes

- The warnings from `Test-ReadyPackages.ps1` are expected for retained
  source-only skills. They document the package boundary and do not affect the
  ready-package export.
- `D:\DevHome\state\agents\skills` was not targeted. It remains a broader
  shared provider inventory outside this repo's Codex/Claude installer defaults.
