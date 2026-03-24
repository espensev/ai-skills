---
name: qa
description: Run tests, check coverage, triage failures, optionally smoke-test configured HTTP endpoints, and generate regression tests. Use when the user wants to test code, check quality, diagnose failures, or generate tests for a change.
---

# QA — Testing & Quality Assurance

You are a QA engineer. You run tests, diagnose failures, assess coverage, and
generate regression tests.

**All commands run to completion autonomously.**

**Config:** `.codex/skills/project.toml` — project-specific paths, commands, modules
**Test command:** from `[commands].test` in project.toml
**Source modules:** from `[modules]` in project.toml (or auto-discovered)

## Commands

| Command | Usage | Purpose |
|---------|-------|---------|
| `run` | `$qa` or `$qa run [scope]` | Run tests — full suite or scoped |
| `smoke` | `$qa smoke` | Start a configured HTTP app, hit all configured endpoints, verify responses |
| `coverage` | `$qa coverage` | Map source modules to tests, find gaps |
| `triage` | `$qa triage` | Diagnose current test failures with root cause analysis |
| `regtest` | `$qa regtest <files>` | Generate regression tests for changed files |

Default to `run` if no command given.

---

## Setup: Load Config

Before any command, load project configuration:

1. Read `.codex/skills/project.toml`
2. Extract `[commands].test` for the test command
3. Extract `[modules]` for the source module list (if configured)
4. Extract `[smoke-test]` for HTTP smoke-test configuration (if configured)
5. Read the conventions file specified in `[project].conventions`

If no project.toml exists, fall back to scanning the project structure:
- Look for `tests/` directory and detect test framework (pytest, jest, etc.)
- List source files in the project root

## Feedback Hierarchy

Use these signals, in order of trust:

1. explicit user correction or rejection
2. failing verification command with concrete output
3. repeat failure pattern across multiple files or runs
4. coverage gap that explains an escaped defect

When the signal is reusable beyond the current run, capture it as durable
feedback instead of leaving it buried in prose.

---

## Command: `run` — Execute Tests

Run the test suite with clear reporting.

### Scoping:

- `$qa run` or `$qa` — full suite
- `$qa run api` — just `tests/test_api.py` (or matching test file)
- `$qa run sessions events` — multiple files
- `$qa run collector` — all tests that import the named module

### Steps:

1. **Resolve scope** to test file paths. If a bare module name is given (e.g.
   `api`), map it to the matching test file. If a source module is given (e.g.
   `collector`), find all test files that import it via Grep.

2. **Run the test command** from `[commands].test` in project.toml:
   ```bash
   <test-command> [scoped files]
   ```

3. **Report results.** Show:
   - Total passed / failed / errors
   - For failures: file, test name, assertion, and one-line root cause
   - Elapsed time

4. **If failures exist**, automatically proceed to triage (Phase 1 only —
   classify each failure, do not attempt fixes).
5. **Flag reusable failures.** If the same class of failure is likely to recur,
   call it out as a regression-test or eval-case candidate in the report.

---

## Command: `smoke` — Live Endpoint Smoke Test

Start the app and verify all endpoints return valid responses.

Use a QA-owned dev-server command from `[smoke-test].start`, not the normal
user launch path. The configured command must stay attached to the QA process
so it can be terminated reliably after the smoke run.

### Steps:

1. **Read smoke config** from `[smoke-test]` in project.toml:
   - `start` — command to start the server
   - `base-url` — base URL for requests
   - `endpoints` — list of endpoints to check

   If no `[smoke-test]` config exists, skip this command and report that
   smoke test configuration is needed.

2. **Start the server** using the configured `start` command. Prefer a
   foreground/stoppable dev command such as
   `python app.py --console --no-open --port <port>`, then wait for the base
   URL to be available (check the first endpoint or a health endpoint).

3. **Hit every configured endpoint** and verify:
   - HTTP status 200
   - Valid JSON (or expected content type)
   - Record response time

4. **Stop the server.**

5. **Report results.** Table of endpoint, status, response time, and any errors.

### Error handling:
- If the server fails to start, report the error and skip endpoint checks.
- If an endpoint returns non-200 or invalid response, mark it as FAIL and continue.
- Always stop the server in the finally block.

---

## Command: `coverage` — Test Coverage Analysis

Analyze which source modules have test coverage and where gaps exist.

### Steps:

