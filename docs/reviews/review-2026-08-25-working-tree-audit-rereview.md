# Review - Working-tree audit rereview

**Date:** 2026-08-25
**Surface:** Pre-report working tree of `recovery/ai-environment-wanted-state-20260822` at `414be3f`, including both pre-existing untracked review reports
**Spec source:** Current user request; no separate feature spec found
**Standards sources:** `AGENTS.md`; `CLAUDE.md`; `codex-skills/AGENTS.md`; `.gitattributes`; `.gitignore`; `scripts/AiEnvironment/README.md`
**Verdict:** FAIL

This report independently rechecks and supersedes
`docs/reviews/review-2026-08-25-working-tree-audit.md`. The earlier report has
the right overall verdict, but its workflow-deletion and line-ending analysis
is unsafe to use as a ship gate.

## Resolution status

- Resolved: restored both tracked `.vscode/workflows` files; ignored packet copies remain local reference material.
- Resolved: split `usage-stats` elapsed guidance by provider and added Claude/Codex contract assertions.
- Held locally: the candidate lock remains uncommitted with its recorded 73/74 failure pending attended Claude `2.1.241` compatibility evidence. A separate fresh adapter rerun passed 74/74 but does not satisfy lock acceptance.
- Still local: 190 line-ending-only paths and the stale local `main` ref remain outside the publication commits.

## Findings

### High

No high-severity findings.

### Medium

- [axis: regression] `cc-workflow/.vscode/workflows/sq-control-real-logging-restore-20260701.json` and `cc-workflow/.vscode/workflows/sq-control-write-readiness-20260701.json` are the only Git-tracked copies, so committing their deletion loses both workflows from a fresh clone.
  Evidence: both paths are tracked at `HEAD` and currently show `D`. Their byte-equivalent replacements under `cc-workflow/workflows/sq-control-final-fan-control-2026-07-01/` exist only in the local workspace: `git ls-files --error-unmatch` exits 1 for both, while `git check-ignore -v` maps both to `.gitignore:9` (`cc-workflow/*`). The normalized contents match, but the replacement location is not versioned.
  Impact: the apparent dedupe removes the only repository-owned copies; ignored local files cannot preserve the workflows for another clone or machine.
  Recommendation: either retain the tracked `.vscode/workflows` copies or atomically move the canonical copies into a tracked path by updating `.gitignore`, adding them, updating references, and only then deleting the old copies.

- [axis: regression] `scripts/AiEnvironment/locks/snd-desk.lock.json:16` declares Claude `2.1.243` as tested while verified controller `snd-desk` currently runs `2.1.241`.
  Evidence: fresh `Get-AiEnvironmentState` reports `provider.claude.version FAIL`, reason `PROVIDER_VERSION_NOT_IN_LOCK`, with `observed=2.1.241;tested=2.1.243`; `scripts/AiEnvironment/Private/Common.ps1:497-498` requires exact membership.
  Impact: the candidate lock adds `UNTESTED_PROVIDER_VERSION` and cannot reach promotion readiness on this controller.
  Recommendation: establish which version was actually exercised. Re-test and record `2.1.241`, or upgrade to `2.1.243` and run acceptance there; do not change the lock solely to silence observation.

- [axis: standards] `scripts/AiEnvironment/locks/snd-desk.lock.json:5,58-64` refreshes the capture and 0.3.0 payload hashes on 2026-08-25 while retaining the sole acceptance result from 2026-08-22.
  Evidence: `capturedAtUtc` is `2026-08-25T00:04:18Z`, but `remember-posttooluse.checkedAtUtc` remains `2026-08-22T02:00:00Z` with the old 73/74 result. `scripts/AiEnvironment/README.md:42-46` requires exercising the new provider/artifact before capture and resolving every manual gate before promotion.
  Impact: the lock looks freshly captured without proving that its acceptance evidence applies to the payload and provider versions it now records.
  Recommendation: rerun the Remember acceptance against the exact candidate payload/version set and record the fresh result, including a current failure if it still times out.

- [axis: regression] `skills-src/usage-stats/SKILL.src.md:447-449` places the Codex-specific `task_started` elapsed-time source in shared text, so the Claude rendering contains an event source its data ladder never defines.
  Evidence: the rendered Claude package repeats the instruction at `claude-skills/skills/usage-stats/SKILL.md:401-403`. The Claude portability test at `claude-skills/tests/test_skill_docs_contract.py:240-245` excludes only the Codex `token_count` sentence and therefore passes despite this leak.
  Impact: Claude cannot follow the advertised measured turn-time procedure and must either downgrade silently to session time or invent an event source.
  Recommendation: put `task_started` under `{{#codex}}`, define a Claude elapsed-time source or explicit fallback under `{{#claude}}`, and assert the provider-specific wording in both contract tests.

### Low

