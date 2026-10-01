---
name: grand-sweep
description: "Operational recipe for multi-tier code audit campaigns run as ZCode dynamic workflows (crew audits, grand sweeps). Use when planning or launching a grand audit campaign, designing tier fan-out, writing or amending the campaign workflow script, recovering a crashed or stopped campaign run, or closing out campaign accounting. Not for a single diff/PR review (review), the audit gate discipline itself (audit-gated-subagents), or ordinary non-audit dynamic-workflow runs."
argument-hint: "<what to audit> [--base <ref>] [--slug <name>]"
user-invocable: true
---

# Grand Sweep

The mechanics for running a multi-agent audit campaign as ZCode dynamic
workflows. Gates, lane ownership, and the chief-operator discipline live in
`audit-gated-subagents`; this skill owns the workflow-engine specifics the
campaigns learned the hard way. Run both together: this recipe executes inside
that discipline. Load the `dynamic-workflows` skill before writing or revising
the script — it carries the engine facade and authoring rules.

Run order: probe → freeze → tiers → launch → recover (if it stops) → verdict
→ remediate → account.

## Step 0 — world-read probe (unconditional)

Make the script's first step probe the workflow world with one trivial
`files.glob` pattern before any fan-out. On rejection: an empty index or
universal pattern-mismatch is a workspace property (e.g. an outer repo
tracking zero files), not a fluke. Build the file manifest with Bash, embed it
as a literal in the workflow script, and route workers to exact-path reads —
`git.*` and exact-path reads keep working when globs do not. Never assume
world reads; never spend worker tokens discovering the manifest.

## Step 1 — freeze the campaign skeleton

Freeze before authoring or launching anything, into
`<repo-container>/.audit/crew/<slug>-<date>/`:

- `STATE.md` (schema `crew-audit/v1`): root, base ref, branch, dirty state,
  authority files, scope rules, frozen scope summary.
- `manifest.json` / `manifest.txt`: the frozen in-scope file list.

If a later tier adds scope items the earlier tiers did not see, the
remediation round re-scopes around them — it does not silently absorb them.

Outputs appear as tiers complete: `FINDINGS.md`, `MAP.md`, `REPORT.md`; the
verdict publishes to the repo review surface (`docs/reviews/audit-*.md`).

## Step 2 — design the tiers

- Breadth tier on the cheapest capable model, one reviewer per file, findings
  with file:line evidence.
- Independent confirmer agents only for medium and high findings. Lows are
  batched into per-file appendices without confirmers.
- Session-model lenses are scoped to contract seams and cross-domain
  semantics; they do not hunt highs. Right-size every tier — the cost axis is
  independent of design robustness.
- Vendor/generated paths are counted, not deep-inspected.
- Model tiering is owner-gated: keep subagents on the session model unless the
  owner explicitly orders a two-tier spend.

## Step 3 — launch

Submit with `CreateWorkflow` (inline `script`, or `path` pointing at the
saved draft). The user confirms the run; it starts in the background and the
completion notification carries the final result — do not poll the run list
while waiting. Name the run `<slug>-<date>` so the run journal lines up with
the `.audit` receipts.

## Step 4 — recovery (crashed or stopped)

A crashed or stopped run is resumed (`ResumeWorkflowRun`) or amended
(`AmendWorkflow`), never rebuilt from scratch — journal replay of finished
steps is free. Amend when the script itself is wrong: the revision imports the
finished work as cache, so only what changed re-pays. On a provider stop,
resolve the cause with the user, then resume the same run ID. An interrupted
run (its owning process exited) is normally continued, not restarted. Do not
treat an interrupted campaign as authorization to restart it changed.

## Step 5 — remediation rules (after the verdict)

- Fixes are new changes against the published verdict, never edits inside the
  audit. Remediation execution is blocked until the verdict issues.
- Re-freeze the base per fix — the branch may move mid-round.
- Every fix lands failing-test-first, with the repo-native test suite of the
  touched areas green in the same commit set.
- Mutation gate: any safety-relevant test created or repaired gets a
  temporary-guard-revert red check before commit. No exceptions.
- Explicit-pathspec commits only. A concurrent session's in-flight dirty
  files are preserved, never dragged in — save-patch → reset → edit → commit
  → re-apply when the file overlaps.
- Docs changes carry their gates in the same commit (Verify-Docs, docs-hygiene
  hook, enforcement pins).

## Step 6 — accounting

At completion, record per-tier token spend and confirmed/refuted counts into
the campaign STATE.md, so the next "evaluate the run" costs one file read.
Per-tier attribution needs one of: each tier as its own run (cleanest), or
tier-prefixed subagent names (`b1-`, `b2-conf-`, `lens-`) summed from the
per-actor token totals `GetWorkflowRun` reports. Names are the only tier
carrier after launch — the prefix is not cosmetic.
