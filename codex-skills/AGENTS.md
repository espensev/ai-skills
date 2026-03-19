## Local Skills

- Use the package-source skills under `skills/` when working on this repository.
- Prefer the smallest matching skill instead of inventing a new workflow:
  - `skills/discover/SKILL.md` for pre-change codebase research.
  - `skills/planner/SKILL.md` for campaign design and agent decomposition.
  - `skills/manager/SKILL.md` for execution orchestration with `scripts/task_manager.py`.
  - `skills/qa/SKILL.md` for test execution, failure triage, and regression coverage.
  - `skills/ship/SKILL.md` for staging and commit packaging.
  - `skills/loop/SKILL.md` for a single-objective inspect-edit-verify loop.
  - `skills/loop-master/SKILL.md` for multi-round or multi-agent supervision.

## Repo Conventions

- Treat this repository as the source package for reusable Codex skills.
- Edit shared source at package-root paths: `skills/`, `scripts/`, `tests/`, `planning-contract.md`, and package docs.
- Use installed-runtime paths under `.codex/skills/` only when the text is explicitly describing the consumer-repo layout.
- Default new runtime configs and prompts to `AGENTS.md`.
- Keep the runtime under `scripts/` stdlib-only unless there is a strong portability reason to change that contract.
- When changing runtime behavior or planning contracts, update the surrounding docs and tests in the same change.
