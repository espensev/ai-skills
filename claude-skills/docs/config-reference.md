# project.toml Configuration Reference

This document explains how `.claude/skills/project.toml` works, including the
template rendering system, all configuration sections, and auto-detection
behavior for supported project types.

## Overview

Every project that uses the campaign skill ecosystem needs a `project.toml`
file at `.claude/skills/project.toml`. This file tells the runtime where to
find state files, what commands to run for testing and building, which model
tiers to use for agents, and how to analyze the codebase.

The file can be created manually or generated automatically via:

```bash
python scripts/task_manager.py init
```

## Template Rendering System

The init command uses a two-stage flow:

1. **Detect** the project type by scanning for marker files.
2. **Render** the template (`project.toml.template`) into the final config
   (`.claude/skills/project.toml`) by substituting placeholders with
   detected values.

### Source files

| File | Purpose |
|------|---------|
| `project.toml.template` | Generic template with `{{PLACEHOLDER}}` tokens. Lives at the repo root. |
| `.claude/skills/project.toml` | Rendered, project-specific config. Created by `init`. |
| `scripts/task_runtime/bootstrap.py` | Contains `detect_project_type()`, `build_init_config()`, and `init_project()`. |
| `scripts/task_runtime/config.py` | Contains `load_config()`, `load_toml_file()`, and `derive_runtime_paths()`. |

### Init flow

When you run `python scripts/task_manager.py init`, the following happens:

1. `init_project()` is called with the repository root path.
2. If `.claude/skills/project.toml` does not exist (or `--force` is passed):
   a. `detect_project_type(root)` scans the root for language marker files
      and returns a detection dict with `name`, `language`, `test`,
      `compile`, `build`, and `has_tests_dir`.
   b. `build_init_config()` reads `project.toml.template`, performs
      placeholder substitution, and returns the rendered TOML string.
   c. The rendered config is written atomically to
      `.claude/skills/project.toml`.
3. The rendered config is loaded and used to resolve paths.
4. Required directories are created: agents dir, plans dir, state file
   parent.
5. If the configured conventions file does not exist, `init` writes a stub at
   `[project].conventions`.
6. If `data/tasks.json` does not exist, an empty default state file is
   created.

Use `--force` to regenerate the config even if it already exists:

```bash
python scripts/task_manager.py init --force
```

### Available placeholders

The template file uses double-brace placeholders that are replaced during
rendering. Each placeholder resolves based on the detected project type:

| Placeholder | Resolved to | Example (Python project) |
|-------------|-------------|--------------------------|
| `{{PROJECT_NAME}}` | JSON-quoted directory name (lowercased, spaces replaced with hyphens) | `"my-project"` |
| `{{CONVENTIONS_PATH}}` | JSON-quoted path to conventions file (default: `"CLAUDE.md"`) | `"CLAUDE.md"` |
| `{{TEST_LINE}}` | `test = "<command>"` with detected test command | `test = "python -m pytest tests/ -q"` |
| `{{TEST_FAST_LINE}}` | `test_fast = "<command>"` if tests detected, else commented out | `test_fast = "python -m pytest tests/ -q"` |
| `{{TEST_FULL_LINE}}` | `test_full = "<command>"` if tests detected, else commented out | `test_full = "python -m pytest tests/ -q"` |
| `{{COMPILE_LINE}}` | `compile = "<command>"` if compile detected, else commented out | `compile = "python -m py_compile {files}"` |
| `{{BUILD_LINE}}` | `build = "<command>"` if build detected, else commented out | `# build = ""` |

When a command is not detected for a given project type, the placeholder
renders as a TOML comment (e.g., `# build = ""`), so the config is always
valid TOML.

### Fallback behavior

If `project.toml.template` does not exist at the repo root, `build_init_config()`
generates a complete config from an inline fallback template. The fallback
produces identical sections and structure -- the only difference is the source.

## Auto-Detection by Project Type

`detect_project_type()` checks for marker files in a specific priority order.
The first match wins. Here is how each supported project type is detected and
what commands are pre-filled:

### Python

**Marker files:** `pyproject.toml`, `setup.py`, or `requirements.txt`

