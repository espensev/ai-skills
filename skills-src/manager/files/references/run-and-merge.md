# `run` launch loop and `merge` procedure

## Command: `run`

Launch agents in parallel isolated worktrees. **Always auto-advances through
all dependency groups until every agent is done or failed.**

### Pre-launch spec validation

Before launching any agent, validate all spec files for the agents about to run:

1. Read each spec file (`agents/agent-{letter}-{name}.md`)
2. Reject any spec that contains `TODO` placeholders — report the offending
   file and stop. The planner (or user) must fill the spec before launch.
3. Confirm the spec has a non-empty `## Task` section and a `## Verification`
   section with at least one command.

If any spec fails validation, report the issue and do not launch. This prevents
agents from starting work with broken or incomplete instructions.

### Steps:

1. **Get launch specs:**
   ```bash
   python scripts/task_manager.py go <plan-id> --json
   ```
   If the backend is waiting for execution, it outputs JSON with agent prompts.

2. **Parse the JSON.** For each agent in the `agents` array, launch it in an
   isolated worktree with the JSON `prompt` field as its task, honoring the
   JSON `model` field as the requested launch tier.

   Map the backend `model` tier to the provider's model lineup: `mini` → the
   provider's low-cost tier, `standard` → the normal general-purpose coding
   tier, `max` → the strongest available tier. Prefer the low tier for bounded
   background subagents, sidecar research, docs, and test-focused work when
   the task fits it — this preserves stronger-model budget for
   integration-heavy or ambiguous tasks. If the preferred model is
   unavailable, fall back to the closest stronger available model rather
   than blocking launch.

   **CRITICAL:** Launch ALL agents of a group together, in a single action, so
   they run in parallel.

3. **Report launch status.**

4. **As agents complete:**
   a. Parse `AGENT_RESULT_JSON` from output.
   b. Record the worktree metadata:
      ```bash
      python scripts/task_manager.py attach <letter> --worktree-path <path> --branch <branch>
      ```
   c. Record the structured result:
      ```bash
      python scripts/task_manager.py result <letter> --payload '<json>'
      ```
   d. Check for newly unblocked:
      ```bash
      python scripts/task_manager.py go <plan-id> --json
      ```
   e. **Auto-launch** any newly ready agents immediately (repeat from step 1).

5. **Continue the auto-advance loop** until no agents remain in `ready` or
   `running` state. Then report the final summary.

### Failure handling during run:

- If an agent fails, mark it failed and continue with other agents.
- If a failed agent blocks downstream agents, report the blocked agents in
  the final summary but do not halt the entire run.
- The final report should clearly list: completed, failed, and blocked agents.
- If verification fails after merge, report the concrete blocker and stop.
  Do not silently retry broad workflows.
- If required tooling or repo state is missing, report the exact blocker
  including the command or file that prevented completion.

---

## Command: `merge`

Merge completed agent worktrees into the main working tree. Runs autonomously.
Prefer backend `go` to drive merge automatically once no ready or running tasks
remain. Use standalone `merge` only when you need to inspect or re-run merge
state directly.

### Steps:

1. **Inventory worktrees:**
   ```bash
   git worktree list
   ```
   Identify all agent worktree paths and branches.

2. **Triage each worktree.** For every file the agent reported modifying:
   - `diff` the worktree version against main working tree
   - Classify as:
     - **no-op** — identical to main (0 diff lines). Skip entirely.
     - **clean** — main has no competing changes. Copy directly.
     - **conflict** — another agent or main also modified this file.

3. **Apply clean changes.** Copy files from clean worktrees to main.

4. **Resolve conflicts.** When multiple agents modified the same file:
   - Prefer the agent with the **later dependency** (integration agents
     are authoritative over the agents they reconcile).
   - If agents are in the same group (no dependency relationship), do a
     manual content merge keeping both changes.
   - Document the resolution in the merge report.

5. **Verify.** Run the test command from `[commands].test` in project.toml:
   ```bash
   python scripts/task_manager.py analyze --json  # to get test command
   ```
   If `[commands].build` is configured, run that too.

6. **Deliver before cleanup** (providers whose delivery contract includes
   autonomous delivery). Stage only campaign-owned validated files,
   create a focused commit (unless the campaign commits are already reachable),
   and normally push the current branch without another confirmation. If commit
   or push fails, preserve the worktrees and report the exact gate.

7. **Clean up only proven-safe worktrees.** Refuse dirty worktrees. Remove a
   worktree only when its branch is reachable from the delivered commit;
   preserve every unmerged branch:
   ```bash
   git worktree remove <path>
   git merge-base --is-ancestor <branch> HEAD && git branch -d <branch>
   ```

8. **Report summary.** For each agent: no-op / merged / conflict-resolved.
   Include test results, delivered commit and remote ref, preserved recovery
   worktrees, and any issues.

### Conflict resolution rules:

- **Integration agent wins** — if a later-group agent depends on earlier-group
  agents and they both touched the same file, the later agent's version is authoritative.
- **Test agent wins for test files** — test agents have final say on test file content.
- **Same-group agents** — manual merge, keep both contributions.
- **Never silently drop changes** — report every conflict and resolution.

### Observation promotion

After merging worktrees, check each merged worktree path for `observations.jsonl`.
If present, promote observations to the project-level log:

1. Read and parse the JSONL file from the worktree root
2. Append each observation to `data/observations.jsonl`
3. Report promoted observation count per worktree

This preserves execution-time signals (test results, build errors, churn,
blockers) that improve future planning.
