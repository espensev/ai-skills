---
name: diagnosing-bugs
description: "Use when the user wants the cause or fix for a reproducible bug, runtime error, flaky behavior, or performance regression. Builds a red-capable feedback loop before changing code. Do not use merely to run or classify a known test suite (use qa), review a diff (use review), or audit runtime efficiency broadly (use deep-audit)."
disable-model-invocation: true
argument-hint: "[<symptom|command>] - loop | perf | fix | postmortem"
allowed-tools: Read, Glob, Grep, Bash, Write
user-invocable: true
agent-invocable: true
---

# Diagnosing Bugs - Tight Feedback Loop

Diagnose hard bugs by first building a command that can catch the user's exact
symptom. Do not jump to a theory before a red-capable loop exists.

**Default command:** `/diagnosing-bugs <symptom>`
**Primary output:** a fix verified by the original loop, or a clear blocked
diagnostic note listing what evidence is missing.

---

## Commands

| Command | Usage | Purpose |
|---------|-------|---------|
| `loop` | `/diagnosing-bugs loop <symptom>` | Build or tighten the red-capable feedback loop. |
| `perf` | `/diagnosing-bugs perf <symptom>` | Establish timing/profiling evidence before fixing a performance regression. |
| `fix` | `/diagnosing-bugs fix <symptom>` | Reproduce, minimize, fix, and verify the bug. |
| `postmortem` | `/diagnosing-bugs postmortem` | Capture cause, regression coverage, and prevention notes after the fix. |

Default to `fix` when the user reports a concrete bug and has not requested a
diagnosis-only pass.

---

## Core Rule

No red-capable command, no confident diagnosis.

A valid loop is:

- **Specific:** it asserts the user's symptom, not just "does not crash".
- **Runnable:** it can be run unattended by the agent.
- **Deterministic enough:** it gives the same verdict, or raises a flaky
  reproduction rate high enough to debug.
- **Fast enough:** seconds if possible; narrow minutes only when the system
  genuinely requires it.

When no loop can be built, stop and report what was tried. Ask for the missing
artifact or access: logs, HAR, trace, core dump, screen recording with
timestamps, fixture input, or permission to add temporary instrumentation.

---

## Phase 1: Build the Feedback Loop

Read local context first: `CONTEXT.md`, `CLAUDE.md`, nearby ADRs, failing test
docs, and the smallest relevant source area.

Try loop shapes in this order:

1. Existing failing test narrowed to the bug.
2. New regression test at the seam that reaches the real bug path.
3. CLI invocation with fixture input and expected output.
4. Curl or HTTP script against a running dev server.
5. Headless browser script with DOM, console, or network assertions.
6. Replay of a captured trace, request, event log, or payload.
7. Throwaway harness that calls the smallest real code path.
8. Property, fuzz, stress, or repetition loop for nondeterministic bugs.
9. Differential loop against an older version, config, dataset, or commit.
10. Human-in-the-loop script only when a manual click is unavoidable.

Record the exact command and one observed result before moving on.

### Tighten the Loop

Make the signal sharper before expanding the search:

- Assert the exact symptom.
- Cut setup cost.
- Pin time, random seed, locale, environment, and filesystem paths when useful.
- Remove unrelated services, data, and initialization.
- For flaky bugs, run repeated attempts and report the reproduction rate.

---

## Phase 2: Reproduce and Minimize

Run the loop and watch it fail for the right reason.

Confirm:

- The observed failure matches the user's symptom.
- The failure reproduces across repeated runs, or has a measured flaky rate.
- The error text, bad output, timing, or UI state is captured.

Minimize one variable at a time: input, config, caller, data, service, or timing.
Keep only load-bearing elements. Do not discard the original unminimized loop;
it is the final verification command.

---

## Phase 3: Hypothesize

Create 3-5 ranked, falsifiable hypotheses before changing code.

Use this format:

```text
If <cause> is true, then <probe/change> should make <observable> change.
```

Surface the ranked list when useful, but do not block progress if the user is
not present. Test the highest-value falsifiable probe first.

---

## Phase 4: Instrument

Probe one variable at a time. Prefer debugger or REPL inspection when available;
otherwise add targeted logs at boundaries that distinguish hypotheses.

For temporary logs:

- Prefix every line with a unique tag such as `[DEBUG-7c4a]`.
- Keep the probe small.
- Remove every tagged line before handoff.

For performance regressions, measure before fixing. Capture baseline timing,
profiler output, query plan, flamegraph, or benchmark output, then compare after
the change.

---

## Phase 5: Fix and Lock Down

When a correct seam exists:

1. Turn the minimized repro into a failing regression test.
2. Run it and confirm it fails for the expected reason.
3. Apply the smallest fix that explains the evidence.
4. Run the regression test.
5. Run the original Phase 1 loop.

If no correct test seam exists, document that as part of the finding and still
verify with the original loop. Do not add a shallow test that cannot catch the
real failure mode.

---

## Phase 6: Cleanup and Handoff

Before declaring done:

- Re-run the original loop and report the command.
- Run the regression test or explain why no correct seam exists.
- Remove temporary debug logs and throwaway harnesses, unless they were
  intentionally promoted to tests or documented tools.
- State the confirmed cause and why the fix addresses it.
- Note what would have prevented the bug: test coverage, guardrail, type,
  schema, observability, or architecture change.

If the same blocker repeats after real attempts, stop with the exact missing
artifact or access needed rather than inventing a diagnosis.
