---
name: handoff
description: "Use when the session opens by pointing back at earlier work instead of describing new work: resume, continue, take over, follow up, pick this up, read the handoff, or a path to a handoff/state/plan file. Reconstructs the prior state from the memory store and the repo, verifies every checkable claim in it, and states what to do next before touching anything. Do not use for a fresh task with no prior state, or to perform the resumed work itself - it routes, it does not build."
{{#claude}}
argument-hint: "[<handoff path>] - or nothing, to find the state yourself"
allowed-tools: Read, Glob, Grep, Bash
user-invocable: true
{{/claude}}
---

# Handoff {{dash}} Resume Intake

An opener like `resume work`, `take over from the handoff`, or `follow up` is
not a description of a task. It is a pointer to state you do not have. Load
that state and check it before acting {{dash}} never guess the task from the
opener alone.

**Output:** a short spoken summary {{dash}} where things stand, what is stale,
what to do next. No file, no edit.
**Default command:** `{{cmd}}handoff`
**Source edits:** none

---

## The rule that makes this skill worth running

**A handoff note is a claim, not a fact.** It was written before the last
things happened. Notes routinely say work is blocked when it landed, name a
branch that merged, or point at a file that moved.

Verify every checkable claim against the repo before you repeat it. Repeating
a stale note as current state is the failure this skill exists to prevent.

---

## Phase 1: Find the state

Work outward. Stop at the first layer that answers the question, but always do
Phase 2 on whatever you find.

1. **An explicit path.** If the user named a file, read that first.
2. **The memory store.** The remember-style layout is
   `<store>/projects/<project-slug>/` holding `now.md` (live buffer),
   `today-*.md` (daily), `recent.md` (7 days), `archive*.md` (older). Read
   newest first. Older archives are usually not preloaded {{dash}} grep them
   only when a question reaches past what you already have.
3. **Handoff files in the repo.** `HANDOFF.md`, `docs/handoffs/`,
   `docs/plans/`, `*handoff*.md`, `*-state.md`.
4. **The repo itself.** Recent commits, branch list, worktrees, dirty files:

```bash
git log --oneline -15
git status --short
git branch -a --sort=-committerdate | head -10
git worktree list
```

If nothing turns up in any layer, say so plainly and ask what to resume. Do
not invent a continuation.

---

## Phase 2: Verify before you repeat

For every concrete claim in the state you loaded, check it:

| Claim shape | Check |
|---|---|
| "landed at `<sha>`" / "committed" | `git show --stat <sha>` {{dash}} exists, and on which branch |
| "blocked on X" / "gate failing" | re-run the gate, or read the commit that supposedly failed |
| "branch `<name>` is in flight" | `git branch -a`, `git log --oneline <name> -5` {{dash}} merged? abandoned? |
| "file `<path>` has Y" | read the file {{dash}} it may have moved or changed |
| "next step is Z" | is Z already done in a later commit? |

Label each claim **confirmed**, **stale**, or **unverifiable**. Unverifiable is
its own class {{dash}} say what could not be checked and why, rather than
passing it through as fact.

If the store is wrong, say so and correct it. A stale note that stays uncorrected
will mislead the next session too.

---

## Phase 3: Reconcile and route

Report in this order:

1. **Where things actually stand** {{dash}} the verified picture, not the note's
   picture.
2. **What changed since the note was written** {{dash}} the stale claims,
   named.
3. **The open decision, if there is one** {{dash}} if the prior session stopped
   on a question the user never answered, that question is the top of the
   report, not a footnote.
4. **What to do next**, routed to the skill that owns it:

| Next step | Route |
|---|---|
| Read and critique a plan, doc, or the handoff itself | `{{cmd}}review --doc <path>` |
| Audit a branch or diff | `{{cmd}}review` |
| Land finished work | `{{cmd}}ship` |
| Run tests | `{{cmd}}qa` |
| Answer a bounded codebase question | `{{cmd}}discover` |
| Reproduce and fix one bug | `{{cmd}}diagnosing-bugs` |
| Fan out parallel lanes | `{{cmd}}manager` |
| Correct or prune the state store | `{{cmd}}memory-management` |

Then do the work, or ask if the open decision blocks it.

---

## Boundaries

- Do not start the resumed work inside this skill. Route to the owning skill,
  or hand back a clear next action.
- Do not merge, push, delete, or reset while reconstructing state. Phase 1 and
  2 are read-only.
- Do not treat an interrupted campaign as authorization to resume it. If the
  prior session was stopped by the user, surface that and ask.
