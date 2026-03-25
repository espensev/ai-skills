# File Map

Source-of-truth reference for every file in the campaign-skills runtime.

## Scripts

### `scripts/task_manager.py` (~2780 lines)

Main CLI entry point. All 20+ subcommands dispatch from here. Owns:

- **Configuration loading** — reads `.codex/skills/project.toml`, derives runtime paths
- **State persistence** — `load_state()` / `save_state()` wrapping `data/tasks.json`
- **Analysis orchestration** — `cmd_analyze()` with cache key computation and snapshot persistence
- **Plan lifecycle wiring** — `cmd_plan()` delegates to `task_runtime/plans.py` with local config bindings
- **Execution lifecycle** — `cmd_run()`, `cmd_result()`, `cmd_merge()`, `cmd_verify()`, `cmd_go()`
- **Agent registration** — `_new_task_record()`, `_empty_agent_result()`, `_empty_merge_record()`
- **Merge runtime** — `_merge_runtime()` copies files from worktrees, detects ownership conflicts
- **Verify runtime** — `_verify_runtime()` runs configured compile/test/build commands
- **Go orchestration** — `_go_runtime()` auto-advances through launch/merge/verify phases

### `scripts/task_runtime/`

Internal runtime support package. No pip dependencies — stdlib only.

| File | Lines | Purpose |
|------|-------|---------|
| `__init__.py` | ~86 | Module exports: `TaskRuntimeError`, `atomic_write`, `load_config`, `derive_runtime_paths`, `now_iso`, `safe_resolve`, state helpers |
| `execution.py` | ~880 | Task execution engine: `sync_state`, `build_agent_prompt`, `cmd_run`, `cmd_complete`, `cmd_fail`, `cmd_reset`, `cmd_status`, `cmd_ready`, `cmd_graph`, `cmd_next`, `cmd_add`, `cmd_new`, `cmd_template`. Also: `resolve_model_for_task`, `compute_dependency_depths`, `assign_groups`, `recompute_ready` |
| `plans.py` | ~900 | Plan lifecycle, approval, and execution |
| `telemetry.py` | ~190 | Cost telemetry: `StepTimer`, `build_telemetry_payload`, `measure_json_bytes`, `estimate_agent_cost_usd`, `estimate_campaign_savings`. Pricing constants: `_MODEL_PRICING` |
| `specs.py` | ~410 | Agent spec parsing: `parse_spec_file` (extracts deps/scope/files/complexity from markdown), `parse_tracker` (reads `live-tracker.md`), `render_spec_template`, `validate_spec_file` |
| `artifacts.py` | ~290 | Plan document rendering: `render_plan_doc`, `persist_plan_artifacts`, `markdown_table`, `render_dependency_graph` |
| `validation.py` | ~240 | Plan validation: `validate_plan`, `plan_validation_warnings`, `finalize_plan_updates` |
| `bootstrap.py` | ~370 | Project init: `cmd_init`, renders `project.toml` from template, creates directory structure |
| `state.py` | ~130 | State I/O: `atomic_write`, `write_state_file`, `load_state`, `save_state`, `default_state`, `empty_execution_manifest` |
| `config.py` | ~200 | Project configuration loading |
| `orchestration.py` | ~400 | Campaign lifecycle orchestration, recovery |
| `merge.py` | ~390 | Workspace merge logic, worktree cleanup |
| `result.py` | ~130 | Structured agent result ingestion |
| `verify.py` | ~130 | Post-merge verification and exit criteria checking |
| `commands.py` | ~80 | Shell command execution and result tracking |

### `scripts/analysis/`

Codebase analysis providers and synthesis pipeline.

