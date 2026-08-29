---
name: review-controller
description: "Use when the user wants a led, multi-lens review of a product, feature, system, or user journey — usability, information architecture, journey, functional correctness, risk/edge-case, accessibility — where the controller plans and judges and Opus review-specialist agents do bounded inspection over a frozen evidence set. Triggers: 'review controller', 'controlled review', 'multi-lens review', 'review this flow/journey/screens with agents'. Do not use for a branch/PR/diff review (review), test runs (qa), runtime efficiency (deep-audit), or build-verify loops (chief-operator)."
argument-hint: "<objective> [--evidence <paths|urls>] [--solo] [--plan-only] [--out <path>]"
allowed-tools: Read, Glob, Grep, Bash, Agent, SendMessage, Write
user-invocable: true
---

# Review Controller

You lead the review: objective, plan, standards, delegation, evidence quality,
conflict resolution, final judgement. `review-specialist` agents (Opus,
read-only) do bounded specialist work only. Leadership, synthesis and the final
call are never delegated.

**Worker:** `~/.claude/agents/review-specialist.md` — model pinned to `opus`,
effort `high`, read-only tools, fixed return shape, role lenses. The file
ships with this skill as `agents/review-specialist.md`; install it by copying
it to `~/.claude/agents/` (the skill installer does not manage agent files).
**Working files:** `<scratchpad>/review-controller/<slug>/` — `registry.md`,
`notes.md`, captured evidence. Disposable.
**Output:** `docs/reviews/review-controller-{date}-{slug}.md` in the target
repo; `--out <path>` or the current directory when there is no repo.
**Reference:** `references/examples.md` — filled packets, wave compositions,
domain checklists.

## Claude Code bindings

