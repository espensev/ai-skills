# Deep Audit State and Report Contracts

Use repository-local state only when authorized. The default layout supports
multiple concurrent audits without collisions:

```text
.audit/deep-audit/<audit-slug>/
  STATE.md
  DISCOVERIES.md
  TRACES.md
  FINDINGS.md
  VERIFICATIONS.md
  MEASUREMENTS.md
  REJECTED.md
  COVERAGE.md
  REPORT.md
```

If the repository has an owning audit/report convention, use it instead and
record the chosen root in `STATE.md`. Keep generated profiler data outside Git
unless the user or repository convention explicitly requires it.

## State Header

Every state file begins with enough identity to prevent accidental cross-audit
reuse:

```text
Schema: deep-audit/v1
Audit slug:
Repository root:
Audited source/runtime boundary:
Baseline revision:
Current revision:
Branch/worktree:
Authority files read:
Dirty-state fingerprint:
Scope:
Exclusions:
Workload assumptions:
Environment:
Audit started:
Last updated:
Product-code writes: allowed | not allowed
Audit-state writes: allowed
Runtime measurements: allowed | plan-only | restricted
```

Repeat this complete block as the first nonblank content of `STATE.md` and every
sibling record file; it is not `STATE.md`-only. The file-specific templates below
start after this required block. Before handoff, verify that every persisted state
file begins with `Schema: deep-audit/v1`.

## `STATE.md`

```markdown
# Deep Audit State

## Current priority

- ID:
- Reason:
- Current mode:
- Exact next mode:

## Revision drift

- Baseline:
- Current:
- Relevant changed paths:
- Records requiring revalidation:

## Progress

- Runtime roots mapped:
- Open discoveries:
- Completed traces:
- Ranked findings:
- Completed verifications:
- Open measurements:
- Rejected hypotheses:
- Known coverage gaps:

## Last handoff

- Mode and target:
- Scope completed:
- Evidence inspected:
- Remaining uncertainty:
- Highest-priority next item:
- Exact next mode:
```

## `DISCOVERIES.md`

```markdown
# Discovery Queue

| Priority | ID | Categories | Location | Suspected multiplier | Depth | Status | Next mode |
|---|---|---|---|---|---|---|---|

## Records

### D-### - Short title

- Location:
- Runtime entry or suspected path:
- FACT evidence:
- Cost/amplification model:
- Safeguards/counter-evidence:
- Current depth:
- Unknowns:
- Required next inspection:
- Recommended next mode:
```

## `TRACES.md`

```markdown
# Execution Traces

## T-### - Target

| Step | Path and symbol | Trigger/condition | Frequency/cardinality | Context | Work/side effect | Multiplier | Evidence |
|---|---|---|---|---|---|---|---|

- Facts:
- Inferences:
- Hypotheses:
- Dominant cost:
- Amplification model:
- Safeguards/counter-evidence:
- Semantic/lifecycle constraints:
- Depth reached:
- Promotion decision:
```

## `FINDINGS.md`

Keep ranked and historical records separate. A rejected item remains in history
and moves to `REJECTED.md`.

```markdown
# Findings

## Ranked summary

| Severity | ID | Status | Confidence | Depth | Claim | Verification | Next action |
|---|---|---|---|---|---|---|---|

## Records

### F-### - Short title

- Claim:
- Status:
- Source revision and evidence citations:
- Severity:
- Confidence:
- Depth:
- Exact location, established call path, and unresolved runtime edges:
- Trigger/reachability/frequency/cardinality:
- CPU/allocation/retention/I/O behavior:
- Concurrency/failure/cancellation/shutdown behavior:
- Existing safeguards and counter-evidence:
- Assumptions and missing evidence:
- Operational impact:
- Recommended targeted change:
- Semantic/lifecycle risks:
- Expected impact:
- Implementation scope:
- Validation, pass, and reject criteria:
- Required follow-up:
```

## `VERIFICATIONS.md`

```markdown
# Adversarial Verifications

| ID | Finding | Result | Revised severity | Revised confidence | Next action |
|---|---|---|---|---|---|

## V-### - F-### short title

- Source revision and original claim:
- Supporting evidence:
- Counter-evidence and limits:
- Additional paths/config/tests/measurements inspected:
- Alternative explanations:
- Semantic/lifecycle constraints checked:
- Result and rationale:
- Revised severity/confidence/recommendation:
- Remaining uncertainty and next mode:
```

## `MEASUREMENTS.md`

