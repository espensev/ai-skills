# `status`, `new`, `review`, `next`, and the tracker file contract

## Command: `status`

```bash
python scripts/task_manager.py sync
python scripts/task_manager.py status
```

For a machine-readable lifecycle snapshot without mutating state:

```bash
python scripts/task_manager.py status --json
```

Use `status --json` as the passive inspection surface. Use `go --json` when you
need launch instructions or a lifecycle transition.

Add `graph` for dependency visualization:

```bash
python scripts/task_manager.py graph
```

---

## Command: `new`

Quick-add a single agent without the full plan workflow:

```bash
python scripts/task_manager.py add <letter> <name> --scope "..." --deps "..." --files "..."
python scripts/task_manager.py template <letter> <name> --scope "..."
```

Then fill in the spec file with Edit tool.

---

## Command: `review`

Skill-level workflow (no dedicated backend primitive — orchestrates existing
primitives and tools):

1. **Read** the agent spec (`agents/agent-<letter>-<name>.md`) and the agent's
   reported diff/changes (from `result` payload or worktree inspection)
2. **Run verification** steps listed in the spec's `## Verification` section
3. **Assess compliance**: do the changes satisfy the spec's scope and exit
   criteria?
4. **Mark complete** via backend:
   ```bash
   python scripts/task_manager.py complete <letter> -s "<one-line summary>"
   ```
   If the work does not meet criteria, mark failed instead:
   ```bash
   python scripts/task_manager.py fail <letter> -r "<reason>"
   ```
5. **Update tracker** file with a tracker entry (if tracker is configured)

---

## Command: `next`

```bash
python scripts/task_manager.py next
```

If agents are ready, **auto-launch them** — do not ask the user.

---

## Tracker File

The tracker file (configured in `[paths].tracker` in project.toml) is a
markdown file that records completed work across campaigns. It provides
continuity between campaigns so planners and managers can see what was done
recently.

**Format:** Markdown table with these columns:

```markdown
| ID | Status | Owner | Scope | Issue | Update |
|---|---|---|---|---|---|
| PROJ-001 | Done | agent-a | `src/app.py` | Add endpoint | Added /api/foo route |
```

**When to update:**
- After the `review` workflow marks an agent complete (step 5 of review)
- After `verify` passes (append a campaign summary row)
- After `go` completes the full lifecycle

**Who updates:** The manager (or the agent, if the spec includes a
post-completion tracker section). Never update the tracker before the work
is verified — tracker entries represent completed, validated work.

**Ship behavior:** the ship skill classifies the tracker file as a "warn" file —
it will be staged for commit but flagged for review.
