# Review - AI4000 skill and wrapper guidance

**Date:** 2026-09-27
**Surface:** Existing guidance and validation entry points in Ai-Skills,
operationAI, and the AI4000 wrapper navigation workspace; resulting docs diff
against Ai-Skills `eade0f7dbcfc36415f56798180f43066755cf4f3`.
**Spec source:** User request to review the AI4000 workspace and fix clear issues,
followed by retirement of the legacy development paths.
**Standards sources:** Root and provider AGENTS/CLAUDE files,
`skills-src/manifest.json`, lifecycle source README, and operationAI lab guidance.
**Verdict:** PASS WITH NOTES - the identified guidance defects are corrected;
runtime behavior and provider readiness were outside this bounded review.

## Findings

- **Medium, standards, resolved:** Root and provider guidance directed shared
  skill edits into provider package trees. `skills-src/manifest.json:2` makes
  `generated_skills` source-owned, and `README.md:247` documents regeneration.
  Corrected both root instructions and both provider instructions to distinguish
  generated skills from provider-owned skills and runtime files.
- **Low, regression, resolved:** The root README still described Remember
  compatibility as lifecycle-package behavior and an ambient-home adapter defect
  as a current blocker. The lifecycle README at
  `codex-skills/local-hooks/devhome-lifecycle/README.md:8` states that the adapter
  was retired and capture belongs to the upstream plugin. Corrected the root
  README and agent guidance without claiming live capture acceptance.
- **Low, regression, resolved:** The root README described every handoff as a
  two-pass Stop flow. The lifecycle README at
  `codex-skills/local-hooks/devhome-lifecycle/README.md:38` describes Codex
  prompt-time preparation. The summary now names that route and its fallback.
- **Low, standards, resolved:** `claude-skills/CLAUDE.md` incorrectly identified
  the package directory as the Git root. `git rev-parse --show-toplevel` resolves
  to Ai-Skills; the instructions now state the package-relative path convention.
- **Medium, regression, source corrected:** The wanted-state profile and local
  lifecycle SessionStart definition still depended on the legacy Ai-Skills
  location. Updated the five profile paths, both hook command variants, and the
  plugin contract expectation to the physical AI4000 source. Installed marketplace
  and plugin migration are a separate controller-owned action.
- **Medium, regression, resolved:** Both providers' telemetry helper scripts
  defaulted to an obsolete repository path. They now preserve explicit
  `-RepoRoot` and `OLLAMA_TELEMETRY_REPO` overrides, otherwise deriving the path
  from `MACHINE_CODE_ROOT`. Missing configuration fails before any live action.
  Both provider-owned skill docs and the release test entry point were updated.

## Verification

- `Test-ReadyPackages.ps1 -StrictSkillManifest -SkipExportSmoke -SkipInstallerSmoke`:
  passed; 26 Codex and 16 Claude install-ready skills.
- `Build-ProviderSkillPackages.ps1 -Check`: passed; 47 generated files across
  16 shared skills.
- `Compare-ProviderSkillParity.ps1 -FailOnUndeclaredFork -MaxRows 5`: passed;
  16 generated pairs and two declared forks.
- `python -m unittest codex-skills.tests.test_skill_docs_contract claude-skills.tests.test_skill_docs_contract`:
  43 passed.
- In `claude-skills`, `python -m pytest tests/test_skill_docs_contract.py tests/test_task_manager.py tests/test_task_manager_portability.py tests/test_plan_lifecycle.py -q -p no:cacheprovider`:
  138 passed.
- `git diff --check`: passed.
- Wrapper README link resolution: all 21 local links exist.
- operationAI tracked PowerShell AST parsing: nine files, zero parse errors.
- After source-path migration, provider docs and local plugin Python contracts:
  49 passed; package generation, parity, and strict manifest gates passed again.
- Pester: 16 isolated telemetry resolution tests, 36 AI environment tests, and
  27 lifecycle plugin synchronization tests passed (79 total). Only resolver
  functions are loaded by the telemetry tests; no live helper tail runs.

## Coverage and boundaries

Ai-Skills began clean. Changes cover guidance, the source wanted-state profile,
the source lifecycle hook definition, four machine-local telemetry helpers, and
their tests. No generated skill, portable install manifest, installed projection,
provider configuration, or credential file was changed by this review lane.
The candidate environment lock remains pinned to its existing commit; it was
not recaptured or marked accepted from the modified worktree.

operationAI is a staging repository. Its existing untracked HQ directories,
configuration filename, and review report were preserved. Its README and lab
boundaries were inspected; its provider integration suites were not run.
The wrapper workspace is unversioned navigation to DevHome-owned source, and
needed no correction. Link and parser checks do not establish runtime behavior.

Export/installer smoke checks, full release validation, installed-root comparison,
live hooks, provider calls, and wrapper execution were not performed by this lane.
Native Claude plugin help was inspected read-only for migration capabilities.
