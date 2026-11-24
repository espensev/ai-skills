# Campaign lifecycle (grand sweep)

Full lifecycle for a kit-based grand sweep. `SKILL.md` carries the method;
this file expands each phase with its owner, artifacts, and failure handling.
Every artifact lives inside `<campaignDir>` unless named otherwise; the
campaign never writes outside its directory, and the repository under audit
is read-only until the remediation gates pass.

## Phase 1 — prep (owner: controller session)

1. Read authority (`audit-gated-subagents`), confirm review-only limits,
   establish machine identity if any machine-sensitive action will occur.
2. Create `<repo-container>/.audit/crew/<slug>-<date>-<run-key>/` and write
   `STATE.md` from `templates/STATE.md` (label `crew-audit/v1`), filling the
   identity/authority and source field groups. Record plainly that `.audit/`
   and `docs/reviews/` are untracked in most consumer roots.
3. Write `scope.json` from `templates/scope.example.json`: lanes, prefixes,
   unit caps, exclusions, named subsets. Every subset path must be a file
   that a lane includes — `freeze` refuses a subset path that is not a
   manifested file id. A subset is never re-swept: one breadth pass covers
   its files (`crew.py subset <name>` shows the mapping), and its deep
   review is a lens set.
4. Author the lens sets as `build/lenses-<set>.json`, one file per set:
   `{set, campaign, lenses:[{name, title, brief, inputs:[repo-relative
   paths]}]}`. `name` must match `^[a-z0-9]+(-[a-z0-9]+)*$`, at most 28
   characters, unique in the file — it becomes the agent name `lens-<name>`
   and the verdict file name. `crew.py lenses <set>` shape-validates and
   fails closed on a bad file. Declare the sets you will run in `scope.json`
   (`lensSets`, optional list, e.g. `["shell", "cmd-surface"]`): `freeze`
   validates each named set exists and passes shape validation and records
   `lensSets` in the manifest. Completeness rule: when declared,
   `lensesComplete` requires every declared set on disk with a valid verdict
   for every lens; when not declared the campaign is breadth-only by explicit
   choice (`lensSetsDeclared: false`, `lensesComplete` stays false with a
   note). Lens candidates carry source `lens:<set>/<name>`.
