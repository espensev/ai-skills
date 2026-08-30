---
name: review-controller
description: "Use when the user explicitly asks Codex to lead a multi-lens, multi-agent review of a product, feature, system, user journey, flow, or screens across usability, information architecture, functional behavior, risk, or accessibility. Do not use for a branch, PR, diff, or merge-readiness review (use review), a source symbol named ReviewController, generic subagent work, broad audit/remediation gates, implementation, QA, runtime-efficiency, security assessment, or one known regression."
---

# Review Controller

Lead one evidence-backed product review through native Codex subagents. The
controller owns the whole-system map, evidence integrity, delegation, claim
verification, synthesis, judgement, and report. Workers supply bounded,
independent lenses; they never become the decision maker.

**Output:** `docs/reviews/review-controller-{date}-{slug}.md`

**Product/source edits:** none

**Subagent writes:** none

**External or live mutations:** none

## Routing Boundary

Use this skill only for an explicitly controlled or multi-agent review of a
product, feature, system, journey, flow, or screens. Useful lenses include
journey, usability, information architecture, functional behavior, risk and
edge cases, and accessibility.

Route elsewhere when the task is:

- a branch, PR, staged change, working-tree diff, document merge review, or
  merge-readiness verdict: use `review`;
- generic lightweight subagent work: use `parallel-agents-light`;
- a broad review-first audit with remediation or approval gates: use
  `audit-gated-subagents`;
- a managed implementation campaign: use `manager`;
- a known regression with a requested fix: use `diagnosing-bugs`;
- QA, runtime-efficiency/scalability, or security assessment: use the dedicated
  workflow.

Do not trigger on a class, function, route, or other source symbol merely named
`ReviewController`.

If the user also asks for fixes, complete and report the review first. Treat any
implementation as a separately routed and authorized follow-up; a reviewer
must not repair its own finding.

## Controller Authority And Safety

Only the controller may:

- frame the decision, users, journeys, boundaries, and limitations;
- capture, identify, freeze, and refresh evidence;
- map the whole system and choose focus areas and lenses;
- accept, reject, merge, reclassify, or verify worker claims;
- resolve disagreements and assign the final judgement;
- write the durable review report.

Workers are read-only. They may inspect only the assigned frozen evidence and
must not edit or create files, run mutation-capable commands, stage or commit,
switch branches, post externally, install, deploy, change runtime/account/
machine state, or spawn descendants. Keep credentials, raw secrets, privileged
operations, destructive actions, and live operator decisions in the controller
thread and outside this workflow.

When repository files are evidence, record the relevant repo state before and
after each wave. Any worker-caused or concurrent change is a stop condition,
not a result to blend into the review.

## Cycle

Run the phases in order. Small or tightly coupled evidence sets may use solo
mode: the controller applies the same evidence, verification, registry, and
report gates without launching workers.

### 1. Frame And Freeze Evidence

Write a one-sentence objective and the decision it supports. Record the affected
users/systems, end-to-end journey, included and excluded boundaries,
constraints, unknowns, and output location.

Capture live or volatile evidence before delegation. Load `browser-control`
when a live browser is required; navigation and capture remain controller work.
Workers receive stable artifacts, never an instruction to explore a live app.

Create a numbered evidence manifest E-1...E-n. Every entry records:

- stable location and evidence type;
- byte length and SHA-256 for each local file, capture, screenshot, DOM/text
  snapshot, or command-output artifact;
- an immutable resource/content identifier and checksum when the platform
  exposes one for an attachment;
- capture time and source URL for web material, with the captured artifact's
  hash. A changing URL alone is not frozen evidence.

Sort entries by E-id and hash the canonical manifest bytes to form the frozen
review fingerprint. Save task notes only in a task-specific scratch directory.

At every freshness gate, re-read every local or captured E-id artifact from its
stable location, recalculate its current byte length and SHA-256, and re-verify
any platform-provided immutable content identifier and checksum. Rebuild the
sorted canonical manifest from those fresh observations, then compare every
entry and the resulting fingerprint with the frozen baseline. Re-hashing the
stored manifest alone is not a freshness check.

Run that full evidence revalidation after Wave 1 before accepting returns,
before any Wave 2, and immediately before writing the report. If an artifact is
unavailable, any E-id observation changed, or any canonical manifest byte
differs, reject stale returns and rerun only affected lenses on one coherent
evidence state. Never combine claims from different states.

### 2. Map The Whole Journey

The controller walks the evidence end to end once before judging details. Map:

- users, roles, entry points, goals, and hand-offs;
- screens/steps, navigation, naming, grouping, and context preservation;
- actions, permissions, state transitions, data effects, and dependencies;
- loading, empty, success, error, partial-failure, retry, undo, and recovery
  states;
- broad-impact or irreversible actions and accessibility-relevant interaction.

Prioritize two or three focus areas by user/system impact, frequency, error
risk, recovery difficulty, uncertainty, and decision relevance. Private risk
hypotheses may guide coverage, but do not send expected findings or a preferred
answer to workers and do not score a review by agreement with predictions.

### 3. Choose Bounded Lenses

Use two read-only workers by default. Use three only when a distinct third lens
adds material coverage and the exposed concurrency has capacity. The controller
also occupies a slot; never assume a fixed slot count or pin a model name.

Choose non-duplicative roles from:

