---
name: deep-audit
description: Use when the user asks for an evidence-backed, multi-pass runtime-efficiency or scalability audit across real execution paths. Covers hot-path reconstruction, CPU, allocation/retention, I/O, concurrency, queues, retries, scheduling, and lifecycle. Do not use for diff review, one known regression with a requested fix, tests, security assessment, bounded feasibility research, or parallel remediation.
---

# Deep Audit - Runtime and Efficiency Investigation

Reconstruct how a system actually executes, identify the multipliers that make
work operationally significant, and separate proven findings from suspicions.
Prefer a few deeply evidenced findings over a catalog of local code smells.

## Scope and Routing

Use this skill for repository or subsystem audits centered on:

- CPU work and algorithmic growth
- allocations, copying, retention, and garbage-collection pressure
- filesystem, network, database, process, device, logging, and IPC behavior
- concurrency, scheduling, locks, queues, timers, workers, and backpressure
- repeated, discarded, eager, overlapping, or retry-amplified work
- startup, steady state, failure, cancellation, recovery, and shutdown
- latency, throughput, responsiveness, scalability, and resource saturation

Route narrower requests elsewhere:

- Use `review` for a branch, PR, staged, or working-tree diff review.
- Use `diagnosing-bugs` for one reproducible failure or performance regression
  when the goal includes a fix.
- Use `discover` for bounded pre-planning research that does not require a
  runtime cost model or multi-pass audit state.
- Use `qa` for test execution, coverage, and failure triage.
- Use a security-specific workflow for authentication, authorization,
  injection, secrets, supply-chain, or vulnerability assessment. Do not claim
  security coverage from a runtime-efficiency audit.
- Use a provider's orchestration workflow when the primary request is parallel
  agents, gate ownership, implementation, and remediation. Deep Audit supplies
  the runtime investigation method; it does not own remediation gates.

This is not a style, naming, formatting, documentation, or general cleanliness
review. Mention those concerns only when they change runtime behavior, hide a
critical invariant, or block reliable operation.

## Modes

Treat these as logical skill arguments; provider invocation syntax may differ.

| Mode | Purpose |
|---|---|
| `discover [scope]` | Map runtime roots and open a prioritized discovery queue |
| `trace <D-id or symbol>` | Reconstruct one end-to-end execution path |
| `audit <D-id or symbol>` | Decide whether one traced candidate supports a finding |
| `deepen <D-id, F-id, or symbol>` | Attack weak assumptions and produce a depth delta |
| `verify <F-id>` | Try to disprove, narrow, downgrade, or reject a finding |
| `profile <D-id, F-id, M-id, or hypothesis>` | Design and, if authorized, run a focused measurement |
| `resume [audit-slug]` | Revalidate repository state and continue the top unresolved item |
| `report [audit-slug]` | Produce an interim or final findings-first synthesis |

For a new audit, default to `discover`. For a terse continuation request, use
`resume` only when a matching state root can be identified unambiguously. Never
jump directly to `report` merely because the current context is short.

### First-Pass Mode Isolation

A new audit, whether selected automatically from natural language or invoked as
`discover`, completes one discovery slice only. It MUST NOT create `F-###` or
`V-###` records, assign finding severity, present a final/comprehensive report,
or prescribe a correction as though it were already validated. Produce the
runtime maps, evidence-backed `D-###` queue, gaps, and one exact next mode and
target. A small repository or apparently obvious issue does not waive this
gate; later `trace`, `audit`, and `verify` passes exist to prevent premature
promotion.

When an amplification claim activates only after a runtime threshold is crossed
(for example duration greater than a timer period, arrivals greater than service
rate, or failures sufficient to trigger retry growth), code shape proves the
mechanism but not that the threshold is crossed. Keep the activation and impact
as `HYPOTHESIS` or `MEASUREMENT REQUIRED` until evidence establishes the runtime
condition.

For one start every interval `I` with fixed finite run duration `D`, steady-state
active runs are bounded by `ceil(D / I)`. Absence of an in-flight guard proves
possible overlap, not time-growing concurrency. Call growth unbounded only when
evidence establishes non-completion, an accumulating queue, or feedback or
slowdown that makes duration or arrival pressure grow with overlap.

