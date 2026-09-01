# Review - Usage Stats Rolling Window

**Date:** 2026-08-26
**Surface:** Current `usage-stats` source contract and package support-file pipeline
**Spec source:** User request to answer rolling 24-hour Codex/ChatGPT token usage
**Standards sources:** `AGENTS.md`; `codex-skills/AGENTS.md`; `skills-src/manifest.json`
**Verdict:** FAIL

## Findings

### High

No high-severity findings.

### Medium

- [axis: spec] `skills-src/usage-stats/SKILL.src.md:107` limits native Codex guidance to the current session even though rolling-window requests span every active session file.
  Evidence: the only aggregate-window command targets optional telemetry at line 95; when that service is unavailable, native cross-session counters are skipped.
  Impact: a request such as "last 24 hours" can be undercounted, downgraded to an estimate, or require an improvised parser.
  Recommendation: provide a tested native rolling-window collector that sums cumulative counter deltas, deduplicates repeated counters, and reports explicit coverage.

- [axis: standards] `scripts/Test-ReadyPackages.ps1:150` validates every `scripts/...` reference only against package-level runtime manifests.
  Evidence: `scripts/Test-ReadyPackages.ps1:122` separately recognizes skill-local support directories, and `scripts/Build-ProviderSkillPackages.ps1:161` explicitly packages those files.
  Impact: a generated skill cannot ship its own focused helper script without failing the release gate.
  Recommendation: accept an existing path relative to the skill root before applying package-runtime validation.

### Low

- [axis: spec] `skills-src/usage-stats/SKILL.src.md:107` does not explicitly distinguish native Codex counters from ordinary ChatGPT web/app conversations.
  Evidence: the counter schema and storage path are Codex-specific.
  Impact: a correct Codex total can be misreported as combined ChatGPT account usage.
  Recommendation: emit machine-readable included/excluded scope and require the answer to preserve it.

## Verification

- Source inspection of the data ladder, package generator, installer, and ready-package validator - completed.
- Implementation tests - pending remediation.

## Coverage Notes

- Reviewed deeply: `skills-src/usage-stats/SKILL.src.md`, provider generator, package installer, ready-package validator, Codex usage contract tests.
- Excluded: unrelated dirty Handoff Relay, browser-control, memory-management, lock, and line-ending-only changes.

## Open Questions

- None. Ordinary ChatGPT web/app usage remains an explicit excluded surface unless an authoritative source is later added.
