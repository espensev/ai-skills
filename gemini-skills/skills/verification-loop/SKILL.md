---
name: verification-loop
description: Mandates empirical reproduction and rigorous testing for all bug fixes and feature additions.
---

# Verification Loop Protocol

## Core Mandate
Validation is the only path to finality. You must empirically prove that your changes work and that no regressions were introduced. Assuming success is strictly prohibited.

## The Verification Cycle
1. **Pre-Execution (Reproduction):**
   - For bug fixes, you MUST reproduce the failure first. Write a failing test or a reproduction script and run it via `run_shell_command`.
   - Capture the error output to confirm you are solving the right problem.
2. **Implementation:**
   - Apply your surgical fixes or feature additions.
3. **Post-Execution (Validation):**
   - Re-run the reproduction script or test. It must now pass.
   - Run the broader project test suite (e.g., `dotnet test`, `npm test`, `pytest`) to ensure no regressions.
   - Run linter and formatting checks to verify structural integrity.
4. **Handling Failures:**
   - If verification fails, diagnose the error output, adjust your strategy, and repeat the Implementation/Validation steps until success is achieved. Do not ask the user for help unless you have exhausted all logical paths.
5. **Final Sign-Off:**
   - You may only declare the task complete once the full verification loop has succeeded.
