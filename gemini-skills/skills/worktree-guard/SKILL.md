---
name: worktree-guard
description: Enforces read-only protection on specific project directories and runs the Verify-ReadOnly script to prevent unauthorized edits.
---

# Worktree Guard Protocol

## Core Mandate
Certain directories in the workspace are **independent product repositories** managed in their own worktrees. They must **never** be modified from the current workspace context.

## Protected Directories (Do Not Modify)
If you encounter these directories (or similar protected ones defined in the workspace), treat them as strictly **READ-ONLY**:
- `Coversight/`
- `Coversight_CodeName_Orange/`
- `Coversight_Win2DSkiaSharp/`
- `Coversight_WinUI_AA/`

> **CAUTION:** DO NOT create, edit, delete, rename, or move any file inside these directories. If changes are required, prompt the user to make them from the specific project's own workspace/worktree.

## Permitted Operations
- **Read-Only Analysis:** You may read schemas, routes, models, static files, and databases from protected directories.
- **Write Access:** You may only write to analysis scripts/tools (`Worktreemanagment/`), workflow templates (`Workflow-standardized/`), data snapshots (`data/`), and root-level config files (like `.gitignore`).

## Mandatory Verification
Before claiming task completion or finishing an edit session, you **must** verify that no protected files were accidentally modified by running:

```powershell
powershell -ExecutionPolicy Bypass -File Worktreemanagment\Verify-ReadOnly.ps1
```

If the script returns an exit code 1 (violations found), you must immediately revert the unauthorized changes before proceeding.
