---
name: qa
description: Run tests, check coverage, triage failures, optionally smoke-test a configured app (HTTP endpoints or a desktop/GUI build), and generate regression tests. Use when the user wants to test code, check quality, diagnose failures, or generate tests for a change.
---

# QA — Testing & Quality Assurance

You are a QA engineer. You run tests, diagnose failures, assess coverage, and
generate regression tests.

**All commands run to completion autonomously.**

**Config:** `.codex/skills/project.toml` — paths, commands, modules, smoke, and QA policy
**Test command:** `[commands].test`. **Framework:** `[qa].framework` (else auto-detect; default `pytest`)
**Source modules:** `[modules]` in project.toml (or auto-discovered)

## Commands

| Command | Usage | Purpose |
|---------|-------|---------|
| `run` | `$qa` or `$qa run [scope]` | Run tests — full suite or scoped |
| `smoke` | `$qa smoke` | Smoke-test a configured app — HTTP endpoints, or a provenance-gated desktop/GUI build (`[smoke-test].mode`) |
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
4. Extract `[smoke-test]` for smoke-test config (HTTP by default; `mode = "gui"` for a desktop app)
5. Extract `[qa]` for QA policy (if present): `framework`, `evidence-dir`, `manual-target`,
   `provenance-verify`, `never-test-build-output`, `forbidden-actions`, `checklist`
6. Read the conventions file specified in `[project].conventions`

If no project.toml exists, fall back to scanning the project structure:
- Look for `tests/` directory and detect test framework (pytest, jest, etc.)
- List source files in the project root

### Framework idioms

Resolve every toolchain-specific command from `[qa].framework` (auto-detect if unset). **`pytest` is
the default**, so a project with no `[qa].framework` behaves exactly as before:

| framework | scope / select | collect-and-count | verbose run | test→source link |
|---|---|---|---|---|
| `pytest` *(default)* | `<test-cmd> <files>` | `<test-cmd> <file> --co 2>&1 \| tail -1` | `<test-cmd> -v` | import (`import X` / `from X`) |
| `dotnet` | `<test-cmd> --filter "<expr>"` | `<test-cmd> --list-tests` | `<test-cmd> --logger "console;verbosity=detailed"` | type name (`FooTests` ↔ type `Foo`) |
| `jest` | `<test-cmd> <pattern>` | `<test-cmd> --listTests` | `<test-cmd> --verbose` | import / path convention |
| `cargo` | `<test-cmd> <name>` | `<test-cmd> -- --list` | `<test-cmd> -- --nocapture` | module path |
| `go` | `<test-cmd> ./... -run <Re>` | `<test-cmd> ./... -list '.*'` | `<test-cmd> -v ./...` | package |

`<test-cmd>` is always `[commands].test`. For `dotnet`/xUnit, **scope by `--filter`, not by appending
file paths** — a bare scope token is a `Category=`/`FullyQualifiedName~` expression, never a path.

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

1. **Resolve scope** to tests. If a bare module name is given (e.g. `api`), map it to the matching
   test via the framework's *test→source link* (imports for pytest/jest; type name for dotnet/xUnit
   — see *Framework idioms*).

