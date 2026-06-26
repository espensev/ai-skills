---
name: build-gate
description: "Validate multi-target build chains, verify artifacts, plan rebuilds, and run tests. Use when project.toml defines build-gate targets or coordinated build/test validation is needed."
---

# Build Gate - Multi-Target Build Validator

Validates the project's build chain across one or more configured targets.
Reads target definitions from `[build-gate.<name>]` tables in project.toml -
each target declares its own build, verify, and test commands.

**All commands run to completion autonomously.**

**Config:** `.codex/skills/project.toml` - targets defined in `[build-gate.<name>]`
**Fallback:** If no `[build-gate]` config exists, use `[commands].build` and
`[commands].test` as a single implicit target.

---

## Commands

| Command | Usage | Purpose |
|---------|-------|---------|
| `verify` | `$build-gate` or `$build-gate verify` | Check current artifact state across all targets |
| `plan` | `$build-gate plan` | Verify first, then report what needs building/rebuilding and why |
| `test` | `$build-gate test [target]` | Run tests for one or all targets |
| `build` | `$build-gate build [target]` | Build one or all targets, then verify |
| `all` | `$build-gate all` | Full pipeline: verify -> plan -> build stale/missing -> test -> final verify |

Default to `verify` if no command given.

---

## Setup: Read Config

Before any command:

1. Read `.codex/skills/project.toml`
2. Read the conventions file specified in `[project].conventions`
3. Enumerate all `[build-gate.<name>]` tables - these are the targets

### Target schema

```toml
[build-gate.<name>]
build     = "<shell command>"          # required (empty string = no build step)
verify    = "<shell command>"          # check build succeeded (exit 0 = pass)
artifacts = ["path/to/output", ...]    # expected output paths (non-zero bytes)
test      = "<shell command>"          # target-specific tests
drift     = "<shell command>"          # detect source-list drift before building
cwd       = "<directory>"              # working directory (default: repo root)
depends   = ["<other-target>"]         # build this target only after its deps
```

All keys except `build` are optional.

### Example

```toml
[build-gate.backend]
build = "cmake --build build --config Release"
verify = "test -f build/Release/app.exe"
artifacts = ["build/Release/app.exe"]
cwd = "native"

[build-gate.frontend]
build = "npm run build"
verify = "test -d dist"
artifacts = ["dist/index.html", "dist/assets/"]
depends = ["backend"]

[build-gate.python-tests]
build = ""
test = "pytest tests/ -q"
```

### Fallback (no config)

If no `[build-gate]` section exists:
- Create one implicit target named `default`
- `build` = `[commands].build` (if present)
- `test` = `[commands].test` (if present)
- No verify or artifacts

---

## Command: `verify` - What's the Current State?

Check existing artifacts without building anything. This is the starting point
for every other command.

### Steps

1. For each target that has `artifacts` or `verify` configured:
   a. Check each artifact path - exists? non-zero bytes?
   b. Check file age - fresh (< 1h), ok (< 24h), or stale (> 24h)
   c. Run the `verify` command if configured
   d. Run the `drift` command if configured - flag source-list mismatches
