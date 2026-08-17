# Deep Audit Mode Contracts

Use the contract for the active mode. Preserve identifiers and evidence classes
across every pass.

## Common Preamble

Start each mode by stating:

- audit slug and state root, or `not persisted`
- repository root, revision, branch, and dirty-state summary
- audited source/runtime boundary
- mode, target, and frozen scope
- write and measurement authority
- evidence or repository drift since the previous pass

Allocate the next identifier by scanning every state record for that namespace
and incrementing the highest value. Never infer the next number from only one
table. Do not delete rejected records or reuse gaps. The controller is the sole
writer and ID allocator; parallel investigators return evidence packets with
provisional labels, and the controller serializes them into state.

End each mode with the handoff defined in
`state-and-report-contracts.md`. Update only records affected by the current
slice.

## `discover [scope]`

Discovery maps runtime architecture and prioritizes investigation. It does not
produce ranked findings.

Inspect, where applicable:

- executable, service, request, message, callback, and event entry points
- startup construction, registration, configuration, and feature gates
- timers, polling loops, schedulers, workers, queues, render/update loops
- filesystem, network, database, process, device, logging, and IPC boundaries
- retry, reconnect, fallback, cancellation, recovery, and shutdown paths
- normal and maximum frequency/cardinality sources

Open zero or more evidence-backed candidates, normally capped at 12 for a
repository-wide pass. Never invent candidates to meet a quota. For every
candidate record:

```text
Discovery ID: D-###
Priority: P0 | P1 | P2 | P3
Categories:
Location: exact path, symbol, and line when available
Runtime entry or suspected path:
FACT evidence already observed:
Suspected cost and amplification model:
Current depth:
Counter-evidence or safeguards already found:
Unknowns:
Required next inspection:
Recommended next mode:
```

Priority reflects investigation urgency, not confirmed severity:

- `P0`: plausible material amplification or lifecycle risk on a reachable path;
  trace next
- `P1`: strong runtime candidate with one or more important bounds unresolved
- `P2`: bounded or secondary candidate worth revisiting after P0/P1
- `P3`: low expected value, preserve only to avoid rediscovery

Also produce:

1. runtime architecture map
2. frequency and cardinality boundary map
3. thread, task, scheduler, dispatcher, lock, and queue boundary map
4. prioritized discovery queue
5. coverage gaps and excluded areas

Stop once the map is coherent and the next target is clear.

## `trace <D-id or symbol>`

Trace beyond the initially named function.

Upstream, establish:

- entry point, registration, callers, branches, and live reachability
- frequency source and controlling configuration
- normal and maximum input cardinality

Downstream, establish:

- concrete implementation selected at runtime
- dominant CPU work, allocations, copies, I/O, and consumers
- ownership, disposal, queues, and backpressure
- errors, retries, fallbacks, cancellation, restart, and shutdown

Resolve the executing thread/task/dispatcher/scheduler, locks and channels,
overlap/reentrancy/fan-out, exception observation, and cancellation propagation.
Search other layers for caching, pooling, batching, deduplication, single-flight,
throttling, capacity bounds, expiration, and rate limiting.

Create `T-###` with this table:

| Step | Path and symbol | Trigger/condition | Frequency/cardinality | Execution context | Work/side effect | Multiplier | Evidence class |
|---|---|---|---|---|---|---|---|

Then record:

```text
Trace ID:
Target:
Depth reached:
Established facts:
Strong inferences:
Remaining hypotheses:
Dominant suspected cost:
Amplification model with variables:
Counter-evidence and safeguards:
Semantic/lifecycle constraints:
Promotion decision: audit | deepen | profile | downgrade | reject
Exact next inspection target:
```

## `audit <D-id or symbol>`

Audit one candidate or tightly related cluster. Before deciding status, answer
or explicitly defer:

