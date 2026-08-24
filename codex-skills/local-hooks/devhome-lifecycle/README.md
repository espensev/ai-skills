# DevHome lifecycle hooks

This directory is the source authority for the machine-local Codex lifecycle
hooks and the shared Claude/Codex **Handoff Relay** used on verified controller
`snd-desk`. The installed projections are under `D:\DevHome\state\codex` and
`D:\DevHome\state\claude`; do not develop the runtime copies independently.

Known placement blocker: `Invoke-RememberAdapter.py` currently derives its
generated mirrors, locks, checkpoints, and logs from ambient `CODEX_HOME`.
Plugin/cache/runtime-file placement is pinned to DevHome, but the broader
no-AppData lifecycle requirement is not complete until adapter state is pinned
as well.

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
| `Stop` | Runs final Remember capture and the compact, evidence-labelled Handoff Relay independently; Codex may launch matching handlers concurrently. |

## Handoff Relay

Handoff Relay is one shared, synchronous implementation with provider-specific
`Stop` output: Claude receives non-error `additionalContext`; Codex receives its
strict `decision: block` continuation shape. It defers while Claude reports
background tasks or session crons.

The first Stop verifies `snd-desk`, resolves the canonical target, snapshots its
hash, and creates a session/turn-scoped draft under the enrolled project's
`tmp\handoff-relay` directory. The agent writes only that draft. The second Stop
validates the state and draft, takes a per-project lock, rejects a changed
canonical hash as a preserved conflict, and atomically publishes `remember.md`.

Target resolution accepts the latest exact `Write next handoff to:` declaration
only from a developer/system transcript record. Without one, it walks `cwd` and
its parents to the nearest enrolled Remember project. The canonical file may be
created on first successful publication, but its parent must already be an
enrolled `D:\DevHome\state\remember\projects\<project>` directory. User-authored
targets, relative paths, unenrolled projects, and paths outside that store do
not write a handoff.

Published handoffs use seven ordered sections: Summary, Outcome, Verified state,
Changed surfaces, Verification, Open risks, and Next gate. The cleaner keeps
bullets only, deduplicates and caps them, limits the body to 450 words, removes
extra prose/code/unknown sections, and drops explicitly unverified or
speculative fact bullets. Verified-state bullets require `[verified]` plus
`Evidence:`; risks require `[risk]` plus `Basis:`. This is deterministic
provenance enforcement, not semantic fact-checking. Missing required content is
preserved as a failed draft instead of replacing the canonical handoff.
Each bullet is also bounded to 512 text elements and 1,024 UTF-8 bytes; the
published document is capped at 32 KiB.

The latest redacted result is written atomically to
`D:\DevHome\state\remember\handoff-relay\latest-status.json`. Raw failed or
conflicting drafts remain under the enrolled project's bounded temporary relay
directory for diagnosis. Shutdown remains fail-open after recording a bounded
failure.

Current acceptance blocker: the installed Remember `0.20.0` PostToolUse hook
exceeds the adapter's three-second upstream bound, so the adapter fails open and
does not produce the expected capture markers. The feature review linked below
records the reproduction.

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
alternate `CODEX_HOME` into AppData or another user-state root. That guarantee
currently covers marketplace configuration, plugin cache, and the six Codex runtime
files; it does not yet cover adapter-generated state noted above.

The command does not acquire source changes: update this checkout separately,
then run synchronization. It never pulls, resets, or cleans Git. Codex owns the
plugin's enabled state and hook-trust records; synchronization proves catalog
and payload convergence, not activation.

The trusted plugin `SessionStart` hook runs its cached bootstrap with the
canonical Ai-Skills source path. The bootstrap therefore checks the six-file
runtime projection against current repository source, not against a possibly
stale cache, and invokes the verified-machine installer only when drift exists.

Plugin hooks are not trusted automatically. Review the reconciliation hook in
`/hooks` after first installation or after its command definition changes. The
existing behavior hooks remain the only registrations for safety and Remember,
so enabling the plugin does not double-submit lifecycle events.

Until that SessionStart definition is explicitly trusted, the plugin can be
installed and enabled while automatic runtime reconciliation is still skipped.

Read-only plugin-cache convergence check:

```powershell
.\codex-skills\local-hooks\devhome-lifecycle\Sync-DevHomeLifecyclePlugin.ps1 -Check
```

## Install or refresh Codex

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

## Install or refresh Claude

The Claude installer uses the same identity gate, installs the shared relay
script under `D:\DevHome\state\claude\hooks`, and merges one owned `Stop`
registration into `settings.json` while preserving unrelated settings and
hooks. It backs up any replaced settings/script files.

```powershell
.\codex-skills\local-hooks\devhome-lifecycle\Install-DevHomeClaudeHandoffRelay.ps1
```

Read-only drift check:

```powershell
.\codex-skills\local-hooks\devhome-lifecycle\Install-DevHomeClaudeHandoffRelay.ps1 -Check
```

Start a fresh Claude session after installation. Codex likewise needs a fresh
session and explicit `/hooks` trust review when its hook definition changes.

## Verification

The repository release gate covers isolated marketplace, cache, installer, and
runtime-projection contracts:

```powershell
Invoke-Pester -Path @(
    '.\codex-skills\local-hooks\devhome-lifecycle\tests\DevHome-Hooks.Tests.ps1',
    '.\codex-skills\local-hooks\devhome-lifecycle\tests\DevHome-PluginSync.Tests.ps1'
) -Output Detailed
```

The Remember adapter suite is a separate host-dependent integration check; one
test invokes the currently installed Claude Remember plugin. It is intentionally
not hidden behind the source-only release gate, and any failure blocks live
lifecycle acceptance. The current acceptance result is recorded in the
repository's
[`docs/reviews/review-2026-08-16-devhome-lifecycle-feature.md`](../../../docs/reviews/review-2026-08-16-devhome-lifecycle-feature.md):

```powershell
python -B -m unittest .\codex-skills\local-hooks\devhome-lifecycle\tests\test_remember_adapter.py
```

Generated `__pycache__` and adapter runtime state are not source artifacts.
