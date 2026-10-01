---
name: grand-sweep
description: "Operational recipe for multi-tier code audit campaigns run as ZCode dynamic workflows (crew audits, grand sweeps). Use when planning or launching a grand audit campaign, designing tier fan-out, writing or amending the campaign workflow script, recovering a crashed or stopped campaign run, or closing out campaign accounting. Not for a single diff/PR review (review), the audit gate discipline itself (audit-gated-subagents), or ordinary non-audit dynamic-workflow runs."
argument-hint: "<what to audit> [--base <ref>] [--slug <name>]"
user-invocable: true
---

# Grand Sweep

Run multi-agent audit campaigns through ZCode dynamic workflows. This is a
source-only recipe: the portable Codex package does not install it or supply
its workflow engine. `audit-gated-subagents` owns authority, lane ownership,
independent plan review, and implementation/verification gates; use both
together. Load `dynamic-workflows` for engine signatures and authoring rules
before writing or revising executable workflow scripts.

Run order: preflight → freeze → author → runtime probe → bounded tiers
→ verdict → authorized remediation → account. Recovery preserves the campaign.

## Step 0 — capability and read preflight

Read repository authority, current dirty/worktree state, and the companion
gate skill. Establish the selected root and any required machine identity
before machine-sensitive actions. Keep inventory read-only and preserve
existing authorization; a published verdict alone does not authorize fixes.

Verify the `dynamic-workflows` companion and actual engine tool contracts:
`CreateWorkflow` for launch; `ResumeWorkflowRun` or `AmendWorkflow` as needed
for recovery; `GetWorkflowRun` or a documented equivalent for receipts.
Prefer the selected engine's installed bundled companion over stale plugin
guide caches; record its path/hash and engine version. Record supported
input, replay, cache and counter behavior. If a required
capability is absent, produce a plan/review and identify the missing contract;
do not fabricate tools, install dependencies, or launch through another backend.

Build the in-scope manifest with repository-native enumeration before
authoring; preserve filenames exactly (for example, parse Git's NUL-delimited
output). Include tracked files and explicitly selected untracked files.
Exclude credentials, private configuration, campaign outputs and out-of-root
targets; count vendor/generated exclusions with reasons. Do not traverse
links into another root without explicit scope authority.

The script's first runtime step probes one known manifest path with
`files.glob`, then verifies exact-path access before fan-out. An empty scope
is reported as empty; an access, index or tool error is not a clean audit.
For a verified glob/index limitation, use the frozen manifest and independently
tested exact-path reads; test `git.*` separately if the script needs it.
Embed a bounded manifest literal or use a manifest-input mechanism documented
by the engine. Stop on unverified access rather than spending reviewer tokens
rediscovering files.

## Step 1 — freeze the campaign receipt

Create a unique `<repo-container>/.audit/crew/<slug>-<date>-<run-key>/`
before authoring or launch. Validate the slug and resolved output path against
the approved root; do not overwrite an existing campaign.

`STATE.md` uses the campaign-record label `crew-audit/v1`. Record these
fields explicitly; this is not an assertion about an engine's JSON schema:

| Field group | Required record |
|---|---|
| Identity and authority | Campaign ID, resolved root/output path, authority files and hashes, scope/operation authorization and review-only limits |
| Source | Requested base and resolved commit SHA (HEAD if no base supplied), branch/HEAD, dirty state and per-input content hashes or immutable snapshot IDs |
| Scope | Revision, manifest path/digest, each in-scope path, read-only dependency paths, and excluded paths with reasons |
| Execution | Script path/revision/digest, actual workflow/run IDs when assigned, actor-to-tier mapping and model assignments |
| Limits | Maximum active workers, files/bytes per batch, script retries/work units, and any token/time ceiling; identify enforcement versus advisory limits |
| Results | Coverage receipts and finding statuses with evidence links; verdict and independent gate artifacts |
| Accounting | Counter source/coverage/timestamp, per-tier attempts and usage, failures, unresolved/deferred work and next action |

