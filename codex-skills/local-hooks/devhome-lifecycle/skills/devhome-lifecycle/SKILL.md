---
name: devhome-lifecycle
description: Check, synchronize, or diagnose the machine-local DevHome Codex safety and Remember lifecycle hooks on enrolled snd-desk. Use when asked about hook drift, lifecycle plugin status, or updating the DevHome hook projection.
---

# DevHome lifecycle

Maintain the Codex lifecycle hooks for verified controller `snd-desk` without
editing the installed projection or Codex trust state by hand.

## Authority

- Source authority:
  `D:\Development\AI-related\Ai-Skills\codex-skills\local-hooks\devhome-lifecycle`
- Installed projection: `D:\DevHome\state\codex\hooks.json` and the four owned
  scripts under `D:\DevHome\state\codex\hooks`
- Plugin cache:
  `D:\DevHome\state\codex\plugins\cache\ai-skills\devhome-lifecycle`; never
  develop there or relocate it through `CODEX_HOME`

The package remains outside the portable provider manifests. The
`devhome-lifecycle@ai-skills` plugin contributes this skill and one startup
reconciler; the five behavior hooks remain registered only through the installed
DevHome projection so they do not execute twice.

## Refresh the plugin choice

From the Ai-Skills repository root, use the normal local sync entrypoint. It
registers the marketplace and proves source-to-cache hash convergence:

```powershell
.\scripts\Install-AgentSkills.ps1 -Provider Codex -CodexLocalPlugin DevHomeLifecycle
```

Do not assume a restart refreshes a local plugin cache. Use
`Sync-DevHomeLifecyclePlugin.ps1 -Check` for a read-only cache check. The startup
bootstrap receives the canonical source path, so runtime reconciliation still
uses current repository files if the materialized plugin cache is old.

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