| File | Lines | Purpose |
|------|-------|---------|
| `__init__.py` | ~6 | Module exports |
| `engine.py` | ~370 | Provider orchestration: `run_analysis` runs configured providers in sequence, merges results, synthesizes derived views. Provider registry: `_PROVIDERS = {"basic": ..., "dotnet-cli": ...}` |
| `basic_provider.py` | ~1250 | Heuristic file scanner: glob-walks project, detects stacks (C#, WPF, Python, etc.), categorizes files, builds module map. Always available. |
| `dotnet_cli_provider.py` | ~500 | .NET CLI analysis: runs `dotnet msbuild` for project graph enrichment, NuGet references, MSBuild item ownership. Optional — graceful fallback when unavailable. |
| `planning_context.py` | ~190 | Planning surface synthesis: `synthesize_planning_context` bundles analysis_health + conflict_zones + ui_surfaces + ownership + coordination_hotspots into stable planner-facing dict |
| `project_graph.py` | ~250 | Project dependency graph: `synthesize_project_graph` from .sln/.csproj relationships, `refresh_project_inventory` for project membership |
| `derived.py` | ~200 | Derived views: `synthesize_ui_surfaces` (startup/shell/webui/packaging surfaces), `synthesize_ownership_summary` (file-to-project assignment) |
| `relations.py` | ~36 | Dependency edges: `synthesize_dependency_edges` (xaml-code-behind, project-reference, package-reference links) |
| `signals.py` | ~180 | Conflict zone detection: `synthesize_conflict_zones` from config and cross-module file patterns |
| `inventory.py` | ~80 | File inventory helpers: `entry_project_memberships`, `set_entry_project_memberships` |
| `models.py` | ~16 | Data models: `AnalysisRequest` dataclass, `ANALYSIS_SCHEMA_VERSION` |

### Other scripts

| File | Purpose |
|------|---------|
| `scripts/task_models.py` | TypedDict definitions for tasks, plans, agent results |
| `scripts/task_constants.py` | Status enums (`TaskStatus`, `PlanStatus`), status symbol maps |

## Configuration

| File | Purpose |
|------|---------|
| `.codex/skills/project.toml` | Project-local config: `[project]`, `[paths]`, `[commands]`, `[analysis]`, `[models]` sections |
| `project.toml.template` | Template rendered by `init --force` for new consumer repos |
| `AGENTS.md` | Project conventions file — every agent reads this first |

## Runtime State

| File | Purpose |
|------|---------|
| `data/tasks.json` | Campaign state: tasks, groups, plans, execution_manifest, sync_audit |
| `data/plans/plan-*.json` | Individual plan files with agents, plan_elements, analysis_summary |
| `data/analysis-cache.json` | Cached analysis snapshot with content-addressed hash key |
| `live-tracker.md` | Human-readable progress tracker (parsed by `parse_tracker`) |

## Agent Specs

| Pattern | Purpose |
|---------|---------|
| `agents/agent-{letter}-{name}.md` | Per-agent task specification. Parsed for: `scope`, `deps`, `files`, `complexity`. Contains verification commands and exit criteria. |

## Documentation

| File | Purpose |
|------|---------|
| `docs/campaign-plan-*.md` | Auto-generated campaign plan documents |
| `docs/config-reference.md` | Configuration reference |
| `docs/codex-launch-mapping.md` | Codex-specific mapping from portable launch tiers to concrete subagent models such as `gpt-5.3-codex-spark` |
| `docs/skill-portability-notes.md` | Package/install portability guidance |
| `docs/json-output-examples.md` | CLI JSON output format examples |
| `planning-contract.md` | Shared planning contract (13 standard plan elements) |
| `plan-schema.md` | Plan JSON schema reference |
| `analysis-schema.md` | Analysis v2 schema reference |

## Tests

| File | Covers |
|------|--------|
| `tests/conftest.py` | Shared fixtures and test helpers |
| `tests/test_analysis.py` | Analysis engine, provider output structure |
| `tests/test_artifacts.py` | Plan document rendering, markdown tables |
| `tests/test_basic_provider_helpers.py` | Basic provider heuristic helpers |
| `tests/test_bootstrap_init.py` | `init --force` project scaffolding |
| `tests/test_cli_commands.py` | CLI subcommand dispatch and argument parsing |
| `tests/test_config.py` | Config loading integration |
| `tests/test_config_direct.py` | Direct config unit tests |
| `tests/test_cost_optimization.py` | Model selection, telemetry, cost estimation, analysis cache |
| `tests/test_dotnet_cli_provider_direct.py` | .NET CLI provider unit tests |
| `tests/test_execution_runtime.py` | Sync, run, complete, fail, reset, dependency computation, prompt building |
| `tests/test_parsing.py` | Spec and tracker parsing |
| `tests/test_plan_groups.py` | Group assignment and dependency depths |
| `tests/test_plan_lifecycle.py` | Plan approval, execution, validation gates |
| `tests/test_planning_context_plan_lifecycle.py` | Plan elements refresh from planning context |
| `tests/test_planning_context_scoping.py` | Planning context scoping rules |
| `tests/test_plans.py` | Plan lifecycle, planning context extraction, conflict zone analysis |
| `tests/test_plans_commands.py` | Plan command-level tests |
| `tests/test_preflight_hardening.py` | Preflight check hardening |
| `tests/test_runtime_correctness.py` | Runtime correctness fixes (H1–M4) |
| `tests/test_skill_docs_contract.py` | README and skill-doc contract validation |
| `tests/test_state_direct.py` | State module direct unit tests |
| `tests/test_state_edge_cases.py` | State edge cases and error paths |
| `tests/test_state_persistence.py` | State persistence round-trip |
| `tests/test_task_manager.py` | Core config/state behavior |
| `tests/test_task_manager_portability.py` | Portability and install-time behavior |
| `tests/test_toml_parsing.py` | TOML parser edge cases |
| `tests/test_typeddict_contracts.py` | TypedDict contract validation |
| `tests/test_validation.py` | Plan validation rules |
