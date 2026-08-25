---
name: devhome-lifecycle
description: Check, synchronize, or diagnose the machine-local DevHome Codex safety and Remember lifecycle hooks plus the shared Claude/Codex Handoff Relay on enrolled snd-desk. Use when asked about hook drift, lifecycle plugin status, automatic handoffs, or updating either DevHome hook projection.
---

# DevHome lifecycle

Maintain the Codex lifecycle hooks and shared Claude/Codex Handoff Relay for
verified controller `snd-desk` without editing installed projections or Codex
trust state by hand.

## Authority

- Source authority:
  `D:\Development\AI-related\Ai-Skills\codex-skills\local-hooks\devhome-lifecycle`
- Codex projection: `D:\DevHome\state\codex\hooks.json` and the five owned
  scripts under `D:\DevHome\state\codex\hooks`
- Claude projection: `D:\DevHome\state\claude\settings.json` plus
  `D:\DevHome\state\claude\hooks\Invoke-HandoffRelay.ps1`
- Plugin cache:
  `D:\DevHome\state\codex\plugins\cache\ai-skills\devhome-lifecycle`; never
  develop there or relocate it through `CODEX_HOME`
- Known blocker: adapter-generated mirrors, locks, checkpoints, and logs still
  derive from ambient `CODEX_HOME`; do not claim full no-AppData placement until
  the production adapter pins those paths to physical DevHome.
- Known blocker: the installed Remember PostToolUse integration currently
  exceeds the adapter's three-second bound and fails open; a green cache/runtime
  check does not prove Remember capture.

The package remains outside the portable provider manifests. The
`devhome-lifecycle@ai-skills` plugin contributes this skill and one startup
reconciler; the five Codex event groups remain registered only through the
installed DevHome projection so they do not execute twice. Handoff Relay is the
shared Stop implementation installed into both agents.

Handoff Relay uses a verified two-pass draft protocol. It resolves the nearest
enrolled ancestor for nested working directories, writes agent output to
session-scoped temporary state, structurally cleans the seven-section handoff,
then hash-checks and atomically publishes under a project lock. Read the latest
redacted result at
`D:\DevHome\state\remember\handoff-relay\latest-status.json`; do not edit or
promote draft/conflict files by hand. The cleaner removes unsupported forms and
explicit speculation, bounds each bullet to 512 text elements and 1,024 UTF-8
bytes, and caps publication at 32 KiB. It does not semantically prove a claim.

## Refresh the plugin choice

From the Ai-Skills repository root, use the normal local sync entrypoint. It
registers the marketplace and proves source-to-cache hash convergence:

```powershell
.\scripts\Install-AgentSkills.ps1 -Provider Codex -CodexLocalPlugin DevHomeLifecycle
```

Do not assume a restart refreshes a local plugin cache. Use
the canonical source synchronizer for a read-only cache check:

```powershell
& 'D:\Development\AI-related\Ai-Skills\codex-skills\local-hooks\devhome-lifecycle\Sync-DevHomeLifecyclePlugin.ps1' -Check
```

The startup bootstrap receives the canonical source path, so runtime
reconciliation still uses current repository files if the materialized plugin
cache is old. Plugin enablement and hook trust remain Codex-managed user state;
an installed/current cache does not prove that SessionStart is active.

## Check

Run the read-only convergence check from the source authority:

```powershell
& 'D:\Development\AI-related\Ai-Skills\codex-skills\local-hooks\devhome-lifecycle\Sync-DevHomeCodexHooks.ps1' -Check
```

## Synchronize

If the check reports drift, run the same script without `-Check`. It delegates
mutation to the identity-gated installer and verifies convergence afterward:

```powershell
& 'D:\Development\AI-related\Ai-Skills\codex-skills\local-hooks\devhome-lifecycle\Sync-DevHomeCodexHooks.ps1'
```

Do not copy files manually, edit generated native memory, or manufacture hook
trust. After refreshing a changed hook definition, restart Codex and review the
new definition in `/hooks`.

Check or synchronize the Claude projection with the dedicated installer:

```powershell
& 'D:\Development\AI-related\Ai-Skills\codex-skills\local-hooks\devhome-lifecycle\Install-DevHomeClaudeHandoffRelay.ps1' -Check
& 'D:\Development\AI-related\Ai-Skills\codex-skills\local-hooks\devhome-lifecycle\Install-DevHomeClaudeHandoffRelay.ps1'
```

Start a fresh Claude session after synchronization. The installer preserves
unrelated settings and hooks and backs up any files it replaces.

Source acquisition is separate: never pull, reset, or clean the Ai-Skills
checkout as part of lifecycle reconciliation.
