---
name: ship
description: Stage, commit, and optionally push validated work. Handles multi-file campaigns, commit grouping, message drafting, and exclusion of temp/sensitive files.
---

# Ship — Commit & Deliver

You package validated work into clean git commits. You handle staging, commit
message drafting, file grouping, and exclusion of files that should not be
committed.

**All commands run to completion autonomously except `push`, which always
confirms with the user first.**

**Config:** `.codex/skills/project.toml` — project-specific paths, commands, modules

## Commands

| Command | Usage | Purpose |
|---------|-------|---------|
| `commit` | `$ship` or `$ship commit` | Stage + commit all current changes as one commit |
| `split` | `$ship split` | Group changes by concern and create multiple commits |
| `preview` | `$ship preview` | Dry-run: show what would be committed without doing it |
| `push` | `$ship push` | Push current branch to remote (confirms first) |

Default to `commit` if no command given.

---

## Setup: Load Config

Before any command, load project configuration:

1. Read `.codex/skills/project.toml`
2. Extract `[modules]` for file grouping in `split` mode
3. Extract `[ship]` section for project-specific exclusions and warnings:
   - `exclude-extra` — additional paths to never commit (beyond universal exclusions)
   - `warn` — files to stage but flag for review
4. Read `.gitignore` for additional exclusions

If no project.toml exists, use the universal exclusion list and auto-discover
file groups from the directory structure.

---

## Command: `commit` — Single Commit

Stage all changes and create one well-structured commit.

### Steps:

1. **Survey the working tree:**
   ```bash
   git status --short
   git diff --stat HEAD
   ```

2. **Classify every file** into one of:

   | Category | Action | Examples |
   |---|---|---|
   | **ship** | Stage and commit | Source files, configs, docs |
   | **skip** | Do not stage | Temp files, build output, secrets, DB files |
   | **warn** | Stage but flag | Files from `[ship].warn` config |

   **Universal exclusions** (never commit, any project):
   - `__pycache__/`, `*.pyc` — Python bytecode
   - `.env`, `credentials.*`, `*.key`, `*.pem` — secrets
   - `node_modules/` — JS dependencies
   - `dist/`, `bin/`, `obj/` — build output
   - `*.db`, `*.db-wal`, `*.db-shm` — database files
   - Files matched by `.gitignore`

   **Project-specific exclusions** from `[ship].exclude-extra` in project.toml.

   **Warning files** from `[ship].warn` in project.toml.

3. **Stage files** by category. Use explicit file paths, not `git add -A`:
   ```bash
   git add <file1> <file2> ...
   ```
   For large sets, batch by directory:
   ```bash
   git add agents/*.md
   git add tests/test_*.py
   ```

4. **Draft the commit message.** Analyze the staged changes to determine:
   - **Type**: What kind of change (feature, refactor, fix, test, docs, chore)
   - **Scope**: Which area of the codebase
   - **Summary**: One-line description (under 72 chars)
   - **Body**: Bullet points of what changed and why

   Follow the project's existing commit style (from `git log`):
   ```
   <Summary line — what changed and why>

   - Bullet point details
   - Another detail
   ```

5. **Create the commit** using a HEREDOC for the message:
   ```bash
   git commit -m "$(cat <<'EOF'
   Summary line here

   - Detail 1
   - Detail 2
   EOF
   )"
   ```

6. **Verify:**
   ```bash
   git log --oneline -1
   git status --short
   ```
   Report the commit hash and any remaining unstaged files.

---

## Command: `split` — Multiple Commits by Concern

Group changes into logical commits, one per concern area.

### Steps:

1. **Survey** the working tree (same as `commit` step 1).

2. **Classify files into groups.** Use `[modules]` from project.toml if
   available — each module category becomes a commit group. If no module
   config exists, infer groups from directory structure:

   | Heuristic | Group Name |
   |---|---|
   | Root-level source files | `core` |
   | `tests/` directory | `tests` |
   | `docs/`, `*.md` in root | `docs` |
   | `scripts/` directory | `scripts` |
   | Config files (`.gitignore`, `requirements.txt`, etc.) | `infra` |
   | Other directories | Use directory name as group |

   If a file could belong to multiple groups, assign it to the one where it
   has the most impact. Prefer smaller, focused commits over large mixed ones.

3. **For each group** (in dependency order — infra first, state last):
   a. Stage only that group's files
   b. Draft a commit message specific to that group
   c. Create the commit
   d. Verify it succeeded

4. **Report** the full list of commits created:
   ```bash
   git log --oneline -N
   ```

### Group ordering:

Commit in this order so each commit builds on the previous:
1. `infra` — config, dependencies
2. Core source files (backend, libraries)
3. API / routing layer
4. Frontend / UI
5. Scripts / tooling
6. Tests
7. Documentation
8. Agent specs (if present)
9. State/tracker files (always last)

### Edge cases:

- If a group has only 1 trivial file, merge it into the nearest related group
- If all changes are in one group, fall back to a single commit (same as `commit`)
- Never create empty commits

---

## Command: `preview` — Dry Run

Show what would be committed without making any changes.

### Steps:

1. **Survey** the working tree.

2. **Classify** all files (ship / skip / warn).

3. **If `split` mode would apply**, show the proposed groups and commit messages.

4. **Report:**
   - Files to commit (with group assignments if splitting)
   - Files to skip (with reason)
   - Files to warn about
   - Proposed commit message(s)
   - Any issues (uncommitted secrets, large files, etc.)

Do not stage, commit, or modify anything.

---

## Command: `push` — Push to Remote

Push the current branch to the remote. **Always confirms with the user first.**

### Steps:

1. **Check remote status:**
   ```bash
   git remote -v
   git rev-list --count origin/main..HEAD 2>/dev/null
   ```

2. **Show what would be pushed:**
   ```bash
   git log --oneline origin/main..HEAD
   ```

3. **Ask the user for confirmation** before pushing. Show:
   - Number of commits
   - Branch name
   - Remote name
   - Any force-push risk

4. **On confirmation:**
   ```bash
   git push -u origin <branch>
   ```

5. **Report** the push result.

### Safety rules:
- **Never force-push** unless the user explicitly requests it
- **Never push to main/master** without warning the user
- **Always show** what will be pushed before doing it
- This is the ONE command that requires user confirmation

---

## File Classification

### Universal exclusions (never stage):
- `__pycache__/`, `*.pyc` — bytecode
- `.env`, `credentials.*`, `*.key`, `*.pem` — secrets
- `dist/`, `bin/`, `obj/` — build output
- `node_modules/` — dependencies
- `*.db`, `*.db-wal`, `*.db-shm` — database files
- `.claude/worktrees/` — agent worktrees
- Files in `.gitignore`

### Project-specific exclusions:
Read from `[ship].exclude-extra` in project.toml. These are paths specific to
the project that should never be committed (temp directories, local config, etc.).

### Warning files:
Read from `[ship].warn` in project.toml. These files will be staged but flagged
for the user to review (state files, tracker files, etc.).

### Everything else:
Source files, configs, docs, tests — stage and commit normally.

---

## Conventions

- Follow the project's existing commit message style (check `git log`)
- Use HEREDOC for commit messages to preserve formatting
- Never skip git hooks (`--no-verify`)
- Never amend commits without explicit request
- Only include a co-author line if the project or user explicitly requires one
- Prefer specific `git add <file>` over `git add -A`
- Read the conventions file (`[project].conventions` in project.toml) for project style
