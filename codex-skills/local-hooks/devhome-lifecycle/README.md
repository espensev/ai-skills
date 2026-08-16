# DevHome Codex lifecycle hooks

This directory is the source authority for the machine-local Codex hooks used
on verified controller `snd-desk`. The installed projection is
`D:\DevHome\state\codex`; do not develop the runtime copy independently.

The package is source-only. It is deliberately absent from
`release-manifest.json` and `codex-skills/package/install-manifest.json` because
the DevHome guardrails and Claude Remember bridge are not portable defaults.

It is also exposed as `devhome-lifecycle@ai-skills` through the repository's
local Codex marketplace. The plugin bundles an operator skill and one startup
reconciler; it does not register a second copy of the behavior hooks below.

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

## Plugin choice and automatic reconciliation

From the Ai-Skills repository root, select the local plugin through the normal
agent-skill synchronization entrypoint:

```powershell
.\scripts\Install-AgentSkills.ps1 -Provider Codex -CodexLocalPlugin DevHomeLifecycle
```

That command registers the repository marketplace, hash-checks the closed plugin
payload in Codex's materialized cache, and installs or refreshes it when needed.
Re-run it after source changes; do not rely on a Codex restart to refresh a local
plugin cache. Use `-Force` when an explicit remove-and-reinstall is wanted.
The local choice is pinned to `D:\DevHome\state\codex`; it does not follow an
alternate `CODEX_HOME` into AppData or another user-state root.

The trusted plugin `SessionStart` hook runs its cached bootstrap with the
canonical Ai-Skills source path. The bootstrap therefore checks the five-file
runtime projection against current repository source, not against a possibly
stale cache, and invokes the verified-machine installer only when drift exists.

Plugin hooks are not trusted automatically. Review the reconciliation hook in
`/hooks` after first installation or after its command definition changes. The
existing behavior hooks remain the only registrations for safety and Remember,
so enabling the plugin does not double-submit lifecycle events.

Read-only plugin-cache convergence check:

```powershell
.\codex-skills\local-hooks\devhome-lifecycle\Sync-DevHomeLifecyclePlugin.ps1 -Check
```

## Install or refresh

The installer runs the hash-bound DevMesh v2 verifier from the local machine
kit and matches the enrolled machine and instance IDs before mutation. It backs
up the closed set of files it replaces, renders absolute command paths for the
target, and never edits Codex hook-trust state.
Its default target is always `D:\DevHome\state\codex`, independent of
`CODEX_HOME`.

```powershell
.\codex-skills\local-hooks\devhome-lifecycle\Install-DevHomeCodexHooks.ps1
```

After refreshing a changed hook definition, restart Codex and review it in `/hooks`.
Referenced script content is deployed by the installer, but hook trust remains
an explicit user decision.

Read-only drift check:

```powershell
.\codex-skills\local-hooks\devhome-lifecycle\Sync-DevHomeCodexHooks.ps1 -Check
```

## Verification

```powershell
Invoke-Pester -Path @(
    '.\codex-skills\local-hooks\devhome-lifecycle\tests\DevHome-Hooks.Tests.ps1',
    '.\codex-skills\local-hooks\devhome-lifecycle\tests\DevHome-PluginSync.Tests.ps1'
) -Output Detailed
python -B -m unittest .\codex-skills\local-hooks\devhome-lifecycle\tests\test_remember_adapter.py
```

Generated `__pycache__` and adapter runtime state are not source artifacts.
