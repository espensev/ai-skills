# Local Agent Skill Access

Use the root sync script when the curated Codex and Claude package skills should
be available from the local agent skill roots, not just from this repo.

## Default Roots

The script targets the local roots that exist on this workstation:

| Provider | Default roots |
|---|---|
| Codex | `C:\Users\Sev\.codex\skills`, `D:\DevHome\state\codex\skills` |
| Claude | `C:\Users\Sev\.claude\skills`, `D:\DevHome\state\claude\skills` |

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

The plugin contributes one operator skill and one startup reconciliation hook.
It does not duplicate the installed DevHome behavior hooks. Re-run the command
after updating this checkout: it hashes the closed source/cache payload and
refreshes stale plugin material explicitly. A restart alone is not treated as a
cache-update mechanism. The trusted cached reconciler delegates to the canonical
Ai-Skills source, then updates the verified runtime projection if needed.
Unlike portable skill-copy targets, this machine-specific plugin is pinned to
`D:\DevHome\state\codex`; `CODEX_HOME` cannot redirect it into AppData.
