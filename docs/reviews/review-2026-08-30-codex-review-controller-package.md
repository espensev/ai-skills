# Review - Codex Review Controller Package

**Date:** 2026-08-30

**Surface:** scoped working-tree package over `2d27dd3`

**Spec source:** `docs/reviews/review-2026-08-30-claude-review-controller.md`

**Standards sources:** `AGENTS.md`, `codex-skills/AGENTS.md`, and the local
`review`, `qa`, and `ship` skill contracts

**Initial verdict:** FAIL

**Final recheck verdict:** PASS WITH NOTES

## Findings

### High

- [axis: regression] `codex-skills/skills/review-controller/SKILL.md:85-101`
  records each evidence artifact's length and digest, but later freshness gates
  only recompute the hash of the already stored manifest bytes. They do not
  explicitly re-read every E-id artifact, recalculate its current length and
  digest, and rebuild the canonical manifest. An artifact can therefore change
  while the stored manifest and review fingerprint remain identical.
  `codex-skills/tests/test_review_controller_skill.py:69-79` asserts related
  keywords but does not require this revalidation sequence.

  Evidence: an independent adversarial pass changed the modeled underlying
  artifact while leaving the stored manifest constant; the before and after
  manifest fingerprints remained equal. The focused test still passed 7/7.

  Impact: workers and the controller can accept findings derived from stale
  evidence even though the report claims a matching final fingerprint.

  Recommendation: at every freshness gate, re-read every local/captured E-id,
  recalculate its current byte length and digest, rebuild the sorted canonical
  manifest, and compare both per-entry identity and the resulting fingerprint
  with the frozen baseline. Strengthen the focused contract test to require
  that sequence.

  **Resolution:** resolved before staging. The corrected contract now requires
  the full per-artifact reread, rehash, manifest rebuild, entry comparison, and
  fingerprint comparison at return, second-wave, report, and completion gates;
  it explicitly rejects re-hashing stored manifest bytes as a freshness check.
  The focused test now asserts that complete sequence. An independent
  adversarial recheck returned ACCEPT.

### Low

- [axis: standards] `skills-src/manifest.json:25` says
  `provider_owned_shared_skills` "ship in both packages", while parity is
  actually computed from same-name directories in both provider source trees
  and portable export/install is selected independently by each install
  manifest. `review-controller` is intentionally selected only by the Codex
  install manifest in this lane.

  Evidence: `scripts/Compare-ProviderSkillParity.ps1:156-179` enumerates the
  provider source trees without consulting install manifests; the export and
  installer scripts use the install-manifest skill lists.

  Impact: the note can make a governed source pair look portable in both
  packages when one provider intentionally holds it out of export.

  Recommendation: describe these as same-name pairs present in both provider
  source trees and state that parity governance is independent of portable
  export/install selection.

  **Resolution:** resolved before staging in `skills-src/manifest.json`; the
  focused package test now preserves the corrected distinction.

## Verification

- Tested staged source/package snapshot `47baa24`: focused skill/document
  contracts passed, 26 tests; full Codex suite passed, 714 tests plus five
  subtests. The final index differs from that tested tree only by this review
  artifact's verification update.
- Corrected-surface independent adversarial recheck - ACCEPT; the stale-evidence
  attack is closed and no new blocker was found.
- Exact staged deterministic routing evals - pass, 38/38 overall; the positive
  `review-controller` and negative staged-diff boundary cases each scored 5/5.
- `scripts/Build-ProviderSkillPackages.ps1 -Check` - pass, 44 files across 16 skills.
- `scripts/Compare-ProviderSkillParity.ps1 -FailOnUndeclaredFork` - pass, 16 generated pairs and two declared forks.
- README/package counts - pass at 41 total, 25 Codex, and 16 Claude skills.
- Exact staged non-strict ready-package validation, export smoke, and temporary
  installer smoke - pass. Source, export, and temporary install hashes match for
  both `SKILL.md` and `agents/openai.yaml`.
- Exact staged strict validation - expected fail only for the seven externally
  owned, unmanifested Claude directories named in the spec source.
- Staged JSON parsing and whitespace checks - pass. Ruff was not available in
  the current system Python/tool path.
- One first full-suite attempt failed only because the long `%TEMP%` worktree
  made a nested Git-worktree portability test exceed its viable Windows path;
  that test passed alone and the complete suite passed from an equivalent short
  worktree at the same staged snapshot.

## Coverage Notes

- Deep-reviewed: `codex-skills/skills/review-controller/SKILL.md`, its
  `agents/openai.yaml`, focused test, three routing-eval fixtures, Codex install
  manifest, both package/catalog README surfaces, provider-fork manifest, and
  the Claude source-audit report.
- Excluded: all Claude implementation/package edits, `codex-state-cleanup`,
  usage-stats, memory-management, lifecycle, environment-lock, and other dirty
  worktree changes.
- Mixed ownership: `README.md`, `codex-skills/README.md`, and
  `codex-skills/package/install-manifest.json` require index-only selective
  patches. A review-controller-only snapshot uses counts of 41 total and 25
  Codex skills.

## Open Questions

- None. The initial high finding was repaired and independently rechecked.
  Strict release readiness remains separately blocked by the seven unmanifested
  Claude skill directories recorded in the spec source. Routing evidence is
  deterministic mock scoring rather than a live paid model probe.
