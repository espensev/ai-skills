# DevHome Codex lifecycle hooks

This directory is the source authority for the machine-local Codex hooks used
on verified controller `snd-desk`. The installed projection is
`D:\DevHome\state\codex`; do not develop the runtime copy independently.

The package is source-only. It is deliberately absent from
`release-manifest.json` and `codex-skills/package/install-manifest.json` because
the DevHome guardrails and Claude Remember bridge are not portable defaults.

## Active hooks

| Event | Behavior |
|---|---|
| `PreToolUse` | Blocks broad destructive commands and direct writes to generated memory or the ACL-protected Sevnet runtime. |
| `SessionStart` | Loads Remember context through the bounded Windows adapter. |
| `UserPromptSubmit` | Blocks high-confidence secrets before prompt submission. Remember does not run concurrently on this event. |
| `PostToolUse` | Captures the accepted transcript for Remember in the background. |
| `Stop` | Performs the final transcript synchronization for the turn. |

The raw Claude Remember hooks stay unregistered. `Invoke-RememberAdapter.py`
translates Codex transcripts into the narrow Claude transcript shape expected by
Remember and contains Git Bash in a Windows Job Object.

## Install or refresh

The installer runs the hash-bound DevMesh v2 verifier from the local machine
kit and matches the enrolled machine and instance IDs before mutation. It backs
up the closed set of files it replaces, renders absolute command paths for the
target, and never edits Codex hook-trust state.

```powershell
.\codex-skills\local-hooks\devhome-lifecycle\Install-DevHomeCodexHooks.ps1
```

After a hook definition changes, restart Codex and review it in `/hooks`.
Referenced script content is deployed by the installer, but hook trust remains
an explicit user decision.

Read-only drift check:

```powershell
.\codex-skills\local-hooks\devhome-lifecycle\Install-DevHomeCodexHooks.ps1 -Check
```

## Verification

```powershell
Invoke-Pester -Path .\codex-skills\local-hooks\devhome-lifecycle\tests\DevHome-Hooks.Tests.ps1 -Output Detailed
python -m unittest .\codex-skills\local-hooks\devhome-lifecycle\tests\test_remember_adapter.py
```

Generated `__pycache__` and adapter runtime state are not source artifacts.