1. Is the path reachable in the current wiring and workload?
2. What triggers it, how often, and with what cardinality?
3. Can it overlap, reenter, fan out, retry, or queue?
4. What CPU, allocation, retention, copying, I/O, and synchronization occur?
5. What happens when dependencies slow or fail?
6. What happens on cancellation, restart, disposal, and shutdown?
7. Is equivalent work performed elsewhere or discarded?
8. Which safeguards or bounds already exist?
9. Which ordering, freshness, consistency, idempotency, timing, ownership,
   observability, rate-limit, or backpressure constraints apply?
10. What evidence could disprove the concern or the proposed correction?

Assign one status: `Hypothesis`, `Supported`, `Confirmed`, `Rejected`, or
`Needs runtime measurement`.

Severity is operational impact under a realistic workload:

- `Critical`: credible catastrophic availability, resource exhaustion, or
  safety impact with little containment
- `High`: reachable, material user/service impact or strong scaling/failure
  amplification
- `Medium`: bounded but meaningful cost or lifecycle risk
- `Low`: localized, small, or workload-limited impact

Confidence is evidence strength, independent of severity.

For `Supported` or `Confirmed`, create `F-###`:

```text
Finding ID:
Claim: one precise falsifiable statement
Status:
Severity:
Confidence:
Depth reached:
Exact location:
Source revision and evidence citations:
Established call path and unresolved runtime edges:
Trigger and reachability:
Frequency and evidence source:
Input cardinality, bounds, and source:
Current operation count/model:
CPU behavior:
Allocation and lifetime behavior:
I/O behavior:
Concurrency and scheduling behavior:
Failure/cancellation/shutdown amplification:
Existing safeguards:
Counter-evidence considered:
Assumptions and missing evidence:
Operational impact:
Recommended targeted change:
Semantic and lifecycle risks:
Expected impact:
Likely implementation scope:
Validation plan:
Pass criteria:
Reject criteria:
Required follow-up:
```

For a rejected candidate, create `R-###` with the evidence and conditions under
which it could become material. For a measurement-blocked candidate, create an
`M-###` rather than inflating confidence.

## `deepen <D-id, F-id, or symbol>`

Do not restate the prior result. Produce new evidence that can change it.

1. Rewrite the claim as one falsifiable sentence.
2. Enumerate its assumptions and label each `FACT`, `INFERENCE`, `HYPOTHESIS`,
   or `MEASUREMENT REQUIRED`.
3. Select the three assumptions most capable of changing severity, confidence,
   or the correction.
4. Inspect at least one level farther upstream and downstream unless a proven
   runtime boundary prevents it.
5. Re-check configuration, alternate implementations, overlap, failures,
   ownership, shutdown, cross-component duplication, safeguards, consumers,
   semantic constraints, and cheaper upstream corrections.

Record:

```text
Target and original claim:
Weakest evidence links:
Additional evidence inspected:
New upstream evidence:
New downstream evidence:
New amplification evidence:
New counter-evidence:
Depth delta:
Revised status, severity, and confidence:
Revised recommendation:
Remaining uncertainty:
Next mode:
```

If there is no depth delta, say so and open a focused measurement or reject the
candidate instead of adding prose.

## `verify <F-id>`

Verification is adversarial. Try to disprove, narrow, downgrade, or redirect the
finding. Re-read the claim, complete trace, evidence packet, and recommendation.
Inspect for unreachable wiring, lower frequency or cardinality, disabling
configuration, alternate implementations, existing mitigation, runtime/compiler
behavior, semantic constraints, cancellation/overlap prevention, contradicting
tests or measurements, and a more consequential upstream cause.

For Critical and High findings, re-walk trigger-to-effect plus slow-dependency,
failure, cancellation, and shutdown paths. Prefer an independent reviewer when
one is available and the scope justifies it.

Allocate `V-###` and record:

```text
Verification ID and target:
Source revision and original claim:
Evidence supporting it:
Evidence against it and limits:
Additional evidence inspected:
Alternative explanations:
Semantic/lifecycle constraints checked:
Result: Confirmed | Confirmed with narrower scope | Downgraded |
        Needs measurement | Rejected
Revised severity and confidence:
Revised recommendation:
Remaining uncertainty:
Required next mode:
```

