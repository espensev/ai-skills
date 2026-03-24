---
name: architecture-decision-records
description: Enforces the creation of Architecture Decision Records (ADRs) for significant architectural changes, specifically for C# and direct SQLite integrations.
---

# Architecture Decision Records (ADR) Protocol

## Core Mandate
Any significant structural change, especially involving C# UI architecture, direct SQLite data access patterns, or cross-project dependencies, requires an Architecture Decision Record (ADR) before implementation.

## ADR Trigger Criteria
- Introducing a new C# UI framework or pattern.
- Changing how the application directly accesses SQLite (e.g., switching ORMs or raw SQL patterns).
- Adding new top-level components or modifying the interaction between the UI and data layer.
- Moving or refactoring core workflow logic in `Workflow-standardized/` or `Worktreemanagment/`.

## ADR Process
1. **Draft ADR:** Before writing code, use the `enter_plan_mode` tool or write a draft ADR in a designated `docs/adr/` directory (create it if it doesn't exist).
2. **Format:** The ADR must include:
   - **Title:** Short, descriptive title.
   - **Status:** Proposed / Accepted / Rejected.
   - **Context:** What is the problem or need?
   - **Decision:** What is the proposed solution (e.g., C# / SQLite specific details)?
   - **Consequences:** What becomes easier or harder?
3. **Review:** Present the ADR to the user for approval.
4. **Implement:** Only proceed with code changes once the ADR is approved.
