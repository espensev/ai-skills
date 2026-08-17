---
name: repo-conventions
description: "Follow the target repository's established conventions before applying fallback guidance for API design, backend or frontend structure, Playwright E2E tests, current research, or a bounded local work cycle. Use when implementing or reviewing one of those areas; do not use when a more specific installed skill owns the task."
---

# Repository Conventions

Start with the repository's actual contracts. Framework-shaped advice is a
fallback, not authority to overwrite an established design.

## Repository-First Workflow

1. Read the nearest `AGENTS.md`, `CONTRIBUTING.md`, project configuration, and
   relevant architecture or test docs.
2. Inspect two or three nearby examples in the same subsystem.
3. Identify the established naming, layering, error, state, test, and tooling
   conventions that constrain the change.
4. Select the narrow playbook below. Apply its fallback rules only where the
   repository is silent or demonstrably inconsistent.
5. Implement the smallest coherent change and verify it with the repository's
   own commands.
6. Report the convention followed, any deliberate exception, verification, and
   remaining risk.

If repository guidance conflicts, call out the conflict and prefer the most
local current authority. Do not quietly invent a third convention.

## Capability Map

This table makes the consolidation auditable. Each former section has one
destination in this skill.

| Former skill / section | Destination here |
|---|---|
| `api-design` / Start Here | Repository-First Workflow |
| `api-design` / Core Rules | API Contracts / Core rules |
| `api-design` / Resource Design | API Contracts / Resources and queries |
| `api-design` / Response Design | API Contracts / Responses and errors |
| `api-design` / Versioning | API Contracts / Compatibility and security |
| `api-design` / Security and Reliability | API Contracts / Compatibility and security |
| `api-design` / Deliverable | Output Contract |
| `backend-patterns` / Workflow | Backend Structure / Workflow |
| `backend-patterns` / Design Rules | Backend Structure / Design rules |
| `backend-patterns` / Review Checklist | Backend Structure / Review checks |
| `backend-patterns` / Deliverable | Output Contract |
| `frontend-patterns` / Workflow | Frontend Structure / Workflow |
| `frontend-patterns` / Design Rules | Frontend Structure / Design rules |
| `frontend-patterns` / Performance Rules | Frontend Structure / Performance |
| `frontend-patterns` / Accessibility Rules | Frontend Structure / Accessibility |
| `frontend-patterns` / Deliverable | Output Contract |
| `e2e-testing` / Dependencies | Browser E2E / Tooling |
| `e2e-testing` / Workflow | Browser E2E / Workflow |
| `e2e-testing` / Anti-Flake Rules | Browser E2E / Stability rules |
| `e2e-testing` / Review Checklist | Browser E2E / Review checks |
| `e2e-testing` / Deliverable | Output Contract |
| `deep-research` / Scope | Current Research / Scope and routing |
| `deep-research` / Dependencies | Current Research / Sources and tools |
| `deep-research` / Workflow | Current Research / Workflow |
| `deep-research` / Research Rules | Current Research / Evidence rules |
| `deep-research` / Deliverable | Output Contract |
| `loop` / Workflow | Bounded Local Cycle / Workflow |
| `loop` / When To Stay Local | Bounded Local Cycle / Stay local when |
| `loop` / When To Pull In Other Skills | Bounded Local Cycle / Route out when |
| `loop` / Execution Rules | Bounded Local Cycle / Rules |
| `loop` / Output Contract | Output Contract |

## API Contracts

### Core rules

- Reuse established resource names, envelopes, versioning, and authentication
  patterns.
- Use nouns for resources and verbs only for true actions.
- Use HTTP status codes semantically; do not return `200` for every outcome.
- Validate input before business logic and keep authentication distinct from
  authorization.
- Make write retry behavior explicit through idempotency and conflict handling
  where needed.

### Resources and queries

- Prefer plural resources and nest only where ownership is real.
- Put filtering, sorting, and pagination in query parameters.
- Prefer cursor pagination for large or append-heavy collections; use offsets
  when stable page numbers are a real product requirement.

### Responses and errors

- Keep success and error shapes stable across related endpoints.
- Return stable machine-readable error codes with useful human messages.
- Do not leak exceptions, SQL details, secrets, or stack traces.
- Include `Location` for newly created resources when appropriate.

### Compatibility and security

- Reserve new API versions for breaking changes and follow the repo's existing
  negotiation style before choosing URL-path versioning.
- Enforce authentication at the boundary and ownership or permission before
  returning protected resources.
- Apply rate limits where abuse is plausible and document asynchronous or
  eventually consistent states.

## Backend Structure

### Workflow

1. Inspect handler, validation, data-access, auth, middleware, logging, and job
   patterns already in use.
2. Match structure to real complexity: handler-first for small surfaces; split
   transport, parsing, business logic, and persistence as complexity grows.
3. Optimize data access before adding abstraction: avoid N+1 queries, select
   only needed fields, and batch or cache only with evidence.
4. Map failures deliberately and retry only genuinely transient operations.

