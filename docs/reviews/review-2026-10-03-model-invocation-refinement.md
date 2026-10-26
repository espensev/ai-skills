# Review: model-side skill invocation refinement

Date: 2026-10-03. Baseline: `1e0b5cb`, branch
`fix/ai-skills-online-followups-20260825`. Scope: review and refine the
packaged skills, especially the Claude package, adopting the Codex-side
conventions where they are better, so that the model selects skills itself
from ordinary task requests instead of relying on slash commands or the
operator's global routing table.

## Provider facts checked on 2026-10-03

Claude Code 2.1.288 documentation:

- Each turn Claude sees a listing of skill names with `description` and
  `when_to_use`; bodies load only on invocation. The listing shares a budget
  of one percent of the context window (fallback 8,000 characters), and above
  it Claude Code silently drops the descriptions of the least-used skills.
  The combined description text per skill is cut at 1,536 characters.
- `disable-model-invocation: true` removes the description from context
  entirely; `user-invocable: false` hides a skill only from the user.
  `skillOverrides` has four states, and only `on` (or no entry) keeps the
  description visible to Claude.
- `allowed-tools` pre-approves tools for the invoking turn and does not
  restrict anything. The docs warn that "a skill can grant itself broad tool
  access" and recommend permission settings for session-wide pre-approval.
- `agent-invocable` is not a frontmatter field; unknown keys are silently
  ignored. `metadata` is a free-form map that Claude Code ignores. The open
  spec and claude.ai upload cap `description` at 1,024 characters with no
  XML tags.

Codex 0.160.0 documentation and source (`openai/codex` at `8f7a0f7a`):

- The catalog shows name, description, and path, within two percent of the
  context window or 8,000 characters. Shortening is silent; omission warns.
  Disabled skills and skills with `allow_implicit_invocation: false` cost no
  budget. The catalog prompt tells the model it must use a skill whose
  description clearly matches the task.
- The parser reads only `name`, `description`, and `metadata`; unknown keys
  are tolerated. `[[skills.config]]` entries apply from user config only and
  select by `path` (or `name`). Explicit `$skill` injection truncates the body
  at 8,000 bytes, although the model is told to read `SKILL.md` fully.

## Findings and changes

1. **`manager` answered work requests with `status`.** The body said
   "Default to `status` if no command given", which is wrong when the model
   selects the skill from a request describing work. The default now applies
   only to invocation by name; a selected work request maps to `go` (or
   `plan` when the user wants to review the decomposition), a progress
   question maps to `status`, and a finished agent maps to `review`.
