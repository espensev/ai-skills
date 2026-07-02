---
name: build-gate
description: "Validate multi-target build chains, verify artifacts, and run target-specific tests before merge or release. Use when project.toml defines build-gate targets or coordinated build/test validation is needed."
---

# Build Gate Protocol

## Core Mandate
Verify that the project's build chain is healthy across all configured targets before any merge, release, or campaign handoff. Detect missing artifacts, stale outputs, source-list drift, and failing target tests.

## Execution Rules
1. **Follow global guardrails:** This is an ops verification skill, not a planning skill; no planning-contract gate applies. Follow GEMINI.md for house consistency.
2. **Read project.toml:** Enumerate `[build-gate.<name>]` tables to discover targets. If absent, fall back to `[commands].build` + `[commands].test` as a single implicit `default` target.
3. **Evidence Over Intuition:** Report exact file paths, timestamps, and exit codes — never assume artifacts are fresh.
4. **Read globally, write nothing:** Build-gate is a verification skill. Do not modify build outputs; only report state.

## Target Schema
Each `[build-gate.<name>]` table may declare:
- `build` — shell command to produce artifacts (required; empty string = no build step)
- `verify` — shell command that exits 0 when the build is good
- `artifacts` — expected output paths (must exist and be non-zero bytes)
- `test` — target-specific test command
- `drift` — command that detects source-list drift before building
- `cwd` — working directory (default: repo root)
- `depends` — list of target names that must build first

## Commands
- `/build-gate verify` — check artifact freshness and run verify commands across all targets (default action)
- `/build-gate plan` — verify, then classify each target as PASS / STALE / DRIFT / FAIL / UNKNOWN and produce a dependency-ordered rebuild plan
- `/build-gate test [target]` — run the test command for one or all targets
- `/build-gate build [target]` — build one or all targets in dependency order, then verify
- `/build-gate all` — full pipeline: verify → plan → rebuild stale/missing → test → final verify

## Failure Classification
| State | Meaning | Recovery |
|-------|---------|----------|
| PASS | Artifacts fresh, verify green | None |
| STALE | Artifacts exist but > 24h old | Rebuild recommended |
| DRIFT | Source-list mismatch | Rebuild required |
| FAIL | Artifacts missing or verify failed | Build required |
| UNKNOWN | No verify/artifacts configured | Run tests to check |

## Output Contract
Report all targets every run — never hide passing targets. For each target, show: artifact count vs expected, freshness window, drift result, verify exit code, test pass/fail count, elapsed time. If `depends` ordering blocks any target, mark it BLOCKED with the failing dependency.
