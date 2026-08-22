# AI environment wanted state

This module is the Phase 1 read-only seam for observing the effective Codex and
Claude environment. It separates reviewed intent, a candidate or accepted lock,
and generated observed state. It does not install, enable, trust, repair, or
remove provider resources.

The public interface is deliberately small:

```powershell
Import-Module .\scripts\AiEnvironment\AiEnvironment.psd1 -Force
$state = Get-AiEnvironmentState
$plan = $state | New-AiEnvironmentPlan
$verification = $state | Test-AiEnvironment
```

`Get-AiEnvironmentState` performs all I/O and emits one normalized snapshot.
`New-AiEnvironmentPlan` and `Test-AiEnvironment` are pure projections of that
snapshot. Provider adapters remain private to the module.

The observer fails closed when a managed marketplace is incomplete, a provider
command times out, Git cannot be observed, a Claude plugin lacks a registry
record, or a persisted Codex hook trust hash differs from the lock. Foreign
marketplace failures stay in a separate owner-review lane so they do not hide
the health of managed payloads.

Every locked payload is also verified against the raw blob at the declared Git
commit, including the committed plugin version. Unsupported provider/resource
shapes fail schema and adapter-coverage validation before observation begins.

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