2. For targets with no artifacts/verify, mark as UNKNOWN (can't verify)

### Report

```
Build Gate - Verify

  Target      Artifacts    Freshness    Drift    Status
  backend     2/2          2h ago       clean    PASS
  frontend    1/2 missing  -            -        FAIL
  py-tests    (none)       -            -        UNKNOWN

  Result: FAIL (1 target missing artifacts)
```

---

## Command: `plan` - What Needs Work?

Run verify first, then analyze what needs building and why.

### Steps

1. Run the full `verify` pipeline (above)
2. For each target, classify:

   | State | Meaning | Action |
   |-------|---------|--------|
   | **PASS** | Artifacts fresh, verify green | No action needed |
   | **STALE** | Artifacts exist but old (> 24h) | Rebuild recommended |
   | **DRIFT** | Source-list mismatch detected | Rebuild required |
   | **FAIL** | Artifacts missing or verify failed | Build required |
   | **UNKNOWN** | No verify/artifacts configured | Run tests to check |

3. Resolve `depends` ordering - if target A depends on B and B needs
   rebuilding, A also needs rebuilding regardless of its own state
4. Produce a build plan

### Report

```
Build Gate - Plan

  Targets needing work:
  1. backend    - DRIFT (source list changed since last build)
  2. frontend   - FAIL  (dist/assets/ missing, depends on backend)

  Build order: backend -> frontend
  Estimated: 2 targets, ~40s based on prior runs

  Clean targets:
  - py-tests   - PASS (156/156 tests, 4s ago)
```

---

## Command: `test` - Run Tests

Run test commands for one or all targets.

### Usage

- `$build-gate test` - run tests for all targets that have `test` configured
- `$build-gate test backend` - run tests for one target only

### Steps

1. If a target name is given, run that target's `test` command only
2. If no target name, run `test` for every target that has one configured
3. If `[commands].test` exists and isn't covered by any target, run it as a
   catch-all
4. Capture: exit code, pass/fail counts, elapsed time per target

### Report

```
Build Gate - Tests

  Target        Result     Count     Time
  backend       PASS       33/33     12s
  py-tests      FAIL       154/156   4s
  (global)      PASS       12/12     2s

  Overall: FAIL (2 test failures in py-tests)
```

For failures, include:
- Test name and file
- First line of error/assertion
- One-line root cause if obvious

---

## Command: `build` - Build Targets

Build one or all targets, then verify.

### Usage

- `$build-gate build` - build all targets in dependency order
- `$build-gate build frontend` - build one target only

### Steps (per target, in dependency order)

1. **Drift check** (if `drift` configured):
   Run the drift command, report warnings but proceed.

2. **Build**:
   ```bash
   cd <cwd>  # if configured
   <build-command>
   ```
   Capture: exit code, stdout/stderr, elapsed time.
   If `build` is empty, skip to verify.

3. **Verify**:
   Check artifacts exist and verify command passes.

4. **Test** (if `test` configured):
   Run target-specific tests.

### Dependency resolution

If target A has `depends = ["B"]`:
- Build B first
- If B fails, skip A and mark it as BLOCKED

### Report

```
Build Gate - Build

  Target      Build    Verify   Tests    Time
  backend     PASS     PASS     33/33    12s
  frontend    PASS     PASS     N/A      28s

  Overall: PASS (2/2 targets green)
```

---

## Command: `all` - Full Pipeline

The complete gate check: verify current state, plan what's needed, build
what's stale or broken, test everything, final verify.

### Pipeline

1. **Verify** - assess current artifact state
2. **Plan** - identify what needs work
3. **Build** - rebuild only targets that need it (FAIL, STALE, DRIFT),
   in dependency order. Skip targets already PASS.
4. **Test** - run all target tests + global test command
5. **Final verify** - confirm all artifacts are now fresh and valid

### Report

Unified report combining all phases:

```
Build Gate - Full Pipeline

  Phase 1: Verify
    backend: STALE (artifacts 26h old)
    frontend: PASS

  Phase 2: Plan
    Rebuilding: backend (stale)
    Skipping: frontend (fresh)

  Phase 3: Build
    backend     PASS     12s

  Phase 4: Test
    backend     PASS     33/33    4s
    frontend    PASS     N/A
    py-tests    PASS     156/156  4s

  Phase 5: Final Verify
    All artifacts fresh and valid.

  Overall: PASS
```

---

## Error Handling

- **Build failure**: Capture full stderr, identify the first error line, report
  file:line and the error message. Continue to next target (unless it's a
  dependency - mark dependents as BLOCKED).
- **Missing tool**: If a build tool is not found (cmake, npm, dotnet, etc.),
  report the missing tool and skip that target.
- **Stale artifacts**: Warn in verify, recommend rebuild in plan, auto-rebuild
  in `all`.
- **No config**: If no `[build-gate]` section and no `[commands].build`, report
  that build-gate configuration is needed and exit.

---

## Integration with Other Skills

| Skill | How Build Gate Helps |
|-------|---------------------|
| `$manager verify` | Delegate to `$build-gate all` for comprehensive build validation |
| `$manager merge` | Run `$build-gate verify` after merge to confirm no artifact corruption |
| `$ship` | Run `$build-gate verify` before commit - if FAIL, suggest `$build-gate all` |
| `$qa` | `$build-gate test` covers build-scoped tests; `$qa` covers full test suite |
| `$observer` | Record `build-error` observations when targets fail |

---

## Conventions

- Never delete build output - only verify it exists
- Report all targets even when some fail (no early exit)
- Capture and report elapsed time per target
- Read project.toml for all project-specific paths and commands
- Respect `depends` ordering - never build a target before its dependencies
- When build commands use platform-specific tooling (PowerShell, Make, etc.),
  invoke them appropriately for the current platform
- Default command is `verify`, not `build` - check before acting
