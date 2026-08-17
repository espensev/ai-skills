# Release Readiness

This repository contains multiple package shapes. Not every package is shipped
the same way, so release readiness is tracked explicitly.

## Ready Packages

| Package | Status | Delivery | Notes |
|---|---|---|---|
| `codex-skills` | Ready | Portable runtime package | Ships skill docs, contracts, and Python runtime modules. |
| `claude-skills` | Ready | Portable runtime package | Ships skill docs, contracts, and Python runtime modules. |

## Not Part Of Skill Export

| Package | Status | Notes |
|---|---|---|
| `telemetry-live-ops` | Source-only machine-local skill | Kept under provider skill trees for this workstation's live `ollama-telemetry` deployment; intentionally excluded from install manifests and ready exports. |
| `devhome-lifecycle` | Source-only local Codex plugin | Offered through the `ai-skills` repository marketplace; excluded from portable manifests and verified with source/runtime plus source/cache contracts. |

## Release Checklist

Run the full local release gate before shipping:

```powershell
.\scripts\Test-ReleaseReadiness.ps1
```

The wrapper runs ready-package validation, README manifest count checks, the
single-source skill regeneration check, Codex and Claude contract tests, isolated machine-local lifecycle catalog/cache/runtime
contracts, provider parity reporting, and git whitespace checks. The lifecycle
Pester tests use disposable fixtures; this source-only gate does not invoke the
installed Claude Remember plugin or prove that the user has trusted the Codex
SessionStart hook.
Use `-IncludeLiveRootCompare` after syncing local Codex and Claude skill roots.

Individual checks are also available when narrowing a failure:

```powershell
.\scripts\Update-ReadmePackageCounts.ps1 -Check
.\scripts\Build-ProviderSkillPackages.ps1 -Check
.\scripts\Compare-ProviderSkillParity.ps1 -MaxRows 20
```

## Single-Source Skill Layer

Skills listed in `skills-src/manifest.json` under `generated_skills` are
authored once in `skills-src/<skill>/SKILL.src.md` and regenerated into both
provider packages with:

```powershell
.\scripts\Build-ProviderSkillPackages.ps1
```

The generated `SKILL.md` files stay committed package outputs, so installers
and exporters are unchanged. Edit the canonical source, regenerate, and commit
both together; never hand-edit a generated `SKILL.md`. Skills not listed in
`generated_skills` (including the drifted `provider_owned_shared_skills`) are
provider-owned and untouched by the generator.

## Export Flow

Validate the ready-package manifests, source-only exclusions, README counts,
export smoke, and installer smoke first:

```powershell
.\scripts\Test-ReadyPackages.ps1
```

Use the root export script to gather the ready packages into one destination:

```powershell
.\scripts\export-ready-skill-packages.ps1 -TargetDir ".\dist\ai-skills-ready-packages" -Force
```

The script reads `release-manifest.json` and exports only packages whose status
is `ready`. If `-TargetDir` is omitted, the script falls back to the manifest
default export location.

## Local Root Compare

After running `Install-AgentSkills.ps1`, compare installed Codex and Claude
skill roots against manifest-listed source files:

```powershell
.\scripts\Compare-AgentSkillRoots.ps1 -Provider Both -FailOnMissingOrStale
```

Pass `-IncludeExtra` when you intentionally want to list unrelated local skills
that are present in an agent root but not managed by these packages.

## Machine-Local Lifecycle Acceptance

After the source-only gate passes, explicitly check the local plugin cache and
DevHome runtime projection:

```powershell
.\codex-skills\local-hooks\devhome-lifecycle\Sync-DevHomeLifecyclePlugin.ps1 -Check
.\codex-skills\local-hooks\devhome-lifecycle\Sync-DevHomeCodexHooks.ps1 -Check
```

The full Remember adapter suite is host-dependent because one test invokes the
installed Claude Remember plugin. Run it separately and treat any failure as a
live lifecycle blocker even when `Test-ReleaseReadiness.ps1` is green:

```powershell
python -B -m unittest .\codex-skills\local-hooks\devhome-lifecycle\tests\test_remember_adapter.py
```

Current host acceptance findings are tracked in
[`docs/reviews/review-2026-08-16-devhome-lifecycle-feature.md`](reviews/review-2026-08-16-devhome-lifecycle-feature.md).

Finally restart Codex, confirm `devhome-lifecycle@ai-skills` is enabled, review
and trust the current SessionStart command in `/hooks`, and perform one attended
new-session smoke. Source acquisition is outside all of these checks; none of
them pulls or cleans the Ai-Skills checkout.

No-AppData acceptance also requires a regression probe proving that an ambient
AppData-like `CODEX_HOME` cannot relocate adapter mirrors, locks, checkpoints,
logs, Remember discovery, or transcript validation. That probe is currently red
and is tracked in the feature review above.
