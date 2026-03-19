---
name: loop
description: Run a focused Codex work loop for one concrete objective. Use when the user wants steady autonomous progress on a bounded change through repeated inspect, edit, verify, and reassess cycles without spinning up a larger campaign.
---

# Loop

Use this skill for the next immediate chunk of work when the goal is clear enough to execute but still needs several local iterations.

## Workflow

1. State the concrete objective and what will count as done.
2. Read only the files needed for the current step.
3. Make the smallest change that advances the objective.
4. Run the narrowest meaningful verification.
5. Reassess the result and either continue the loop or stop.

## When To Stay Local

- The blocker is in one small code path or one tightly related file set.
- The next useful action is implementation, not broad research.
- Parallel agents would spend more time coordinating than executing.

## When To Pull In Other Skills

- Use `discover` if a missing codebase fact blocks a safe edit.
- Use `qa` when the loop reaches a meaningful verification checkpoint or failures need triage.
- Use `planner` or `manager` only when the work clearly expands into a multi-agent campaign.
- Use `ship` only after the user asks to package or push the finished change.

## Execution Rules

- Keep the immediate blocker local to the main Codex agent.
- Avoid broad scans when a targeted read or grep is enough.
- Prefer one verified step over several speculative edits.
- Stop and report once the objective is met, the remaining risk is external, or a real ambiguity changes scope or architecture.

## Output Contract

End each loop with a short status that includes:

- objective
- current result
- files changed
- verification run
- next risk or reason for stopping