Treat bounds and eviction as counter-evidence before calling them waste or
retention problems. A capacity mismatch, cache eviction, or bounded collection
is not a finding without a proven consumer, required lifetime or hit behavior,
and operational impact. Reject or defer a plausible decoy rather than inventing
benefit for data whose use is not established.

Read [mode-contracts.md](references/mode-contracts.md) before executing a mode.
When persisting, resuming, or reporting, also read
[state-and-report-contracts.md](references/state-and-report-contracts.md).

## Authority and Safety Gate

Establish the allowed boundary before investigating:

1. **Product code:** deep audit is read-only by default. Recommend changes, but
   do not implement them unless the user separately asks for fixes.
2. **Audit state:** create repository-local state only when the request permits
   durable audit artifacts. Otherwise keep the result in the response or use a
   user-specified output path.
3. **Runtime access:** passive local inspection and existing safe tests are
   allowed when relevant. Do not run production profiling, load tests, fault
   injection, privileged diagnostics, paid workloads, or service restarts
   without explicit authority.
4. **Instrumentation:** prefer existing telemetry. If measurement requires code
   changes, dependency installation, or persistent configuration, stop at a
   measurement plan unless that mutation is explicitly authorized. Isolate any
   authorized temporary instrumentation and account for cleanup.
5. **Existing work:** preserve dirty worktree changes and distinguish source,
   generated, deployed, and live runtime copies before drawing conclusions.

An explicit narrower user restriction overrides every default allowance above.
If the user says not to run tests, probes, commands, or measurements, do not run
them even when they appear local, harmless, read-only, or useful; inspect
existing artifacts only. Never infer authority from low risk. Accurately record
every test, probe, runtime command, and measurement that was actually executed;
do not claim an activity was skipped when the tool trace shows otherwise.

If a requested measurement could materially affect users, data, cost, service
health, or machine state, report the exact risk and required authority instead
of silently executing it.

## PASS 0: Establish Current Truth

Before opening discoveries:

- resolve the repository root and applicable instruction files
- record branch, revision, dirty state, and relevant submodule or worktree state
- identify the audited source tree and any deployed or generated runtime copy
- freeze the audit scope, exclusions, workload assumptions, and environment
- locate existing architecture docs, tests, benchmarks, telemetry, and prior
  audit state, but verify drift-prone claims against current code
- state whether repository-local audit writes and runtime measurements are
  permitted

Do not treat comments, filenames, old reports, or textual call searches as
proof of live reachability. Resolve registrations, configuration, factories,
dependency injection, reflection, callbacks, generated code, framework hooks,
and native boundaries where they can affect the path.

## Cost Model

Estimate significance as:

```text
execution frequency
x input cardinality
x work per item
x overlap, fan-out, retry, or failure amplification
x duration for which the behavior persists
```

Report total operations and avoidable operations separately. Define the
correctness-preserving required baseline before calling work redundant:
`redundant = total - required`.

For every serious candidate, define the variables and establish or explicitly
defer:

- trigger and reachability
- normal and maximum frequency
- the meaning, source, and bounds of `n`
- work, allocation, copying, I/O, synchronization, and retention per execution
- overlap, reentrancy, fan-out, retry, queueing, and slow-dependency behavior
- correctness constraints and existing mitigation
- failure, cancellation, restart, disposal, and shutdown behavior
- the measurement that would confirm or reject material impact

Big-O notation, a suspicious statement, or a microbenchmark alone does not
establish operational importance.

## Evidence and Depth

Label material claims:

- `FACT`: directly established by implementation, configuration, test output,
  runtime output, or measurement
- `INFERENCE`: strongly implied by multiple facts but not directly measured
- `HYPOTHESIS`: plausible and falsifiable, with important evidence missing
- `MEASUREMENT REQUIRED`: static evidence cannot establish the key runtime fact

Use stable identifiers across passes: `D-###` discovery, `T-###` trace, `F-###`
finding, `V-###` verification, `M-###` measurement, and `R-###` rejected
hypothesis. Never renumber or reuse an identifier. In multi-agent work, the
controller is the only state writer and ID allocator; reviewers return proposed
records without assigning final IDs.

