# Project Conventions

This repository is the source package for the shared campaign-skill runtime.
Treat this repository root as the git root and the canonical place to make
reusable changes before they are copied into consumer repos.

## Scope

- Edit shared source here: `scripts/`, `skills/`, `tests/`, contract docs, and package docs.
- Do not treat generated runtime files as package source. Do not commit populated `.claude/`, `data/`, `agents/`, or campaign-tracker artifacts from local runs.
- Keep package docs talking about package-root files. Only describe `.claude/skills/...` paths when you are explicitly talking about the installed consumer layout.

## Runtime Invariants

- `scripts/task_manager.py` is the installed entrypoint and compatibility boundary.
- `analysis_v2` is the canonical machine-facing analysis payload.
- `analysis_v2.planning_context` is the canonical planner-facing surface.
- Plan JSON under `data/plans/` is authoritative; markdown campaign docs are derived artifacts.
- `project.toml.template` must stay template-only and portable.

## Change Discipline

- When changing CLI behavior or contracts, update the surrounding docs and tests in the same change.
- Preserve the stdlib-only runtime under `scripts/`; do not introduce pip dependencies into the installed runtime.
- Prefer small support modules over growing `task_manager.py`, but keep the external CLI contract stable.
- Keep examples, reports, and maintainer notes clearly separated from install-time artifacts.

Treat the following as package API changes, not casual doc edits:

- `planning-contract.md`
- `plan-schema.md`
- CLI behavior in `scripts/task_manager.py`
- install paths documented in `README.md`

## Prerequisites

- Python 3.10+
- Git
- `pytest`, `ruff`, and `mypy` for local validation parity

Minimal setup:

```bash
python -m pip install -e .[dev]
```

## Validation

- Run focused tests for the touched surface before handoff.
- For CI parity on Python checks, run `python -m ruff check scripts tests` and `python -m mypy scripts --ignore-missing-imports`.
- Run `python -m pytest tests/test_skill_docs_contract.py tests/test_task_manager.py tests/test_task_manager_portability.py tests/test_plan_lifecycle.py -q` when you change contracts, docs, or core runtime behavior.

## Consumer Sync Workflow

After validating a reusable change here, sync only the install-time package
artifacts into a consumer repository:

1. Copy the relevant `skills/<skill>/` folders.
2. Copy `planning-contract.md` and `project.toml.template` into the consumer
   `.claude/skills/` directory.
3. Copy `scripts/task_manager.py`, `scripts/analysis/`, and
   `scripts/task_runtime/` into the consumer repo `scripts/` directory.
4. Run `python scripts/task_manager.py init --force` inside the consumer repo.
5. Keep consumer-specific config, plans, and tracker artifacts in the consumer
   repo only.

## File Guide

| Path | What changes here usually mean |
|---|---|
| `scripts/task_manager.py` | Backend CLI or plan/state behavior changed |
| `scripts/analysis/*.py` | Analyzer provider/runtime behavior changed |
| `scripts/task_runtime/*.py` | Internal runtime helper behavior changed |
| `tests/test_plan_lifecycle.py` | Plan approval, execution, and validation gates changed |
| `tests/test_task_manager.py` | Core config/state behavior changed |
| `tests/test_task_manager_portability.py` | Portability or install-time behavior changed |
| `tests/test_skill_docs_contract.py` | README and skill-doc contract changed |
| `skills/*/SKILL.md` | Installed skill behavior or operator guidance changed |
| `README.md` | Public package entry point changed |
| `analysis-schema.md` | Canonical analyzer schema or planning-context contract changed |
| `plan-schema.md` | Persisted plan snapshot contract changed |
