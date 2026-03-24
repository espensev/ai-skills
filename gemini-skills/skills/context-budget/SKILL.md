---
name: context-budget
description: Strategies for minimizing token usage and maximizing context efficiency during complex tasks.
---

# Context Budget Protocol

## Core Mandate
Your context window is your most precious resource. Every file you read and every search result you return consumes tokens and increases the cost of subsequent turns. You must operate surgically.

## Efficiency Guidelines
1. **Search, Don't Scroll:**
   - Prefer `grep_search` to find specific symbols or keywords rather than reading entire files.
   - Limit `total_max_matches` and use `include_pattern` to narrow the scope of your searches.
2. **Surgical Reads:**
   - When using `read_file` on large files, ALWAYS use `start_line` and `end_line` to read only the relevant methods or classes.
   - If you only need to see imports or exports, read the top or bottom 50 lines.
3. **Avoid Unnecessary Output:**
   - When using `run_shell_command`, append quiet flags (e.g., `npm install --silent`, `git --no-pager`, `> /dev/null`).
   - Do not print large JSON payloads, logs, or unminified code into the chat unless explicitly requested.
4. **Parallel Execution:**
   - Perform independent searches or reads concurrently to save conversation turns.
5. **Consolidate Memory:**
   - If you discover important architectural patterns, summarize them concisely in your plan rather than keeping multiple large files open in your working memory.
