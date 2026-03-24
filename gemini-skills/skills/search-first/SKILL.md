---
name: search-first
description: Enforces a strict search-before-write policy to prevent duplicating existing logic, missing established patterns, or ignoring existing tests.
---

# Search-First Protocol

## Core Mandate
Never write new utility functions, UI components, or boilerplate code without first verifying that an equivalent does not already exist in the codebase. 

## The Search-First Loop
1. **Define the Need:** Identify the specific logic, component, or pattern you are about to implement.
2. **Execute the Search:**
   - Use `glob` to look for file names that might match (e.g., `*Button*`, `*StringUtils*`).
   - Use `grep_search` to look for function signatures, class names, or specific API usages.
3. **Analyze the Results:**
   - If a match is found, **reuse it**. Read the surrounding code to understand its intended usage and any required parameters.
   - If no match is found, proceed with implementation, but ensure your new code follows the style of similar existing modules.
4. **Test Discovery:**
   - Before modifying an existing file, search for its corresponding test file (e.g., if editing `UserService.cs`, search for `UserServiceTests.cs`).
   - You must read the existing tests to understand the current expected behavior before making modifications.
