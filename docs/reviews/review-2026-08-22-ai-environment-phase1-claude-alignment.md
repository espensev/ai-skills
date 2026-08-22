# Review - AI Environment Phase 1 Commit and Claude Alignment

**Date:** 2026-08-22
**Surface:** fixed point `origin/main` (`5881f07`) → `HEAD` (`5d22bf5`) on
`recovery/ai-environment-wanted-state-20260822`; 1 commit, 15 paths,
+4133/-1. Live Claude state under `D:\DevHome\state\claude` was read to judge
the Claude lane of the observer.
**Spec source:** handoff note at
`D:/DevHome/state/remember/projects/d--Development-AI-related/remember.md`
(Phase 1 outcome, verified-state claims, next gate); user request "review and
align for Claude as needed".
**Standards sources:** `CLAUDE.md`, `AGENTS.md` (repo),
`D:\DevHome\state\claude\CLAUDE.md` (global), `scripts/AiEnvironment/README.md`,
`docs/reviews/review-2026-08-22-ai-environment-wanted-state.md` (the design
review shipped inside the commit).
**Verdict:** PASS WITH NOTES — keep `5d22bf5` as the Phase 1 local commit; it
is read-only and mutates nothing. Three Medium findings (all latent on this
machine) should land as a follow-up commit on the same branch before any push
or lock promotion.

## Findings

### High

No findings.

### Medium

- [axis: regression] `scripts/AiEnvironment/Private/Get-CodexEnvironmentObservation.ps1:97-124`
  — an `observed` marketplace that is not `local`-typed, or that has vanished
  from `config.toml`, reports `Result=PASS` with zero reasons, while the same
  check row carries `ReasonCode=FOREIGN_MARKETPLACE_ROOT_MISSING` and
  `Evidence=sourceExists=False;manifestValid=False` for a source the guard at
  `:43` never opened.
  Evidence: both DEGRADED branches (`:98`, `:103`) require `$configured -and
  $sourceTypeMatches`; otherwise `$foreignMarketplaceIssue` stays false and
  `:120` yields PASS. Critic probe with a stubbed `codex.cmd`: declared
  `observed` marketplaces `absent` (unconfigured), `gitmp` (`source_type =
  "git"`), `nosuchtype` → all `PASS`, `REASONS: (none)`; an empty reason list
  renders top-level `CURRENT` (`Common.ps1:1126`).
  Impact: a declared observed marketplace disappearing from Codex config is
  invisible; a git-typed one (e.g. `chrome-devtools-plugins` at
  `D:\DevHome\state\codex\config.toml:369`, not yet in the profile) would
  produce a self-contradicting row. Latent today: the only observed
  marketplace in the profile (`wt-local`) is local-typed and degrades
  correctly. No test covers a non-local or unconfigured observed marketplace.
  Recommendation: emit a distinct non-PASS result (or a truthful
  `NOT_APPLICABLE` reason code with evidence that does not assert
  `sourceExists=False`) when `$configured` is false or the type is
  unsupported; add one Pester case per branch.

- [axis: spec] `scripts/AiEnvironment/profiles/snd-desk.json:58` vs
  `scripts/AiEnvironment/locks/snd-desk.lock.json:22` — the profile pins the
  lifecycle plugin `targetRoot` to the `0.2.0` cache directory while the
  candidate lock pins `version: "0.1.0"` (the version at commit `5881f07`).
  Evidence: `git show 5881f07:codex-skills/local-hooks/devhome-lifecycle/.codex-plugin/plugin.json`
  → `0.1.0`; working tree → `0.2.0`; live report shows
  `OWNED_PLUGIN_PAYLOAD_MISMATCH expected=11;…;mismatched=10`.
  Impact: the two reviewed documents describe different plugin versions.
  Every future bump needs a profile edit plus a lock recapture, with a
  guaranteed mismatch window; the lock is supposed to be the single promotion
  artifact.
  Recommendation: derive the versioned cache segment from `lock.version`
  (profile holds `cacheRoot`, adapter appends `<name>\<lock.version>`), or move
  `targetRoot` into the lock resource. Do it when the lock is recaptured for
  the relay/0.2.0 commit.

