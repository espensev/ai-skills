---
name: codebase-onboarding
description: A systematic workflow for exploring and understanding a new or unfamiliar codebase before attempting any changes.
---

# Codebase Onboarding Protocol

## Core Mandate
When entering a new project or addressing a broad request in an unfamiliar area, you must build a mental map of the system before modifying files. Guesswork is prohibited.

## The Onboarding Steps
1. **Identify the Rules:**
   - Look for `GEMINI.md`, `CLAUDE.md`, `AGENTS.md`, or `CONTRIBUTING.md`.
   - Read these files first. They contain the non-negotiable rules for the workspace.
2. **Locate the Truth:**
   - Find where schemas, environment variables, and configurations are defined (e.g., `.vibecheck/truthpack/`, `schema.prisma`, `docker-compose.yml`).
   - Understand the single sources of truth.
3. **Map the Architecture:**
   - Use the `list_directory` tool on the root and key source folders (e.g., `src/`, `lib/`, `app/`).
   - Identify the entry points (e.g., `Program.cs`, `main.go`, `index.ts`).
4. **Understand the Boundaries:**
   - Check `.gitignore` or workspace configuration to identify read-only or protected directories.
   - Do not cross architectural boundaries without explicit justification.
5. **Summarize and Plan:**
   - Only after this exploration, formulate your strategy. Share a concise summary of your findings before moving to execution.
