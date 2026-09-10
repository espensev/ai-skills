---
name: devhome-lifecycle
description: Check, synchronize, or diagnose the machine-local DevHome Codex safety lifecycle hooks plus the shared Claude/Codex Handoff Relay on enrolled snd-desk. Use when asked about hook drift, lifecycle plugin status, automatic handoffs, or updating either DevHome hook projection.
---

# DevHome lifecycle

Maintain the Codex lifecycle hooks and shared Claude/Codex Handoff Relay for
verified controller `snd-desk` without editing installed projections or Codex
trust state by hand.

## Authority

- Source authority:
  `D:\Development\AI-related\Ai-Skills\codex-skills\local-hooks\devhome-lifecycle`
- Codex projection: `D:\DevHome\state\codex\hooks.json` and the two owned
  scripts under `D:\DevHome\state\codex\hooks`
- Claude projection: `D:\DevHome\state\claude\settings.json` plus
  `D:\DevHome\state\claude\hooks\Invoke-HandoffRelay.ps1`
- Plugin cache:
  `D:\DevHome\state\codex\plugins\cache\ai-skills\devhome-lifecycle`; never
  develop there or relocate it through `CODEX_HOME`
- Remember: Codex capture runs through the upstream `remember@remember-dev`
  plugin (pinned checkout `D:\DevHome\state\remember\artifacts\remember-current`),
  not through this package; the former Windows adapter was retired in 0.3.1.

The package remains outside the portable provider manifests. The
`devhome-lifecycle@ai-skills` plugin contributes this skill and one startup
reconciler; the three Codex event groups remain registered only through the
installed DevHome projection so they do not execute twice. Handoff Relay is the
shared Stop implementation installed into both agents.

When Codex supplies a supported `UserPromptSubmit` payload, the hook prepares a
verified turn-bound draft transaction and supplies its exact destination as
developer context. Confirm that context in the actual session; an enabled
administrative definition alone does not prove host adoption. Complete material work
and verification, add only that draft with a dedicated `apply_patch` call, then
give the normal final answer and required Run closeout. In code mode use only
`text(await tools.apply_patch(...));` in the call. First Stop publishes when the
observed native transcript proves a completed single-file Add with matching
content and no later work. Mixed calls, shell writes, pending tools, steering,
post-draft compaction or unknown transcript shapes retain bounded recovery.
Repeated prompt events and recovery preserve the original canonical baseline.
The active draft instruction governs authoring; keep the canonical startup
declaration for routing. A bounded completion receipt suppresses repeated Stops
only while no later transcript work exists. Review the new prompt relay entry
in `/hooks` after source synchronization; do not edit Codex trust state.

Claude and unprepared Codex turns retain the verified two-pass draft protocol.
It skips SDK-driven Claude sessions, `codex exec` runs, and Codex subagent
rollouts entirely (health code `non-interactive-sdk|exec|subagent`), and it
skips short tool-free
Q&A identified in supported transcripts, except handoff-related requests. The
question must end in `?`, and question/reply must each fit 500 characters;
substantial written work and missing replies retain recovery. Other
unknown or unreadable transcripts retain recovery. Tool use remains a
conservative checkpoint signal, including read-only calls. This does not replace
the separate startup write instruction or establish explicit project opt-in.
It resolves the nearest enrolled ancestor for nested working directories,
rejects declared targets belonging to another workspace, and writes agent output to
session-scoped temporary state, structurally cleans the seven-section handoff,
then hash-checks and atomically publishes under a project lock. Exact section
names are accepted with or without Markdown heading prefixes. Stop preparation and
the final outcome surface as bounded plain-language UI messages; internal error
codes stay in health records. After a Stop recovery prompt, end with 1-2 self-contained
sentences summarizing the task outcome and a useful next action or blocker;
state when no follow-up is needed without inventing work. Never end with only
handoff status or a generic acknowledgement, repeat the full substantive answer
or Run closeout, or claim publication from a draft write. Read
the global most-recent redacted
result at `D:\DevHome\state\remember\handoff-relay\latest-status.json`; it can
be overwritten by a later project. Do not edit or promote draft/conflict files
by hand. State-less raw drafts are quarantined as orphaned on the next attempt
for that project. The cleaner removes unsupported forms and explicit
speculation. Both prompts state the exact section budgets from the validator's
shared definition, including labels and evidence. Follow those budgets and put
the current user priority first; link deferred work separately. Over-budget
content fails the whole draft with `draft-budget-exceeded`, retaining the old
canonical context and the original draft, without another continuation. Exact
duplicates can be removed, but facts and gates are never clipped to fit.
Each bullet is bounded to 512 text elements and 1,024 UTF-8 bytes, with publication
capped at 32 KiB. The cleaner does not semantically prove a claim.

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

## Diagnose visible hook failures

Convergence checks prove only the owned source-to-projection bytes. They do not
clear failures from foreign plugin hooks and they do not prove behavioral
capture. For a visible `PreToolUse:<tool>` or `PostToolUse:<tool>` error:

1. Preserve the exact event/tool label, status text, exit code, and timestamp.
2. Inspect effective `D:\DevHome\state\claude\settings.json` registrations and
   the enabled plugin manifests. Map the matching command to its owner before
   changing anything; Hookify and other foreign plugin hooks are outside this
   package's source authority.
3. Probe the exact failing launcher token in the hook process environment. For
   a `python3` registration on Windows, run `Get-Command python3 -All`,
   `where.exe python3`, and `python3 --version`, recording `$LASTEXITCODE`.
   Probe `python` or `py -3` separately only to identify a supported repair;
   their success does not make `python3` healthy.
4. Reproduce with one harmless tool call, apply any authorized fix at the
   owning source or supported provider setting, restart the affected provider,
   and repeat that same call.

Treat hook log pings as liveness breadcrumbs, not durable capture output. For
Remember, check whether the store checkpoint (`tmp\last-save.json`) and the
event's expected artifact under `D:\DevHome\state\remember\projects\<slug>`
advance before and after the exact event. Do not patch an installed plugin cache, and do
not disable or rewrite a foreign hook without user authorization. A successful
DevHome lifecycle `-Check` does not clear a foreign hook failure.

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