Track depth independently from severity:

- **Depth 0 - Shape:** suspicious pattern only
- **Depth 1 - Local:** implementation and immediate data structures inspected
- **Depth 2 - Call chain:** relevant callers, callees, and concrete runtime
  implementations inspected
- **Depth 3 - Runtime context:** trigger, reachability, frequency, cardinality,
  configuration, execution context, and lifecycle established or measured
- **Depth 4 - Amplification and semantics:** overlap, retries, failure,
  backpressure, ownership, shutdown, and correctness constraints inspected
- **Depth 5 - Validation:** the claim was adversarially verified or measured
  with objective pass and reject criteria

Do not rank a finding at Depth 0 or 1. Critical and High findings normally need
Depth 4 and an independent `verify` pass before final reporting.

## Operating Loop

Run one coherent investigation slice per pass:

1. Establish or refresh PASS 0 current truth.
2. Select the highest-value unresolved target, not the easiest file to discuss.
3. Trace upstream to the trigger and downstream to dominant work and consumers.
4. Inspect thread, task, scheduler, queue, ownership, failure, and lifecycle
   boundaries.
5. Search for counter-evidence and existing guards before promoting a finding.
6. Promote, reject, deepen, or open a measurement requirement.
7. Update only the affected audit records and end with an exact handoff.

Stop at a safe boundary when the slice grows too broad. Do not manufacture
completeness by skimming remaining candidates.

## Finding Promotion Gate

Before creating a ranked `F-###`, confirm that:

- the reachable concrete implementation and relevant trigger were inspected
- frequency and input cardinality were proven, bounded, or assigned an `M-###`
- dominant downstream work, consumers, and resource lifetime were inspected
- execution context, overlap, retries, queueing, and slow-dependency behavior
  were considered
- failure, cancellation, disposal, restart, and shutdown were considered
- caches, bounds, pools, batching, deduplication, throttling, and rate limits
  were checked across layers
- ordering, freshness, consistency, idempotency, timing, ownership, and
  backpressure constraints were recorded
- counter-evidence was actively sought
- the operational impact is precise and falsifiable
- the recommendation is targeted and has objective pass and reject criteria

If the gate is incomplete, retain the item as a discovery, hypothesis, or
measurement requirement. `Confirmed` requires direct measurement or equivalent
deterministic proof; strong static evidence is `Supported`.

## Recommendation Rules

Prefer, in order: remove unnecessary work; remove duplication; prevent overlap;
reduce frequency; coalesce or batch; bound queues, retries, caches, and
concurrency; improve algorithms; reduce repeated parsing/copying/I/O; move
blocking work off latency-sensitive paths; reduce proven high-frequency
allocation; then consider architecture changes.

Never recommend caching without key, ownership, invalidation, concurrency, and
memory bounds. Never recommend parallelism without ordering, capacity, rate
limits, cancellation, and backpressure. State exactly which operation count,
wait, allocation, queue, retry, or latency source should decrease.

## Persistent State and Handoff

When durable state is authorized, default to:

```text
.audit/deep-audit/<audit-slug>/
```

Use a repository convention such as `docs/audits/` instead when one exists, and
record the chosen root. State artifacts do not authorize product-code changes.

At the end of every pass, report:

- repository revision and drift status
- mode and target completed
- files, symbols, runtime roots, and evidence inspected
- identifiers opened, changed, verified, measured, or rejected
- coverage gaps and remaining uncertainty
- highest-priority next item and exact next mode

## Completion

Call the result complete only when the frozen scope and major runtime roots are
accounted for, P0 and P1 candidates are resolved or explicitly measurement-
blocked, Critical and High findings are adversarially verified, important CPU,
memory, I/O, concurrency, failure, cancellation, and shutdown paths are covered,
repository drift is reconciled, and remaining gaps are explicit. Otherwise
label the output `Interim Deep Audit Report`.

Use [depth-test.md](examples/depth-test.md) only to evaluate auditor behavior or
when a pass is stuck at a local code smell.
