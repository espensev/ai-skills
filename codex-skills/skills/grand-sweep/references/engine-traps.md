# ZCode dynamic-workflow engine traps (grand sweep)

Observed engine behaviours that broke or cost real grand-sweep campaigns.
Each entry is dated and cited to campaign evidence; where the installed
`dynamic-workflows` documentation is silent, the entry says "not documented"
— treat the observation as the current best evidence and re-verify on engine
updates, not as a guaranteed contract.

1. **Journals and run listing are keyed to the launching session's working
   directory.** Four breadth runs launched from a campaign directory were
   invisible from the repository root (tri-root-ultramax, 2026-11-23;
   `D:\DevHome\.audit\crew\tri-root-ultramax-20261123-3f9d\STATE.md`
   incident log). Rule: launch from the repository root and record the
   launching session, its cwd, the run ids and the journal location in
   `STATE.md` at launch time.

2. **`AmendWorkflow` carries no args.** Four runs errored the same day
   (2026-11-23, tri-root-ultramax incident log) when a lane passed runtime
   args through amend; relaunch used fresh `CreateWorkflow` per lane.

3. **An access-only probe can pass while every ask is broken.** The
   2026-11-23 probe verified file access and its round-trip sub-check passed,
   but a tuple/object mismatch between crew output and the script meant every
   ask interpolated `undefined` (same incident log; ~10 minutes of garbage
   fan-out). Rule: probe must include the ask-content gate — the gate checks
   the record's dynamic fields (id, root, dir, every file/field tuple string)
   and the `focus`/brief text with word boundaries (`\bundefined\b`,
   `\bnull\b`, `\[object`, `\bNaN\b`); static rubric wording is exempt, so a
   legitimate focus containing "possibly-null" passes.

4. **`files.glob` is unreliable in this environment** (DriverError on every
   pattern, 2026-10-02/03; repeated cost in later campaigns). Freeze
   manifests as literals and read plan/verdict state via `world.run` helpers. This is why
   `crew.py freeze` writes the manifest and unit plan to disk, and the drivers load them
   through `world.run` instead of discovering files with a glob.

5. **Amend cache can replay a stale `world` read.** A cached `files.read`
   with an unchanged path key returned the OLD file content even after a live
   `world.run` had executed in the predecessor (ps-env-sweep, 2026-11-18,
   memory note `zcode-dynamic-workflow-authoring`). Prefer a fresh
   `CreateWorkflow` with `--pending` (zero finished units = free) over
   trusting amendment invalidation.

6. **Provider windows stall flash tiers for hours.** Rate-limit code 1308
   ("Usage limit reached for 5 hour") stops runs as `stopped`/`provider`,
   not catchable in-script; runs resume free across the window by journal
   replay (tri-root 2026-11-11: core lane 66/1,290 units after 4h with 6/16
   workers rate-limited; runs stalled rate-limited for hours on 2026-11-21/23
   campaigns). Plan multi-window spans and record burn cadence.

7. **Another session's runs cannot be stopped or amended from here.**
   Orphaned breadth runs from the dead 2026-11-11 campaign were inert —
   `TaskStop` cannot reach other sessions' runs (tri-root memory note,
   2026-11-22). Hand off run ids and launching session in `STATE.md`.

8. **`CreateWorkflow` requires a user confirmation**, so an unattended
   automation fire cannot be assumed to launch a workflow. Automations
   should resume stopped runs or run bounded native agent-lane waves over
   pending records; see `lifecycle.md` tender contract. (Not documented in
   the installed engine docs; observed in campaign launches, 2026-11.)

9. **Journals can vanish entirely, and receipts can be wiped with the
   directory.** The 2026-11-21 `.audit/` + `.zcode/` cleanup killed the
   frozen manifest, verdicts, drafts and saved workflows of a live campaign;
   breadth runs became unresumable (tri-root memory note, 2026-11-22). The
   kit snapshot, on-disk verdicts, and the resume-check paragraph in every
   ask exist so a fresh launch re-buys only unfinished work.

10. **A `name:` key in the `/* zcode-workflow */` metadata block is rejected
    on submission** ("Unrecognized key(s) … 'name'", 2026-11-11, cost all
    five launches one round). Keys are `description` and `args` only; the run
    label comes from `CreateWorkflow`'s `name` parameter.

11. **Wide fan-out starves later stages under per-item chaining** — with 274
    batches, all reviewer asks enqueue FIFO before any confirmer and the
    confirm lane got zero work in 21h (2026-10). Make confirmation its own
    wave over on-disk verdicts after the reviewer join; the kit's
    `confirm.dwf.ts` exists for exactly this.

12. **Flash-written verdict JSON frequently contains invalid escapes**
    (~1/15 files: bare backslashes in Windows paths, 2026-10). File-writing
    asks carry an explicit "escape all backslashes when writing JSON" line,
    and every disk reader tolerates unparseable files so one bad verdict
    drops only its own findings.

13. **Never hot-repair a staging verdict whose owning actor is still
    running** — a live reviewer rewrites its own file on read-back and the
    controller repair was observed vanishing mid-edit (2026-10). Sweep or
    repair only over settled nodes.

14. **Never build script scope from a live glob in a shared tree** —
    deriving targets mid-run breaks journal replay determinism when
    concurrent sessions add files ("inputHash differs", 2026-09-29). Freeze
    at submit time; the pre-flight guards (HEAD + manifest digest + dirty
    set) aborted three poisoned launches at ~zero cost on 2026-11-18.
