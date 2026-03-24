---
name: security-scan
description: Audits PowerShell automation scripts for safe execution policies and prevents destructive commands against protected repositories.
---

# Security Scan Protocol (PowerShell Tooling)

## Core Mandate
All local workspace tooling and automation must be written in PowerShell (`.ps1`). This skill ensures these scripts are safe, non-destructive, and respect the read-only boundaries of protected worktrees.

## Pre-flight Audit Requirements
Before executing or finalizing any PowerShell script (especially in `Worktreemanagment/`):

1. **Execution Policy:** Ensure scripts are invoked with `powershell -ExecutionPolicy Bypass` only when necessary and documented. Do not permanently alter system-wide execution policies.
2. **Worktree Protection:** 
   - Scan the script for commands like `Remove-Item`, `Set-Content`, `Move-Item`, or `git clean`, `git reset` that target protected directories (`Coversight/`, etc.).
   - If destructive commands target protected paths, the script is **INVALID**.
3. **Safe Defaults:**
   - Use `-WhatIf` and `-Confirm` parameters during testing of destructive commands on allowed directories.
   - Avoid hardcoding absolute paths; use relative paths based on the workspace root.
4. **Verification:** Ensure the script plays nicely with `Verify-ReadOnly.ps1`. Scripts must not bypass the read-only verification checks.