### Design rules

- Prefer the simplest structure that stays clear and testable.
- Do not force repository or service layers into tiny codebases.
- Keep auth, rate limiting, logging, and stable error mapping at boundaries.
- Make background work explicit and observable.
- Treat caching as a consistency tradeoff, not a default.

### Review checks

- Is validation near the boundary?
- Is business logic separated from transport concerns where needed?
- Are data-access patterns efficient and testable?
- Are retries safe and bounded?
- Are secrets absent from source and logs useful for diagnosis?

## Frontend Structure

### Workflow

1. Inspect the design system, routing/data model, state choices, styling, and
   accessibility patterns.
2. Reuse existing primitives.
3. Keep state local until multiple surfaces truly share it.
4. Model loading, empty, error, and success states explicitly.
5. Build responsive and keyboard-accessible behavior into the first pass.

### Design rules

- Prefer composition over over-abstracted component trees.
- Respect established typography, spacing, motion, forms, and validation.
- Do not add `useMemo` or `useCallback` by default; follow the repository's
  React compiler or profiling guidance.
- Add stable test selectors only when user-facing queries are insufficient.
- Avoid animation that hides state transitions or slows interaction.

### Performance

- Optimize measured render or bundle problems, not guesses.
- Code-split heavy surfaces and virtualize only genuinely long lists.
- Avoid client state when server rendering or loader data is the better fit.

### Accessibility

- Preserve focus order and complete keyboard access.
- Prefer semantic elements, label controls, and expose visual-only status
  changes to assistive technology.

## Browser E2E

### Tooling

- Use the target repo's Playwright runner, config, fixtures, app start command,
  auth helpers, and seeded data.
- Use browser tooling for interactive diagnosis when available; retain CLI
  traces, screenshots, and configured video as the portable fallback.

### Workflow

1. Reuse the existing test layout and fixtures.
2. Select elements by accessible role, label, text, or stable product contract.
3. Wait for specific visibility, response, URL, or semantic success states.
4. Keep assertions close to the user-visible effect.
5. Save artifacts that make a failure diagnosable.

### Stability rules

- Do not use arbitrary sleeps when a real condition exists.
- Do not hide deterministic bugs with global retries.
- Isolate tests from shared mutable data where practical.
- Introduce page objects or helpers only when they reduce real duplication.

### Review checks

- Does the test use the repo's server command and conventions?
- Are selectors intention-revealing and waits tied to system behavior?
- Does failure output preserve enough evidence to debug quickly?

## Current Research

### Scope and routing

Use this playbook for current market, vendor, standards, tool, or technology
decisions that need multiple sources. Use a documentation-specific skill for a
single library's API and an OpenAI-specific docs skill for OpenAI products.

### Sources and tools

- Built-in web search and direct source reading are sufficient.
- Specialized search or extraction tools are optional accelerators.
- Prefer primary sites, official docs, release notes, filings, standards, and
  reputable reporting.

### Workflow

1. State the decision and break it into a few sub-questions.
2. Search broadly, then narrow to primary or high-quality sources.
3. Prefer current evidence and label unavoidable older evidence.
4. Separate sourced fact, inference, and recommendation.
5. Synthesize a concise recommendation with citations near supported claims.

### Evidence rules

- Source every important externally verifiable claim.
- State when evidence is weak, mixed, inferred, or stale.
- Keep the source set tight and relevant.
- Do not delegate or parallelize research unless the user explicitly asks.

## Bounded Local Cycle

### Workflow

1. State one concrete objective and its done condition.
2. Read only the files needed for the current step.
3. Make the smallest coherent change.
4. Run the narrowest meaningful verification.
5. Reassess and continue or stop.

### Stay local when

- the blocker is one code path or tightly related file set;
- the next action is implementation, not broad research; and
- coordination would cost more than execution.

### Route out when

- `discover` is needed to establish a missing codebase fact;
- `qa` owns a meaningful verification checkpoint or failure triage;
- `planner` or `manager` is needed for a durable multi-agent campaign; or
- `ship` is needed after the user authorizes packaging or delivery.

### Rules

- Keep the immediate blocker in the main agent.
- Prefer targeted reads and one verified step over broad speculative edits.
- Stop when the objective is met, the remaining risk is external, or a real
  ambiguity changes scope or architecture.

## Output Contract

Return only the fields relevant to the selected playbook, plus:

1. repository convention followed and any deliberate exception
2. design or implementation result
3. verification command and result
4. edge cases, compatibility risk, or next risk

For API work include endpoint, method/status, request/response, auth,
idempotency, pagination, and breaking-change notes. For backend work include
layer boundaries, data/caching risk, and failure handling. For frontend work
include component structure, state/data flow, user states, and accessibility.
For E2E work include tests, startup assumptions, selectors/waits, and artifacts.
For research include recommendation, findings, tradeoffs, assumptions, and
source links. For a bounded cycle include objective, current result, changed
files, verification, and reason for stopping.