`manifest.json` is the authoritative path/content-identity list;
`manifest.txt` is an optional readable projection. Include selected dirty
and untracked contents and all inputs used as evidence. Freeze scope/source
fields by revision; update execution/results/accounting as work progresses.

Workers use the pinned snapshot or verify input hashes before and after each
unit. Discard results whose inputs changed. Check identities before launch,
recovery and verdict. A moved ref or edited source requires a recorded scope
revision and review of affected work and dependent confirmations/lenses.
New scope is either explicitly deferred outside the verdict or admitted by a
reviewed revision whose missing tiers complete before publication.

## Step 2 — design bounded tiers

- Assign every in-scope path to one primary breadth unit. Batch small related
  files within the frozen limits; split oversized files with explicit section
  coverage. Queue work within the active-worker ceiling.
- Keep subagents on the session model unless existing owner authorization
  permits model tiering. A cheaper model must be capable of its assigned work;
  cost is independent of evidence quality. ZCode selects one run-wide
  `subagent_model`; different model tiers need separate linked runs, not
  per-actor overrides. Leave engine model/concurrency overrides unset unless
  the owner requests them as required by the loaded contract; bound script
  dispatch through the reviewed queue/batch plan.
- Assign session-model lenses to concrete contract seams, callers and
  cross-domain behavior. Lenses may raise any severity supported by evidence.
  List their source/dependency inputs so recovery can check freshness.
- Confirm medium/high candidates independently against pinned source and
  counterevidence. Low candidates remain explicitly unconfirmed appendix
  items until reviewed; they are not counted as confirmed defects.
- Count vendor/generated paths without blanket deep inspection. Review
  relevant integration boundaries and generating sources when in scope.
- Give each lane required reads, exact read/output ownership, exclusions,
  validation, failure handling and receipt paths. Workers write separate
  receipts; the controller aggregates. Preserve the companion's independent
  plan/spec review gate before implementation.

A coverage receipt records path/input identity, unit/actor, result artifact
and status: `pending`, `completed`, `failed`, `deferred` or `excluded`,
with reasons for the last three. A returned worker is not proof of coverage.

Each finding has a stable ID, severity, path/line and input identity, impact,
supporting evidence, counterevidence and confirmer result. Track
`candidate`, `confirmed`, `refuted`, `duplicate` or `inconclusive`;
duplicates link to a canonical ID. Deduplicate before allocating confirmers,
retain attempt lineage, and do not inflate defect counts with duplicate votes.

## Step 3 — launch and reconcile the verdict

Submit through verified `CreateWorkflow` inputs and honor its actual
confirmation flow within existing authorization. Use the campaign name and
save returned workflow/run IDs, script revision and receipt locations.
Use background completion notifications when supported; do not repeatedly
poll a run list. A missing notification can justify one bounded status check.

Enforce frozen script retry/work-unit limits and retry only transient failures
that the script actually receives. ZCode retries transient provider failures
internally without a cap; a script retry count cannot bound a pending ask.
Token/time ceilings are advisory unless a verified external controller can
observe them and stop the run using documented `TaskStop` inputs. Record that
enforcer and its observation limits; do not claim a hard ceiling without it.
On a surfaced limit, provider stop or deterministic script failure, stop new
fan-out, preserve receipts and report unfinished units with partial accounting.

Publish `FINDINGS.md`, `MAP.md`, `REPORT.md` and the review verdict at
`docs/reviews/audit-*.md`. Reconcile the manifest against coverage receipts
and finding/confirmation outcomes. The controller checks evidence and owns
the verdict; worker completion or confirmer votes alone cannot approve it.
A complete review requires all in-scope units completed, reconciled input
identities and no unresolved medium/high candidates. Findings may still make
the verdict FAIL. Failed/deferred units or unresolved material findings
require an explicitly partial/follow-up report, never an implied clean pass.
Budget stops and empty scope are not complete reviews.

