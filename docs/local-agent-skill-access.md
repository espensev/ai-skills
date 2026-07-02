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
