---
name: verification-loop
description: "Run a repo-appropriate build, lint, typecheck, test, and diff review sequence before handoff. Use after significant code changes, refactors, or before declaring a branch ready for review."
---

# Verification Loop

Verify work with the commands that actually belong to the repo. Do not assume a
Node-only workflow.

## Workflow

1. Detect the available verification surface from the repo:
   - package scripts
   - Python, .NET, Rust, Go, or other project files
   - existing CI commands
   - documented test commands
2. Run the strongest applicable sequence in this order:
   - build or compile, if relevant
   - typecheck or static analysis
   - lint or format check
   - tests
   - targeted smoke checks when the change affects a runnable surface
3. Stop on the first blocking failure unless the next step is needed to expose
   independent issues.
4. Review the diff after command checks pass.
5. Classify notable failures or repeated warnings into durable feedback:
   - local-only note if it is a one-off symptom
   - observation if it should influence the next run
   - eval case if it is a recurring regression or blocker
6. Report readiness with blockers, not vibes.

## Command Selection Rules

- Prefer repo-defined commands over hand-written substitutes.
- If multiple profiles exist, choose the fastest one that still validates the
  changed surface, then say what you skipped.
- Use `rg` for codebase scans when available; otherwise use the platform
  fallback.

## Quick Safety Checks

- Search for obvious secrets or credentials introduced by the change.
- Search for debug logging or temporary flags left behind.
- Check that changed files have tests or a stated reason they do not.
- Review migration, config, or deployment implications when relevant.

## Feedback Capture Rules

- Prefer explicit evidence: failing command output, diff lines, or user
  corrections.
- If the repo already uses observer artifacts, write concise entries to
  `data/observations.jsonl` and refresh
  `docs/observer/project-intelligence.md` only when the user asked for durable
  tracking or the repo already opted into it.
- When the same failure pattern should become a standing regression check, turn
  it into an eval case with:
  `python scripts/observe_to_eval.py --merge eval/cases/light-skill-cases.json`
- Do not generalize a broad new rule from a single flaky test or ambiguous log.

## Output

Return a compact report:

```text
VERIFICATION REPORT

Build: pass | fail | n/a
Types/Static: pass | fail | n/a
Lint/Format: pass | fail | n/a
Tests: pass | fail | n/a
Diff review: pass | fail
Overall: ready | not ready

Blocking issues:
- ...

Skipped checks:
- ...

Feedback:
- ...
```