| Command | Value |
|---------|-------|
| test | `python -m pytest tests/ -q` (or `python -m pytest -q` if no `tests/` dir) |
| compile | `python -m py_compile {files}` |
| build | *(empty)* |

### Node.js

**Marker files:** `package.json`

| Command | Value |
|---------|-------|
| test | `npm test` if a `test` script exists in package.json; else `npx vitest` if vitest is a dependency; else `npx jest` if jest is a dependency; else empty |
| compile | *(empty)* |
| build | `npm run build` if a `build` script exists in package.json; else empty |

### Rust

**Marker files:** `Cargo.toml`

| Command | Value |
|---------|-------|
| test | `cargo test` |
| compile | *(empty)* |
| build | `cargo build` |

### Go

**Marker files:** `go.mod`

| Command | Value |
|---------|-------|
| test | `go test ./...` |
| compile | `go vet ./...` |
| build | `go build ./...` |

### C++

**Marker files:** `CMakeLists.txt` or `*.vcxproj` (when no `.csproj`/`.wapproj` files are present)

| Command | Value |
|---------|-------|
| test | `ctest --test-dir build --output-on-failure` (CMake only) |
| compile | *(empty)* |
| build | `cmake --build build` (CMake only) |

### .NET

**Marker files:** `*.csproj`, `*.wapproj`, `*.sln`, or `*.slnx`

| Command | Value |
|---------|-------|
| test | `dotnet test` |
| compile | *(empty)* |
| build | `dotnet build` |

### Unknown

If no marker files match, all command fields are left empty. The init output
will prompt you to edit the config manually:

```
Next: edit .claude/skills/project.toml and fill in [commands].test
```

### Detection priority order

Detection runs top-to-bottom and returns on the first match:

1. Python (pyproject.toml / setup.py / requirements.txt)
2. Node.js (package.json)
3. Rust (Cargo.toml)
4. Go (go.mod)
5. C++ (CMakeLists.txt or vcxproj without csproj/wapproj)
6. .NET (csproj / wapproj / sln / slnx)
7. C++ fallback (vcxproj alone, when .NET was not matched)
8. Unknown

## Configuration Sections

### `[project]` -- Required

Project identity and conventions.

```toml
[project]
name = "my-project"
conventions = "CLAUDE.md"
```

| Key | Required | Description |
|-----|----------|-------------|
| `name` | Yes | Project name used in status output and plan metadata. |
| `conventions` | Yes | Path to the conventions/architecture file that agents read first. |

### `[paths]` -- Recommended

File and directory paths for runtime state.

```toml
[paths]
state = "data/tasks.json"
plans = "data/plans"
specs = "agents/"
tracker = "live-tracker.md"
analysis_cache = "data/analysis-cache.json"
```

| Key | Default | Description |
|-----|---------|-------------|
| `state` | `data/tasks.json` | Path to the JSON file holding runtime task state. |
| `plans` | `data/plans` | Directory where plan JSON files are stored. |
| `specs` | `agents/` | Directory where agent spec files (`agent-{letter}-{name}.md`) live. |
| `tracker` | `live-tracker.md` | Path to the human-readable campaign tracker file. |
| `analysis_cache` | `data/analysis-cache.json` | Path to the cached analysis snapshot file. |

### `[commands]` -- Required (at least `test`)

Verification commands for project checks. These are used by plan finalization,
run preflight, `verify`, and agent specs.

```toml
[commands]
test = "python -m pytest tests/ -q"
test_fast = "python -m pytest tests/ -q -k 'not slow'"
test_full = "python -m pytest tests/ -q"
compile = "python -m py_compile {files}"
build = "npm run build"
```

| Key | Description |
|-----|-------------|
| `test` | Primary test command. Required for verify and agent verification steps. |
| `test_fast` | Fast subset of tests. Used by `verify --profile fast`, falling back to `test` when unset. |
| `test_full` | Full test suite. Used by `verify --profile full`, falling back to `test` when unset. |
| `compile` | Compile/lint check. `{files}` is expanded to the active plan's owned file paths at runtime. |
| `build` | Full build command. Run during verify when configured. |

