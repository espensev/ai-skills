# Post-merge release readiness

The full source release gate passes after correcting merge inconsistencies at
`9b1304ffe9bf0ba80d0abec30e36f76e85e5a295`. Checked on SND-DESK, 2026-10-02.

The first run failed because Claude `review-controller` appeared in both
`optional_skills` and `source_only_skills`, and the root README total was 42
instead of 43. Keep the merge's installable Claude controller; remove its
source-only entry and regenerate README counts with the existing script.
A new Python contract reproduced the overlap before the manifest fix and passes
afterward.

The next runs exposed two stale test contracts. The readiness fixture omitted
`TelemetryRepositoryRoot.Tests.ps1`, although the wrapper now invokes it. The
lifecycle test required a hardcoded main Codex home, contradicting the
account-specific installer dispatch introduced in `48dd1bc`. Update the fixture
and the assertion to check account forwarding without overriding `CodexHome`;
the synchronizer retains physical-path validation. The existing six isolated
account-dispatch cases pass. No lifecycle runtime or installer code changed.

Validation: `pwsh -NoProfile -File scripts/Test-ReleaseReadiness.ps1`, exit 0.

- Ready-package validation, temporary export and installer smokes pass.
- README counts: Codex 26, Claude 17, total 43.
- Generated packages: 47 files across 16 skills match canonical source.
- Provider parity: 16 generated pairs, two declared forks, no undeclared forks.
- Python provider/plugin contracts: 50 pass.
- Pester: orchestration 3, lifecycle 129, plugin cache 69, installer 21,
  environment 36, telemetry resolution 16; 274 pass in total.
- Working and staged whitespace checks pass.

Original failures and the final log are retained locally under
`D:/AI4000/_organization/release-readiness-20261002-1548/`;
`release-readiness-complete.log` and `complete-result.json` record the successful
full run. Earlier log files retain their original nonzero outcomes.

This establishes source packaging and disposable-fixture contracts. Installed
root comparison was not requested or run, and no installation was performed.
Grand-sweep stays source-only; actual launch, recovery and external-stop
acceptance remain open because this session has no ZCode workflow tools.
Figure Studio's concurrent calibration and dirty authoring work were untouched.
