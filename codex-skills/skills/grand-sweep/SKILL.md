---
name: grand-sweep
description: "Operational recipe for multi-tier code audit campaigns run as ZCode dynamic workflows (crew audits, grand sweeps), with a versioned campaign kit: crew.py freeze/lanes/units/agg, generic workflow drivers, and a tender prompt for unattended resumption. Use when planning or launching a grand audit campaign, freezing scope, resuming a stopped run, running a recurring sweep automation, or closing out campaign accounting. Not for a single diff/PR review (review), the audit gate discipline itself (audit-gated-subagents), or ordinary non-audit dynamic-workflow runs."
argument-hint: "<what to audit> [--base <ref>] [--slug <name>]"
user-invocable: true
---

# Grand Sweep

Run multi-agent audit campaigns through ZCode dynamic workflows using the
campaign kit shipped in this skill directory (`scripts/crew.py`,
`workflows/*.dwf.ts`, `templates/`). `audit-gated-subagents` owns authority,
lane ownership, independent plan review, and implementation/verification
gates — use both together. Load `dynamic-workflows` for engine signatures
before touching workflow scripts. `usage-stats` owns token accounting rules;
this skill records and reconciles, it does not redefine counters.

Use the kit first: freeze scope with `crew.py freeze`, probe, then launch the
generic drivers from the kit snapshot the freeze wrote into the campaign.
Re-authoring a bespoke manifest builder and ~1,000-line workflow script per
campaign is the fallback, used only when the kit cannot express the campaign
shape — record why in `STATE.md` when you fall back. Campaigns that
re-authored everything have lost receipts, saved workflows and journals
whenever `.audit/` was cleaned (2026-11-21 wiped a live campaign); the kit is
versioned here and snapshotted per campaign precisely so that cannot recur.

Read `references/lifecycle.md` for the full prep → launch → tend → verdict →
close/retire contract and the tender automation rules; while holding native
lanes, the controller keeps `<campaign>/build/controller-active.json`'s
`heartbeatUtc` fresh so the tender stands down. Read
`references/engine-traps.md` before authoring or amending any workflow
script; every entry there is an observed failure that cost a real campaign
time or tokens.

Run order: prep → freeze → probe → launch → tend → verdict → authorized
remediation → account. Recovery preserves the campaign; never restart it
silently.

## Step 0 — prep: authority and campaign directory

Read repository authority, current dirty/worktree state, and the companion
gate skill. Establish the selected root and any required machine identity
before machine-sensitive actions. Keep inventory read-only; a published
verdict alone does not authorize fixes.

Create a unique `<repo-container>/.audit/crew/<slug>-<date>-<run-key>/` before
freeze. Validate the slug and resolved output path against the approved root;
do not overwrite an existing campaign. Write `STATE.md` from
`templates/STATE.md` (label `crew-audit/v1`) and keep the field groups of its
table current as the campaign progresses. Say plainly in the receipt that
`.audit/` and `docs/reviews/` are untracked in most consumer roots: publish
the verdict to a tracked location, or mirror the receipt's small files to the
pCloud backup root, so a directory cleanup cannot kill the campaign record
again.

## Step 1 — freeze with the kit

Write a `scope.json` (see `templates/scope.example.json`): campaign id, clean
checkout root, full commit SHA, lanes with prefixes and unit caps, optional
exclusion globs and named subsets. `freeze` fails closed: it refuses a HEAD
mismatch or a dirty `git status`, refuses overlapping lane includes, refuses
tracked files that are neither assigned nor excluded, and refuses duplicate
lane prefixes.

Run `python -I crew.py <campaignDir> freeze --scope scope.json --kit
<path/to/this/package>`. It writes `manifest.json` (authoritative
file/identity list) and `units.json` — deterministic, no timestamps — plus
`build/freeze-receipt.json` with the timestamps, scope digest and per-file
kit snapshot hashes, and snapshots `scripts/` and `workflows/` into
`<campaignDir>/build/kit/` preserving the package layout
(`build/kit/scripts/crew.py`, `build/kit/workflows/*.dwf.ts`). Workflows are
always launched from that snapshot
— never run the package in place, and never let a campaign depend on the
skill checkout staying put. A frozen campaign not launched within 7 days is
retired in `STATE.md`; a re-freeze after scope change uses `--replace`, which
moves the previous manifest into `superseded/<utc-stamp>/` (never deletes)
and increments `revision`.

