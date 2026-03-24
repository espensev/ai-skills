---
name: api-design
description: "Design consistent HTTP and REST APIs. Use when defining or reviewing endpoints, status codes, pagination, filtering, idempotency, error contracts, versioning, or authentication behavior."
---

# API Design

Design APIs that are predictable for clients and compatible with the existing
repo conventions.

## Start Here

1. Inspect the existing API surface first.
2. Reuse established naming, envelope, versioning, and auth patterns unless
   there is a clear reason to change them.
3. If the repo has no established convention, use the rules below.

## Core Rules

- Use nouns for resources and verbs only for true actions.
- Use HTTP status codes semantically; do not return `200` for every outcome.
- Validate inputs before business logic runs.
- Return stable error codes and human-readable messages.
- Paginate list endpoints.
- Make retry behavior clear for writes:
  - idempotency for unsafe operations when needed
  - conflict handling for duplicate or stale writes
- Separate authentication from authorization in both code and responses.

## Resource Design

- Prefer plural resource names.
- Use nested resources only when ownership is real and helpful.
- Keep filtering, sorting, and pagination in query parameters.
- Prefer cursor pagination for large or append-heavy collections.
- Prefer offset pagination when users truly need page numbers.

## Response Design

- Keep success shapes consistent across related endpoints.
- Keep error shapes consistent across the whole API.
- Do not leak internal exceptions, SQL details, or stack traces.
- Include location headers for newly created resources when relevant.

## Versioning

- Follow existing repo conventions first.
- If introducing explicit versioning, prefer URL-path versioning unless the
  platform already standardizes on header-based negotiation.
- Reserve new versions for breaking changes.

## Security and Reliability

- Enforce auth at the boundary.
- Check ownership or permission before returning protected resources.
- Apply rate limiting where abuse is plausible.
- Document eventual consistency or async completion states clearly.

## Deliverable

When asked to design or review an API, provide:

1. endpoint shape
2. method and status codes
3. request and response contract
4. auth and idempotency notes
5. pagination or filtering rules
6. edge cases or breaking-change risks