1. **Build the source-to-test map.** Use the `[modules]` config from project.toml
   to get the list of source files. For each source module, grep all test files
   for imports:
   ```bash
   grep -l "import <module>\|from <module>" tests/test_*.py
   ```
   If no `[modules]` config, scan the project root for `.py` files (or
   equivalent source files for the project's language).

2. **Count tests per file** using the test framework's collection mode:
   ```bash
   <test-command> <file> --co 2>&1 | tail -1
   ```

3. **Build the coverage matrix:**

   | Source Module | Test Files | Test Count | Coverage |
   |---|---|---|---|
   | `module.py` | test_module, ... | 25 | Good |
   | `other.py` | (none) | 0 | None |

   Coverage levels:
   - **Good**: 10+ targeted tests
   - **Basic**: 1-9 tests
   - **None**: 0 tests

4. **Identify gaps.** List:
   - Source modules with no test coverage
   - Source modules where test count < public function count / 2
   - Test files that don't match any source module (orphan tests)

5. **Identify key public functions without tests.** For modules with Basic or
   None coverage, list the public functions (non-underscore-prefixed) and check
   if any test calls them.

6. **Report.** Coverage matrix + gap list + recommendations.

---

## Command: `triage` — Failure Diagnosis

Diagnose current test failures with structured root cause analysis.

### Steps:

1. **Run the full suite** with verbose output:
   ```bash
   <test-command-verbose>
   ```

2. **If all pass**, report the pass count and exit.

3. **For each failure**, analyze:
   - **Test name** and file
   - **Error type** (AssertionError, ImportError, AttributeError, etc.)
   - **Root cause classification:**
     - `import-error` — module not found or circular import
     - `schema-drift` — test expects a DB column/table that changed
     - `api-contract` — endpoint returns different shape than expected
     - `refactor-break` — function moved/renamed, test still references old location
     - `data-assumption` — test assumes specific data that isn't there
     - `env-issue` — missing dependency, file path, permission
     - `logic-bug` — actual code bug exposed by the test
   - **Suggested fix** — one-line description of what to change

4. **Group failures** by root cause classification.

5. **Report.** Grouped failures with suggested fixes. If failures are
   interrelated (e.g. one import error causes 10 downstream failures),
   identify the root failure and mark others as cascading.
6. **Promote durable feedback.** For repeated regressions or blockers, include
   the exact scenario that should become a regression test or eval case.

---

## Command: `regtest` — Generate Regression Tests

Generate targeted regression tests for specific changed files.

### Usage:

- `$qa regtest app.py` — generate tests for changes in app.py
- `$qa regtest collector.py collector_services.py` — multiple files
- `$qa regtest --diff` — auto-detect changed files from `git diff`

### Steps:

1. **Identify what changed.** If `--diff` is specified:
   ```bash
   git diff --name-only HEAD
   git diff --cached --name-only
   ```
   Otherwise use the file list from the arguments.

2. **For each changed source file:**
   a. Read the source file
   b. Read the existing test file(s) for that module
   c. Identify which functions/methods were added or modified
   d. Check which of those are already covered by existing tests
   e. Note the specific bug or failure mode the new test protects against

3. **Generate new tests** for uncovered changes:
   - Follow the existing test patterns in the project (read existing tests to
     learn the conventions — fixtures, test structure, mocking patterns)
   - Use descriptive test names: `test_<function>_<scenario>`
   - Keep tests deterministic — no network calls, no real DB

4. **Write tests** to the appropriate test file using the Edit tool.
   - If a test file exists for the module, add to it
   - If no test file exists, create `tests/test_<module>.py` (or the
     project's test naming convention)
   - Never overwrite existing tests — only add new ones

5. **Run the new tests** to verify they pass:
   ```bash
   <test-command> <new-test-file>::<NewTestClass> -v
   ```

6. **Report.** List of generated tests with what they cover.

---

## Auto-Discovery: Source-to-Test Map

When no explicit source-to-test map is available, build one dynamically:

1. List all source files from `[modules]` in project.toml (or scan project root)
2. For each source module, grep test files for import references
3. Build the mapping at runtime — no hardcoded tables needed

This replaces any project-specific hardcoded mapping with a general approach
that works for any codebase.

---

## Conventions

- Read `.codex/skills/project.toml` for all project-specific paths and commands
- Read the conventions file (`[project].conventions`) for test patterns and style
- Tests should follow the patterns already established in the project
- No external dependencies beyond what's in the project's dependency file
- Tests must be deterministic — no network, no real filesystem side effects
