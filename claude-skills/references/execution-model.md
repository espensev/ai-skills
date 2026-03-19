# Execution Model

## Goal

Run every refactor as a sequence of bounded campaigns, not one large rewrite. Each campaign should be small enough to complete, verify, and ship before starting the next.

## Campaign shape

Every campaign must have:

- **One goal statement** — a single sentence describing what changes when this campaign lands.
- **Explicit exit criteria** — a checklist that, when complete, means the campaign is done. No ambiguity.
- **2–4 parallel agents** with disjoint file ownership.
- **One integration pass** — a single agent or the orchestrator merges parallel work into a coherent whole.
- **One verification pass** — tests, linting, manual review, or whatever the project uses to confirm correctness.

## Ownership model

### Rules

- Every file or directory modified during a campaign has exactly one owner.
- Ownership is declared before work begins, not discovered during it.
- If two agents need to change the same file, restructure the work so one agent extracts a module and the other consumes it.
- Read access is unrestricted. Write access is exclusive.

### Recommended ownership splits

Adapt these to the project. Not all will apply.

| Owner | Typical scope |
|---|---|
| **contract-owner** | Interfaces, schemas, type definitions, API contracts, migration scripts |
| **core-owner** | Business logic modules, service extraction, domain layer |
| **transport-owner** | API routes, RPC layer, protocol adapters, client abstraction |
| **runtime-owner** | Entry points, startup, configuration, scheduling, deployment scripts |
| **ui-owner** | Frontend components, state management, transport client |
| **test-owner** | Test infrastructure, fixtures, CI configuration (not individual test files — those follow their module owner) |

### Resolving conflicts

If ownership is ambiguous:

1. Ask: "Who created this file's current shape?" — they likely own it.
2. Ask: "Who needs to change it most this campaign?" — assign ownership to them.
3. If still unclear, the orchestrator owns it and delegates specific changes.

## Sequencing

### Within a campaign

1. Spec and contract work first (blocking).
2. Parallel implementation work (non-blocking between agents).
3. Integration pass (blocking).
4. Verification pass (blocking).

### Between campaigns

- Each campaign's exit criteria must be met before the next campaign starts.
- Exception: if two campaigns have fully disjoint ownership and no shared dependencies, they can overlap.
- The orchestrator decides whether to overlap, not individual agents.

## Escalation

When an agent encounters something outside its write-set or beyond its scope:

1. Document the issue in the tracker with enough context for another agent to act.
2. Do not make the change yourself.
3. Continue with the rest of your work if possible.
4. If the blocker prevents all progress, mark your campaign status as blocked and specify what you need.

## Campaign sizing

- A campaign should take hours to days, not weeks.
- If a campaign feels too large, split it. The overhead of two small campaigns is lower than the risk of one that stalls.
- If a campaign has more than 4 agents, it is almost certainly too large.

## Completion protocol

When a campaign finishes:

1. Verify all exit criteria are met.
2. Update the tracker with: status, outcomes, any scope changes discovered.
3. Update the roadmap if the campaign revealed new phases or changed priorities.
4. Archive the campaign's agent specs (move to `agents/archive/` or mark as completed).
5. Begin planning the next campaign.