- **Journey:** end-to-end flow, hand-offs, context, re-entry, findability;
- **Usability:** clarity, discoverability, feedback, efficiency, prevention;
- **Information Architecture:** naming, grouping, navigation, mental models;
- **Functional:** behavior, permissions, state, data effects, side effects;
- **Risk & Edge-Case:** failure, concurrency, boundaries, recovery,
  irreversibility;
- **Accessibility:** semantics, keyboard/focus path, contrast, motion, targets;
- **Verification:** decide named claims against named evidence;
- **Adversarial:** try to falsify decision-critical claims and expose a named
  coverage gap.

One worker gets one role, one exact question, and a disjoint primary scope.
Intentional overlap is allowed only for labelled independent verification.
Launch all initially ready workers together so they actually run in parallel.

If the subagent launcher is unavailable, capacity is exhausted, or a launch
fails, run the same lens packets sequentially in the controller. Record the
fallback and failed/unavailable lane; never imply parallel review occurred.

Before execution, give the user a compact kickoff:

```text
OBJECTIVE   <one sentence and decision supported>
USERS       <affected users and systems>
JOURNEY     <start -> steps/hand-offs -> outcome>
EVIDENCE    <E-ids, stable locations, review fingerprint>
FOCUS       <2-3 areas and why they matter>
LANES       <role -> one exact question and scope>
GATES       <return and controller-verification requirements>
OUTPUT      docs/reviews/review-controller-<date>-<slug>.md
```

### 4. Dispatch Self-Contained Packets

Every worker receives its whole context in one packet:

```text
ROLE       <one lens>
OBJECTIVE  <one exact question>
CONTEXT    <users, product/system, journey, decision; no preferred answer>
SCOPE      Inspect: <E-ids/locations>  Exclude: <explicit boundaries>
EVIDENCE   <canonical E-id manifest and review fingerprint>
CRITERIA   <lens-specific qualities and relevant states>
RULES      read-only; evidence only; no child agents or mutations
RETURN     <= 8 findings, <= 600 words; each finding includes:
           title | severity | confidence | claim tag | observation |
           [E-id:location] | user impact | system impact |
           recommendation | validation
COVERAGE   E-ids/areas inspected, no-issue checks, skipped items with reason
OPEN       low-confidence hypotheses and out-of-scope dependencies
STOP       insufficient/changed evidence, conflicting requirements, scope
           expansion, broad impact, major trade-off, or required mutation
```

Tag claims as Verified, Interpretation, Open question, or Assumption. A finding
must name an affected user or system, a consequence, and an exact E-id location.
Low-confidence claims go to Open, never Findings.

### 5. Gate, Verify, And Reconcile

Maintain a controller-owned registry:

`ID | area | source lens | severity | confidence | claim tag | status |
evidence | impact | recommendation | validation | resolution`

For every return:

1. Run the full per-artifact freshness check, rebuild the canonical manifest,
   and confirm every E-id plus the review fingerprint still matches the frozen
   baseline.
2. Enforce packet scope, return shape, evidence identity, word/finding limits,
   affected user/system, consequence, confidence, and validation step.
3. Directly inspect the cited evidence and relevant journey context for every
   proposed finding, regardless of severity, before accepting it.
4. Directly verify every accepted no-significant-issue coverage claim; an empty
   finding list is not proof of complete coverage.
5. Reject out-of-scope, unsupported, stale, duplicate-only, or speculative
   claims. Redirect once for one correctable packet gap; then reject and record
   the reason.
6. Merge duplicates by claim and evidence while retaining the strongest proof.
   Isolate disagreement and resolve by stronger evidence, explicit requirement,
   or direct test, never by vote or worker agreement.

Agent agreement is not verification. Keep unresolved low-confidence material in
Open Questions and state any coverage limit that weakens the judgement.

### 6. Use At Most One Targeted Second Wave

Wave 2 is optional and may address only:

- a disputed claim that direct inspection cannot settle;
- a material coverage gap that can change the judgement; or
- independent falsification of a decision-critical claim.

Give the worker the exact claims and necessary E-ids without the originating
reasoning or preferred answer. Never launch a broad second review. If no
independent slot exists, the controller performs and records the direct check.

### 7. Judge And Report Findings First

Run the full per-artifact freshness check and recheck the rebuilt review
fingerprint, then write:

```markdown
# Review - {Title}
**Date:** ... **Objective:** ... **Decision supported:** ...
**Mode:** delegated (lanes and waves) | sequential fallback | solo
**Evidence fingerprint:** ...

## Findings
### Critical
### High
### Medium
### Low
## Leader Judgement
## Scope And Method
## Whole-System And Journey Assessment
## Cross-Cutting Themes
## Action Plan
## Open Questions
## Evidence, Coverage, And Confidence
## Agent Roster, Fallbacks, And Rejected Claims
```

Every accepted finding traces to a verified E-id and includes user/system
impact, recommendation, and validation. The final answer states the report path
and one leader judgement. Do not post it to any external destination unless the
user separately authorizes that mutation.

## Completion Gate

The review is complete only when:

- the final per-artifact revalidation and rebuilt evidence fingerprint match
  the state every accepted claim used;
- every focus area has explicit coverage or a recorded exclusion;
- the controller verified every accepted finding and no-issue claim;
- every decision-critical dispute is resolved or visibly blocks judgement;
- no worker wrote, spawned descendants, or changed local/external state;
- the durable findings-first report exists and names all limitations and
  fallbacks.
