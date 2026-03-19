# Product Runtime Cost Optimization Backlog

## Scope

This backlog targets **when the skill is running in product workflows** (not
maintenance-only repo tasks). It focuses on reducing wall time, token/context
footprint, and failed/autonomous run waste for `/manager go`.

## Measured Baseline (2026-03-12)

Commands run from the package repo root:

- `python scripts/task_manager.py analyze --json`
- `python scripts/task_manager.py plan preflight --json`
- `python -m pytest tests/ -q`
- `python -m pytest tests/ -q --durations=10`

Observed:

- `analyze`: ~235ms via CLI (`~116.9ms` in direct runtime call)
- `preflight`: ~297ms
- `pytest` full: `649 tests (648 passed) in 24.85s`
- Analysis payload: `290` files, `112,939` JSON bytes (compact)
- Cache noise in analysis inventory: `221` files (`76.2%`)
- Simulated optimized analysis (exclude caches + basic mode): `69` files,
  `35,160` JSON bytes, runtime ~`21.0ms`

## Prioritized Backlog

## P0 - Stop Wasted Autonomy Before Launch (Blocker)

### Exact changes

1. Add a safe remediation mode to preflight:
- `scripts/task_manager.py`
: extend `plan preflight` with `--fix-safe` that can run non-destructive
  bootstrapping when prerequisites are missing.
2. Add safe fixes:
- If `.claude/skills/planning-contract.md` is missing but package contract is
  available, copy/install it.
- If `[project].conventions` path is missing and `CLAUDE.md` exists at repo
  root, update config to that path.
3. Keep existing failure behavior when auto-fix cannot safely resolve.
4. Document new usage:
- `skills/manager/SKILL.md`
- `skills/manager/SKILL.md`

### Acceptance criteria

- `python scripts/task_manager.py plan preflight --fix-safe --json` returns
  `ready=true` for fixable missing-runtime scenarios.
- No destructive writes.
- Existing preflight behavior unchanged when `--fix-safe` is omitted.

### Expected savings

- Avoids full failed autonomous launches.
- Per prevented failed run, saves one full verify cycle (`~20s` local baseline)
  plus downstream agent/model spend.

## P1 - Reduce Analysis Payload and Token Footprint (Highest ROI)

### Exact changes

1. Expand default analysis excludes:
- `scripts/analysis/basic_provider.py`
: add to `DEFAULT_ANALYSIS_EXCLUDE_GLOBS`:
  - `.mypy_cache/**`
  - `.pytest_cache/**`
  - `.ruff_cache/**`
  - `.venv/**`
  - `venv/**`
  - `.tox/**`
2. Set product runtime defaults:
- `.claude/skills/project.toml`
- `project.toml.template`
: add:
```toml
[analysis]
mode = "basic"
exclude-globs = [
  ".git/**",
  "node_modules/**",
  ".tmp*/**",
  "dist/**",
  "bin/**",
  "obj/**",
  "__pycache__/**",
  ".mypy_cache/**",
  ".pytest_cache/**",
  ".ruff_cache/**",
  ".venv/**",
  "venv/**",
  ".tox/**",
]
```
3. Add tests:
- `tests/test_analysis.py` for exclude behavior.

### Acceptance criteria

- `analyze --json` does not include cache-path files.
- Defaults still allow overrides from user config.

### Expected savings (measured in this repo)

- Analysis runtime: `116.9ms -> 21.0ms` (`-82.1%`)
- File inventory size: `290 -> 69` (`-76.2%`)
- Analysis JSON bytes: `112,939 -> 35,160` (`-68.9%`)
- Direct prompt/context cost reduction for analysis-fed planning.

## P2 - Add Verification Profiles (Fast Gate vs Full Final)

### Exact changes

1. Add profile-aware verification commands:
- `.claude/skills/project.toml`
- `project.toml.template`
: extend `[commands]` with:
  - `test_fast`
  - `test_full`
2. Add CLI/profile support:
- `scripts/task_manager.py`
: add `verify --profile {default,fast,full}` and use profile-specific command
 resolution:
  - `default`: `compile`, optional `build`, `test`
  - `fast`: `compile`, optional `build`, `test_fast` fallback to `test`
  - `full`: `compile`, optional `build`, `test_full` fallback to `test`