- [axis: regression] `scripts/AiEnvironment/AiEnvironment.psm1:146` —
  `RESOURCE_LOCK_MISSING` is a `RepairReady` blocker (`:95`) but is absent from
  the `BLOCK_PROMOTION` action set, so a managed resource with no lock entry
  plans as `BLOCKED_RECONCILIATION`.
  Evidence: live plan row `BLOCKED_RECONCILIATION hook:claude-handoff-relay
  managed artifact`.
  Impact: harmless today (RepairReady can never be true while the reason is
  present) but the action type tells an operator "reconciliation pending"
  when the truthful action is "capture a lock entry first"; a Phase 2 apply
  path keyed on action type would mis-route it.
  Recommendation: add `RESOURCE_LOCK_MISSING` to the `BLOCK_PROMOTION` set and
  pin it with a Pester case.

### Low

- [axis: regression] `scripts/AiEnvironment/Private/Common.ps1:659` — plugin
  table headers match only `[plugins."…"]`; marketplaces (`:647`) and hooks
  (`:667`) accept both quote styles via `Unquote-AiTomlKey`. Codex does write
  literal-quoted table keys (`config.toml:1082`, the `[projects.'…']` block).
  A `[plugins.'x@y']` header is silently dropped → `OWNED_PLUGIN_DISABLED`
  (fails closed, wrong diagnosis). One-line fix: mirror the marketplace
  pattern.

