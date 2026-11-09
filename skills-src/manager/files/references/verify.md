# `verify` — Post-Merge Validation

Validates the merged codebase and assesses readiness for the next campaign.
Runs autonomously after backend `go` reaches merge completion (or standalone
any time).

Read the provider context's `project.toml` for the project's build/test/compile
commands.

### Phase 1: Build + compile checks

Run the compile command from `[commands].compile` in project.toml (with `{files}`
expanded to the active plan's owned files). If `[commands].build` is configured,
run that too.

Report any failures immediately.

### Phase 2: Full test suite

Run the test command from `[commands].test` in project.toml. If you explicitly
request `verify --profile fast` or `verify --profile full`, the backend will
prefer `[commands].test_fast` or `[commands].test_full` when configured and
fall back to `[commands].test` otherwise.

All tests must pass. If failures exist, report them with file:line and the
failing assertion. Do not proceed to Phase 3 until builds and tests are green
(or failures are clearly pre-existing).

### Phase 3: Exit criteria verification

Get the canonical exit criteria from the plan JSON:

```bash
python scripts/task_manager.py plan criteria --json
```

This returns the exit criteria from the latest valid executed/approved plan.
Surface those criteria in the verification report as the canonical acceptance
checklist for the campaign.

If `plan criteria` fails, report that no valid canonical plan is available for
exit-criteria verification. Do not reconstruct exit criteria from markdown.

The current backend verification gate is still command/task-state based: builds,
tests, task status, and merge readiness determine pass/fail. Do not claim that
the backend auto-proved each natural-language criterion unless you verified that
separately.

### Phase 4: Optional drift follow-up

If you need deeper drift review, treat it as a follow-up audit rather than part
of the backend pass/fail gate. Good manual follow-ups include campaign markdown
drift, tracker inconsistencies, and conventions docs that no longer match the
codebase.

### Phase 5: Stale state cleanup

```bash
python scripts/task_manager.py sync
```

Then check for:
- Tasks stuck in `running` state (no active worktree) — reset to `ready` or `done`
- Orphan worktrees (exist on disk but not in task state) — remove
- Draft plans that were never executed — report for cleanup consideration

### Phase 6: Readiness report

Produce a summary with:

- **Build status**: pass/fail
- **Test status**: N passed, N failed
- **Exit criteria**: N criteria surfaced from the canonical plan plus the overall backend gate result
- **Drift findings**: optional follow-up audit findings, if any
- **Stale state**: items cleaned up (or "none")
- **Blockers**: anything that would prevent the next `go` from succeeding
- **Observer flags**: if `data/observations.jsonl` contains recent `blocker` (warning), `regression` (failure), or `workaround` (warning/debt) observations
- **Feedback handoff**: which findings should stay local, enter the
  observation log, or become eval cases — recorded for future planning, not just
  mentioned in the current report

### Refactor-aware verification

When the active plan includes refactor elements (R1, R2, R3 from the planning
contract's refactor mode), verify adds these checks:

- **R2 — Behavioral invariants:** For each invariant listed in the plan, confirm
  the behavior is preserved (run the test or command that exercises it). Report
  any broken invariant as a verify failure.
- **R3 — Rollback strategy:** Confirm the rollback mechanism described in the
  plan is still viable (e.g., the backup branch exists, the migration has a
  down path). Report as a warning if rollback readiness cannot be confirmed.

### Integration with `go`:

The `go` command's full lifecycle is: `plan` → backend `go` → `merge` → `verify`.
If `verify` finds test failures or build errors after merge, it reports them
but does not attempt auto-fixes (that would exceed merge scope).

### Discovery-replan during execution

If during `run` or `merge` an agent reports a blocker that requires more
research (e.g., an undocumented API, an unexpected dependency):

1. Mark the agent as `failed` with a clear reason.
2. Continue with remaining agents (standard error recovery).
3. In the final summary, recommend the `discover` skill with a targeted
   question, followed by re-planning to address the gap.

Do not pause the entire pipeline for discovery — complete what can be completed,
then report what needs further research.

### Optional durable feedback

If the repo already keeps an observation log, or the user explicitly asks for a
feedback trail:

- record evidence-backed blockers, regressions, and drift in
  `data/observations.jsonl`
- refresh `docs/observer/project-intelligence.md` when the summary is stale
- append recurring blocker/regression patterns to the observation log so the
  next campaign starts from better evidence
- where the repository provides an observation-to-eval converter, convert those
  patterns into eval cases with it; if the converter is not present (for
  example a skills-only install without the runtime files), record the
  eval-case candidate in the observation entry or report instead.