## Step 1b — design the campaign inside the kit's shapes

- Assign every in-scope path to exactly one breadth unit (`freeze` packs
  units within the lane's `maxFiles`/`maxBytes`; a file at or above
  `soloAtBytes` becomes its own `oversize` unit). Lens sets are authored at
  prep as `build/lenses-<set>.json`:
  `{set, campaign, lenses:[{name, title, brief, inputs:[repo-relative paths]}]}`
  — `name` matches `^[a-z0-9]+(-[a-z0-9]+)*$`, at most 28 characters, unique
  in the file, because it becomes the agent name `lens-<name>` and the
  verdict file name. A subset is never re-swept: one breadth pass covers its
  files, and its deep review is a lens set; `crew.py subset <name>` maps
  subset files to their units and statuses. Declare the lens sets you will
  run in `scope.json` (`"lensSets": ["shell", "cmd-surface"]`): when
  declared, `lensesComplete` requires every declared set on disk with a valid
  verdict for every lens; when not declared the campaign is breadth-only by
  explicit choice (`lensSetsDeclared: false`, `lensesComplete` stays false
  with a note).
- Seed controller-raised candidates via `build/seeded.json` instead of
  re-reviewing them: `{campaign, candidates:[{severity, where, what,
  evidence, source}]}` (verification-gate triage, a previous review's open
  questions). They join the confirmation tier with source `seed:<source>`;
  `freeze` validates the file when present and records only the count.
- Keep all review tiers on the session model unless the current request or
  applicable workspace policy authorizes model changes. Within that
  authority, use the cheapest capable model for mechanical breadth checks,
  the standard tier for lenses, and the session model for verdicts and
  independent confirmation of medium/high candidates. ZCode selects one
  run-wide `subagent_model`; when using different models, create separate
  linked runs over the same frozen receipt and record each run's model.
- Breadth asks carry the audit rubric, the lane focus, `path:line` citations
  with quoted evidence, sha256 verification with `failed`/`input-changed` on
  mismatch, and no style opinions. Lens candidates may raise any severity
  supported by evidence. Confirm medium/high candidates independently against
  pinned source and counterevidence — hand confirmers an existing
  verification-gate log as primary evidence and expect downgrades and
  refutations; low candidates stay explicitly unconfirmed appendix items.
- Each finding keeps a stable content-addressed candidate id (`C-` plus the
  first 10 hex of the sha256 over the normalized identity: `where` path +
  line + the first 120 characters of normalized `what`; `path:line`,
  `path:line:col`, `./path:line` and `path(line)` forms all normalize to the
  same identity). Lens candidates carry source `lens:<set>/<name>`, so
  re-runs never renumber and confirm files stay attached. Severity, `path:line`,
  evidence, counterevidence and confirmer outcome (`confirmed`, `refuted`,
  `inconclusive`, `duplicate` — duplicates link to a canonical id) ride along;
  the kit de-duplicates on the normalized identity and lists every source
  that raised a candidate. Do not inflate counts with duplicate votes. Each
  workflow report states what is `notCovered`, including records left pending
  by `limit`.

## Step 2 — probe, then launch

ZCode engine reality: `files.glob` is unreliable here, so the drivers take
the frozen manifest as literals; `CreateWorkflow` requires a user
confirmation, so an unattended automation fire cannot be assumed to launch —
automations resume or use native agent lanes instead; `AmendWorkflow` carries
no args; `TaskStop` cannot reach another session's run. See
`references/engine-traps.md` for the dated evidence.

Before fan-out, the workflow's first steps probe: verify the first record's
file identity (read + sha256), round-trip a `probe-ok` marker through
staging, and pass the ask-content gate. The gate checks the record's dynamic
fields (id, root, dir, every file/field tuple string) and the `focus`/brief
text with word boundaries (`\bundefined\b`, `\bnull\b`, `\[object`,
`\bNaN\b`); the static rubric wording is exempt, so a legitimate focus
containing "possibly-null" passes. A probe that only checked access once
passed while every ask said `undefined`; the content gate is what catches
that. Probes carry no resume check — every launch performs the real read,
hash, write and read-back. Probe failure is a stop-and-report condition, not
a clean audit.

