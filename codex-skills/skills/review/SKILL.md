---
name: review
description: "Review a branch, pull request, worktree, staged diff, or fixed-point diff against repo standards, specs, and regression risk. Use when the user asks to review changes, audit work before merge, inspect a PR-style diff, or review since a commit/branch/tag."
---

# Review - Diff and Change Audit

Review changed work without modifying source files. Produce a findings-first
audit that separates documented-standard violations, spec mismatches, and
regression risks.

**Output:** `docs/reviews/review-{date}-{slug}.md`
**Default command:** `$review`
**Source edits:** none

---

## Commands

| Command | Usage | Purpose |
|---------|-------|---------|
| `branch` | `$review` or `$review <fixed-point>` | Review `HEAD` against a fixed point, usually the default branch merge-base |
| `working` | `$review --working` | Review unstaged and staged working-tree changes |
| `staged` | `$review --staged` | Review only staged changes |
| `spec` | `$review --spec docs/spec.md <fixed-point>` | Review against an explicit spec source |

Default to `branch` if no command is supplied.

---

## Review Principles

- Findings lead the report. Summaries and praise come after issues, never before.
- Every finding must cite concrete evidence: `file:line`, diff hunk, command
  output, or a quoted spec/standard line.
- Separate axes in the analysis:
  - **Standards:** documented project conventions, coding standards, and repo
    instructions.
  - **Spec:** explicit user request, issue, PRD, campaign plan, or task brief.
  - **Regression:** behavior that could break even when no standard or spec line
    covers it.
- Do not report preferences as defects. If no documented standard supports a
  style concern, call it a note or omit it.
- Do not fix issues in this skill. Recommend the next command (`$qa`, `$ship`,
  `$manager verify`, or direct implementation) after the review is complete.

---

## Phase 1: Resolve the Review Surface

Choose exactly one diff surface.

### Fixed-point review

If the user supplies a commit, branch, tag, or ref:

```bash
git rev-parse --verify <fixed-point>
git diff --stat <fixed-point>...HEAD
git diff --name-status <fixed-point>...HEAD
git log --oneline <fixed-point>..HEAD
```

If the ref does not resolve, stop and report the bad fixed point. If the diff is
empty, stop and report that there is nothing to review against that fixed point.

### Default branch review

If no fixed point is supplied, detect the default branch instead of hardcoding
`main`:

```bash
BASE=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||') || BASE="main"
git rev-parse --verify "origin/$BASE"
git diff --stat "origin/$BASE"...HEAD
git diff --name-status "origin/$BASE"...HEAD
git log --oneline "origin/$BASE"..HEAD
```

If the branch diff is empty but the working tree is dirty, ask yourself whether
the user asked for worktree review. If yes, switch to the working-tree surface;
otherwise report the empty branch diff and note the dirty worktree separately.

### Working-tree review

For `--working`:

```bash
git status --short
git diff --stat
git diff --name-status
git diff --cached --stat
git diff --cached --name-status
```

Review both unstaged and staged changes. Keep them labeled separately when a
finding depends on where the change lives.

### Staged review

For `--staged`:

```bash
git diff --cached --stat
git diff --cached --name-status
```

If there are no staged changes, stop and report that there is nothing staged to
review.

---

## Phase 2: Find Standards and Spec Sources

### Standards sources

Read any files that exist:

- `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`
- `CONTRIBUTING.md`, `CODING_STANDARDS.md`, `STYLEGUIDE.md`
- project conventions from `.codex/skills/project.toml` (`[project].conventions`)
- relevant docs under `docs/architecture/`, `docs/api/`, or `docs/testing/`

Only enforce standards that are documented or clearly established by nearby
code in the changed area.

### Spec sources

Look in this order:

1. explicit `--spec <path>` argument
2. user-provided issue, PRD, task brief, or campaign doc path
3. issue references in branch name or commits (`#123`, `GH-123`, `Closes #123`)
4. matching files under `docs/`, `specs/`, `agents/`, or `.scratch/`
5. the current user request, if no file exists

If no spec exists, continue with standards and regression review. Record
`Spec source: none found` in the report.

---

## Phase 3: Inspect the Diff

For each changed file:

1. Read the diff hunk and the surrounding source file.
2. Read direct tests or callers when the change touches behavior.
3. Classify risk:
   - public API, schema, config, auth, persistence, deployment, build, or test
     harness changes are high risk.
   - docs-only or comment-only changes are usually low risk unless they change
     documented commands, paths, or contracts.
4. Check the three axes:
   - Standards: does the change violate a documented project rule?
   - Spec: is something requested missing, partial, wrong, or extra?
   - Regression: could this break existing behavior, data shape, tests, or
     runtime assumptions?

For very large diffs, enumerate every changed file and state which files were
deep-reviewed versus sampled. Do not hide skipped files.

### Optional Local Delegation

If `$delegate` is installed and the diff is large, it may be used only for a
first-pass bounded review of already-fetched diff chunks. The controller must
verify every delegated observation before it becomes a finding.

---

## Phase 4: Run Lightweight Verification When Useful

Run read-only verification commands when they are cheap, relevant, and already
defined by the repo:

- targeted tests for changed code
- linters/typechecks for changed language surfaces
- doc link/path checks for docs-only changes

Do not turn this into full QA unless the user asked for it. If full verification
is needed, recommend `$qa run` or `$manager verify`.

Record every command run and its result. If you skip verification, explain why.

---

## Phase 5: Write the Review Report

Create `docs/reviews/` if needed and write:

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
`PASS` only when the reviewed surface has no findings and verification, if
relevant, did not fail.

---

## Completion Gate

The review is complete only when:

- the fixed point or worktree surface was validated and non-empty
- standards and spec sources were listed, including `none found` where true
- every finding has evidence and an axis label
- every changed file is either reviewed deeply or explicitly listed as sampled
  or excluded
- verification commands run or were explicitly skipped with a reason
- the durable report path is written and mentioned in the final response

