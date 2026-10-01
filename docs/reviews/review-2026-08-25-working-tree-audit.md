# Working-tree audit - superseded

The 2026-08-25 audit reviewed `recovery/ai-environment-wanted-state-20260822`
at `414be3f` after PR #7 merged into `origin/main` at `3ca00e7`. Its original
FAIL verdict remains historical; use the [independent rereview](review-2026-08-25-working-tree-audit-rereview.md)
for findings, resolutions, unresolved acceptance, and safe delivery guidance.

The rereview corrected two unsafe recommendations:

- The `.vscode/workflows` files were the only tracked workflow copies. Their
  byte-equivalent local replacements were ignored, so deleting the tracked
  originals would lose them from a fresh clone. Both tracked files were restored.
- `.gitattributes` already pinned LF. Diagnose unintended working-copy rewrites
  and preserve explicit task ownership; do not add redundant policy or broadly
  renormalize the repository.

It also records the provider-specific elapsed guidance/test repair. The
candidate lock's Claude-version and Remember acceptance evidence remained an
independent gate; the isolated fake-Claude adapter pass did not satisfy it.

## Retained historical evidence

- Initial status: 204 dirty paths, including 190 CR/LF-only paths; substantive
  diff 13 files, +328/-918. Observer count 14 included an untracked Codex review.
- Generation check passed: 44 files across 16 skills. Provider parity passed:
  16 pairs, one declared fork. Claude/Codex documentation contracts passed
  16/19 tests respectively; run each package separately because root-level
  collection collides on their `tests` module names.
- The cost guidance correctly separated native token counters from measured
  monetary cost; counters alone do not prove billing.
- Observer reported `ACCEPTANCE_FAILED`, `DRIFTED`, `SOURCE_UNTRUSTED`, and
  `UNTESTED_PROVIDER_VERSION`; promotion and repair were false. Full
  release-readiness and Pester were not run by this audit.

These counts and observations describe the dated review, not current installed
provider state. The [rereview](review-2026-08-25-working-tree-audit-rereview.md)
retains the detailed acceptance/version questions and subsequent evidence.
