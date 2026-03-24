---
name: backend-patterns
description: "Apply practical backend architecture patterns for handlers, validation, business logic, data access, caching, and background work. Use when implementing or refactoring server-side code and APIs."
---

# Backend Patterns

Structure backend code around the real complexity of the system. Do not import
architecture for its own sake.

## Workflow

1. Read the current backend shape:
   - route or handler structure
   - validation approach
   - data access layer
   - auth and middleware conventions
   - logging and background job patterns
2. Match the architecture to the codebase size:
   - simple handler-first code for small surfaces
   - split validation, business logic, and data access when complexity grows
3. Keep boundaries explicit where they help:
   - transport or handler logic
   - validation or parsing
   - domain or business logic
   - persistence or API clients
4. Optimize data access before adding abstraction:
   - avoid N+1 queries
   - fetch only needed fields
   - batch or cache where it matters
5. Handle failure deliberately:
   - stable operational errors
   - consistent error mapping at the boundary
   - retries only for genuinely transient failures

## Design Rules

- Prefer the simplest pattern that preserves clarity.
- Do not force repository or service layers into tiny codebases.
- Keep auth, rate limiting, and logging at system boundaries.
- Make background work explicit and observable.
- Treat caching as a consistency tradeoff, not a default.
- Preserve existing repo conventions unless they are actively harmful.

## Review Checklist

- Is the request validation close to the boundary?
- Is business logic separated from HTTP concerns where needed?
- Are data access patterns efficient and testable?
- Are transient failures retried safely?
- Are secrets and credentials kept out of source?
- Are logs structured enough to debug failures?

## Deliverable

When implementing or reviewing backend work, return:

1. chosen structure and why
2. boundaries between layers
3. query or caching risks
4. error-handling approach
5. verification steps
