# Campaign record — crew-audit/v1

Campaign ID: `<slug>-<date>-<run-key>`
Started: <UTC date>. Controller session: <session id / description>.
Status: PREP | LAUNCHED | TENDING | VERDICT | CLOSED | RETIRED

> Note: `.audit/` and `docs/reviews/` are untracked in most consumer roots.
> Publish the verdict to a tracked location or mirror the small receipt
> files to the pCloud backup root; a directory cleanup must not kill the
> campaign record (2026-11-21 wipe).

## Identity and authority

- Root: `<resolved checkout root>`. Output path: `<resolved campaign dir>`
  (validated unique, under the approved root).
- Authority files: <paths + hashes>.
- Authorization: <owner go, dates>. Review-only limits: <state>.

## Source (frozen at prep)

- Requested base: <ref or "current HEAD">. Resolved commit: `<full sha>`.
- Branch/HEAD: <branch>. Dirty state at freeze: <empty | deferred list>.
- Per-file identity: `manifest.json` files[] (sha256, bytes, kind),
  deterministic (no timestamps). Frozen-at, scope digest and kit snapshot
  hashes: `build/freeze-receipt.json`. Superseded freezes: `superseded/`.

## Scope

- Revision: <n>. Manifest path/digest: `manifest.json` `<sha256>`.
- Lanes: <lane name -> prefix, include prefixes, unit caps>.
- Exclusions: counted and listed in `manifest.json` exclusions[] with reasons.
- Subsets: <name -> description> (informational only — one breadth pass
  covers them; `crew.py subset <name>` maps files to units/statuses).
- Lens sets: `build/lenses-<set>.json` — `{set, campaign,
  lenses:[{name, title, brief, inputs}]}`, `name` `^[a-z0-9]+(-[a-z0-9]+)*$`,
  ≤28 chars, unique per file.
- Read-only dependency paths: <list>.

## Execution

- Kit: `build/kit/` snapshot (per-file sha256 in the `build/freeze-receipt.json`
  kit block; package commit `<sha or "untracked">`).
- Scripts/args: `build/kit/workflows/breadth.dwf.ts` (campaign, crewPy, lane,
  pendingOnly, limit, focus), `lenses.dwf.ts` (campaign, crewPy, set, limit),
  `confirm.dwf.ts` (campaign, crewPy, limit, minSeverity).
- Launch-time record (fill at launch; keep `build/runs.json` in step):
  - `build/runs.json`: `[{stage, lane|null, set|null, runId, model,
    launchedAtUtc, state ∈ running|completed|stopped|errored|orphaned|superseded}]`
    — the source `close` (item 5) and the sweep tender read.
  - Run ids: <breadth-<lane> -> dwfrun-…; lenses-<set> -> dwfrun-…; confirm -> dwfrun-…>
  - Launching session: <session id>
  - Launching session cwd: <absolute path> (launch from the repository root,
    never the campaign directory — run listing and journals key on cwd)
  - Journal location: <path to the CLI workflow-run journal / sqlite db>
- Actor-to-tier mapping and model per run: <fill>.
- The `builder`/specialist agent types may be unavailable (provider removed);
  verify the model id exists before launch and probe cheaply.

## Limits

- Concurrency: <engine default | explicit>. Flash tiers are paced by
  provider quota and rate windows; expect multi-window (5h) spans and record
  burn cadence below.
- Unit caps: from `scope.json` (`maxFiles`, `maxBytes`, `soloAtBytes`).
- Token/time ceilings: advisory unless a verified external stopper exists;
  `TaskStop` cannot reach another session's run.

## Results

- (fill: per-run status, coverage receipts under `build/`, verdicts under
  `staging/` — attempts tracked per verdict, `attempts >= 3` failed is
  terminal-failed and never re-dispatched; verdict doc at
  `docs/reviews/audit-*.md` or tracked location; machine-readable verdict at
  `build/verdict.json` with `verdict` PASS|FAIL|PARTIAL and `verdictDoc`.)

## Accounting

- `build/accounting.json`: `{usageSource, per-run spentTokens | unavailable: true}`
  — required by `close` item 6.
- Counter source: <GetWorkflowRun usage.spentTokens per run; check
  subagentsTruncated before per-actor sums>. Timestamp: <UTC>.
- Per-run usage, retries/resumes, failures: (fill).
- Burn cadence: (fill — tokens per window, observed rate-limit stops).

## Prep / incident log

- (dated one-line entries: freeze, probes, launches, stops, recoveries,
  incidents with run ids.)
