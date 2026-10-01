# Review - Grand Sweep Workflow

**Date:** 2026-10-01
**Surface:** Document review of `codex-skills/skills/grand-sweep/SKILL.md`.
**Spec source:** User request to review and improve the grand-sweep workflow; no separate specification found.
**Standards sources:** Repository `AGENTS.md`, `codex-skills/AGENTS.md`, `skills-src/manifest.json`, and `codex-skills/skills/audit-gated-subagents/{SKILL.md,references/pass0-and-gates.md}`.
**Baseline:** 98 lines; SHA256 `BA89CC97D9BDFBACFB3C5DC00D78594DA72204081622DA211DDB2AF4ACB2AD57`; checkout HEAD `48dd1bc24263cbe026f64239526f288723b0e5cc`.
**Verdict on baseline:** FAIL. Findings below cite the original document's line numbers and quote its relevant instructions because the imported skill is untracked.
**Disposition:** Initial document revision accepted with notes; continuation verification is recorded below. ZCode runtime execution remains unavailable through this session's tools.

## Findings

### High

1. **[axis: standards] Overlapping dirty work is reset instead of stopped.**
   - Evidence: `SKILL.md:85` prescribes “save-patch → reset → edit → commit → re-apply when the file overlaps.” The companion at `audit-gated-subagents/SKILL.md:88` says to stop when active dirty work overlaps; `:148` repeats that safety stop.
   - Impact: a campaign following this recipe can remove another session's in-flight work, race its edits, or fail to restore all staged/untracked state. Saving a patch does not establish ownership.
   - Recommendation: stop the overlapping lane, preserve the worktree and index, and resolve ownership or use an isolated worktree. Commit only within existing authorization.

2. **[axis: regression] Frozen paths and replayed results can describe different source versions.**
   - Evidence: `SKILL.md:35` freezes a “base ref, branch, dirty state” and `:37` a file list. `:68` directs resume/amend and `:69` says finished journal steps replay. No resolved commit, reviewed-content digest, or recovery freshness check is required.
   - Impact: cached reviews may refer to earlier contents while remaining workers read later edits. This is a missing recipe contract, not a demonstrated engine defect.
   - Recommendation: pin resolved commits, actual contents including selected dirty/untracked files, authority inputs, manifest and script revisions. Check freshness before launch, recovery and verdict; reuse only results whose inputs still match.

### Medium

3. **[axis: spec] A completed verdict cannot be reconciled against planned work.**
   - Evidence: `SKILL.md:42` names output files, `:49` requires medium/high confirmation, and `:93` records only token spend and confirmed/refuted counts. `:39` sends added scope to remediation without requiring its missing audit tiers.
   - Impact: failed files, unresolved confirmations, duplicate findings and scope additions can disappear from apparently complete totals.
   - Recommendation: require per-path coverage states, stable finding IDs and explicit confirmation outcomes. Publish partial/follow-up status when material work is unresolved. Defer new scope or review an approved scope revision before including it in a verdict.

4. **[axis: regression] Engine-specific guarantees are used without a capability check.**
   - Evidence: `SKILL.md:27` promises exact-path and Git reads after glob failure; `:69` promises replay is “free”; `:70` promises amendment imports cache; `:97` relies on per-actor totals from `GetWorkflowRun`.
   - Local evidence: README `:101` and install manifest `:32` identify a source-only ZCode import. No engine schema or `dynamic-workflows` companion was located in the bounded repository search; current callable tool metadata has no `CreateWorkflow`, `ResumeWorkflowRun`, `AmendWorkflow` or `GetWorkflowRun`.
   - Impact: an agent may author an unusable workflow, misdiagnose access errors as glob failures, or make unsupported claims about recovery and cost.
   - Recommendation: require the companion and live tool contracts before executable authoring/launch. Probe exact reads separately; distinguish an empty scope from access/tool failures. Preserve planning/reporting capability when the engine is unavailable.

5. **[axis: spec] Right-sizing has no enforceable operational limits.**
   - Evidence: `SKILL.md:47` assigns “one reviewer per file”; `:52` says “Right-size every tier.” No active-worker, batch-size, retry or campaign-work ceiling is specified.
   - Impact: a large manifest can create excessive fan-out; independent file reviews also need an explicit path to cross-file contract coverage.
   - Recommendation: freeze available execution limits, batch small related files with explicit ownership, and use bounded seam lenses. Keep session-model defaults; existing owner authorization governs any tier changes.

6. **[axis: standards] Remediation applies behavior-test and named documentation gates universally.**
   - Evidence: `SKILL.md:81` requires “Every fix” to land failing-test-first; `:88` assumes `Verify-Docs`, a docs-hygiene hook and enforcement pins. The companion's validation ladder at `:157`–`:163` differentiates review, docs, comments, behavior and release changes.
   - Impact: documentation-only corrections acquire irrelevant tests or nonexistent commands. Temporarily reverting a guard also needs isolation from shared work.
   - Recommendation: use the target repository's real checks and match them to the change. Retain regression-first behavior fixes and isolated negative checks for safety guards.

## Original Improvement Plan

Keep this skill as a provider-owned, source-only ZCode recipe. Change only its source document and this review; preserve the existing README, install manifest and unrelated dirty reviews.

1. Add dependency/capability preflight and a compact campaign receipt contract.
2. Pin source and script identities; record coverage, findings and scope revisions.
3. Bound concurrency, batches, retries and campaign work using existing limits.
4. Qualify recovery/cache claims and check input freshness.
5. Replace overlap reset with a stop; retain the companion's independent plan and verification gates.
6. Record measured/estimated/unavailable usage distinctly, including stopped attempts.