Treat the verification result as a state transition, not an add-only note. If
the claim, status, severity, confidence, recommendation, or next action changes,
reconcile the target finding's current summary prose, ranked row, and detailed
record, plus `STATE.md` and `REPORT.md` when they repeat that current state.
Historical text may retain superseded values only when explicitly labeled
original or superseded. Before handoff, search the state root for contradictory
current values; a `V-###` is incomplete while denormalized current-state surfaces
disagree.

The revised recommendation must address the proven mechanism while preserving
live ownership and lifecycle accounting. Do not clear a registry, task set,
queue, or ownership table merely to remove old entries when referenced work may
still be alive. Retain truthful accounting until the owner removes completed work
or an explicitly designed drain/transfer step has finished.

Before completing `verify`, apply this checklist:

- map every proposed edit to the proven mechanism or a recorded semantic
  constraint, and remove unrelated cleanup from the recommendation
- when collection entries self-remove on completion or may still represent live
  work, MUST NOT recommend clearing or replacing the collection unless evidence
  proves every entry completed or ownership was safely transferred
- search for the exact superseded severity, confidence, recommendation, and next
  action across the state root; update each current occurrence or prefix it
  explicitly with `Original:` or `Superseded:`
- do not claim reconciliation passed from a summary row alone; compare the
  summary prose, ranked row, detailed finding, verification, state, and report

If rejected, create `R-###` and remove the item from ranked findings without
deleting its history.

## `profile <D-id, F-id, M-id, or hypothesis>`

First design the smallest focused measurement. Execute it only when the
authority and safety gate permits.

Inspect existing telemetry, diagnostics, benchmarks, and workload fixtures
before adding instrumentation. Prefer distributions and counts over isolated
averages: invocation rate, inter-arrival time, duration percentiles, active
concurrency, queue depth/age, retry rate, CPU samples, allocation rate, retained
memory, GC, lock wait/hold, thread-pool or dispatcher delay, I/O count/bytes,
payload size, spawn count, frame time, and startup/shutdown duration as relevant.

Create or update `M-###`:

```text
Measurement ID and related item:
Hypothesis:
Why static inspection is insufficient:
Environment and revision:
Workload, data shape, concurrency, warmup, repetitions, and duration:
Instrumentation point/tool and overhead:
Metrics and units:
Baseline:
Expected signal if true:
Confirmation threshold:
Rejection threshold:
Confounders/noise controls:
Safety, cost, cleanup, and authorization:
Commands or procedure:
Raw artifact location:
Execution status: planned | partial | completed | blocked
Observed data with units and sample counts:
Interpretation: confirmed | rejected | narrowed | inconclusive
Next action:
```

Do not infer causality from correlation or use a microbenchmark as proof of an
end-to-end bottleneck without connecting it to real frequency and workload.

## `resume [audit-slug]`

1. Resolve the state root and load every record.
2. Re-read repository instructions and current root/branch/revision/dirty state.
3. Compare current revision and relevant paths with the recorded baseline.
4. Mark traces, findings, and measurements stale when changed code,
   configuration, generated output, deployment, or workload can invalidate them.
5. Do not repeat valid work merely to refill context.

Select the next item in this order:

1. stale or unverified Critical/High finding
2. P0 discovery with incomplete trace
3. measurement blocking severity or recommendation
4. uninspected failure, cancellation, shutdown, queue, or overlap path
5. high-frequency path lacking cardinality or concrete implementation
6. remaining P1/P2/P3 work
7. report only when the completion contract is met or the user asks for interim
   synthesis

Complete one coherent slice and end with the exact next mode.

## `report [audit-slug]`

Use the findings-first structure and completion rules in
`state-and-report-contracts.md`. Never hide uninspected scope or measurement
gaps behind a confident executive summary.