2. **Codex `ship` contradicted the delivery rule.** The Codex copy kept a
   push-confirmation fork ("always confirms with the user first", "the ONE
   command that requires user confirmation") that the Claude fix in `b27be87`
   never reached. The fork is collapsed: both providers push the current
   branch normally without a second confirmation, show what will be pushed,
   stop and preserve the local commit when authentication or ancestry is
   unclear, and push only to `origin` when an `upstream` remote exists. The
   skill also maps ordinary requests to commands (commit or land, push or
   deliver, what would be committed).
3. **Descriptions were not trigger-first.** `ship`, `memory-management`
   (both providers), and `skill-authoring` now start with "Use when", put the
   user's phrasing first, and end with one near-miss exclusion. The `ship`
   description is now shared rather than forked.
4. **`discover` had an unquoted description containing a colon.** A plain
   YAML scalar with `: ` fails to parse in strict parsers, which leaves the
   skill without a description. Both provider copies now quote it.
5. **`cc-workflow-builder` (Claude-only) exceeded the limits.** Its
   description was 1,154 characters with angle brackets and an unquoted colon.
   It is now 1,009 characters with neither, keeping the trigger phrases and
   schema constraints.
6. **Model-invocable Claude skills carried broad `allowed-tools` grants.**
   `discover`, `handoff`, `manager`, `memory-management`, `planner`, `qa`,
   `review`, `ship`, `codebase-design`, `telemetry-live-ops`,
   `resolving-merge-conflicts`, and `review-controller` pre-approved Bash,
   Edit, Write, or Agent for any turn in which the model chose them. Those
   grants are removed; ordinary provider permissions apply. `delegate` keeps
   its narrow MCP grants together with `disable-model-invocation: true`.
7. **Non-standard frontmatter keys.** `agent-invocable` is removed from
   `delegate`, `diagnosing-bugs`, `codebase-design`, and `telemetry-live-ops`.
   Provenance (`extracted-from`, `portable-since`) moved under `metadata` in
   `docs-sync`, `memory-management`, `smart-test`, and `usage-stats`.
8. **`skill-authoring` guidance.** Added the subcommand-mapping rule, the
   1,024-character and angle-bracket limits, the quoting rule, both providers'
   listing budgets, the Claude field list (`when_to_use`, `paths`,
   `metadata`), and the `allowed-tools` policy.
9. **Documentation.** `docs/local-agent-skill-access.md` now describes
   automatic selection for every packaged skill except `delegate`, the
   command mapping, the no-grant policy, and the four `skillOverrides` states
   with the listing budget.
10. **Contract tests.** Claude: every packaged skill without
    `disable-model-invocation: true` carries no `allowed-tools`, and no skill
    uses `agent-invocable` or top-level provenance keys; every description is
    at most 1,024 characters, has no angle brackets, and is quoted when it
    contains a colon. Codex: the same description test. Checked against the
    committed baseline: the new tests fail on the old `ship` grant, the old
    `cc-workflow-builder` length and brackets, the unquoted `discover`
    description, and the `delegate` key.

## Behaviour change for Claude users

In default permission mode, invoking `/ship`, `/qa`, `/review`, or the other
changed skills no longer pre-approves Bash, Edit, or Write for that turn, so
their commands prompt like any other tool call. Add `permissions.allow` rules
in settings when a workflow needs session-wide pre-approval. Bypass
permission mode is unaffected.

## Reported, not changed

- Codex user config (`D:\DevHome\state\codex\config.toml`) disables the
  canonical copies of `manager`, `planner`, `memory-management`, `discover`,
  and `browser-control`:

  ```toml
  [[skills.config]]
  path = 'D:\DevHome\state\codex\skills\manager\SKILL.md'
  enabled = false
  ```

  with matching entries for the other four paths. Those skills cannot be
  selected by Codex until the operator enables them. `ship` and
  `skill-authoring` are enabled (only duplicate copies under
  `D:\DevHome\state\agents\skills` are disabled).
- Claude `skillOverrides` set `planner`, `deep-audit`, `delegate`,
  `chief-operator`, `codebase-design`, `docs-clean`,
  `resolving-merge-conflicts`, and `cc-workflow-builder` to `off`. The
  installed Claude listing is roughly 6,100 characters of names and visible
  descriptions against an 8,000-character fallback budget; `review-controller`
  (580 characters) is the largest entry. Keep new descriptions under about
  450 characters.
- The operator's global `CLAUDE.md` routing table duplicates the
  descriptions. It lives outside this repository; trimming it is recommended
  once the probes below hold, because it biases selection and the probe
  prompts had to avoid its exact trigger words.
- `manager` is about 660 lines, so Codex explicit `$manager` injection
  truncates the body at 8,000 bytes. A router-plus-references split is a
  follow-up, not part of this change.
- A concurrent Codex session edited `scripts/measure_hook_cost.py`, its
  tests, and `docs/reviews/review-2026-10-03-automatic-skill-invocation.md`
  while this work was in progress. Its owner committed them as `888ca2f`, and
  its later controls review and fixtures as `de21d09`; this change stages
  none of them. The Codex skill root also has pre-existing drift in
  `scripts/skill_feedback_loop.py` that this change does not touch.
- The Codex account homes `D:\DevHome\state\codex-accounts\account3` and
  `account4` hold skill copies last refreshed on 2026-09-30. The check below
  reports nine drifted `SKILL.md` files per home, including `ship` with the
  old push confirmation and `manager` with the `status` default, and two
  missing `usage-stats` references. Sessions under those homes keep the old
  behaviour until refreshed:

  ```powershell
  .\scripts\Install-AgentSkills.ps1 -Provider Codex -CodexTargets `
    'D:\DevHome\state\codex-accounts\account3\skills', `
    'D:\DevHome\state\codex-accounts\account4\skills' -Check
  ```

  Rerun with `-Force` instead of `-Check` to update them. The duplicate copies
  under `D:\DevHome\state\agents\skills` are also stale, but Codex config
  disables them.

## Validation

- `Build-ProviderSkillPackages.ps1 -Check`: PASS, 51 files across 16 skills.
- `Compare-ProviderSkillParity.ps1 -FailOnUndeclaredFork`: PASS.
- Docs contract tests: Claude 23 and Codex 25, all PASS.
- `Test-ReleaseReadiness.ps1`: PASS. `git diff --check`: clean.
- Machine verifier: exactly one `VERIFIED` for `snd-desk`,
  `ca96d510-7d87-4cec-8e1a-bd8fc3866903`.
- Installed roots: Claude `-Force` refresh of all 17 manifest skills, `-Check`
  PASS; Codex `-Force` for the five changed skills, `-Check` reports only the
  pre-existing `skill_feedback_loop.py` drift.

## Fresh-session probes

Method: fresh `claude -p` (Opus 5.5) and `codex exec` sessions in throwaway
fixture repositories under `%TEMP%`, with ordinary prompts that name no skill
and avoid the trigger words of the operator's routing table. Selection is read
from the `Skill` tool call in Claude's `stream-json` output and from `SKILL.md`
reads in Codex's `--json` output. Codex ran its configured default model
(`gpt-6.1-sol` at low reasoning effort, per `config.toml`; the stream does not
name it) with `--sandbox workspace-write` for C1 and `read-only` otherwise.
Each prompt ran to completion once, with the operator's settings, hooks, and
global instructions active. Times are Claude's reported duration and Codex wall-clock
time.

- **P1, Claude `ship`: PASS.** Prompt: "The subtraction fix in calculator.py
  is validated and its tests pass. Get it into the repository history and out
  to origin." Claude selected `ship`, reran the tests, staged only
  `calculator.py`, committed, and pushed to the fixture's bare origin without
  asking for confirmation. The untracked `scratch.txt` stayed out of the
  commit. Seven turns, 38 seconds.
- **P2, Claude `manager`: selection and command mapping PASS.** Prompt:
  "Spread this across several isolated coding agents working at once and
  bring their results together: add type hints to each module in src and make
  sure the tests still pass." Claude selected `manager` and executed the work
  instead of reporting `status`: three Haiku agents in isolated worktrees
  under the central worktree root, one commit per module, a merge into
  `main`, a test rerun (3 passed), and worktree cleanup. The fixture had no
  manager backend, so the agents ran directly.
- **Probe permissions.** P1 and P2 passed `--allowedTools` only. That flag
  pre-approves tools and restricts nothing, and the operator settings default
  to `bypassPermissions`, so both runs had full tool access. A check with
  `--permission-mode default` confirmed that print mode then denies `Write`
  (recorded in `permission_denials`, no file created); the remaining probes
  use it.

- **P3, Claude `memory-management`: PASS.** Prompt: "For future sessions in
  this project, keep the fact that its tests must run with python -B because
  stale bytecode broke a run today. Put it where it belongs." Claude selected
  `memory-management` first. Default mode denied its write to a project
  `CLAUDE.md` and its run of the bundled audit script, so it saved a topic
  file and a `MEMORY.md` index line in the fixture's auto-memory directory,
  which Claude Code permits, and named the write it would have preferred.
  Eleven turns, 38 seconds.
- **P4, Claude `skill-authoring`: PASS.** Prompt: "Codex keeps picking the
  wrong one of our two testing skills; fix the triggering." Claude selected
  `skill-authoring`, not `qa` or `smart-test`. It compared the installed
  copies, checked the Codex `[[skills.config]]` entries, and aimed its edits
  at `skills-src/{qa,smart-test}/SKILL.src.md` rather than the generated
  copies. Both edits were denied; it proposed new descriptions with the
  rebuild, test, and reinstall steps and asked before changing anything.
  52 turns, 209 seconds.
- **P5, Claude control: PASS.** "What is 17 times 23?" selected no skill and
  used no tools: 391 in one turn.
- **C1, Codex `ship`: PASS.** The P1 prompt, pointed at `./shiprepo-codex`.
  Codex announced `ship`, read its `SKILL.md`, staged only `calculator.py`,
  committed, pushed to the bare origin, and left `scratch.txt` untracked
  without a confirmation request. It did not rerun the tests, citing the
  user's validation. 51 seconds.
- **C2, Codex `skill-authoring`: PASS.** The P4 prompt. Codex read
  `skill-authoring` first and reached the same diagnosis as P4; the read-only
  sandbox blocked edits, so it returned proposed descriptions. 56 seconds.
- **C3, Codex control: PASS.** The P5 prompt returned 391 with no skill read
  and no command. 23 seconds.
- **P6 and C4, `smart-test` versus `qa`: PASS.** With an uncommitted
  docstring edit in `src/alpha.py`, the prompt "Check only the tests that
  cover what I changed." selected `smart-test` in both providers, and both
  mapped the change to `tests/test_alpha.py` alone. Default mode denied
  Claude's test run (23 seconds); Codex ran that file read-only and it passed
  (48 seconds).

P4 and C2 both proposed adding a changed-file exclusion to `qa`: its
description ("the user wants tests run") names no `smart-test` boundary, while
`smart-test` excludes `qa`. Their prompt asserted a mis-selection that P6 and
C4 did not reproduce, so both descriptions are unchanged and the pair heads
the trigger-set follow-up below.

Negative controls for `docs-sync`, `smart-test`, `diagnosing-bugs`,
`skill-authoring`, and `usage-stats` ran in the concurrent
[invocation controls review](review-2026-10-03-invocation-controls.md), whose
tested entries match this commit; none of its fourteen negative runs selected
a skill.

After the probes the repository tree was clean, the Claude install check
passed, and the Codex check reported only the existing
`skill_feedback_loop.py` drift. Fixtures and raw streams remain under
`%TEMP%\aiskills-probe-20261003-042109` and are not committed.

## Follow-ups

- Split `manager` into a short router with `references/` so explicit Codex
  invocation injects the whole entry point.
- Trim the global `CLAUDE.md` routing table to the few entries whose
  behaviour differs from the descriptions.
- Decide whether to enable `manager`, `discover`, and `memory-management` for
  Codex; the config entries above are the only blocker.
- Build a 10 to 20 prompt trigger set per skill (explicit, implicit,
  contextual, negative) and run it with `codex exec --json` and
  `claude plugin eval` instead of ad hoc probes. Start with `qa` versus
  `smart-test` ("run the tests", "test my changes", "run the full suite") and
  change their descriptions only if the set shows a mis-selection.
