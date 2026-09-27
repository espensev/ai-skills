# Review - Codex skill eval refresh

**Date:** 2026-09-27

**Surface:** working tree before commit

**Spec source:** current user request to review and improve Codex skills against data

**Standards sources:** `AGENTS.md`, `codex-skills/AGENTS.md`, `codex-skills/eval/README.md`

**Verdict:** PASS

## Findings

No open findings.

The review initially found two medium regression risks. Both were resolved before
this final pass:

- Broad banned substrings were narrowed to provider-leakage checks, so correct
  negated safety guidance is not rejected.
- The contract now requires a green scorer result, unique fixture IDs, exact
  case/response parity, and complete manifest coverage. The scorer also rejects
  duplicate list IDs directly.

## Verification

- `python -m unittest codex-skills.tests.test_skill_docs_contract` - pass, 24 tests.
- `python -m pytest codex-skills/tests -q` - pass, 725 tests and 5 subtests.
- `scripts/Test-ReleaseReadiness.ps1 -SkipUnitTests` - pass.
- `git diff --check` - pass.

## Coverage Notes

- Files reviewed deeply: all seven changed Codex eval/evaluator/test files.
- Files sampled or excluded: generated `eval/results/latest.json` was checked through parsed invariants and the scorer rather than line-by-line prose review.

## Open Questions

- None.
