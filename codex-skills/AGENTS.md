## Local Skills

- Use the package-source skills under `skills/` when working on this repository.
- Prefer the smallest matching skill instead of inventing a new workflow:
  - `skills/discover/SKILL.md` for pre-change codebase research.
  - `skills/planner/SKILL.md` for campaign design and agent decomposition.
  - `skills/manager/SKILL.md` for execution orchestration with `scripts/task_manager.py`.
  - `skills/qa/SKILL.md` for test execution, failure triage, and regression coverage.
  - `skills/ship/SKILL.md` for staging and commit packaging.
  - `skills/repo-conventions/SKILL.md` for repository-first engineering or a
    single-objective inspect-edit-verify cycle.
  - `skills/loop-master/SKILL.md` for multi-round or multi-agent supervision.

## Repo Conventions

- Treat this repository as the source package for reusable Codex skills.
- In the Ai-Skills checkout, consult `../skills-src/manifest.json` before
  editing a skill. Author `generated_skills` in
  `../skills-src/<skill>/SKILL.src.md` and its support files, then regenerate
  with `../scripts/Build-ProviderSkillPackages.ps1`; do not edit those generated
  provider copies directly. Provider-owned skills, runtime source, tests,
  contracts, and package docs remain at their package-root paths.
- Treat `local-hooks/devhome-lifecycle/` as the controller-specific source
  authority for the local `devhome-lifecycle@ai-skills` plugin. It is not part
  of the portable package, must stay out of `package/install-manifest.json`, and
  must be reconciled through the repository-root installer rather than edited
  in the Codex cache or `D:\DevHome\state\codex` runtime projection. Keep
  lifecycle state under the physical DevHome root; allow alternate roots only
  through explicit test-only seams. Codex Remember capture belongs to the
  upstream `remember@remember-dev` plugin; the former Windows adapter is retired.
- Use installed-runtime paths under `.codex/skills/` only when the text is explicitly describing the consumer-repo layout.
- Default new runtime configs and prompts to `AGENTS.md`.
- Keep the runtime under `scripts/` stdlib-only unless there is a strong portability reason to change that contract.
- When changing runtime behavior or planning contracts, update the surrounding docs and tests in the same change.