5. Optionally write `build/seeded.json` to seed controller-raised candidates
   instead of re-reviewing them (verification-gate triage, a previous
   review's open questions):
   `{campaign, candidates:[{severity, where, what, evidence, source}]}`.
   They join the confirmation tier with source `seed:<source>`; `freeze`
   validates the file when present and records only the count.
6. Run `python -I crew.py <campaignDir> freeze --scope scope.json --kit
   <path/to/this/package>`. It verifies HEAD == `scope.commit` and a clean
   `git status`, assigns every tracked file, packs units, snapshots the kit
   into `build/kit/` preserving the package layout
   (`build/kit/scripts/crew.py`, `build/kit/workflows/*.dwf.ts`), and writes
   `manifest.json` and `units.json`
   (deterministic — no timestamps, so two freezes of the same tree and kit
   are byte-identical) plus `build/freeze-receipt.json`
   (`frozenAtUtc`, `scopeSha256`, kit package dir/commit/per-file hashes,
   manifest and units digests).
7. Run the independent plan/spec review gate before launch
   (`audit-gated-subagents`).

## Phase 2 — launch (owner: controller session)

1. Record in `STATE.md` (Execution group) at launch time: the launching
   session, its cwd, and the journal location, and maintain
   `build/runs.json` — one entry per launch: `{stage, lane|null, set|null,
   runId, model, launchedAtUtc, state}` with `state` one of `running`,
   `completed`, `stopped`, `errored`, `orphaned`, `superseded`. This file is
   what `close` (item 5) and the tender read. Launch from the repository
   root, never from the campaign directory — run listing and journals key on
   the launching session's cwd (engine-traps #1).
2. Launch each driver from the snapshot paths —
   `build/kit/workflows/breadth.dwf.ts`, `build/kit/workflows/lenses.dwf.ts`,
   `build/kit/workflows/confirm.dwf.ts` — via `CreateWorkflow` with
   `crewPy` set to `build/kit/scripts/crew.py` (the snapshot keeps the
   package layout) and the specified args (`breadth`: `campaign`, `crewPy`,
   `lane`, `pendingOnly`, `limit`, `focus`; `lenses`: `campaign`, `crewPy`,
   `set`, `limit`; `confirm`: `campaign`, `crewPy`, `limit`, `minSeverity`),
   honoring the user confirmation flow. Provider quota and rate windows pace
   the flash tiers; expect multi-window spans and record the burn cadence.
   Measure throughput after the first 30 minutes: when runs report
   `rate_limited` and the stage is crawling, stop them on purpose (record it
   in `build/runs.json` and `STATE.md`) and continue with native agent lanes
   that write the same verdict formats, then aggregate with the same
   `crew.py` commands — native lanes were about ten times faster than
   slot-throttled workflow runs (engine-traps #15) and run on the session
   model, so record that for accounting.
3. The workflow probes before fan-out: file identity + sha256, `probe-ok`
   staging round-trip, and the ask-content gate. Probes carry no resume
   check — every launch performs the real read, hash, write and read-back.
   A probe failure is a stop-and-report condition.
4. A frozen campaign not launched within 7 days is retired (Phase 5) —
   a stale freeze no longer matches a moving repository.

## Phase 3 — tend (owner: any session with the run ids)

- A run with no settled step for 30 minutes is a stop-and-report condition.
  Check the run by id (`GetWorkflowRun`); list tools can miss runs across
  cwd drift. Reflect each run's real state in `build/runs.json` — a dead
  run with no journal is `orphaned`, not `stopped`.
- Rate-window stops (`stopped`/`provider`) are pacing, not failure: resume
  after the window rolls, or replace with a fresh launch that adopts on-disk
  verdicts (`pendingOnly` defaults to true for exactly this).
- Diagnose before resuming. Prefer fresh `CreateWorkflow` over
  `AmendWorkflow` when underlying files changed (engine-traps #5). Never
  resume a superseded predecessor; never repair staging files of running
  nodes.
- Attempt accounting: a reviewer that finds an existing failed verdict for
  its record increments `attempts` (default 1 when absent) in the file it
  writes. A verdict file with no `unitId` counts as failed
  (`unitId-missing`); malformed or failed verdicts accumulate attempts in a
  sidecar `<unitId>.attempts` file, so garbage still reaches terminal-failed
  at 3. A record whose latest failed verdict has `attempts >= 3` is
  `terminal-failed`: excluded by `--pending`, reported separately by
  `status`, listed by `close`, and never re-dispatched — escalate instead.
- Cross-session reality: another session's runs cannot be stopped or amended
  from this one. If the launching session is gone, adopt via fresh launch
  over on-disk verdicts.
- Runs and automations advance only while the app is open: in the first live
  use the owning app process exited for about six hours and all seven runs
  came back `stopped` with `stop_reason="interrupted"` while the
  automation's run count stayed 0 (engine-traps #17). Resuming the
  interrupted runs under their original ids worked — finished steps
  replayed, completed units stayed completed.

## Phase 4 — verdict (owner: controller session)

1. Aggregate: `agg` per lane (breadth coverage), `lensagg` per set,
   `candidates` (de-duplicated, content-addressed ids), `confirmagg`.
2. Re-hash inputs: `check all` must be clean against the frozen manifest.
3. Run the confirm tier on the session model over medium/high candidates
   (`confirm.dwf.ts`) — only after `breadthComplete` and `lensesComplete`
   are both true: the candidate set is not final before that, and
   `confirmComplete` is false until both hold, then true only when every
   medium/high candidate has a confirm verdict. Seeded candidates from
   `build/seeded.json` join the tier with source `seed:<source>`.
   `crew.py confirmagg` counts outcomes. Lens and confirm asks name the
   frozen root and commit and require reading under that root; confirm asks
   require quoted lines and an explicit `counterevidence` entry. Hand
   confirmers an existing verification-gate log from the same tree as
   primary evidence where one exists — in the first live use it settled
   several claims, and severity calibrated both ways: expect downgrades and
   refutations, not blanket confirmation.
4. Publish `FINDINGS.md`, `MAP.md`, `REPORT.md`, `build/accounting.json`
   and `build/verdict.json`, then run
   `python -I crew.py <campaignDir> close` — it enforces the seven-item
   closure checklist (below) and exits non-zero while anything is open.
5. Publish the verdict doc at `docs/reviews/audit-*.md` or the tracked
   location chosen in prep; mirror small receipt files to the pCloud backup
   root when the consumer root is untracked. Mark partial results explicitly.

Closure checklist (`close` enforces; every item reported pass/fail):

1. No lane has a pending or non-terminal failed unit; terminal failures are
   listed with reasons.
2. Every lens in every lens set has a valid verdict.
3. No medium/high candidate lacks a confirm verdict.
4. `check all` is clean — otherwise the verdict must be PARTIAL, which is
   itself a close failure for PASS/FAIL.
5. No entry of `build/runs.json` is `running`.
6. `build/accounting.json` exists with a `usageSource` and a `spentTokens`
   value or an explicit `unavailable: true` per run.
7. `build/verdict.json` exists with `verdict` in `PASS|FAIL|PARTIAL` and a
   `verdictDoc` path that exists.

**Valid completed verdict** — the single normative definition for every
writer (workflow subagents and native tender lanes alike): the file parses as
JSON, `unitId` matches, and `status` is `completed`. Any other existing file
is a failed attempt — including a file with no `unitId` (recorded as
`unitId-missing`). Failed attempts accumulate in the verdict's `attempts`
field or its `<unitId>.attempts` sidecar.

Candidate identity = normalized `where` path + line + the first 120
characters of normalized `what`; `path:line`, `path:line:col`, `./path:line`
and `path(line)` forms all normalize to the same identity, and lens sources
are `lens:<set>/<name>`.

## Phase 5 — close or retire

- **Close**: verdict published, gates passed, `STATE.md` accounting closed
  with elapsed time, usage source, coverage, confirmation counts, changed
  surfaces, verification, remaining risk and next gate.
- **Retire**: a frozen-but-unlaunched campaign older than 7 days, or an
  abandoned campaign, is marked retired in `STATE.md` with reason and date;
  superseded freezes live under `superseded/` (never deleted). Retired
  campaign directories are preserved; findings worth keeping are re-anchored
  to a surviving location before any cleanup.

## The tender contract (recurring automation)

`templates/tender-prompt.md` is a complete prompt for a recurring ZCode
automation ("sweep tender"). Its contract:

1. It reads `python -I crew.py <campaignDir> status` (computed from staging
   directly) and `build/runs.json` for each campaign explicitly listed in
   its configuration — it never touches a campaign not listed.
2. For `stopped` runs it resumes them (or launches replacements that adopt
   on-disk verdicts).
3. For pending records it runs bounded native agent-lane waves writing the
   section-4 verdict formats; the "valid completed verdict" definition above
   is the single normative reference for what a wave writes, and a wave
   never re-dispatches terminal-failed records. Its confirmation stage waits
   until `breadthComplete` and `lensesComplete` are both true before
   dispatching confirmations.
4. It aggregates with the kit commands and calls `CronPauseSelf` once every
   listed campaign reports `complete`.
5. It never creates another automation, never mutates the repository under
   audit, and never runs machine-sensitive commands. `CreateWorkflow`
   requires user confirmation, so an unattended fire cannot launch dynamic
   workflows — that is why the tender uses native lanes.
6. Before any wave it reads `<campaign>/build/controller-active.json` and
   stands down (log only) while its `heartbeatUtc` is fresher than 30
   minutes: an automation created in a session fires inside that same
   session, so the tender can fire inside the controller's own session while
   controller-issued lanes are in flight, and it cannot see those lanes
   (engine-traps #16). The controller refreshes the heartbeat while it holds
   lanes.
7. Runs and automations advance only while the app is open (engine-traps
   #17); a tender fire during an app-closed period does nothing, and
   interrupted runs resume under their original ids once the app is open
   again.
