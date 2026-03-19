# Campaign Skills

A portable package for the generic multi-agent campaign skill stack used by
Claude Code.

This source package contains the installable skill docs, the
`task_manager.py` backend, and the portability tests that consumer repos can
vendor into their own `.claude/skills` runtime tree.

## Package Layout

| Path | Purpose |
|---|---|
| `skills/<skill>/SKILL.md` | Installable skill definitions |
| `planning-contract.md` | Shared planning contract copied into `.claude/skills/` |
| `plan-schema.md` | Optional schema reference copied into `.claude/skills/` |
| `analysis-schema.md` | Optional analysis schema reference for `analysis_v2` |
| `project.toml.template` | Config template rendered into `.claude/skills/project.toml` by `init --force` |
| `pyproject.toml` | Local validation and development tooling config |
| `CLAUDE.md` | Package development conventions |
| `scripts/task_manager.py` | Backend CLI copied into the target repo `scripts/` directory |
| `scripts/analysis/` | Analyzer provider runtime copied into the target repo `scripts/` directory |
| `scripts/task_runtime/` | Internal runtime support package copied into the target repo `scripts/` directory |
| `scripts/task_models.py` | TypedDict contracts used by tests and local tooling |
| `scripts/task_constants.py` | Shared status constants and symbols for local tooling/tests |
| `docs/skill-portability-notes.md` | Handoff notes and package/install guidance |
| `docs/file-map.md` | Reference map of runtime and package files |
| `docs/config-reference.md` | Config and init reference |
| `docs/program-flow.md` | End-to-end command/runtime lifecycle reference |
| `docs/reports/` | Validation checklists and revalidation reports |
| `examples/` | Example plan artifacts and bridge scripts |
| `tests/` | Portability and runtime verification tests |
| `.github/workflows/validate.yml` | Package validation pipeline |

## Skills

| Skill | Command | Purpose |
|---|---|---|
| Manager | `/manager` | Orchestrate parallel agents: plan, launch, merge, verify |
| Planner | `/planner` | Design structured campaign plans with agent decomposition (supports `--mode refactor` for phased refactors) |
| Discover | `/discover` | Research codebase before planning (supports optimization discovery) |
| QA | `/qa` | Run tests, coverage, triage failures, and optional configured smoke checks |
| Ship | `/ship` | Stage, commit, and push with smart file classification |

## Workflow

The generic campaign workflow moves through four stages:

```text
/discover <question>        -> findings document (docs/discovery-*.md)
/planner <description>      -> campaign plan with agent specs
/manager run ready          -> launches agents in parallel worktrees
/manager merge              -> merges agent work into main
/manager verify             -> validates build, tests, and readiness
/qa run                     -> run test suite
/ship commit                -> stage and commit changes
```

For end-to-end autonomous execution:

```text
/manager go "Add feature X"
```

For phased refactors:

```text
/planner --mode refactor "Extract storage layer"
```

## Installation

### Per-project install

This installs the runtime files into a consumer repo. The target runtime layout
is different from this package layout.

```bash
mkdir -p <project>/.claude/skills
mkdir -p <project>/scripts

for d in skills/discover skills/manager skills/planner skills/qa skills/ship; do
  cp -r "$d" <project>/.claude/skills/
done

cp planning-contract.md project.toml.template <project>/.claude/skills/
cp scripts/task_manager.py <project>/scripts/
cp -r scripts/analysis <project>/scripts/
cp -r scripts/task_runtime <project>/scripts/

cd <project>
python scripts/task_manager.py init --force
```

`init --force` renders `.claude/skills/project.toml`, creates the runtime state
directories, and writes a stub conventions file at the configured
`[project].conventions` path when it is missing.

If you also want the schema reference docs in the installed tree, copy
`plan-schema.md` and `analysis-schema.md` into `<project>/.claude/skills/`.

### Global install

```bash
mkdir -p ~/.claude/skills

for d in skills/discover skills/manager skills/planner skills/qa skills/ship; do
  cp -r "$d" ~/.claude/skills/
done

cp planning-contract.md project.toml.template ~/.claude/skills/
```

The `init --force` command renders `.claude/skills/project.toml` from
`project.toml.template` using local project detection. Generate that file per
consumer repo; do not ship a populated `project.toml` from this package. It
also creates a stub conventions file if the configured path does not exist yet.

## Configuration

All project-specific values live in `.claude/skills/project.toml`. Ship
`project.toml.template`, then let `python scripts/task_manager.py init --force`
generate the real config in the consumer repo.

Minimal working configuration:

