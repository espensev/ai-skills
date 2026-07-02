# Validation Tooling Enhancement Review

**Date:** 2026-07-02
**Scope:** ready-package validation, local agent sync verification, README count
tracking, and provider parity reporting.

## Findings Addressed

- `scripts/Test-ReadyPackages.ps1` now validates the installer path and
  Antigravity bootstrap path, not only package export shape.
- `package/install-manifest.json` can declare `source_only_skills`, so retained
  machine-local or deprecated skill directories stop appearing as unmanaged
  shipping drift while still remaining explicit.
- Manifest-listed skills are checked for direct command references to
  source-only skills, preventing portable skills from depending on local-only
  entrypoints.
- README package counts are checked from manifests and can be refreshed with
  `scripts/Update-ReadmePackageCounts.ps1`.
- Local Codex and Claude skill roots can be compared against source manifests
  with `scripts/Compare-AgentSkillRoots.ps1` after sync.
- Shared provider skill drift can be inspected with
  `scripts/Compare-ProviderSkillParity.ps1`.
- `scripts/Test-ReleaseReadiness.ps1` now gives one release gate for package
  validation, count checks, contract tests, parity reporting, and diff checks.
- Subagent review findings were folded back into the scripts: source-only
  skill intersections fail generically, README count checks require explicit
  rows, and local-root compare can surface source-only installs plus extra files
  inside managed directories.

## Tracking Boundary

The new scripts and docs are source artifacts and should be tracked. No
generated smoke output should be tracked; the smoke scripts default to temp
directories outside the repo. Existing `.gitignore` rules already exclude
`dist/`, `.tmp/`, local agent state, and the imported reference corpus, so no
ignore removal is needed for this pass.
