---
name: review
description: "Use when the user asks for a findings-first review or asks you to review and advise — on a branch, pull request, worktree, staged diff, or fixed-point diff, or on a written artifact such as a plan, design doc, handoff note, spec, or proposal — against repo standards, specs, and regression risk. Do not use to implement a fix, run a test campaign (use qa), diagnose one bug (use diagnosing-bugs), or audit runtime efficiency (use deep-audit)."
{{#claude}}
argument-hint: "[<fixed-point>] — branch | --working | --staged | --spec <path> | --doc <path>"
allowed-tools: Read, Glob, Grep, Bash, Write
user-invocable: true
{{/claude}}
---

# Review - Change and Document Audit

Review changed work, or a written artifact, without modifying any source file.
Produce a findings-first audit that separates documented-standard violations,
spec mismatches, and regression risks.

**Output:** `docs/reviews/review-{date}-{slug}.md`
**Default command:** `{{cmd}}review`
**Source edits:** none

---

## Commands

| Command | Usage | Purpose |
|---------|-------|---------|
| `branch` | `{{cmd}}review` or `{{cmd}}review <fixed-point>` | Review `HEAD` against a fixed point, usually the default branch merge-base |
| `working` | `{{cmd}}review --working` | Review unstaged and staged working-tree changes |
| `staged` | `{{cmd}}review --staged` | Review only staged changes |
| `spec` | `{{cmd}}review --spec docs/spec.md <fixed-point>` | Review against an explicit spec source |
| `doc` | `{{cmd}}review --doc <path>` | Review a written artifact — plan, design doc, handoff note, spec, or proposal |

Default to `branch` if no command is supplied. If the user names a document,
plan, or handoff instead of a ref — "review and advise on this plan", "read the
handoff and review it" — use `doc` with that path.

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
- Do not fix issues in this skill. Recommend the next command (`{{cmd}}qa`, `{{cmd}}ship`,
  `{{cmd}}manager verify`, or direct implementation) after the review is complete.

---

## Phase 1: Resolve the Review Surface

Choose exactly one review surface — four are diffs, one is a document.

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

### Document review

For `--doc <path>`, or when the user points at a plan, handoff, spec, or
proposal rather than a ref:

```bash
test -f "<path>" && wc -l "<path>"
git log --oneline -5 -- "<path>"
```

Read the document in full before writing anything. There is no diff, so the
three axes bind to the document instead:

- **Standards:** repo instructions, `CLAUDE.md`/`AGENTS.md`, and the conventions
  the document itself claims to follow.
- **Spec:** what the user asked the document to accomplish, and what the
  document promises in its own opening.
- **Regression:** claims that are stale or already false. Verify every concrete
  assertion — a named file, commit, flag, or status — against the repo before
  accepting it. A handoff that says work is "blocked" when the commit landed is
  a finding, not context.

Cite by `path:line` in the document, plus the repo evidence that contradicts or
confirms each checkable claim. Unverifiable claims are their own finding class:
say what could not be checked and why, rather than passing them through.

---

## Phase 2: Find Standards and Spec Sources

### Standards sources

Read any files that exist:

- `{{ctx}}`, `{{ctx-other}}`, `GEMINI.md`
- `CONTRIBUTING.md`, `CODING_STANDARDS.md`, `STYLEGUIDE.md`
- project conventions from `.{{provider-lc}}/skills/project.toml` (`[project].conventions`)
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

If `{{cmd}}delegate` is installed and the diff is large, it may be used only for a
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
is needed, recommend `{{cmd}}qa run` or `{{cmd}}manager verify`.

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
{{#codex}}

{{/codex}}