## Step 4 — recover without stale replay

Save current run ID, script/scope revisions, finished-unit receipts and partial
accounting before recovery. Diagnose the stop and use the same run's supported
recovery operation when appropriate: `errored` needs a corrected script and
`AmendWorkflow`; `stopped` can use `ResumeWorkflowRun` after its cause is resolved.
Do not resume a `superseded` predecessor; use the returned successor run ID.
A user-stopped run stays stopped until the user requests continuation.
Respect provider-reported stops and
existing approval; do not repeatedly retry an unchanged failure or silently
restart an interrupted campaign with different inputs.

Verify source, authority, manifest, script and model/limit identities against
the frozen receipt. Reuse finished results only when their inputs still match.
Amend a script error using documented engine behavior, invalidating affected
steps and their dependent reviews. If selective invalidation is unsupported,
stop and record the required reviewed revision or replacement run; retain and
link the original campaign instead of silently treating cached work as fresh.

Resume replays completed `world.run` outputs; these are not fresh verification.
Require a documented live check for current-state gates. Amendment matches
stable actor names and byte-identical ask sequences; changed asks run live.
After the first live workspace write or live `world.run`, workspace-dependent
cached observations run live again, while answer-only asks may remain cached.
Capture the operation's actual run ID/revision rather than assume amendment
always preserves or always replaces a run.

Journal replay and amendment may avoid re-execution when the engine guarantees
it; do not promise free replay or automatic cache inheritance. Record actual
attempts/usage, including retries, amendments and any linked replacement run.

## Step 5 — remediate only after the gates

- Publish the verdict first. Apply only authorized fixes after the companion's
  independent plan/spec review passes; review-only campaigns end at reporting.
- Re-freeze affected source and base per fix. Keep remediation revisions and
  findings linked to the audit evidence rather than rewriting its history.
- Stop a lane when another session's dirty work overlaps. Preserve its files
  and index; resolve ownership or use an isolated worktree. Never reset or
  stash another session's work to make a commit convenient.
- For behavior fixes, demonstrate a failing regression before the fix and run
  the touched area's repository-native checks. For safety-guard tests, prove
  the negative case by disabling the guard in an isolated test copy/worktree,
  then restore it and verify green before acceptance.
- Docs/comment-only fixes use the repository's actual readback, link, hygiene
  and diff checks. Do not invent `Verify-Docs`, hooks or tests the repo lacks.
- Require independent verification and controller acceptance after fixes.
  Commit only when authorized, with explicit pathspecs and inspected staged
  diffs; preserve unrelated tracked, staged and untracked work.

## Step 6 — account for complete and stopped work

Update accounting at tier boundaries, stops/recovery and completion. Use
measured engine/native counters when available; label estimates and unavailable
values explicitly. Never report missing usage as zero. Record counter coverage
and timestamp; cached input/reasoning are subsets when the provider includes
them in input/output totals, not extra tokens.

Persist planned actor-to-tier mappings before launch and attach actual
actor/run IDs when assigned. Tier-prefixed names such as `b1-`, `b2-conf-`
and `lens-` are useful identifiers, not the only carrier.
Use documented per-actor counters or linked per-tier runs if available.
Otherwise report measured campaign totals with per-tier usage unavailable.
Check `GetWorkflowRun.subagentsTruncated` before summing actor totals: the
inspected engine returns at most 64 actors. A truncated list yields partial
tier attribution; retain `usage.spentTokens` as the complete reported run total
or use separate linked run totals for exact tier attribution. Record the
counter's documented scope without inventing input/output splits.
Reconcile attempts and unique finding counts, including unresolved/refuted/
duplicate outcomes; do not double-count cumulative totals across resumes.
Close `STATE.md` with elapsed time, usage source, coverage, confirmation
counts, changed surfaces, verification, remaining risk and the next gate.
