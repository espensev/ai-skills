# Review - Working-Tree Audit (usage-stats closeout, lock refresh, dedupe)

**Date:** 2026-08-25
**Surface:** working tree of `recovery/ai-environment-wanted-state-20260822` at `414be3f` (branch is fully merged into `origin/main` `3ca00e7` via PR #7; 0 commits ahead, so the working tree is the only unreviewed surface)
**Spec source:** none found (user request: "review and audit for improvements")
**Standards sources:** `CLAUDE.md`, `AGENTS.md`, `scripts/AiEnvironment/README.md`, `.gitignore`, `claude-skills/tests/test_skill_docs_contract.py`, `codex-skills/tests/test_skill_docs_contract.py`
**Verdict:** SUPERSEDED (original verdict: FAIL) — use `review-2026-08-25-working-tree-audit-rereview.md` for corrected workflow and line-ending guidance

`git status` reports 204 dirty paths; 190 differ only by CR/LF. The
substantive diff (`git diff --ignore-cr-at-eol`) is 13 files, +328/-918, and
matches the observer's own `DirtyPathCount=14` (13 + the untracked Codex review
report).

## Findings

### High

No findings.

### Medium

- [axis: regression] `scripts/AiEnvironment/locks/snd-desk.lock.json:16` - The
  refreshed lock declares Claude `testedVersions: ["2.1.243"]` but the installed
  Claude is `2.1.241`, so the lock fails the observer's own compatibility gate.
  Evidence: `Get-AiEnvironmentState` → `provider.claude.version FAIL`
  (`PROVIDER_VERSION_NOT_IN_LOCK`, `observed=2.1.241;tested=2.1.243`);
  `Common.ps1:497-498` requires exact membership. The module exports only
  `Get-AiEnvironmentState`, `New-AiEnvironmentPlan`, `Test-AiEnvironment`
  (`AiEnvironment.psd1:8-12`) — there is no capture command, so the version was
  hand-typed. Codex `0.149.1` was updated correctly in the same edit.
  Impact: adds a fourth active status (`UNTESTED_PROVIDER_VERSION`) that did not
  exist at the committed lock; promotion cannot pass on this machine even after
  the Remember acceptance is fixed.
  Recommendation: set `testedVersions` to the version actually exercised
  (`2.1.241`), or upgrade Claude first and re-test; never record a version the
  acceptance suite did not run against.

- [axis: regression] `scripts/AiEnvironment/locks/snd-desk.lock.json:5,58-65` -
  `capturedAtUtc` moved to `2026-08-25T00:04:18Z` and every payload hash was
  refreshed for plugin `0.3.0`, but the single acceptance entry is unchanged:
  `remember-posttooluse` `FAIL`, `checkedAtUtc: 2026-08-22T02:00:00Z`, evidence
  "73/74".
  Evidence: diff shows no change below line 57; observer reports
  `Acceptance.Passed=false` with the 08-22 timestamp.
  Impact: the lock presents a fresh capture whose only gate evidence predates
  the capture by three days and predates the relay/plugin `0.3.0` payload it
  now hashes; a reader cannot tell whether the acceptance was re-run against the
  new payload.
  Recommendation: re-run the Remember PostToolUse acceptance against the current
  payload and record the new `checkedAtUtc` and result (still `FAIL` is fine —
  it just has to be current), or add a note field that acceptance is carried
  forward.

- [axis: spec] `skills-src/usage-stats/SKILL.src.md:441-478` (rendered to
  `claude-skills/skills/usage-stats/SKILL.md:401,409-410,425`) - The new
  `closeout` command is written into the shared (non-conditional) body but
  leans on Codex-only concepts: "the turn's `task_started` event" for Elapsed,
  and "approval requests/denials" / `0 denials` for Execution. Claude Code
  transcripts and hooks logs expose neither.
  Evidence: `grep task_started claude-skills/skills/usage-stats/SKILL.md` →
  lines 401, 409, 410, 425. The Claude contract test
  (`claude-skills/tests/test_skill_docs_contract.py:240-245`) only asserts the
  `token_count` sentence is absent, so it passes while the Codex event name
  ships in the Claude package.
  Impact: on Claude the skill instructs measuring from an event that does not
  exist; a literal follower either fabricates an Elapsed figure or reports
  `not exposed` for the headline field of the new command.
  Recommendation: move the `task_started` sentence and the denials counter
  under `{{#codex}}`, give the `{{#claude}}` branch its own Elapsed source
  (first/last transcript timestamp or hooks-log `timestamp`), and extend the
  Claude portability test to `assertNotIn("task_started", ...)`.

### Low

- [axis: standards] `.gitignore:14-15` - The two explicit allowlist lines for
  `cc-workflow/.vscode/workflows/sq-control-*-20260701.json` remain after the
  files are deleted in the working tree.
  Evidence: `git status` shows both as `D`; content is byte-identical (after CR
  stripping) to the surviving
  `cc-workflow/workflows/sq-control-final-fan-control-2026-07-01/*.workflow.json`,
  so the delete is a clean dedupe. The README and prior review
  (`docs/reviews/review-2026-07-08-cc-workflow-merge-fit.md:18`) reference only
  the surviving copies.
  Impact: dead negation rules; a future file with the same name would be
  silently re-tracked.
  Recommendation: drop lines 12-15 (the whole `.vscode/workflows` carve-out)
  in the same commit as the deletion.