Launch each driver (`breadth.dwf.ts`, `lenses.dwf.ts`, `confirm.dwf.ts`) from
the snapshot paths `build/kit/workflows/<name>.dwf.ts`, passing
`build/kit/scripts/crew.py` as the `crewPy` argument (the snapshot keeps the
package layout), via verified `CreateWorkflow` inputs, honoring its
confirmation flow within existing authorization. Record in `STATE.md` at
launch time: the run id per entry of `build/runs.json` (`stage`, `lane|set`,
`runId`, `model`, `launchedAtUtc`, `state` — `running`, `completed`,
`stopped`, `errored`, `orphaned`, `superseded`), the launching session, the
launching session's working directory, and the journal location. Launch from
the repository root, never from the campaign directory — run listing is keyed
to the launching session's cwd, and four runs launched from a campaign
directory were invisible from the repo root on 2026-11-23. Provider quota and
rate windows pace the flash tiers; plan multi-window spans (a campaign can
lap several 5-hour windows) and record the burn cadence in `STATE.md`
accounting. Measure throughput after the first 30 minutes: if runs report
`rate_limited` and the stage is crawling, stop them on purpose (record it)
and continue with native lanes writing the same verdict formats.

## Step 3 — tend

A run with no settled step for 30 minutes is a stop-and-report condition:
check the run by id with `GetWorkflowRun` (list tools can miss runs across
cwd drift), diagnose, then either `ResumeWorkflowRun` after the cause is
resolved or a fresh launch that adopts on-disk verdicts. The drivers write
one verdict file per record as it lands, and every ask carries a resume
check: if the verdict file exists and parses, return it — do not redo the
work. That makes re-launch idempotent and bounds the cost of a journal
vanishing. Do not repair a staging verdict file whose owning actor node is
still running; sweep only settled nodes. Prefer a fresh `CreateWorkflow` over
`AmendWorkflow` when underlying files changed: amend cache can replay a stale
`world` read. A record whose latest failed verdict has `attempts >= 3` is
`terminal-failed`: excluded by `--pending`, reported by `status`, and a
stop-and-report condition — stop re-dispatching it and escalate. Failed
attempts accumulate even when the verdict file itself is garbage: a verdict
with no `unitId` counts as failed (`unitId-missing`), and malformed or failed
verdicts record attempts in a sidecar `<unitId>.attempts` file so garbage
still reaches terminal-failed at 3. Lens and confirm asks name the frozen
root and commit and require reading under that root; confirm asks require
quoted lines and an explicit `counterevidence` entry.

## Step 4 — verdict

Aggregate with the kit (`agg`, `lensagg`, `candidates`, `confirmagg`),
reconcile `check` output against the frozen manifest, and let `crew.py close`
enforce the closure checklist. The controller reads the evidence and owns the
verdict; worker completion or confirmer votes alone cannot approve it. A
complete review requires all in-scope units completed, reconciled input
identities, and no unresolved medium/high candidates — `close` fails while
anything is open. Publish `FINDINGS.md`, `MAP.md`, `REPORT.md`,
`build/verdict.json` and the verdict at `docs/reviews/audit-*.md` (or the
tracked location chosen in prep), marked explicitly partial when units failed
or were deferred. Budget stops and empty scope are not complete reviews.

## Step 5 — remediate only after the gates

- Publish the verdict first. Apply only authorized fixes after
  `audit-gated-subagents`' independent plan/spec review passes; review-only
  campaigns end at reporting.
- Re-freeze affected source per fix; keep remediation revisions linked to the
  audit evidence rather than rewriting its history.
- Stop a lane when another session's dirty work overlaps; never reset or
  stash another session's work to make a commit convenient.
- For behavior fixes, demonstrate a failing regression before the fix and run
  the touched area's repository-native checks. Require independent
  verification and controller acceptance after fixes. Commit only when
  authorized, with explicit pathspecs and inspected staged diffs.

## Step 6 — account

Update accounting at tier boundaries, stops/recovery and completion, per
`usage-stats`. Check `GetWorkflowRun.subagentsTruncated` before summing
per-actor totals (at most 64 actors returned); retain `usage.spentTokens` as
the complete run total. Cross-session limits are real: another session's runs
cannot be stopped or amended from here, so a campaign spanning sessions must
hand off the run ids, the launching session, and the journal location in
`STATE.md`. Write `build/accounting.json` (`usageSource`, `spentTokens` per
run or explicit `unavailable: true`) — `close` requires it. Never report
missing usage as zero. Close `STATE.md` with
elapsed time, usage source, coverage, confirmation counts, changed surfaces,
verification, remaining risk and the next gate.