```markdown
# Measurements

| ID | Related item | Hypothesis | Status | Metrics | Thresholds | Result |
|---|---|---|---|---|---|---|

## M-### - Short title

- Hypothesis and missing static fact:
- Revision/environment/workload:
- Instrumentation and overhead:
- Metrics/units/baseline:
- Confirmation and rejection thresholds:
- Confounders/noise controls:
- Safety/authorization/cleanup:
- Commands/procedure and raw artifacts:
- Observed data with samples:
- Interpretation and next action:
```

## `REJECTED.md`

```markdown
# Rejected Hypotheses

## R-### - Short title

- Original discovery/finding:
- Original suspicion:
- Evidence inspected:
- Reason rejected or downgraded:
- Conditions under which it could become material:
- Do not rediscover unless:
```

## `COVERAGE.md`

```markdown
# Coverage Map

| Runtime area | Entry point | Evidence inspected | Depth | Status | Gap | Next mode |
|---|---|---|---|---|---|---|
```

Account for applicable startup; requests/messages; timers/schedulers;
workers/queues; callbacks/events; render/update loops; CPU; allocation/retained
memory; filesystem/network/database/process/device/logging/IPC; failure/retry;
cancellation/recovery; and shutdown.

## Handoff Block

End every persisted pass and user-facing update with the equivalent of:

```text
DEEP_AUDIT_HANDOFF

Audit slug and state root:
Repository revision and drift status:
Mode and target completed:
Scope completed:
Files/symbols/runtime roots inspected:
Discoveries opened/closed:
Traces completed:
Findings created/changed:
Verifications completed:
Measurements opened/completed:
Hypotheses rejected:
Coverage gaps:
Remaining uncertainty:
Highest-priority next item:
Exact next mode:
```

## Report Contract

Write `REPORT.md` only on explicit `report` or when the requested audit scope is
complete. Lead with findings rather than process narration.

```markdown
# Final Deep Audit Report

Use `Interim Deep Audit Report` when the completion gate is not met.

## Verdict and confidence

- Overall runtime assessment:
- Most consequential multiplier/bottleneck:
- Highest-risk scaling/lifecycle issue:
- Highest-value opportunity:
- Coverage and confidence:

## Ranked findings

List Confirmed, then Supported findings by operational impact. Preserve each
finding's severity, confidence, depth, linked verification record, evidence links,
targeted recommendation, semantic risk, and validation criteria.

## Runtime architecture and cost map

- startup and construction
- requests/messages/events/timers/workers/queues/render loops
- frequency and cardinality boundaries
- threads/tasks/schedulers/dispatchers/locks
- I/O and external dependency boundaries
- failure/retry/cancellation/recovery/shutdown

## Hot-path table

| Rank | Entry/trigger | Frequency/cardinality | Dominant work | Allocation/retention | I/O/blocking | Amplification | Evidence | Action |
|---|---|---|---|---|---|---|---|---|

## CPU, memory, and duplicate work

Separate algorithmic CPU, repeated work, allocation churn, retained growth,
large/burst allocation, ownership, and actual leaks.

## I/O, concurrency, and lifecycle

Assess I/O granularity/timeouts, scheduling, overlap, locks, queues,
backpressure, failure amplification, cancellation, restart, and shutdown.

## Measurement requirements

Tie every unmeasured claim to an `M-###` with workload, metrics, thresholds,
confounders, safety, and expected signal.

## Preserve list and rejected hypotheses

Record efficient or correctness-critical choices that should not be disturbed,
plus meaningful concerns that were disproved.

## Staged optimization plan

1. Safe, high-confidence targeted changes
2. Measurable structural improvements
3. Architecture changes only when justified by concrete operational gain

For each stage include expected impact, implementation/semantic risk, and
objective validation.

## Coverage and uncertainty

- scope inspected and excluded
- partially or uninspected runtime roots
- stale evidence or repository drift
- environment and measurement limitations
- exact next actions
```

## Completion Gate

A final report requires:

- current revision and source/runtime boundary revalidated
- frozen scope and major runtime roots represented in `COVERAGE.md`
- high-frequency and high-cardinality entry points identified
- applicable timers, workers, queues, handlers, callbacks, render/update loops,
  and external I/O boundaries inspected
- P0/P1 discoveries audited, measured, rejected, or explicitly blocked
- Critical/High findings adversarially verified
- important CPU, allocation, retained-memory, I/O, concurrency, failure, retry,
  cancellation, and shutdown paths inspected
- facts separated from inferences, hypotheses, and measurements
- rejected hypotheses and preserve-worthy implementation recorded
- remaining gaps explicit

If any condition is unmet, publish an interim report and list the exact work
needed for completion.
