---
name: smart-test
description: "Map changed files to the minimal useful test subset instead of running the full suite. Use for fast feedback before full QA, commit, merge, or build validation."
{{#claude}}
disable-model-invocation: true
argument-hint: "<files|--diff|--map> — run targeted tests or show the source-to-test map"
allowed-tools: Read, Glob, Grep, Bash
user-invocable: true
extracted-from: WinOverSight
portable-since: 2026-03-26
{{/claude}}
---

# Smart Test {{dash}} Targeted Test Selector

Given a set of changed files, determines and runs the minimal test subset
instead of the full test suite. Reads module definitions from project.toml
and builds source-to-test mappings dynamically.

**All commands run to completion autonomously.**

**Config:** `.{{provider-lc}}/skills/project.toml` {{dash}} modules, test commands, conflict zones

---

## Commands

| Command | Usage | Purpose |
|---------|-------|---------|
| `run` | `{{cmd}}smart-test file1.py file2.ts` | Run tests for specific changed files |
| `diff` | `{{cmd}}smart-test` or `{{cmd}}smart-test --diff` | Auto-detect changed files from git diff, run their tests |
| `map` | `{{cmd}}smart-test --map` | Show the full source-to-test mapping without running anything |

Default to `diff` if no arguments given.

---

## Setup: Load Config

Before any command:

1. Read `.{{provider-lc}}/skills/project.toml`
2. Extract `[modules]` {{dash}} maps module names to source file lists
3. Extract `[commands].test` {{dash}} the test runner command
4. Extract `[smart-test]` section if present (optional overrides)

### Optional config

```toml
[smart-test]
# Explicit source-to-test mappings that override auto-discovery.
# Each key is a source glob, value is a list of test files/globs.
# Use when auto-discovery can't resolve the relationship.

[smart-test.mappings]
"src/schema.sql"    = ["tests/test_data_contract.py", "tests/test_schema.py"]
"src/routes/*.ts"   = ["tests/api/*.test.ts"]
"*.proto"           = ["tests/"]  # protobuf changes = full suite

[smart-test.cross-cutting]
# Files that, when changed, require the full test suite.
# Auto-detected: conftest.py, jest.config.*, pyproject.toml, package.json
paths = ["conftest.py", "jest.config.ts"]
```

---

## Source-to-Test Mapping Strategy

Build the mapping in priority order:

### 1. Explicit mappings (highest priority)

If `[smart-test.mappings]` is configured, use those first. Exact source {{arrow}}
test file relationships defined by the user.

### 2. Module-based mapping

Use `[modules]` from project.toml. For each changed source file:
- Find which module it belongs to
{{#claude}}
- Grep test files for imports of that module name
{{/claude}}
{{#codex}}
- Search test files with `rg` for imports of that module name
{{/codex}}
- Pattern: `import <module>`, `from <module>`, `require.*<module>`, etc.

### 3. Convention-based mapping

If no module match, try naming conventions:
- `src/foo.py` {{arrow}} `tests/test_foo.py`
- `src/foo.ts` {{arrow}} `tests/foo.test.ts` or `tests/foo.spec.ts`
- `src/components/Bar.tsx` {{arrow}} `tests/components/Bar.test.tsx`
- `lib/foo.rs` {{arrow}} `tests/foo.rs` or `src/foo/tests.rs`

### 4. Import-based discovery (fallback)

{{#claude}}
Grep all test files for references to the changed file's exports:
{{/claude}}
{{#codex}}
Search all test files with `rg` for references to the changed file's exports:
{{/codex}}
- Function names, class names, type names
- File path references

### Cross-cutting files

Some files trigger the full suite when changed:
- Auto-detected: `conftest.py`, `jest.config.*`, `setup.cfg`, `pyproject.toml`,
  `package.json`, `tsconfig.json`, `Cargo.toml`, `CMakeLists.txt`
- User-configured: `[smart-test.cross-cutting].paths`

When a cross-cutting file is in the changeset, warn and run the full suite.

---

## Command: `run` {{dash}} Test Specific Files

### Steps

1. For each file argument, resolve through the mapping strategy (above)
2. Group resolved test files by test harness:
   - Detect harness from file extension and project config
   - Python (`.py`) {{arrow}} `pytest`
   - TypeScript/JavaScript (`.ts`, `.tsx`, `.test.ts`) {{arrow}} configured test runner
   - Rust (`.rs`) {{arrow}} `cargo test`
   - C/C++ {{arrow}} configured native test harness
   - Other {{arrow}} `[commands].test`
3. Run each harness with its scoped test file list:
   ```bash
   <test-command> <test-file-1> <test-file-2> ...
   ```
4. Report results per harness

### Report

```
Smart Test {{dash}} Run

  Changed Files:
    src/api.py {{arrow}} tests/test_api.py, tests/test_routes.py
    src/auth.py {{arrow}} tests/test_auth.py

  Results:
    Harness    Files    Passed    Failed    Time
    pytest     3        42/44     2         3s

  Coverage: 2/2 changed files have targeted tests
  Unmapped: (none)
```

---

## Command: `diff` {{dash}} Auto-Detect Changes

### Steps

1. Detect changed files:
   ```bash
   git diff --name-only HEAD
   git diff --cached --name-only
   ```
   If on a feature branch, also include changes against the default branch.
   Detect the default branch instead of hardcoding `main`:
   ```bash
   BASE=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||') || BASE="main"
   git diff --name-only "origin/$BASE...HEAD"
   ```
2. Filter to source files (exclude docs, configs unless cross-cutting)
3. Check for cross-cutting files {{dash}} if found, warn and run full suite
4. Pass remaining files to the `run` pipeline

---

## Command: `map` {{dash}} Show Source-to-Test Mapping

### Steps

1. Scan all source files from `[modules]` (or auto-discover from project root)
2. Resolve test targets for each source file using the mapping strategy
3. Display as a table

### Report

```
Smart Test {{dash}} Source-to-Test Map

  Source                    Test Target                   Method
  src/api.py               tests/test_api.py             convention
  src/auth.py              tests/test_auth.py            convention
  src/schema.sql           tests/test_data_contract.py   explicit
  src/utils.py             (none)                        {{dash}}

  Coverage: 3/4 source files have targeted tests
  Unmapped: src/utils.py
```

---

## Fallback Behavior

If mapping cannot determine specific tests for a changed file:
1. Check `[modules]` from project.toml for module membership
{{#claude}}
2. Grep test files for imports of the changed module
{{/claude}}
{{#codex}}
2. Search test files with `rg` for imports of the changed module
{{/codex}}
3. Try convention-based naming
4. If still no match, report "no targeted tests found" for that file
5. Suggest `{{cmd}}qa run` for full suite if many files are unmapped

Never silently skip a changed file {{dash}} always report its mapping status.

---

## How Smart Test Relates to QA and Build Gate

These three skills cover testing at different scopes:

| Skill | Scope | When to Use |
|-------|-------|-------------|
| `{{cmd}}smart-test` | **Changed files only** {{dash}} minimal targeted subset | Fast feedback during development, pre-commit |
| `{{cmd}}qa run` | **Full test suite** {{dash}} comprehensive validation | Pre-merge, campaign verification |
| `{{cmd}}build-gate test` | **Per-build-target tests** {{dash}} target-specific | Build pipeline validation |

**Typical chain:** `{{cmd}}smart-test --diff` (fast) {{arrow}} fix failures {{arrow}} `{{cmd}}qa run` (full) {{arrow}} `{{cmd}}build-gate all` (build + verify + test)

Smart test is a **speed optimization**, not a replacement for qa. Use it for
fast iteration; always run `{{cmd}}qa` or `{{cmd}}build-gate all` before merge/ship.

## Integration

| Skill | How Smart Test Helps |
|-------|---------------------|
| `{{cmd}}qa run` | Start with `{{cmd}}smart-test --diff` for speed, then `{{cmd}}qa run` for comprehensive validation |
| `{{cmd}}manager verify` | Use for quicker agent-scoped validation in worktrees |
| `{{cmd}}build-gate test` | Smart test covers targeted tests; build-gate covers build-scoped tests |
| `{{cmd}}observer` | Record test results as `test-pass` / `test-fail` observations |
| `{{cmd}}ship` | Run `{{cmd}}smart-test --diff` before commit for fast validation |

---

## Conventions

- Read project.toml for all project-specific paths and commands
- Never run the full suite when targeted tests are available
- Always report unmapped files {{dash}} visibility over silence
- Group by test harness to avoid redundant invocations
- Cross-cutting file changes always trigger full suite with a warning