Completion requires a coherent readback of the revised recipe, independent review of the changed document, source-only classification and reference checks, the repository package validation command, and proof that unrelated dirty files retain their hashes. No engine execution or installation is part of this change.

## Verification

- PASS: complete original document read and line-number capture; baseline SHA256 above.
- PASS: Git status and HEAD inspection. The skill was untracked; two package files and two older review documents were already modified.
- PASS: `skills-src/manifest.json` omits `grand-sweep` from `generated_skills`; `codex-skills/package/install-manifest.json` includes it in `source_only_skills`.
- PASS: companion gate and validation-ladder readback.
- PASS: bounded source/tool capability searches; no engine contract was located. Search absence is local evidence, not a claim about all ZCode installations.
- PASS: local verifier returned `VERIFIED`, machine `snd-desk`, instance `ca96d510-7d87-4cec-8e1a-bd8fc3866903`.
- NOT RUN: engine execution, unavailable through the current tools and outside this document change.
- PASS: `.\scripts\Test-ReadyPackages.ps1 -StrictSkillManifest -SkipExportSmoke -SkipInstallerSmoke` reported 26 Codex shipping skills and two source-only skills.
- PASS: revised-document readback, frontmatter/name/discovery checks, seven step headings, companion gate path and provider-owned/source-only classification.
- PASS: hashes of all four pre-existing modified files match their recorded pre-edit hashes.
- PASS: `git diff --check` for tracked work; both untracked documents were additionally checked with `git diff --no-index --check -- NUL <document>` and a final-newline/trailing-whitespace/conflict-marker scan. No-index status 1 denotes new-file differences; no whitespace diagnostics were emitted.
- PASS: independent revised-document review returned ACCEPT after correcting planned-versus-actual run ID mapping and manifest attribution. This is document verification, not engine execution.

## Implemented Revisions

| Finding | Resolution in revised skill |
|---|---|
| 1: overlapping dirty work | Step 5 stops conflicting lanes, preserves files/index, and limits commits to existing authorization |
| 2: stale source/replay | Steps 1 and 4 pin inputs and revisions, discard changed-input results, and require documented cache invalidation |
| 3: incomplete verdict | Steps 1–3 record coverage and unique finding states, revise or defer added scope, and distinguish partial reporting from complete review |
| 4: unavailable contracts | Step 0 checks actual companion/tool contracts; Steps 4 and 6 qualify replay/cache/counter behavior |
| 5: uncontrolled fan-out | Steps 1–3 freeze limits, batch bounded work, queue units and stop on ceilings/errors |
| 6: inappropriate checks | Step 5 differentiates behavior/safety-guard checks from repository-native docs/comment checks |

The audit receipt is now defined in the skill, with planned tier mappings recorded before launch and actual actor/run IDs attached when assigned. Accounting persists at stops as well as completion and distinguishes measured, estimated and unavailable usage. The README, manifests and older reviews were not edited in this turn. The source-only skill and this new review remain untracked; no commit or installation was performed.

## Coverage Notes

- Deep-reviewed: the complete skill, both repository authority files, generated-source ownership manifest, companion skill and PASS 0/gate reference.
- Sampled: README dependency note, install-manifest selection, and `Test-ReadyPackages.ps1:396`–`:442`.
- Excluded: unrelated package changes and historical reviews; external ZCode runtime, provider configuration and credentials.
- Original package-check gap: source-only validation checked only directory presence. The continuation adds required metadata and local-support checks; it still cannot validate engine execution behavior.

## Continuation: Engine Contract And Source-Only Validation

The user requested continuation. [Discovery findings](../discovery-grand-sweep-validation.md) identify the installed bundled companion and the smallest meaningful checker fix.

- Installed ZCode version `3.14.4.7912` provides the companion at `C:/Program Files/ZCode/resources/glm/packages/bundled-skills/skills/dynamic-workflows/SKILL.md`; its SHA256 is `370E8B89C4FAE16ED306E5564372C8C1C8CDEAC021011BE174DC25A9F38AA722`. An older plugin-guide cache was not the selected installed authority.
- The recipe now distinguishes errored amendment, stopped resume and superseded successors; rejects journaled `world.run` outputs as fresh verification; and explains documented amendment cache matching/invalidation.
- Model selection is run-wide. Different authorized model tiers require linked runs; per-actor model selection is unsupported.
- Internal provider retries are unlimited. Script dispatch limits and an externally enforced token/time ceiling are distinct; no hard ceiling is claimed without an actual enforcer.
- Actor snapshots are truncated at 64 and expose `subagentsTruncated`. Truncated prefix sums yield partial tier attribution, while `usage.spentTokens` remains the complete reported run total with its documented scope.
- The checker adds source-only SKILL.md metadata and local-support checks while leaving portable script/command requirements installable-only. Shipping counts and source-only selection are preserved.
- The stronger check exposed two pre-existing missing discovery triggers. Only description lines in Claude `cc-workflow-builder` and `verify` were normalized.
- Builder regression evidence: RED eight failures/five passes, then GREEN 13 passes. Tests invoke the actual copied checker against isolated fixtures; no actual skill source is mutated.
- Independent continuation QA and final artifact checks are recorded before closeout.

## Open Questions

- Installed source establishes the documented signatures, recovery/cache and accounting fields. Actual launch/recovery and an external token/time stop enforcer remain untested because workflow tools are unavailable in this session.
- No new portable installation or native Codex workflow backend is proposed.
