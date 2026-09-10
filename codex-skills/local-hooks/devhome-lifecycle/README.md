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
| `UserPromptSubmit` | Blocks high-confidence secrets; separately prepares a turn-bound Codex handoff destination. |
| `Stop` | Runs the compact, evidence-labelled Handoff Relay. |

## Handoff Relay

Handoff Relay is one shared, synchronous implementation with provider-specific
`Stop` output: Claude receives non-error `additionalContext`; Codex receives its
strict `decision: block` continuation shape. It defers while Claude reports
background tasks or session crons. Both providers receive bounded
`systemMessage` notices when preparation starts and when publication succeeds,
fails, or conflicts.

For Codex, the relay's `UserPromptSubmit` handler verifies `snd-desk`, resolves
the enrolled target, and snapshots its hash before model work. It supplies the
exact draft destination as developer context without a preparation tool call or
model continuation. Session ID, turn ID and a readable transcript are required;
missing preparation retains the two-pass Stop protocol below. The canonical
startup declaration remains routing information; the active draft instruction
directs authoring for this turn.

After completing all work and verification, the agent adds only the draft in a
dedicated `apply_patch` call, then gives its normal final answer and required Run
closeout. The observed code-mode wrapper `text(await tools.apply_patch(...));`
is supported. First Stop accepts this path only when the native transcript
records a completed single-file Add for this session/turn, the recorded content
matches the bounded draft, the dedicated call completes, and no later work or
steering appears. Mixed calls, shell writes, update-only records, pending tools,
post-draft compaction, and unknown transcript shapes retain recovery. This is a
conservative adapter for observed Codex 0.153.4 records, not a stable transcript
API or semantic proof of the handoff's claims.

Repeated prompt events preserve an active baseline. A missing or stale draft
requests at most one recovery continuation without refreshing that baseline;
the stale attempt is archived. If another Stop handler has already continued
the turn, stale prepared content fails neutrally instead of creating a loop.
Q&A still skips draft authoring/publication, although prompt-time preparation
adds one bounded process and temporary state write. Background-work skips remain.
Compaction or missing instructions cannot grant publication on file existence.

Prepared publication and Q&A skips record at most 32 completion entries in one
32-KiB-bounded `completed.json` under the project lock. A repeated Stop is skipped
only while its transcript has no later work; new messages or tools need another
capture. Failed/conflict attempts remain archived as before. The receipt is
duplicate suppression, not proof of publication; a receipt-write failure after
publication remains a PUBLISHED result with `completionReceiptSaved=false`.

Only interactive sessions relay. After project resolution the hook classifies
the session and records a neutral `SKIPPED` health result with code
`non-interactive-sdk` (Claude: `CLAUDE_CODE_ENTRYPOINT` starts with `sdk`, or
the transcript's records carry an `sdk*` entrypoint), `non-interactive-exec`
(Codex: `session_meta` source `exec` or originator `codex_exec`), or
`non-interactive-subagent` (Codex: `session_meta.source` carries a `subagent`
object, or `session_meta.session_id` names a root thread other than the
rollout's own `id`; a spawned worker writes its own rollout under its own id).
Those sessions get no draft, no continuation prompt, and no canonical write;
an unreadable or unrecognized transcript stays on the interactive path.

For Claude and unprepared Codex turns, the first Stop verifies `snd-desk`, resolves the canonical target, snapshots its
hash, and creates a session/turn-scoped draft under the enrolled project's
`tmp\handoff-relay` directory. A declared target must match the nearest enrolled
workspace; a declaration for another project is skipped. When a supported
transcript establishes a short Q&A turn with no tools, Stop skips preparation
except for handoff-related requests. The question must end in `?`; both the
question and accumulated assistant reply are limited to 500 characters each.
Substantial written work and missing replies retain recovery. Missing, malformed,
or unrecognized transcripts retain the recovery path. Tool activity is a
conservative checkpoint signal, including read-only tools; this is not yet an
explicit project opt-in policy or a semantic change detector.

In that recovery protocol, the agent edits only the draft, then ends with 1-2 useful, self-contained
sentences summarizing the task outcome and the most relevant next action or
blocker. If no follow-up is needed, it says so without inventing work. A handoff
status or generic acknowledgement alone is insufficient. It condenses the
earlier answer without repeating it in full or repeating its Run closeout,
and does not claim publication from the draft write.
The second Stop validates the state and draft, takes a per-project lock, rejects
a changed canonical hash as a preserved conflict, and atomically publishes
`remember.md`.

The prompt handler adds a new Codex-managed hook definition. After synchronizing,
review that `UserPromptSubmit` relay entry in `/hooks` in a fresh Codex session.
Installation proves file convergence; it does not manufacture hook trust or
prove that a running session loaded the new definition. Whole-task model/time
savings still require matched native-session measurements; fixture success does
not establish the observed 37.7-second continuation is entirely avoidable.

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
bullets only, deduplicates them, limits the body to 450 words, removes
extra prose/code/unknown sections, and drops explicitly unverified or
speculative fact bullets. Verified-state bullets require `[verified]` plus
`Evidence:`; risks require `[risk]` plus `Basis:`. This is deterministic
provenance enforcement, not semantic fact-checking. Missing required content is
preserved as a failed draft instead of replacing the canonical handoff.
Both authoring prompts render the same section limits consumed by validation:

| Section | Maximum bullets | Total words | Words per bullet |
|---|---:|---:|---:|
| Summary | 2 | 45 | 26 |
| Outcome | 3 | 60 | 26 |
| Verified state | 4 | 100 | 34 |
| Changed surfaces | 4 | 60 | 24 |
| Verification | 4 | 70 | 26 |
| Open risks | 3 | 55 | 26 |
| Next gate | 2 | 40 | 24 |

Word counts include labels and evidence. An over-budget unique fact or gate
fails the entire draft with `draft-budget-exceeded`; it is never clipped or
dropped to make a successful publication fit. The previous canonical bytes
remain intact, the original draft is archived, and Stop returns a bounded
message without another continuation. Exact duplicates remain safe to remove,
including duplicates encountered after a section reaches its bullet limit.
Put the current priority first in Next gate and link deferred work separately.
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