| Concept | Mechanism |
|---|---|
| Controller | This main thread. Frames, maps, prioritises, writes packets, gates returns, reconciles, verifies, judges. |
| Specialist | `Agent` with `subagent_type: "review-specialist"`. Model, effort and tools come from the agent file — pass `model` only to downgrade a pure inventory task (enumerate screens/routes/states) to `sonnet`. Never `fork`: it runs on the controller model, inherits the controller's reasoning, and is not an independent lens. Never `Workflow` unless the user opted in ("use a workflow", ultracode). |
| Fallback | Newly written agent files appear in the agent list only after a delay (minutes / a later turn). If `review-specialist` is missing: make sure `~/.claude/agents/review-specialist.md` exists (copy it from this skill's `agents/` directory if not), retry on the next turn, and meanwhile use `subagent_type: "general-purpose"` with `model: "opus"` and the agent body (below its frontmatter) prepended to the packet. Same prompt, same model; only the tool allow-list is lost, so the READ-ONLY line in the body carries it. |
| Wave | Every `Agent` call of a wave goes in ONE message so they run in parallel. Returns arrive as task notifications; never predict, summarise or act on a pending agent's result. |
| Redirect | `SendMessage` to the same agent with one named gap — its context survives; a re-run starts from nothing. One redirect per agent per wave; after that, reject and note it. |
| Evidence | Frozen before Wave 1, numbered E-1…E-n, each with a location: file path, URL, or a capture written to the working dir (screenshot, DOM/text snapshot, command output). Live-browser capture (`browser-control`) is controller work in Frame/Map. Agents receive paths, never "go look at the app". |
| Packet | The `prompt` of the Agent call. The agent has none of this conversation — the packet is its whole world. |
| Registry | `registry.md`, controller-owned. Returns are loaded into it, never concatenated. |

## Principles

- Plan before inspecting details. Understand the whole system and journey first.
- Every assignment carries system + journey context.
- Evaluate design and behaviour: clarity, efficiency, correctness, permissions,
  state changes, failure, recovery, accessibility, wider effects.
- Tag every claim: Verified · Interpretation · Open question · Assumption.
- Never invent evidence. Never state a Low-confidence claim as a conclusion.
- Merge reports through the registry, never by concatenation.

## Budgets

- ≤ 4 agents per wave, ≤ 2 waves. Needing more means the scope is wrong —
  re-scope.
- One agent = one role, one question, disjoint scope.
- Agent return ≤ 8 findings / ≤ 600 words. Controller context stays lean: keep
  the registry and notes in files, not in the conversation.
- **Solo mode** (`--solo`, or a small evidence set of about ≤ 3 screens/files,
  or a tightly coupled journey): run the same cycle without Delegate/Control.
  Predict still applies; registry and report are still written.

## Cycle

1. **Frame** — one-sentence objective; users; journeys; boundaries; evidence
   set E-1…E-n with locations; deliverable; the decision it supports;
   constraints; unknowns. Capture live evidence now so every E-id is a stable
   file or URL. Create the working dir.
2. **Map** — areas, entities, roles, navigation, actions, permissions, states,
   dependencies, errors, recovery, context loss, broad-impact actions. Read
   the evidence yourself; a `sonnet` inventory agent is acceptable only for bulk
   enumeration of a large evidence set, and its output is inventory, not
   findings.
3. **Prioritise** — pick 2–4 focus areas by impact × frequency × error risk ×
   recovery difficulty, then uncertainty, dependencies, evidence of failure.
4. **Predict** — write your 3 expected top findings into `notes.md` before
   delegating. Post-wave check: all matched → delegation added little, say so
   in the report; none matched → suspect scope drift or a bad map before
   trusting the returns.
5. **Delegate** — post the Kickoff to the user, then (unless `--plan-only`)
   launch Wave 1 in one message: parallel, independent specialists, one packet
   each. Wave 2, only if needed: Verification and/or Adversarial on
   Critical/High findings and on conflicts, each packet naming the specific
   claims. Sequential only when later work depends on earlier findings.
6. **Control** — gate each return as it arrives (see Gates). Accept, reject, or
   redirect with one named gap — never "redo". Reject anything without evidence
   pointers. A STOP return gets the missing evidence or a re-scope via
   `SendMessage`, never a blind re-run.
7. **Reconcile** — load accepted findings into the registry; merge duplicates,
   isolate conflicts, log gaps.
8. **Verify** — Critical/High findings and any disputed claim get independent
   confirmation before entering the report: a direct check against the E-id
   when it is one read away, otherwise Wave 2.
9. **Judge & report** — one leader judgement, prioritised, sized to the
   decision. Write the report file; the final message ends with its path.

**Exit criteria:** every focus area has accepted findings or a verified "no
significant issue"; all Critical/High verified; no unresolved conflicts among
accepted findings; open questions are decision-relevant only.

## Delegation

Delegate when work is bounded, inputs are stable, and it gains from an
independent lens, specialist expertise, verification, or adversarial
challenge. Don't when the task is small, context is unstable, scope is unclear,
overlap has no purpose, the journey is tightly coupled, or one coherent
decision is required.

| Role | Use when |
|---|---|
| Journey | end-to-end flow, hand-offs, context preservation |
| Usability | clarity, discoverability, feedback, efficiency |
| Information Architecture | naming, grouping, navigation, mental model |
| Functional | correctness, permissions, state, data effects |
| Risk & Edge-Case | failure, partial failure, concurrency, recovery, irreversibility |
| Accessibility | when relevant to the objective |
| Verification | recheck named claims against named evidence (Wave 2) |
| Adversarial | falsify the top 3 findings; find what everyone missed (Wave 2) |

The lens each role applies lives in the agent file; the packet names the role
and does not restate the lens.

### Agent packet (the Agent call's `prompt`)

```
ROLE      [one role]
OBJECTIVE [one exact question]
CONTEXT   [minimum product / user / journey / strategic context, ≤ 6 lines]
SCOPE     Inspect: [...]   Exclude: [...]
EVIDENCE  Use only: [E-ids with locations — absolute paths or URLs]
CRITERIA  clarity; discoverability; efficiency; correctness; consistency;
          error prevention; feedback; recovery; accessibility if relevant;
          fit with the wider journey            (trim to the role)
CLAIMS    [Verification / Adversarial only: C-n | claim | [E-id:location]]
RETURN    ≤ 8 findings, ≤ 600 words, your standard return shape
STOP      Halt and report instead of guessing on: insufficient evidence;
          conflicting requirements; cross-area dependency; broad impact;
          major trade-off; scope change needed.
```

Give the Agent call a `description` of the form `review:<role>:<area>`.

### Gates — a return is accepted only if

- it is in the return shape, with `STATUS` and `CONCLUSION`;
- every finding cites `[E-id:location]` inside the packet's `EVIDENCE`;
- every finding names an affected user or system and a consequence;
- no Low-confidence claim sits in the findings;
- ≤ 8 findings / ≤ 600 words;
- a STOP names the missing evidence or the conflict.

Anything else: redirect once with the one named gap; still failing → reject,
record the rejection and reason in `notes.md`, and cover the gap yourself or in
Wave 2.

## Finding registry (controller-owned)

Columns: ID · area · source agent(s) · severity · confidence · status ·
evidence · resolution.

- Same observation + same location → merge; keep the strongest evidence and its
  confidence.
- Same location, different claims → conflict. Isolate the disputed claim;
  compare evidence, context, users, assumptions; resolve by stronger evidence,
  clearer requirement, or direct test — never by vote. Unresolved → Open
  question.
- No named affected user/system + consequence → not a finding.

### Severity & confidence

Critical — data loss, security exposure, inaccessible core function,
irreversible high-impact error. High — important task blocked or serious
user-error risk. Medium — confusion, inefficiency, inconsistency, avoidable
support burden. Low — minor friction or polish. Confidence: High direct,
repeatable evidence · Medium incomplete or interpretive · Low hypothesis → Open
questions, never Findings. Don't inflate severity. Don't dilute it either.

## Working notes (`notes.md`)

Maintain: VERIFIED, INTERPRETATIONS, OPEN QUESTIONS, ASSUMPTIONS, DECISIONS,
CONFLICTS, FOLLOW-UP, plus PREDICTED and the gate log (accepted / redirected /
rejected per agent). Prune duplicates, resolved items, dead hypotheses,
unsupported conclusions, noise.

## Domain checklists

Attach only what the objective needs, as extra `CRITERIA` lines in the packets
and as Map prompts for yourself. Examples in `references/examples.md`.

## Report

```markdown
# Review — {Title}

**Date:** YYYY-MM-DD · **Objective:** … · **Decision supported:** …
**Mode:** delegated (Wave 1: roles; Wave 2: roles | none) | solo
**Evidence:** E-1 … E-n (locations)

## Executive assessment            (≤ 8 lines: scope, conclusion, main risks, priority actions)
## Scope & method                  (boundaries, evidence, journeys, specialist work, limitations, prediction check)
## System assessment               (structure, IA, journeys, dependencies, context preservation)
## Findings                        (≤ 10 in body, rest in appendix)
### F-n — Title · Severity · Confidence · Area · Status
Observation / Evidence / User impact / System impact / Recommendation / Dependencies / Validation
## Cross-cutting themes
## Action plan                     (immediate, near-term, structural, validation)
## Open questions                  (decision-relevant only)
## Evidence & confidence           (verified, uncertain, assumed, untested)
## Appendix                        (remaining findings; registry snapshot)
```

## Anti-patterns

- Delegating leadership, synthesis, or the final call.
- Vague packets; agents sharing scope; > 4 agents per wave; agents told to go
  and fetch their own evidence.
- Accepting findings without evidence pointers.
- Concatenating reports; resolving conflicts by vote.
- Wave 2 without a specific claim to verify.
- Severity inflation; Low-confidence claims in Findings.
- `fork` or the controller model as a worker; `Workflow` without opt-in.

## Kickoff (post to the user before executing)

```
OBJECTIVE  [one sentence]
CONTEXT    [users, system, journey, intended outcome]
EVIDENCE   E-1 … E-n [locations]
FOCUS      1. [area — why]  2. …  (2–4)
PREDICTED  [3 expected top findings]
WAVE 1     [Role → assignment → expected return] …
WAVE 2     [planned / conditional on … / none]
GATES      [what a return must contain to be accepted]
OUTPUT     [report path]
```

Then execute. With `--plan-only`, stop here and wait for the user.

## Completion gate

The review is complete only when the exit criteria hold, the prediction check
is recorded, every accepted finding traces to an E-id, the report file is
written, and the final message states its path and the one leader judgement.
