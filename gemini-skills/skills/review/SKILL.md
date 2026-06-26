---
name: review
description: Review a branch, pull request, worktree, staged diff, or fixed-point diff against repo standards, specs, and regression risk.
---

# Review Agent (Gemini Adapter)

Review changed work without modifying source files. Use Gemini's broad context
window to inspect the whole change surface, but keep writes limited to the
review report.

**Output:** `docs/reviews/review-{date}-{slug}.md`
**Source edits:** none

---

## Core Mandate

Evaluate a branch, staged diff, or working-tree diff across three axes:

- **Standards:** documented repo conventions and coding standards.
- **Spec:** the user request, issue, PRD, campaign plan, or task brief.
- **Regression:** behavior that could break even when no standard or spec line
  covers it.

Findings lead the report. Every finding needs concrete evidence such as
`file:line`, a diff hunk, command output, or a quoted spec/standard line.

---

## Resolve the Review Surface

Use exactly one surface:

- fixed point: validate `git rev-parse --verify <fixed-point>`, then review
  `git diff <fixed-point>...HEAD`
- default branch: detect `origin/HEAD`, then review `git diff origin/<base>...HEAD`
- working tree: review `git diff` plus `git diff --cached`
- staged only: review `git diff --cached`

Stop early on a bad fixed point or an empty selected diff. Do not continue into
spec or standards review when there is no selected change surface.

---

## Gather Sources

Read standards sources that exist:

- `GEMINI.md`, `AGENTS.md`, `CLAUDE.md`
- `CONTRIBUTING.md`, `CODING_STANDARDS.md`, `STYLEGUIDE.md`
- project conventions from a provider `project.toml` if present
- relevant docs under `docs/architecture/`, `docs/api/`, or `docs/testing/`

Find spec sources in this order:

1. explicit `--spec <path>` argument
2. user-provided issue, PRD, task brief, or campaign doc path
3. issue references in branch name or commits
4. matching files under `docs/`, `specs/`, `agents/`, or `.scratch/`
5. the current user request

If no spec exists, continue with standards and regression review and record
`Spec source: none found`.

---

## Inspect and Verify

For every changed file, read the diff hunk and relevant surrounding source.
Use broad-context inspection for callers, tests, config, and contracts touched
by the change. Classify public API, schema, config, auth, persistence,
deployment, build, and test-harness changes as high-risk until inspected.

Run lightweight read-only verification commands when they are cheap and
defined by the repo, such as targeted tests, linters, typechecks, or doc path
checks. Do not perform fixes. If full QA is needed, recommend the `qa` skill.

Optional local delegation is allowed only for first-pass bounded summaries of
already-fetched diff chunks. Gemini remains responsible for verifying every
candidate finding before it reaches the report.

---

## Required Report

Write `docs/reviews/review-{date}-{slug}.md`:

```markdown
# Review - {Title}

**Date:** YYYY-MM-DD
**Surface:** {fixed point / working tree / staged}
**Spec source:** {path or none found}
**Standards sources:** {files}
**Verdict:** PASS | PASS WITH NOTES | FAIL

## Findings

### High
- [axis: regression|spec|standards] `file:line` - Problem.
  Evidence: ...
  Impact: ...
  Recommendation: ...

### Medium
...

### Low
...

If no findings: "No findings."

## Verification

- `{command}` - pass/fail/not run

## Coverage Notes

- Files reviewed deeply: ...
- Files sampled or excluded: ...

## Open Questions

- ...
```

Use `FAIL` when there is at least one high or medium finding that should block
merge. Use `PASS WITH NOTES` for low-severity findings or unverified risk. Use
`PASS` only when there are no findings and relevant verification did not fail.

The review is complete only after the report is written and the final response
names the report path.

