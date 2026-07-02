---
name: diagnosing-bugs
description: "Build and use a tight feedback loop for hard bugs, failing tests, runtime errors, flaky behavior, and performance regressions. Use when the user asks to diagnose, debug, or fix something broken, throwing, failing, slow, flaky, or regressed."
---

# Diagnosing Bugs Protocol

## Core Mandate

Diagnose hard bugs by first building a command that can catch the user's exact
symptom. Do not jump to a theory before a red-capable loop exists.

## Execution Rules

1. **Build the loop first:** No red-capable command, no confident diagnosis.
2. **Match the user symptom:** The loop must assert the reported behavior, not
   just "does not crash".
3. **Minimize before fixing:** Shrink inputs, callers, data, config, services,
   and timing one variable at a time.
4. **Probe falsifiably:** Create 3-5 ranked hypotheses and test one prediction
   at a time.
5. **Verify the original:** After the fix, rerun the original unminimized loop.

## Feedback Loop

A valid loop is specific, unattended, deterministic enough, and fast enough to
iterate. Prefer these loop shapes:

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

Record the exact command and one observed result before moving past loop
construction.

## Reproduce and Minimize

Run the loop and confirm the failure is the right failure. Capture the error
text, bad output, timing, UI state, or reproduction rate. Then remove one
variable at a time and keep only load-bearing elements.

Do not discard the original scenario; it is the final verification command.

## Hypothesize and Instrument

Create ranked hypotheses in this format:

```text
If <cause> is true, then <probe/change> should make <observable> change.
```

Use debugger or REPL inspection when available. Otherwise add targeted logs at
boundaries that distinguish hypotheses. Prefix temporary debug logs with a
unique tag such as `[DEBUG-7c4a]` so cleanup is reliable.

For performance regressions, measure before fixing: baseline timing, profiler
output, query plan, flamegraph, or benchmark output.

## Fix and Lock Down

When a correct seam exists:

1. Turn the minimized repro into a failing regression test.
2. Confirm it fails for the expected reason.
3. Apply the smallest fix that explains the evidence.
4. Run the regression test.
5. Run the original feedback loop.

If no correct seam exists, document that limitation instead of adding a shallow
test that cannot catch the real failure mode.

## Output Contract

Every diagnosis or fix handoff must include:

- loop command and observed result
- minimized repro or reason it could not be minimized
- confirmed cause, or ranked hypotheses still under test
- fix summary, if a fix was applied
- regression test command, or why no correct seam exists
- original-loop verification result
- cleanup status for temporary logs and harnesses

If no loop can be built, stop and report what was tried plus the missing
artifact or access needed: logs, HAR, trace, core dump, screen recording with
timestamps, fixture input, or permission to add temporary instrumentation.
