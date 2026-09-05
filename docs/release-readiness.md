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

Run the full local release gate before shipping. The repo scripts require
**PowerShell 7+ (`pwsh`)** — they rely on .NET APIs such as
`[System.IO.Path]::GetRelativePath` that Windows PowerShell 5.1 does not have:

```powershell
.\scripts\Test-ReleaseReadiness.ps1
```

The wrapper runs ready-package validation, README manifest count checks, the
single-source skill regeneration check, provider parity enforcement, Codex and Claude contract tests, isolated machine-local lifecycle catalog/cache/runtime
contracts, provider parity reporting, and git whitespace checks. Parity
*enforcement* is a separate, non-skippable step: `-SkipParityReport` silences
the human-readable table but never the gate. The lifecycle
Pester tests use disposable fixtures; this source-only gate does not invoke the
installed Claude Remember plugin or prove that the user has trusted the Codex
SessionStart hook.
Use `-IncludeLiveRootCompare` after syncing local Codex and Claude skill roots.

Individual checks are also available when narrowing a failure:

```powershell
.\scripts\Update-ReadmePackageCounts.ps1 -Check
.\scripts\Build-ProviderSkillPackages.ps1 -Check
.\scripts\Compare-ProviderSkillParity.ps1 -MaxRows 20
.\scripts\Compare-ProviderSkillParity.ps1 -FailOnUndeclaredFork
```

## Provider Parity Enforcement

`Compare-ProviderSkillParity.ps1` compares every skill that ships in both
`claude-skills/skills/` and `codex-skills/skills/`, including pairs held out of
the portable release. It classifies each pair:

- **Generator-enforced** — listed in `generated_skills`. Body differences are
  produced by the generator and byte-verified by
  `Build-ProviderSkillPackages.ps1 -Check`, so they are not reported as drift.
  These pairs are instead linted for description declaration: each provider's
  canon must resolve to exactly one `description:` line, and if the two
  providers' descriptions differ, each must come from its own
  `{{#claude}}` / `{{#codex}}` conditional block. A description that diverges
  without a conditional block declaring it is an error.
- **Declared fork** — listed in `declared_provider_forks` in
  `skills-src/manifest.json` with a reason. Reported, never failed.
- **Undeclared fork** — a pair that differs, is not generated, and is not
  declared. This is the failure case.

`-FailOnUndeclaredFork` exits 1 naming the offending skill. It runs as its own
release-gate step with an explicit `$LASTEXITCODE` guard, because `Invoke-Step`
does not propagate child exit codes.

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
`generated_skills` (including `provider_owned_shared_skills`) are
provider-owned and untouched by the generator; the check mode also fails on any
unplanned file inside a generated skill's package directory — not just `.md`, so
a stray `.py` or `.json` is caught too — and on CRLF-corrupted `SKILL.src.md`
sources.

Verbatim support files live under `skills-src/<skill>/files/` (copied to both
providers) or `skills-src/<skill>/files-claude/` and
`skills-src/<skill>/files-codex/` (copied to that provider only).

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

The Grok/Kimi Remember bridge is a second source-only package with its own
tests. `Test-ReleaseReadiness.ps1` does not run them yet; run them by hand
after touching `codex-skills\local-hooks\remember-bridge` and treat a failure
as a live capture blocker for those two hosts. The end-to-end case needs Git
Bash and the pinned checkout at `D:\DevHome\state\remember\artifacts\remember-current`
and skips itself elsewhere:

```powershell
python -B -m unittest .\codex-skills\local-hooks\remember-bridge\tests\test_remember_bridge.py
Invoke-Pester -Path .\codex-skills\local-hooks\remember-bridge\tests\RememberBridge-Install.Tests.ps1
.\codex-skills\local-hooks\remember-bridge\Install-RememberBridge.ps1 -Check
```

Finally restart Codex, confirm `devhome-lifecycle@ai-skills` is enabled, review
and trust the current SessionStart command in `/hooks`, and perform one attended
new-session smoke. Source acquisition is outside all of these checks; none of
them pulls or cleans the Ai-Skills checkout.

No-AppData acceptance also requires a regression probe proving that an ambient
AppData-like `CODEX_HOME` cannot relocate adapter mirrors, locks, checkpoints,
logs, Remember discovery, or transcript validation. That probe is currently red
and is tracked in the feature review above.