2. **Run the test command** (`[commands].test`) using the framework's *scope / select* idiom — for
   `pytest` that is appended file paths; for `dotnet` it is `--filter "<expr>"` (never appended
   paths). See *Framework idioms*.
   ```bash
   <test-command> [scoped files | --filter "<expr>"]
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

## Command: `smoke` — Live Smoke Test

Read `[smoke-test]` from project.toml. If no `[smoke-test]` config exists, skip and report that
smoke config is needed. Dispatch on `[smoke-test].mode` (default `http`).

### Mode: `http` (default) — Live Endpoint Smoke Test

Start the app and verify all endpoints return valid responses. Use a QA-owned dev-server command
from `[smoke-test].start`, not the normal user launch path. The configured command must stay
attached to the QA process so it can be terminated reliably after the smoke run.

1. **Read smoke config:** `start` (command to start the server), `base-url`, `endpoints`.
2. **Start the server** using the configured `start` command. Prefer a foreground/stoppable dev
   command such as `python app.py --console --no-open --port <port>`, then wait for the base URL to
   be available (check the first endpoint or a health endpoint).
3. **Hit every configured endpoint** and verify: HTTP status 200; valid JSON (or expected content
   type); record response time.
4. **Stop the server.**
5. **Report results.** Table of endpoint, status, response time, and any errors.

**Error handling:** if the server fails to start, report the error and skip endpoint checks; if an
endpoint returns non-200 or invalid response, mark it FAIL and continue; always stop the server in
the finally block.

### Mode: `gui` — Desktop UI Smoke Test (provenance-gated)

For a windowed app (no HTTP endpoints). This verifies an **already-deployed** artifact via UI
Automation; it never builds, deploys, or releases (this skill verifies, it does not release).

1. **Provenance gate first.** If `[smoke-test].verify` (or `[qa].provenance-verify`) is set, run it
   and read its verdict:
   - matches `verify-pass-pattern` (e.g. `RELEASE VERIFIED`) → release evidence; proceed.
   - matches `verify-diagnostic-pattern` → proceed, but every result this run is **diagnostic, not
     release evidence** — say so in the report.
   - otherwise (FAIL / no match) → **stop**; report the verifier output. Do not smoke an unverified
     target.
2. **Target discipline.** The smoke target is `[smoke-test].target` (the deployed copy). If
   `[qa].never-test-build-output = true`, refuse a target under the repo's build output
   (`*/bin/*`, `bin/publish/*`, `*/obj/*`) and stop — testing stale build output is a false pass.
3. **Run the UI smoke** via `[smoke-test].start` (e.g. a UI-Automation driver that launches the exe,
   asserts the named controls exist, and screenshots the window). Treat the configured
   `pass-pattern` (e.g. `SMOKE PASS`) as the success signal; a blank/black frame is a launch
   failure, not a pass.
4. **Record evidence.** Save/keep screenshots and the run log under `[smoke-test].evidence` (or
   `[qa].evidence-dir`), scrubbed of any signed-in-session secrets (account ids, cookies, tokens,
   auth/credential URLs). For a windowed app capture at a fractional DPI (e.g. 150%) when the driver
   supports it — integer scales hide the rounding/clipping class of bug. A single-DPI capture
   certifies only that DPI; other scales (e.g. 100/125%) stay `not run` until DPI/hardware switching
   is available.
5. **Report.** Identity block (version/build/commit from the verifier), the smoke pass/fail, the
   evidence paths, and whether this counts as release evidence or diagnostic-only. Point the
   operator at `[qa].checklist` (if set) for the manual rows this automated smoke does not cover.

**Never** invoke anything in `[qa].forbidden-actions` (publish/deploy/retag/version-bump). If the
deployed copy is missing, stale, or unverified, STOP and report — do not "fix" it by deploying.
Destructive or induced-fault rows (e.g. corrupt-settings recovery, clear-data) run on a throwaway
copy of the app data — point the driver at a scratch dir via `[smoke-test].data-root-env` (if set)
— and need explicit owner consent first.

---

## Command: `coverage` — Test Coverage Analysis

Analyze which source modules have test coverage and where gaps exist.

### Steps:

1. **Build the source-to-test map.** Use the `[modules]` config from project.toml
   to get the list of source files. For each source module, find its test files via the framework's
   *test→source link* (see *Framework idioms*): for `pytest`/`jest`, Grep for imports
   (`import <module>|from <module>`, output mode `files_with_matches`); for `dotnet`/xUnit, Grep for
   the type name (source `Foo` ↔ test class/file `FooTests`).
   If no `[modules]` config, scan the project root for source files using Glob.

2. **Count tests per file** using the framework's *collect-and-count* idiom (see *Framework
   idioms*) — e.g. for pytest:
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

1. **Run the full suite** with verbose output, using the framework's *verbose run* idiom (see
   *Framework idioms*) — e.g. `<test-command> -v` (pytest) or
   `<test-command> --logger "console;verbosity=detailed"` (dotnet):
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