3. Update `/manager verify` guidance:
- `skills/manager/SKILL.md`
: document profile-specific verify behavior and fallback rules.
4. Add tests:
- `tests/test_cli_commands.py`
- `tests/test_task_manager_portability.py`

### Acceptance criteria

- `verify` can run with `--profile fast` and `--profile full`.
- Backward compatibility: existing repos with only `[commands].test` still work via the default profile and fallback rules.

### Expected savings

- Full test baseline: `24.85s`.
- Top 6 slow tests account for `13.81s`; moving them to full-only path yields
  fast gate around `6-11s`.
- Gate-time reduction target: `50-70%` per run.

## P3 - Reuse Analysis Within One Campaign Run

### Exact changes

1. Add analysis snapshot caching per run:
- `scripts/task_manager.py`
- `scripts/task_runtime/config.py`
  : persist a sidecar cache at `data/analysis-cache.json`.
2. Cache key:
- repo root + git HEAD + analysis config hash + changed/untracked file metadata.
3. Reuse cached analysis between:
- discovery analysis
- `plan create` analysis summary generation

### Acceptance criteria

- No duplicate analysis execution in same run if cache key unchanged.
- Cache invalidates automatically on code/config changes.

### Expected savings

- Saves one analysis pass per campaign lifecycle.
- Current repo: ~`0.1-0.2s` per run.
- Large repos: typically seconds-level.
- Also avoids duplicate large analysis payload handling.

## P4 - Bound Worst-Case Verification Burn

### Exact changes

1. Add configurable command timeouts:
- `scripts/task_manager.py`
- `.claude/skills/project.toml`
- `project.toml.template`
: introduce `[timeouts]` keys (for example: `compile`, `build`, `test_fast`,
`test_full`) with sane defaults.
2. Include timeout status in verify JSON and manifest.
3. Update docs:
- `skills/manager/SKILL.md`
- `skills/manager/SKILL.md`

### Acceptance criteria

- Hung verify commands terminate deterministically.
- Timeout failures are reported as explicit blocker reasons.

### Expected savings

- Prevents 10-minute default burn in hang scenarios.
- Example: lowering test timeout from 600s to 180s saves up to 420s/run in
failure cases.

## P5 - Add Cost Telemetry to Runtime Artifacts

### Exact changes

1. Emit per-step cost telemetry fields:
- `scripts/task_manager.py`
- `scripts/task_runtime/artifacts.py`
: add metrics such as:
  - `analyze_ms`
  - `preflight_ms`
  - `verify_ms`
  - `commands[].duration_ms`
  - `analysis_json_bytes`
  - `launched_agents`
  - `failed_agents`
2. Persist metrics in execution manifest and JSON output.
3. Add report section in `/manager go` final report format.

### Acceptance criteria

- Telemetry appears in machine-readable output without breaking existing fields.
- Metrics available for ROI dashboards.

### Expected savings

- Indirect but material: enables budget enforcement and profile tuning.
- Target after 2 iterations: `15-30%` runtime/cost reduction from measured
bottlenecks.

## Implementation Status

| Item | Status | Date |
|------|--------|------|
| P1 — Reduce analysis payload | **DONE** | 2026-03-12 (defaults include all cache excludes; recursive exclude bug fixed) |
| P2 — Verification profiles | **DONE** | 2026-03-12 (default/fast/full wired in verify; manager docs updated for profile behavior) |
| P5 — Cost telemetry | **DONE** | 2026-03-12 (StepTimer + payload metrics + campaign savings) |
| Model tiering | **DONE** | 2026-03-12 (complexity→model mapping, `[models]` config, manager launch) |
| P0 — Safe remediation | **DONE** | 2026-03-12 (--fix-safe copies planning-contract, creates CLAUDE.md stub) |
| P3 — Analysis caching | **DONE** | 2026-03-12 (sidecar snapshot reuse with git/config/file-metadata invalidation) |
| P4 — Command timeouts | **DONE** | 2026-03-12 ([timeouts] config, per-command defaults, timeout detection in verify) |

## KPI Targets

- `analyze` p50 runtime: `<= 30ms` in this repo
- analysis payload bytes: `>= 60%` reduction
- gate verify p50: `<= 10s`
- failed-autonomy runs from preflight issues: near zero
- final full-verify pass rate unchanged vs current baseline