```toml
[project]
name = "My App"
conventions = "CLAUDE.md"

[commands]
test = "python -m pytest tests/ -q"
# test_fast = "python -m pytest tests/ -q -k 'not slow'"
# test_full = "python -m pytest tests/ -q"
```

`test_fast` and `test_full` are optional profile-specific overrides for
`python scripts/task_manager.py verify --profile fast|full`; when they are not
set, the runtime falls back to `[commands].test`.

The base planning surface contains 13 standard plan elements. In refactor mode
(`/planner --mode refactor`), elements `R1`, `R2`, and `R3` are added on top
of that shared contract.

Use `[analysis].mode = "basic" | "auto" | "deep"` to control provider
selection. `basic` runs only the portable heuristic scanner. `auto` and `deep`
keep `basic` as the base layer and then try optional deep providers such as
`dotnet-cli` when they are available. You can also pin optional providers with
`[analysis].providers`, for example `["dotnet-cli"]`.

Use `[analysis].include-globs` / `[analysis].exclude-globs` to tune codebase
scanning for mixed-language repos such as C#, XAML, and C++. The analyzer emits
a `project_graph` for solution/project relationships, including `.sln`,
`.csproj`, `.wapproj`, `.vcxproj`, and `CMakeLists.txt` links, plus
startup-project inference and package manifest metadata when found. When
`dotnet-cli` applies, it also enriches `.csproj` files with MSBuild item
ownership and `package_references`, and adds NuGet package nodes to the
`project_graph`. Conflict zones are synthesized from the final merged file view,
so linked XAML or other deep-provider ownership updates feed back into planner
signals. Merge-sensitive dependency edges such as `xaml-code-behind` are also
rebuilt from the final merged file view, so ownership and dependency data stay
aligned. The merged model also derives higher-level `ui_surfaces` and
`ownership_summary` views inside `analysis_v2` for planner consumption, and now
also synthesizes a planner-facing `planning_context` that bundles analysis
health, coordination hotspots, startup/package surfaces, and ownership
summaries into one stable planning surface. The legacy output is now a
compatibility projection over `analysis_v2`, which is documented in
`analysis-schema.md`.

## Design Direction

The current architecture is intentionally schema-first and planner-first:

- `analysis_v2` is the canonical machine-facing analysis payload.
- `analysis_v2.planning_context` is the canonical planner-facing surface.
- top-level `files`, `conflict_zones`, `project_graph`, and related fields are
  maintained as compatibility projections for existing tooling.
- degraded analysis remains explicit through
  `planning_context.analysis_health`, so planner and manager flows can respond
  conservatively when optional providers are unavailable.

The installed entrypoint remains `scripts/task_manager.py`, but internal
refactors should keep moving behavior behind smaller runtime modules without
changing the consumer install layout or CLI contract.

## Runtime Layout

After vendoring, the target repo should have this runtime layout:

| Installed location | Purpose |
|---|---|
| `.claude/skills/manager/SKILL.md` | Manager skill runtime doc |
| `.claude/skills/planner/SKILL.md` | Planner skill runtime doc (includes refactor mode) |
| `.claude/skills/planning-contract.md` | Shared planning contract |
| `.claude/skills/project.toml` | Generated project-local config |
| `scripts/task_manager.py` | Backend command surface |
| `scripts/analysis/*.py` | Analyzer provider/runtime modules |
| `scripts/task_runtime/*.py` | Internal runtime support modules used by `task_manager.py` |
| `data/tasks.json` | Runtime task state |
| `data/plans/plan-*.json` | Authoritative machine-readable campaign plans |
| `docs/campaign-*.md` | Human-readable campaign records |
| `agents/agent-{letter}-{name}.md` | Per-agent task specifications |
| `live-tracker.md` | Human-readable progress tracker |

## Validation

Package validation should prove both the package layout and the installed
runtime flow:

- static doc and path contract checks
- `task_manager.py` portability tests
- clean-room install smoke using the documented install flow

## Development

For local validation in this package, install the development tooling
from `pyproject.toml`:

```bash
python -m pip install -e .[dev]
```

That installs `pytest`, `ruff`, and `mypy` for this package repo only. The
installed consumer runtime under `scripts/` remains stdlib-only.

Useful maintainer references:

- `docs/file-map.md`
- `docs/config-reference.md`
- `docs/program-flow.md`

## Requirements

- Claude Code CLI
- Python 3.10+
- Git
- Project-specific test/build tools referenced from `[commands]`

The Python runtime under `scripts/` has no pip dependencies; it uses only the
Python standard library.

## References

- `docs/skill-portability-notes.md`
- `references/`
- `tests/`
