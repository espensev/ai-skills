# DevHome lifecycle hooks

This directory is the source authority for the machine-local Codex lifecycle
hooks and the shared Claude/Codex **Handoff Relay** used on verified controller
`snd-desk`. The installed projections are under `D:\DevHome\state\codex` and
`D:\DevHome\state\claude`; do not develop the runtime copies independently.

Codex Remember capture is not part of this package. It runs through the
upstream Claude Remember Codex plugin (`remember@remember-dev`, served from the
pinned checkout at `D:\DevHome\state\remember\artifacts\remember-current`);
the former Windows adapter was retired in 0.3.1.

The package is source-only. It is deliberately absent from
`release-manifest.json` and `codex-skills/package/install-manifest.json` because
the DevHome guardrails and Handoff Relay are not portable defaults.

It is also exposed as `devhome-lifecycle@ai-skills` through the repository's
local Codex marketplace. The plugin bundles an operator skill and one startup
reconciler; it does not register a second copy of the behavior hooks below.

## Active hooks

| Event | Behavior |
|---|---|
| `PreToolUse` | Blocks broad destructive commands and direct writes to generated memory or the ACL-protected Sevnet runtime. |
| `UserPromptSubmit` | Blocks high-confidence secrets before prompt submission. |
| `Stop` | Runs the compact, evidence-labelled Handoff Relay. |

## Handoff Relay

Handoff Relay is one shared, synchronous implementation with provider-specific
`Stop` output: Claude receives non-error `additionalContext`; Codex receives its
strict `decision: block` continuation shape. It defers while Claude reports
background tasks or session crons. Both providers receive bounded
`systemMessage` notices when preparation starts and when publication succeeds,
fails, or conflicts.

The first Stop verifies `snd-desk`, resolves the canonical target, snapshots its
hash, and creates a session/turn-scoped draft under the enrolled project's
`tmp\handoff-relay` directory. The agent edits only that file, then repeats its
substantive user-facing closeout instead of replacing it with a bare draft path.
The second Stop validates the state and draft, takes a per-project lock, rejects
a changed canonical hash as a preserved conflict, and atomically publishes
`remember.md`.

Target resolution accepts the latest exact `Write next handoff to:` declaration
only from a developer/system transcript record. Without one, it walks `cwd` and
its parents to the nearest enrolled Remember project. The canonical file may be
created on first successful publication, but its parent must already be an
enrolled `D:\DevHome\state\remember\projects\<project>` directory. User-authored
targets, relative paths, unenrolled projects, and paths outside that store do
not write a handoff.

Published handoffs use seven ordered sections: Summary, Outcome, Verified state,
Changed surfaces, Verification, Open risks, and Next gate. The cleaner accepts
those exact section names with or without Markdown heading prefixes, keeps
bullets only, deduplicates and caps them, limits the body to 450 words, removes
extra prose/code/unknown sections, and drops explicitly unverified or
speculative fact bullets. Verified-state bullets require `[verified]` plus
`Evidence:`; risks require `[risk]` plus `Basis:`. This is deterministic
provenance enforcement, not semantic fact-checking. Missing required content is
preserved as a failed draft instead of replacing the canonical handoff.
Each bullet is also bounded to 512 text elements and 1,024 UTF-8 bytes; the
published document is capped at 32 KiB.

The latest redacted result is written atomically to
`D:\DevHome\state\remember\handoff-relay\latest-status.json`. This is a global
most-recent record and can be replaced by a later project, so the live
`systemMessage` uses plain outcome language while internal diagnostics retain
stable error codes. The handoff header is the completion evidence for a specific
turn. Raw failed or conflicting drafts remain under the enrolled
project's bounded temporary relay directory for diagnosis. A state-less raw
draft is quarantined as `*.orphaned.*.draft.md` on the next relay attempt for
that project instead of remaining indefinitely active-looking. Shutdown remains
fail-open after recording a bounded failure.

Visible Claude hook errors must be attributed to their registration owner. An
owned projection check does not clear foreign plugin hooks such as Hookify. Probe
the registration's exact launcher token in Claude's environment (`python3` is
distinct from `python` on Windows), then repair the owning source or supported
provider setting rather than an installed plugin cache.

This projection registers no Remember hooks. Codex loads them from the
`remember@remember-dev` plugin's own `hooks/hooks.codex.json`, which runs the
upstream Bash scripts directly (Git Bash must be on the user PATH).

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
currently covers marketplace configuration, plugin cache, and the three Codex
runtime files.

The command does not acquire source changes: update this checkout separately,
then run synchronization. It never pulls, resets, or cleans Git. Codex owns the
plugin's enabled state and hook-trust records; synchronization proves catalog
and payload convergence, not activation.

The trusted plugin `SessionStart` hook runs its cached bootstrap with the
canonical Ai-Skills source path. The bootstrap therefore checks the three-file
runtime projection against current repository source, not against a possibly
stale cache, and invokes the verified-machine installer only when drift exists.

Plugin hooks are not trusted automatically. Review the reconciliation hook in
`/hooks` after first installation or after its command definition changes. The
existing behavior hooks remain the only registrations for safety and Handoff Relay,
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

Live Remember capture for Codex is accepted separately against the
`remember@remember-dev` plugin; these tests do not exercise it.
