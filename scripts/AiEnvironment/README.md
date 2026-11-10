# AI environment wanted state

This module is the cross-provider wanted-state observation, planning, and Phase 2
lock lifecycle seam for the effective Codex and Claude environment. It separates
reviewed intent, a candidate or accepted lock, and generated observed state. It
still does not install, enable, trust, repair, or remove live provider resources;
automated reconciliation remains held for a later apply phase.

The public interface exports six functions:

```powershell
Import-Module .\scripts\AiEnvironment\AiEnvironment.psd1 -Force
$state = Get-AiEnvironmentState
$plan = $state | New-AiEnvironmentPlan
$verification = $state | Test-AiEnvironment

# Phase 2 lock lifecycle & observed-state output:
Update-AiEnvironmentLock
$state | Save-AiEnvironmentState
Approve-AiEnvironmentLock
```

`Get-AiEnvironmentState` performs all observation I/O and emits one normalized
snapshot. `New-AiEnvironmentPlan` and `Test-AiEnvironment` are pure projections
of that snapshot. `Save-AiEnvironmentState` writes schema-validated
`<profileId>.observed.json` snapshots (defaulting to
`<DevHomeStateRoot>\ai-environment\<profileId>.observed.json`).
`Update-AiEnvironmentLock` captures a `candidate` lock from a clean, identified
Git `HEAD`, live provider versions, verified source/target payload digests, and
persisted Codex hook trust hashes. `Approve-AiEnvironmentLock` promotes a
`candidate` lock to `accepted` only when the source worktree is clean and every
observation, compatibility, trust, and behavioral acceptance gate passes with
`CURRENT` status. Provider adapters remain private to the module.

The Claude adapter also observes the existing `Test-HandoffNote.ps1`
SessionStart registration: event, matcher, exact command, timeout, synchronous
execution, script existence, duplicate registrations, and `disableAllHooks`.
This is an observed resource owned by DevHome, so it needs no Ai-Skills payload
lock and grants no repair authority. The observer expands `%NAME%` references
in its profile's expected command and script path at read time; Claude's
`settings.json` still contains a concrete command. A passing observation proves
the selected settings file, not effective policy from other settings layers
or execution in a fresh Claude session.

The observer fails closed when a managed marketplace is incomplete, a provider
command times out, Git cannot be observed, a Claude plugin lacks a registry
record, or a persisted Codex hook trust hash differs from the lock. Foreign
marketplace failures stay in a separate owner-review lane so they do not hide
the health of managed payloads.

Every locked payload is also verified against the raw blob at the declared Git
commit, including the committed plugin version. Because `locks/snd-desk.lock.json`
is versioned inside `Ai-Skills` itself, `Get-AiGitObservation` treats a
descendant `HEAD` as matching `lock.source.commit` when `lock.source.commit` is
an ancestor of `HEAD` and zero tracked changes occurred inside any managed
`sourceRoot` between `lock.source.commit` and `HEAD`; rollbacks, divergent
branches, and any change inside a managed `sourceRoot` fail closed with
`SOURCE_COMMIT_MISMATCH`. Unsupported provider/resource shapes fail schema and
adapter-coverage validation before observation begins. Managed Codex plugin
profiles declare a stable cache root; the observer selects its version child
from the lock and rejects missing or unsafe lock versions.

Companion workstation state hygiene scripts live alongside the module in
`scripts/`:

- `scripts/Repair-CodexSkillConfig.ps1` (`-Check`, `-DryRun`, `-IncludeCompanionAccounts`):
  prunes only simple `[[skills.config]]` blocks whose `path` no longer exists on
  disk and whose `enabled` flag is `false`, verifying semantic TOML equivalence
  via `tomllib` before atomic replacement.
- `scripts/Sync-SharedSkillLock.ps1` (`-Check`, `-DryRun`, `-SeedLockPath`):
  reconciles `<AGENTS_HOME>/.skill-lock.json` (`version = 3`) against installed
  `SKILL.md` folders under `<AGENTS_HOME>/skills`.

The checked-in `snd-desk.lock.json` is intentionally `candidate` while the
recovered source worktree contains unaccepted local changes. Promotion requires
an accepted lock backed by a clean, identified commit and passing behavioral
acceptance gates.

Use this maintenance loop for upgrades:

1. Change reviewed intent in `profiles/snd-desk.json` and keep provider-specific
   observation details inside the private adapters.
2. Exercise the new provider version and changed artifact in fixtures.
3. Capture a `candidate` lock from an identified commit, including payload and
   hook-trust hashes; do not mark it accepted from a dirty worktree.
4. Generate and review observed state, resolve every blocker and manual gate,
   then promote the lock in a separate reviewed change.
5. Keep automated repair disabled until the later apply phase consumes only an
   accepted lock and independently verifies the result.

Run the focused contracts with:

```powershell
Invoke-Pester -Path .\scripts\tests\AiEnvironment.Tests.ps1 -Output Detailed
```