- [axis: regression] repository-wide - 190 of 204 dirty paths differ only by
  line endings (`warning: ... CRLF will be replaced by LF` on every
  `claude-skills/`, `codex-skills/` Python/Markdown file; LF→CRLF on `LICENSE`
  and two `.cmd` hooks). There is no `.gitattributes` pinning `eol`.
  Evidence: `git diff --stat` (204 files) vs `git diff --ignore-cr-at-eol --stat`
  (13 files).
  Impact: `git status`/`git add -A` are unusable without filtering; a careless
  `ship` would produce a ~190-file whitespace commit. The observer already
  filters this correctly (`DirtyPathCount=14`), so promotion logic is not
  affected.
  Recommendation: add a `.gitattributes` (`* text=auto`, `*.cmd text eol=crlf`,
  `*.ps1 text eol=crlf` or whatever matches the committed state) and renormalize
  once, in its own commit, before shipping the substantive 13 files.

- [axis: standards] `scripts/AiEnvironment/locks/snd-desk.lock.json:9` -
  `requireCleanWorktree: true` with `state: candidate` was re-captured from a
  worktree the observer reports as `WorktreeClean=false`. This is permitted for
  a candidate (`CLAUDE.md:32-36` only forbids marking `accepted` from a dirty
  tree), so it is a note, not a defect — but the lock's own hashes cover files
  (`Install-DevHomeClaudeHandoffRelay.ps1`, `Invoke-HandoffRelay.ps1`) whose
  committed state is `414be3f`, which is what `HeadMatchesLock=true` confirms.
  Recommendation: none beyond keeping `state: candidate` until the tree is
  clean at the target commit.

## Positive notes (after findings)

- `Build-ProviderSkillPackages.ps1 -Check` PASS: all 44 generated files across
  16 skills match `skills-src`, including the new `{{#codex}}`-only
  memory-management paragraph and both usage-stats renderings.
- `Compare-ProviderSkillParity.ps1 -FailOnUndeclaredFork` PASS (16 pairs, 1
  declared fork).
- Both docs-contract suites pass (claude 16/16, codex 19/19) and the new tests
  assert real contract lines rather than headings only.
- The `CLAUDE.md`/`AGENTS.md` observer paragraphs are identical, correctly
  name `profiles/` vs `locks/` vs generated output, and match module behavior
  (observer is read-only; `PromotionReady`/`RepairReady` both false today).
- The usage-stats `cost` rewrite correctly stops treating native token counters
  as proof of cost (`SKILL.src.md:237-242`).

## Verification

- `git fetch origin` - pass (`origin/main` advanced `5881f07..3ca00e7`; branch 0 ahead / 1 behind)
- `python -m pytest tests/test_skill_docs_contract.py` in `claude-skills/` - pass (16)
- `python -m pytest tests/test_skill_docs_contract.py` in `codex-skills/` - pass (19). Note: running both packages from the repo root collides on `tests` module names and aborts collection; run per package.
- `pwsh scripts/Build-ProviderSkillPackages.ps1 -Check` - pass
- `pwsh scripts/Compare-ProviderSkillParity.ps1 -FailOnUndeclaredFork` - pass
- `Get-AiEnvironmentState` (read-only) - ran; `Status=ACCEPTANCE_FAILED`, active `ACCEPTANCE_FAILED,DRIFTED,SOURCE_UNTRUSTED,UNTESTED_PROVIDER_VERSION`
- `scripts/Test-ReleaseReadiness.ps1`, Pester suites - not run (full gate; recommend `/qa` before ship)

## Coverage Notes

- Files reviewed deeply: `AGENTS.md`, `CLAUDE.md`, `README.md`,
  `skills-src/usage-stats/SKILL.src.md`, `skills-src/memory-management/SKILL.src.md`,
  `codex-skills/skills/memory-management/SKILL.md`, both
  `tests/test_skill_docs_contract.py`, `scripts/AiEnvironment/locks/snd-desk.lock.json`,
  the two deleted `cc-workflow/.vscode/workflows/*.json` (compared to surviving copies).
- Files sampled: generated `claude-skills/skills/usage-stats/SKILL.md` and
  `codex-skills/skills/usage-stats/SKILL.md` (covered by build `-Check`; grepped
  for the portability finding only).
- Excluded: 190 CR/LF-only paths; untracked
  `docs/reviews/review-2026-08-25-published-handoff.md` (already a review artifact,
  its findings target the handoff note, not this diff).
- The five branch commits were not re-reviewed; they are merged and have prior
  reports (`review-2026-08-22-*`, `review-2026-08-25-handoff-relay-final.md`).

## Open Questions

- Was Claude `2.1.243` actually exercised somewhere (another machine, a
  since-downgraded install), or is it a typo for `2.1.241`?
- Is the `.vscode/workflows` dedupe intentional, or a side effect of a sync
  tool? The content match suggests intentional, but no commit message says so
  yet.
- Local `main` is still `5881f07` (stale vs `origin/main`); fast-forward before
  the next lock capture so `source.commit` can target a main-reachable clean
  commit.

## Recommended next command

Fix the three Medium items directly (lock version, acceptance re-run,
`closeout` conditionals + test), add `.gitattributes` and prune `.gitignore`,
then `/qa` (full gate) and `/ship` in three commits: eol-normalize, dedupe,
feature.