Commands should invoke real executables directly, for example `python -m pytest`
or `npm run build`. Avoid shell builtins, pipelines, and redirection when you
want portable behavior across POSIX and Windows.

### `[modules]` -- Optional

Manual module boundary definitions. Override these only when auto-discovery
produces incorrect results.

```toml
[modules]
core = ["src/main.py"]
tests = ["tests/"]
```

Keys are module names; values are lists of file or directory paths belonging
to that module. The analyzer uses these to compute module-level metrics and
cross-module dependency edges.

### `[conflict-zones]` -- Optional

Explicit conflict zone declarations. Files listed together in a zone must
not be concurrently modified by different agents.

```toml
[conflict-zones]
zones = ["file1.py, file2.py | reason they conflict"]
```

Each entry is a string with the format: comma-separated file paths, a pipe
separator, and a human-readable reason for the conflict.

### `[analysis]` -- Optional

Controls the project analyzer behavior.

```toml
[analysis]
mode = "basic"
exclude-globs = [
  ".git/**",
  "node_modules/**",
  "__pycache__/**",
]
# include-globs = ["*.cs", "*.xaml"]
```

| Key | Default | Description |
|-----|---------|-------------|
| `mode` | `"basic"` | Analysis mode. `"basic"` uses the built-in file/import scanner. |
| `exclude-globs` | See template | Glob patterns for files and directories to exclude from analysis. |
| `include-globs` | *(not set)* | When set, only files matching these globs are analyzed. Useful for mixed-language repos. |

### `[models]` -- Optional

Maps agent complexity tiers to Claude model names. Agents inherit their
model from their complexity rating (set during planning).

```toml
[models]
low = "haiku"
medium = "sonnet"
high = "opus"
```

| Key | Default | Description |
|-----|---------|-------------|
| `low` | `"haiku"` | Model for low-complexity agents. Cheapest, fastest. |
| `medium` | `"sonnet"` | Model for medium-complexity agents. Good balance. |
| `high` | `"opus"` | Model for high-complexity agents. Most capable. |

Valid values: `"haiku"`, `"sonnet"`, `"opus"`. Invalid values fall back to
`"sonnet"`.

### `[timeouts]` -- Optional

Per-command timeout in seconds. Prevents hung verification steps from
burning time and cost.

```toml
[timeouts]
compile = 120
build = 300
test = 600
test_fast = 300
test_full = 600
```

All values are optional. When not set, commands run without an explicit
timeout.

### `[smoke-test]` -- Optional

Configuration for smoke-testing a running HTTP application during verification.
If the repo does not expose an HTTP app or API, omit this section entirely.
This section is consumed by the `/qa smoke` skill flow, not by the core
`task_manager.py verify` path.

```toml
[smoke-test]
start = "<dev-server command>"
base-url = "http://127.0.0.1:8000"
endpoints = ["/health"]
```

| Key | Description |
|-----|-------------|
| `start` | Command to start the HTTP app in the background for QA smoke runs. |
| `base-url` | Base URL to hit once the app is running. |
| `endpoints` | List of HTTP paths to check for successful responses. |

### `[ship]` -- Optional

Controls the ship/release workflow.
This section is consumed by the `/ship` skill flow rather than the core
`task_manager.py` backend.

```toml
[ship]
exclude-extra = []
warn = []
```

| Key | Description |
|-----|-------------|
| `exclude-extra` | Additional glob patterns to exclude from the ship artifact. |
| `warn` | Patterns that trigger warnings during the ship check. |

## How Config Is Loaded

The runtime loads config through `load_toml_file()` in
`scripts/task_runtime/config.py`. It tries these TOML parsers in order:

1. `tomllib` (Python 3.11+ standard library)
2. `tomli` (backport package for older Python)
3. Built-in minimal TOML parser (`parse_toml_simple()`) as a last resort

The built-in parser handles sections, string values, string arrays, and
booleans. It is sufficient for all `project.toml` features but does not
support the full TOML specification.

After loading, `derive_runtime_paths()` resolves all `[paths]` entries
relative to the repository root and returns a `RuntimePaths` typed dict
containing the resolved `agents_dir`, `state_file`, `plans_dir`,
`tracker_path`, and `tracker_file`.
