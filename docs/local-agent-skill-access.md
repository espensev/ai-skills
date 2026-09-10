# Local Agent Skill Access

Use the root sync script when the curated Codex and Claude package skills should
be available from the local agent skill roots, not just from this repo.

## Default Roots

The script targets the local roots that exist on this workstation:

| Provider | Default roots |
|---|---|
| Codex | `C:\Users\Sev\.codex\skills`, `D:\DevHome\state\codex\skills` |
| Claude | `C:\Users\Sev\.claude\skills`, `D:\DevHome\state\claude\skills` |

On enrolled `snd-desk`, the profile paths are junctions to the matching
`D:\DevHome\state` roots. The installer resolves those link identities and
de-duplicates them; the table shows both discovery paths, not two physical
copies.

If `CODEX_HOME` or `CLAUDE_HOME` is set, the script also uses
`$env:CODEX_HOME\skills` or `$env:CLAUDE_HOME\skills`.

## Commands

Preview what would be copied:

```powershell
.\scripts\Install-AgentSkills.ps1 -Provider Both -DryRun
```

Copy only missing manifest-listed package entries:

```powershell
.\scripts\Install-AgentSkills.ps1 -Provider Both
```

Refresh existing manifest-listed entries as well:

```powershell
.\scripts\Install-AgentSkills.ps1 -Provider Both -Force
```

Compare installed files against the package manifests:

```powershell
.\scripts\Compare-AgentSkillRoots.ps1 -Provider Both -FailOnMissingOrStale
```

Pass `-IncludeExtra` only when auditing unrelated local skills in the same
roots; extras are intentionally ignored by the default compare.

The script copies only the skills, support files, runtime files, and runtime
directories listed in each provider's `package/install-manifest.json`. It does
not delete unrelated local skills, and it does not copy source-only package
material such as `telemetry-live-ops`.

## Local Codex plugin choice

Machine-local components remain outside those portable manifests. Register the
repository marketplace separately when `devhome-lifecycle` should appear as an
AI Skills plugin choice:

```powershell
.\scripts\Install-AgentSkills.ps1 -Provider Codex -CodexLocalPlugin DevHomeLifecycle
```

Use `-Provider Both` instead when the Claude roots should be refreshed in the
same invocation. Add `-DryRun` for a read-only package preview plus plugin
convergence report; add `-Force` only for an explicit package refresh and plugin
reinstall.

The plugin contributes one operator skill and one startup reconciliation hook.
It does not duplicate the installed DevHome behavior hooks. Re-run the command
after updating this checkout: it hashes the closed source/cache payload and
refreshes stale plugin material explicitly. A restart alone is not treated as a
cache-update mechanism. The trusted cached reconciler delegates to the canonical
Ai-Skills source, then updates the verified runtime projection if needed; until
that SessionStart hook is trusted, automatic reconciliation is skipped.
Unlike portable skill-copy targets, this machine-specific plugin's registration,
cache, and three runtime files are pinned to `D:\DevHome\state\codex`;
`CODEX_HOME` cannot redirect those surfaces into AppData. The adapter-state
exception is called out separately below.

The three lifecycle surfaces are intentionally distinct:

| Surface | Location | Authority |
|---|---|---|
| Source | `D:\Development\AI-related\Ai-Skills\codex-skills\local-hooks\devhome-lifecycle` | Canonical; update Git separately. |
| Plugin cache | `D:\DevHome\state\codex\plugins\cache\ai-skills\devhome-lifecycle\` | Materialized copy refreshed by the command above. |
| Codex runtime hooks | `D:\DevHome\state\codex\hooks.json` and two owned files under `hooks\` | Installed projection reconciled from source. |
| Claude Handoff Relay | `D:\DevHome\state\claude\settings.json` and `hooks\Invoke-HandoffRelay.ps1` | Dedicated installer preserves unrelated settings/hooks and owns only its exact Stop command and script. |
| Handoff Relay state | `D:\DevHome\state\remember\projects\<project>\tmp\handoff-relay\` and `D:\DevHome\state\remember\handoff-relay\latest-status.json` | Session drafts, hash/lock state, preserved failures/conflicts, and one redacted health record; canonical output remains `<project>\remember.md`. |

Read-only checks:

```powershell
.\codex-skills\local-hooks\devhome-lifecycle\Sync-DevHomeLifecyclePlugin.ps1 -Check
.\codex-skills\local-hooks\devhome-lifecycle\Sync-DevHomeCodexHooks.ps1 -Check
.\codex-skills\local-hooks\devhome-lifecycle\Install-DevHomeClaudeHandoffRelay.ps1 -Check
```

Installation does not prove activation. Plugin enablement and hook trust are
Codex-managed user choices; after first installation or a hook command change,
restart Codex, confirm `devhome-lifecycle@ai-skills` is enabled, and review the
SessionStart reconciler in `/hooks`.
