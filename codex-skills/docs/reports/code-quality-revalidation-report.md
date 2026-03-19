# Code Quality Revalidation Report

**Project:** workflow-automation / codex-skills  
**Date:** 2026-03-12  
**Scope:** 22,378 LOC across 50 Python files (`scripts/` + `tests/`)  
**Method:** reran repository gates, rechecked the prior high-severity findings against the current tree, and updated the report to match the code that actually exists today.

---

## Executive Summary

| Dimension | Grade | Current Signal |
|---|---|---|
| Architecture | A- | Clean analyzer/runtime split, no urgent structural regressions found |
| Code Quality | B+ | One medium runtime trust-boundary issue, one medium analysis robustness issue |
| Test Suite | A- | `649/649` passing; broad portability and lifecycle coverage |
| Security | B | Windows `shell=True` runtime path removed; residual absolute-path trust remains |
| API/Docs | A- | Config docs now match command behavior; previous stale findings cleared |
| Tooling | A | `ruff` clean, `mypy` clean on `scripts/`, `pytest` clean |

**Overall Health: A-** — The repo is in materially better shape than the earlier snapshot suggested. Most previously reported critical/high items are already fixed or were stale by the time this revalidation ran. The main remaining work is tightening a few trust-boundary decisions, not broad remediation.

---

## What Changed During Revalidation

- `python -m ruff check scripts tests` now passes cleanly.
- `python -m mypy scripts --ignore-missing-imports` now passes cleanly.
- The full suite now passes at `649/649`.
- Windows runtime command execution no longer routes through `shell=True`; `_split_command()` now keeps the raw command string while using `shell=False`, and `_run_runtime_command()` now returns a structured failure entry for `OSError` cases instead of leaking an unhandled process-launch failure. See `scripts/task_manager.py:2137-2208`.
- The config reference now documents the executable-style command contract instead of implying that shell builtins and pipelines are portable. See `docs/config-reference.md`.

---

## Active Findings

| # | Issue | Location | Severity | Notes |
|---|---|---|---|---|
| 1 | Recorded absolute paths still have a broader trust boundary than relative paths | `scripts/task_manager.py:2093-2116` | MEDIUM | Relative paths are root-contained via `safe_resolve`, but absolute paths are allowed unless they hit a small denylist. This is probably intentional for worktree support, but it is still a wider trust surface than the relative-path case. |
| 2 | Provider loop still downgrades some programmer-error classes to skipped providers | `scripts/analysis/engine.py:66-75` | MEDIUM | `TypeError`, `KeyError`, `AttributeError`, `IndexError`, and `UnicodeDecodeError` are treated as `"unexpected"` provider skips instead of surfacing hard failures. That keeps analysis resilient, but it can hide provider regressions. |
| 3 | Verification command expansion is still string-based, even though filenames are filtered | `scripts/task_runtime/specs.py:208-214` | LOW | The `{files}` placeholder is now sanitized to a safe path subset, and the runtime no longer uses `shell=True` on Windows, but this is still a string-template contract rather than a tokenized command model. |
| 4 | Temp-file hardening is stronger on POSIX than on Windows | `scripts/task_runtime/state.py:68-84`, `scripts/analysis/dotnet_cli_provider.py:289-317` | LOW | POSIX atomic writes explicitly set `0600`; Windows currently relies on default ACL behavior for temp files. |

---

## Closed Or Stale Findings From The Earlier Snapshot

These earlier claims no longer match the current repo:

- `task_manager.py` no longer contains the reported bare `except Exception:` block.
- `diff_tracker.py` no longer catches `NameError`; the cited area now catches `RuntimeError`.
- `_load_json_payload()` already caps stdin to 10 MiB.
- Relative-path traversal through `_resolve_recorded_path()` is already blocked by `safe_resolve`.
- The install manifest already includes the full `scripts/analysis` runtime directory, so `inventory.py` and `project_graph.py` are not missing from the shipped runtime.
- CI no longer treats mypy as non-blocking.
- The previous report’s tool snapshot (`174/174` tests, `ruff` clean, `70` mypy errors) was stale by the time this revalidation ran.

---

## Test Quality Snapshot

### Current Results

- `649/649` tests pass.
- Portability coverage includes plan lifecycle, runtime bootstrapping, command parsing, analysis fallback behavior, and packaging/install flows.
- Focused regression tests were added around the Windows runtime-command execution path and process-launch failure handling.

### Residual Test Risks

| # | Issue | Area | Severity |
|---|---|---|---|
| T1 | Large multi-purpose test modules remain expensive to triage | `tests/test_analysis.py`, `tests/test_task_manager_portability.py` | MEDIUM |
| T2 | `patch_env` is still a context-manager helper rather than a fixture-based isolation layer | `tests/conftest.py` | MEDIUM |
| T3 | Concurrency/race validation is still thinner than lifecycle and portability coverage | state/worktree execution paths | MEDIUM |

---

## Documentation & CI Snapshot

### Confirmed Good

- `README.md` matches the packaged runtime layout.
- `package/install-manifest.json` correctly ships runtime directories instead of enumerating every analysis module individually.
- `.github/workflows/validate.yml` runs `ruff`, `mypy`, and `pytest` as blocking gates.
- `project.toml.template` is safe despite unquoted placeholders because `build_init_config()` substitutes JSON-encoded values before writing the rendered config.

### Follow-Up Worth Considering

| # | Issue | Location | Severity |
|---|---|---|---|
| D1 | Command contract was historically described as shell-oriented; executable-only guidance should stay consistent across docs | `docs/config-reference.md`, future command docs | LOW |
| D2 | The report and docs should keep distinguishing package-source artifacts from consumer-runtime artifacts | `docs/skill-portability-notes.md`, `README.md` | LOW |

---

## Tool Results

| Tool | Result |
|---|---|
| `python -m pytest tests -q` | `649/649` passed in `24.87s` |
| `python -m ruff check scripts tests` | All checks passed |
| `python -m mypy scripts --ignore-missing-imports` | Success: no issues found in `25` source files |

---

## Recommended Next Work

1. Decide whether `_resolve_recorded_path()` should keep accepting external absolute paths, or whether worktree paths should be validated against a narrower allowlist.
2. Decide whether `analysis/engine.py` should fail fast on programmer-error classes instead of recording them as skipped providers.
3. Add concurrency-focused tests around state persistence and worktree reconciliation before treating the runtime as fully hardened.
4. Keep command examples executable-oriented (`python -m ...`, `dotnet ...`, `npm run ...`) so the docs continue to match the runtime contract on both Windows and POSIX.
