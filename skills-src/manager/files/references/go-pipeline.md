# `go` — Full Autonomous Pipeline

This is the highest-autonomy command. It runs the entire lifecycle without user
input:

1. **Analyze** the codebase (`analyze`)
2. **Design** agent breakdown
3. **Register** agents in the plan (`plan`)
4. **Auto-approve and execute** the plan
5. **Fill in all spec files** with complete instructions
6. **Launch** group 0 agents immediately (`run`)
7. **Auto-advance** through subsequent groups as agents complete
8. **Merge** all agent worktrees into main (`merge`)
9. **Verify** builds, tests, and readiness (`verify`)
10. **Deliver** the validated campaign (providers whose delivery contract
    includes autonomous commit and push; otherwise stop at the verified state
    and report the remaining gate)

Internally this prefers the backend lifecycle: `plan` → backend `go`.

## Phase ownership

- Phases 1–5 follow the `analyze` and `plan` sections of SKILL.md and the
  planning details in [planning-handoff.md](planning-handoff.md).
- Phases 6–7 follow the `run` loop in [run-and-merge.md](run-and-merge.md).
- Phase 8 follows the `merge` procedure in
  [run-and-merge.md](run-and-merge.md).
- Phase 9 follows the `verify` phases in [verify.md](verify.md).
- Phase 10 follows the provider's delivery contract; the manager entrypoint
  states the delivery rule that applies to this provider.

## Non-interactive emphasis

During `go`, treat the user's invocation as full authorization: no approval
requests, no stopping after planning unless a real blocker exists, no TODOs
left in specs or plans, and no hand-mutation of runtime state when a
task-manager command exists. A failed agent is marked failed and the pipeline
continues; the final summary lists completed, failed, and blocked agents, and
reports any post-merge verification blocker instead of silently retrying broad
workflows. If required tooling or repository state is missing, report the
exact blocker including the command or file that prevented completion.