- [axis: standards] `scripts/tests/AiEnvironment.Tests.ps1:369-395` — the
  "candidate lock backed by raw blobs" test duplicates all 16 payload hashes
  from `locks/snd-desk.lock.json` into the test body and asserts the lock
  equals that copy, then verifies blobs at `5881f07`. The blob verification
  is legitimate; the duplicated hash table is a snapshot of a data file. Every
  lock recapture now requires a lockstep test edit, and the test fails in any
  clone lacking `5881f07`. Recommendation: keep the blob check, drop the
  literal table (assert the lock's own entries against `git cat-file`).

- [axis: regression] `scripts/AiEnvironment/Private/Common.ps1:902-921` —
  `Compare-AiLockedPayload` shares `missing`/`mismatched` between source and
  target sides; evidence `missing=0;mismatched=2` cannot say which side
  drifted. Same pattern at `:1101` (`$missingRecordedPaths` reused for
  "recorded but not installed").

- [axis: spec] `scripts/AiEnvironment/Private/Get-ClaudeEnvironmentObservation.ps1:127`
  — hook registration lookup is hard-coded to the `Stop` event; the profile
  resource carries only `registrationContains`. Correct for the Handoff Relay;
  a second Claude hook on another event would report
  `CLAUDE_HANDOFF_REGISTRATION_MISSING`. Add optional `desired.event` when
  needed.

- [axis: spec] `scripts/AiEnvironment/Private/Common.ps1:979` vs `:762-766` —
  fallback `VersionExpected` counts only resources with a non-empty `version`;
  the main path also counts `kind: plugin`. Failure path only.

- [axis: standards] Handoff wording "51/51 unsupported shapes rejected" is true
  (critic re-enumerated all 60 triples: 9 accepted / 51 rejected, zero
  mismatches) but the durable suite covers 1 of the 51
  (`AiEnvironment.Tests.ps1:416,434`); no test pins the schema `oneOf` list
  (`profile.schema.json:111-184`) to the runtime allowlist
  (`Common.ps1:114-124`). They match today and can drift silently.

- [axis: standards] `D:\DevHome\state\claude\CLAUDE.md` (global) named the
  repo as `D:\Development\Ai-Skills`; it lives at
  `D:\Development\AI-related\Ai-Skills`. Fixed in the alignment pass.

## Claude lane — live state behind the observer's Claude findings

Verified against `D:\DevHome\state\claude` (junction target of
`C:\Users\Sev\.claude`, so registry records under either prefix resolve to the
same directory):

- `CLAUDE_PLUGIN_RECORD_MISSING declared=23;missingRecords=1` —
  `settings.json` `enabledPlugins` carried `"frontend-design@frontend-design": true`.
  No marketplace named `frontend-design` exists in
  `plugins/known_marketplaces.json`, no registry record; the live plugin is
  `frontend-design@claude-plugins-official`. Dead key.
- `CLAUDE_PLUGIN_RECORD_PATH_MISSING missingPaths=1` —
  `plugins/installed_plugins.json` held a `scope: local` record for
  `code-review@claude-plugins-official` bound to project
  `D:\Development\Ai_Supervision` (does not exist) with cache
  `…\code-review\d5c15b861cd2` (does not exist), dated 2026-03-13. Dead record.
- `RESOURCE_LOCK_MISSING hook:claude-handoff-relay` — correct by construction:
  the relay source files are untracked (`Install-DevHomeClaudeHandoffRelay.ps1`,
  `hooks/Invoke-HandoffRelay.ps1`), so no commit-backed lock entry can exist.
  Installed relay hash equals source hash (`a16aba0d…`); installer `-Check`
  reports `CURRENT 2 files`.
- `REMEMBER_ACCEPTANCE_FAILED` — carried from the lock; not re-run here.

## Alignment pass (performed after the review, identity `VERIFIED snd-desk`)

1. `D:\DevHome\state\claude\settings.json` — removed the dead
   `enabledPlugins["frontend-design@frontend-design"]` key.
2. `D:\DevHome\state\claude\plugins\installed_plugins.json` — removed the dead
   local-scope `code-review` record for the non-existent `Ai_Supervision`
   project.
   Backups of both originals:
   `D:\DevHome\state\claude\hook-backups\ai-environment-align\20260822-054641\`.
3. `D:\DevHome\state\claude\CLAUDE.md` (global) — corrected the Ai-Skills repo
   path.
4. Repo `AGENTS.md` and `CLAUDE.md` — added one mirrored Package Boundary
   bullet declaring `scripts/AiEnvironment/` the read-only observer, the lock
   the promotion artifact, and the observed report generated output. Both
   files were already dirty with the relay wording; the bullet rides with that
   uncommitted doc change.
5. Regenerated `D:\DevHome\state\ai-environment\snd-desk.observed.json`
   (atomic temp+move). Result: reasons 15 → 13, checks 24;
   `provider.claude.plugin-registry` now `PASS
   (ids=26;records=26;missingPaths=0;declared=22;missingRecords=0)`. Remaining
   Claude-lane reasons: `REMEMBER_ACCEPTANCE_FAILED`, `RESOURCE_LOCK_MISSING
   hook:claude-handoff-relay`. Top status unchanged: `ACCEPTANCE_FAILED`,
   `PromotionReady=false`, `RepairReady=false`. New report SHA-256
   `E38B3C9A0604A1E5223A04852006AE6F952808469B7123BB683A89AC2A683E7C`.

Not touched: Codex config, hook trust, plugin caches, the committed module,
the candidate lock, remotes.

## Handoff claims verified

| Claim | Result |
|---|---|
| HEAD `5d22bf5`, parent `5881f07`, tree `78ca88da…` | match |
| 0 origin-only / 1 local-only vs `origin/main` | match |
| Index empty | match |
| `git fsck --full --strict` | passes (2 dangling objects, not errors) |
| Commit is exactly the 15 reviewed paths | match |
| Observed report SHA-256 `B85784…216` (pre-alignment) | match |
| Pester 30/30 | reproduced twice (controller + critic) |
| Live state: `ACCEPTANCE_FAILED`, 15 reasons, 24 checks, 15 actions | reproduced (pre-alignment) |
| Claude relay projection `CURRENT` | reproduced |
| 9/9 supported, 51/51 unsupported resource shapes | reproduced by critic enumeration |
| Real `config.toml` parses (5 marketplaces, 24 plugins, 18 hook-trust records, 180 skill entries) | reproduced by critic |

## Verification

- `Invoke-Pester scripts/tests/AiEnvironment.Tests.ps1` — pass 30/30 (twice).
- `Get-AiEnvironmentState | New-AiEnvironmentPlan | Test-AiEnvironment` —
  pass; run before and after the alignment pass.
- `Install-DevHomeClaudeHandoffRelay.ps1 -Check` — `CURRENT`, 2 files.
- `Get-VerifiedMachineIdentity.ps1` — `VERIFIED snd-desk`.
- Critic probe of `Get-CodexEnvironmentObservation` with hermetic fixtures —
  reproduced the foreign-marketplace fail-open (table in Medium #1).
- Full `Test-ReleaseReadiness.ps1` — not re-run (handoff reports PASS; only
  the wanted-state slice is in scope).

## Coverage Notes

- Deep-reviewed by controller: `AiEnvironment.psm1`, `AiEnvironment.psd1`,
  `Get-ClaudeEnvironmentObservation.ps1`, `Common.ps1` 1-520 and 751-1000,
  profile, lock, module README, root README diff, `Test-ReleaseReadiness.ps1`
  diff, the shipped review document, `Get-CodexEnvironmentObservation.ps1`
  36-126 (to confirm the critic), `AiEnvironment.Tests.ps1` 355-400.
- Deep-reviewed by adversarial critic: `Get-CodexEnvironmentObservation.ps1`,
  `Common.ps1` 520-750 and 1000-1151, the three JSON schemas,
  `AiEnvironment.Tests.ps1` in full.

## Open Questions

- Should the relay commit also recapture the lock at that commit (0.2.0 +
  relay payload), or does the lock stay pinned at `5881f07` until Remember
  acceptance is green? The profile/lock version skew depends on it.

## Recommended next commits (same branch, before push)

1. `fix(ai-environment)`: Medium #1 (+2 tests), Medium #3 (+1 test), Low TOML
   plugin-key regex. Small, mechanical; builder-tier.
2. `feat(devhome-lifecycle)`: the Claude Handoff Relay (two untracked files +
   the already-edited docs/tests/0.2.0 bump), then recapture the candidate
   lock at that commit with a `hook:claude-handoff-relay` payload and resolve
   Medium #2 at the same time.

## Fix pass (same day, `fix(ai-environment)` commit)

- Medium #1 fixed: an `observed` marketplace absent from `config.toml` now
  reports `FOREIGN_MARKETPLACE_NOT_CONFIGURED` (DEGRADED, routed to
  `REVIEW_FOREIGN_OWNER`); a non-`local` one reports check result `UNKNOWN`
  with `FOREIGN_MARKETPLACE_SOURCE_UNINSPECTED` and evidence that names the
  source type instead of asserting `sourceExists=False`. Healthy observed rows
  carry `FOREIGN_MARKETPLACE_OBSERVED`. Two tests added.
- Medium #3 fixed: `RESOURCE_LOCK_MISSING` now plans as `BLOCK_PROMOTION`;
  existing test expectation tightened.
- Low fixed: `[plugins.'…']` single-quoted headers parse via
  `Unquote-AiTomlKey`. One test added.
- Low fixed: the lock-snapshot test derives expected counts from the lock
  document instead of a duplicated hash table.
- Medium #2 (profile/lock version skew) deliberately left for the relay
  commit and lock recapture.
- Verification: `Invoke-Pester` 33/33; `Test-ReleaseReadiness.ps1
  -SkipParityReport` PASS (lifecycle 49/49, installer 3/3, wanted-state 33/33,
  package gates).
