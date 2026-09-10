---
name: handoff
description: "Use when the session opens by pointing back at earlier work instead of describing new work: resume, continue, take over, follow up, pick this up, read the handoff, or a path to a handoff/state/plan file. Reconciles the latest user direction with the prior state, verifies the claims the next action relies on, and continues through the workflow that owns the work. Do not use for a fresh task with no prior state, or for handoff authoring."
argument-hint: "[<handoff path>] - or nothing, to find the state yourself"
allowed-tools: Read, Glob, Grep, Bash
user-invocable: true
---

# Handoff — Resume Intake

An opener like `resume work`, `take over from the handoff`, or `follow up` is
not a description of a task. It is a pointer to state you do not have. Load
that state and check it before acting — never guess the task from the
opener alone.

**Output:** a brief status — where things stand, which claims are stale,
and the next authorized action. Intake is read-only; the work continues
through the workflow that owns it.
**Default command:** `/handoff`
**Source edits:** none during intake

---

## The rule that makes this skill worth running

**A handoff note is a claim, not a fact.** It was written before the last
things happened. Notes routinely say work is blocked when it landed, name a
branch that merged, or point at a file that moved. Its next step also does
not override later user direction.

Verify every claim you rely on or report as current before you repeat it.
Repeating a stale note as current state is the failure this skill exists to
prevent.

---

## 1. Establish the current scope

- Read the latest user direction first. Explicit priorities, exclusions,
  existing authorization, and cancellation decisions come before the old plan.
- Identify the requested outcome and the prior claims needed to act on it. Do
  not revive deferred work just because an old `Next gate` lists it first.
- When the user asks to park other findings, route a concise durable note into
  the requested documentation work — evidence, ownership boundaries,
  remaining questions, and the next gate. Keep it out of the active task.

---

## 2. Find the authoritative state

Start with an explicit path or the injected current handoff. Prefer the current
project tracker over an older recap. Search outward only as far as needed, and
always run step 3 on whatever you find.

1. **The named handoff, state, or plan file.**
2. **The bounded Remember project store** at
   `<store>/projects/<project-slug>/`: `remember.md` (current handoff),
   `now.md` (live buffer), then relevant `today-*.md` or `recent.md`. Search
   older `archive*.md` only when the request reaches beyond current context.
3. **Handoff files in the repo.** `HANDOFF.md`, `docs/handoffs/`,
   `docs/plans/`, `*handoff*.md`, `*-state.md`.
4. **The repo itself.** Recent commits, branch list, worktrees, dirty files:

```bash
git log --oneline -15
git status --short
git branch -a --sort=-committerdate | head -10
git worktree list
```

Use provider-native memory only under its supplied read policy. Do not
recursively read all stores, transcripts, skills, or historical audit
artifacts by default.

If no usable state exists in any layer, say so plainly and ask one concise
question about what to resume, while continuing any independent work the
current request makes clear. Do not invent a continuation.

---

## 3. Verify the claims the next action relies on

Check current scope and ownership before editing. Classify each relied-on
claim as **confirmed**, **stale**, or **unverifiable**. Unverifiable is its own
class — say what could not be checked and why, rather than passing it
through as fact.

| Claim shape | Check |
|---|---|
| "landed at `<sha>`" / "committed" / "merged" | `git show --stat <sha>`; current branch ancestry |
| "branch `<name>` is in flight" | `git branch -a`, `git log --oneline <name> -5` — merged? abandoned? |
| "file `<path>` has Y" | read the file, or compare its recorded hash — it may have moved |
| "installed behavior matches source" | the actual runtime, selected configuration, and source/runtime hashes |
| "blocked on X" / "gate failing" | does the blocking condition still apply to the current request? re-run the gate if so |
| "gate passed" | reuse a receipt whose inputs and environment still match; rerun when inputs changed |
| "next step is Z" | the latest tracker and later commits — is Z already done? |

`shell/powershell/scripts/Test-HandoffNote.ps1` performs the commit / branch /
path / test rows of this table mechanically and already ran at session start
for the current project; read its `stale` rows first, then verify the
remaining prose claims by hand.

Refresh volatile runtime, machine identity, trust, authentication, and branch
facts before actions that depend on them. A source test or administrative
probe does not prove interactive runtime adoption. Preserve unrelated dirty
work.

Keep verification proportional: verify every claim you rely on or report as
current, without rerunning historical campaigns unrelated to the next action.
Name any practical verification limit instead of silently promoting old
results.

If the store is wrong, say so. A stale note that stays uncorrected will
mislead the next session too; correct it within the authorized follow-on task.

---

## 4. Reconcile and continue

Report in this order, briefly:

1. **Where things actually stand** — the verified picture, not the
   note's picture.
2. **What changed since the note was written** — the stale claims,
   named.
3. **The open decision, if there is one** — if the prior session stopped
   on a question the user never answered, that question is the top of the
   report, not a footnote.
4. **What to do next**, routed to the workflow that owns it:

| Next step | Route |
|---|---|
| Read and critique a plan, doc, or the handoff itself | `/review --doc <path>` |
| Audit a branch or diff | `/review` |
| Land validated work | `/ship` |
| Run tests | `/qa` |
| Answer a bounded codebase question | `/discover` |
| Reproduce and fix one bug | do it directly in this session: reproduce, fix, test |
| An explicitly requested multi-agent campaign | `/manager` — never for ordinary resumed work |
| Correct or prune the state store | `/memory-management` |

Carry existing user authorization forward; do not ask for it again just
because a session resumed. Honor an explicit prior stop or cancellation unless
later direction supersedes it.

Then do the work in this same session. Intake alone is not completion, and
naming the next gate is not an outcome — stop only when an unanswered
decision genuinely blocks the work, and never treat an ordinary commit, push,
or merge as that gate.

---

## State and publication boundaries

- Steps 1—3 are read-only. Do not merge, push, delete, or reset during
  intake; delivery follows the resumed task's authorization and ownership
  checks.
- Do not treat an interrupted campaign as authorization to resume it. If the
  prior session was stopped by the user, surface that and ask.
- A bounded Remember handoff and provider-native memory are separate. Native
  memory updates require an explicit user request and the prescribed update
  route; `/memory-management` governs that route.
- An active relay draft instruction selects the handoff destination. Its
  canonical path is routing information, not a second write target. Follow
  the supplied authoring limits and draft-write ordering; never claim that a
  successful draft write proves publication.
- Reserve the handoff's next gate for the current priority. Link deferred work
  rather than compressing unrelated campaigns into it.

---

## Writing the next handoff

Every `[verified]` bullet names its check in backticks (a sha, a branch, a
path, or a `X.Tests` name) so the verifier can prove it. A claim with no
possible check goes under Open risks with its basis, never under Verified
state: the relay drops bullets tagged unverified, and the verifier reports
tokenless verified bullets as uncheckable.