- [axis: regression] repository-wide, 190 tracked paths differ only by line endings even though `.gitattributes:1-14` already pins text and the affected extensions to LF.
  Evidence: `git status --porcelain` reports 203 tracked dirty paths; `git diff --ignore-cr-at-eol --name-only` reduces that to 13 substantive paths. Git warns that the working copies will be normalized back to LF.
  Impact: broad staging would create noisy, hard-to-review churn and risks mixing normalization with the 13 intended changes.
  Recommendation: diagnose the checkout/editor operation that rewrote the working copies, restore them to the existing attribute policy, and stage only explicit task-owned paths. Do not add a second `.gitattributes` policy or renormalize the repository as proposed by the superseded report.

- [axis: regression] `docs/reviews/review-2026-08-25-working-tree-audit.md:75-101,165-170` is not safe as an operational ship plan.
  Evidence: it calls the workflow deletion a clean dedupe even though the replacements are ignored and untracked, and says no `.gitattributes` exists even though the tracked file already defines LF policy at lines 1-14. Its recommended next command would delete the only tracked workflows and add redundant line-ending policy.
  Impact: following the report literally can lose versioned workflow artifacts and compound worktree noise.
  Recommendation: use this rereview as the current audit surface and correct or retire the superseded report before publication.

- [axis: regression] local `main` remains at `5881f07` while fetched `origin/main` and remote `main` are `3ca00e74`.
  Evidence: `git rev-parse main origin/main` and `git ls-remote origin refs/heads/main`; recovery `HEAD` `414be3f` is already an ancestor of `origin/main`.
  Impact: a later branch switch or lock capture can accidentally use the pre-merge local default branch.
  Recommendation: preserve the dirty recovery worktree first, then fast-forward local `main` before the next clean-source capture.

## Verification

- Installed machine verifier - pass: controller `snd-desk`, instance `ca96d510-7d87-4cec-8e1a-bd8fc3866903`, status `VERIFIED`.
- `git ls-remote origin refs/heads/main refs/heads/recovery/ai-environment-wanted-state-20260822` - pass: remote refs are `3ca00e74` and `414be3f`.
- Pre-report `git status --porcelain` and `git diff --ignore-cr-at-eol` - pass: 203 tracked dirty paths, 13 substantive tracked paths, 190 line-ending-only paths, 2 untracked reports, 0 staged paths. Writing this rereview adds a third untracked report.
- Workflow normalized-content comparison - pass: each deleted tracked file matches its ignored local replacement.
- `git check-ignore -v` plus `git ls-files --error-unmatch` for both replacement workflows - expected audit failure reproduced: both replacements are ignored and untracked.
- Fresh `Get-AiEnvironmentState` - observation completed: `Status=ACCEPTANCE_FAILED`; active statuses also include `DRIFTED`, `SOURCE_UNTRUSTED`, and `UNTESTED_PROVIDER_VERSION`; `DirtyPathCount=15`; promotion and repair are false.
- `scripts/Build-ProviderSkillPackages.ps1 -Check` - pass: 44 files across 16 skills.
- `scripts/Compare-ProviderSkillParity.ps1 -FailOnUndeclaredFork` - pass: 16 pairs, 1 declared fork.
- Claude docs contract - pass: 16 tests.
- Codex docs contract - pass: 19 tests.
- `git diff --check` - pass.
- Full release-readiness and Pester suites - not run; this was a findings-first review, and the focused checks already expose merge blockers.
- Post-review resolution evidence (2026-08-25): `python -B -m unittest .\codex-skills\local-hooks\devhome-lifecycle\tests\test_remember_adapter.py` passed 74/74. That isolated suite uses a fake Claude executable, so the candidate lock correctly remains unresolved and uncommitted.

## Coverage Notes

- Reviewed deeply: all 13 substantive tracked paths; both deleted workflows and their ignored local equivalents; `.gitignore`; `.gitattributes`; both untracked review reports; current local/remote refs; fresh AiEnvironment observation.
- Excluded from content review: 190 paths proven line-ending-only by `--ignore-cr-at-eol`; the already merged five-commit branch history.
- The DevHome transcript check was used only to validate the Codex event-field claim. DevHome content is ephemeral and is not a durable audit dependency.

## Open Questions

- Was Claude `2.1.243` actually exercised for this candidate, or should the current controller be re-tested at `2.1.241`?
- Should the canonical workflow artifacts remain in the tracked `.vscode/workflows` path, or should `cc-workflow/workflows/` become the tracked source of truth?
- Which checkout/editor operation rewrote 190 LF-pinned files to CRLF?

## Recommended next gate

Preserve the dirty recovery worktree. Resolve the tracked-workflow destination,
correct the provider-specific `closeout` contract and tests, re-run current
acceptance for a truthfully tested Claude version, and normalize only the
unintended working-copy line endings. Then run full QA before any staging or
lock promotion.
