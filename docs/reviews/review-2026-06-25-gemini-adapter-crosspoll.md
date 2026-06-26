# Review - Gemini Adapter + Cross-Poll Branch WIP

**Date:** 2026-06-25
**Surface:** branch WIP on `feature/ops-skills-eval-crosspoll` (committed `main..HEAD` = 3 commits + uncommitted working tree)
**Spec source:** user request ("review, suggest improvements, implement, export") + `docs/skill-directory-review-2026-06-25.md`
**Standards sources:** `claude-skills/CLAUDE.md`, `gemini-skills/docs/skill-portability-notes.md`, `README.md`, `release-manifest.json`
**Verdict:** FAIL (one High finding blocks a clean Gemini release; fix approved and applied in the same change)

> Produced by dogfooding the newly added portable `review` skill against this branch. The skill's documented report format was followable end to end, which is itself a validation signal for the skill.

## Findings

### High

- **[axis: regression] all 28 shipped Gemini command wrappers resolve to a non-existent skill path in the bootstrapped install.**
  Every wrapper uses `@{../../skills/<name>/SKILL.md}` (e.g. `gemini-skills/.gemini/commands/qa.toml:1`).
  That path is correct for the **source repo** and the **exported package**, where skills sit at `<root>/skills/`. But `scripts/bootstrap.ps1` installs skills one level deeper, at `<target>/.gemini/skills/<name>/` (`bootstrap.ps1:30` creates `.gemini/skills`, `:55` copies skills there; wrappers go to `.gemini/commands` at `:31`/`:79`). The installed layout is also what the package itself documents (`docs/skill-portability-notes.md:46-59`).
  **Evidence (empirical, bootstrap into a temp target):**
  | Wrapper path | Resolves to | Exists? |
  |---|---|---|
  | `../../skills/qa/SKILL.md` (shipped) | `<target>/skills/qa/SKILL.md` | **No** — there is no `skills/` at target root |
  | `../skills/qa/SKILL.md` (fix) | `<target>/.gemini/skills/qa/SKILL.md` | **Yes** — the real skill |
  **Impact:** after `bootstrap.ps1`, every Gemini `/<skill>` command injects a path that points at a missing file, so the command loses its skill body. Affects all 28 wrappers.
  **Recommendation (approved — Approach A):** make `bootstrap.ps1` rewrite the wrapper path on copy (`@{../../skills/` -> `@{../skills/`) so source and exported-package wrappers stay correct while the installed copy matches `.gemini/skills/`. Re-bootstrap to confirm resolution.
  **Caveat:** Gemini's `@{}` is documented "workspace-aware" and Gemini CLI is not installed on this machine, so the resolver behavior could not be confirmed live. The filesystem mismatch is certain, and the repo's original wrappers (`../../docs/instructions/...`) show file-relative authoring, under which `../skills/` is correct. A live `gemini /skills reload` should still confirm before the Gemini package is relied on in production.
  **The fix is monotonic:** under file-relative resolution it corrects the path; under a workspace-aware reading the install was already unresolved (the alternative form would be `@{.gemini/skills/<name>/SKILL.md}`), so the change cannot regress a currently-working state — worst case it is no worse than before, best case it is fixed.

### Medium

- None.

### Low

- **[axis: standards] a few Gemini command wrappers exist on disk but are not listed in the install manifest** (e.g. `gemini-skills/.gemini/commands/tdd.toml`, `continuous-learning.toml`). *(Deferred — not changed in this pass.)* Harmless today because export and bootstrap are manifest-driven, so these are simply ignored. Worth reconciling (add to the manifest or remove) so the `.gemini/commands/` directory and the manifest do not drift.
  Evidence: 31 wrapper `.toml` files present; `package/install-manifest.json` lists 28 `command_wrappers`.

## Verification

- `python -m pytest claude-skills/tests/test_skill_docs_contract.py -q` - pass (9 passed)
- `python -m pytest codex-skills/tests/test_skill_docs_contract.py -q` - pass (9 passed)
- Manifest skill counts vs README (78 = 19 + 31 + 28) - pass (claude 19, codex 31, gemini 28)
- `scripts/bootstrap.ps1` into a temp target, then filesystem path-resolution check - confirmed the High finding (shipped path missing, `../skills/` path present)
- Post-fix re-bootstrap into a fresh temp target - pass (28/28 wrappers install, each resolving to its real skill; source tree retains `../../`)
- Cross-poll parity sweep - pass: command-contract check on `delegate` / `token-audit` / `worktree-preflight` (all documented commands present) + leak-class grep over `gemini-skills/skills/` for `.claude`/`.codex` paths, `$`-prefix (Codex) command refs, and `@{` includes (no matches)
- `git check-ignore dist` - pass (export artifact is gitignored; auto-commit will not sweep it)
- `scripts/export-ready-skill-packages.ps1 -TargetDir .\dist\ai-skills-ready-packages -Force` - pass (3 packages, 19 + 31 + 28 skills; exported bootstrap carries the fix; packaged wrappers correctly retain `../../`)

## Coverage Notes

- **Files reviewed deeply:** the three `review/SKILL.md` variants; all 28 Gemini wrappers (`@{...}` path); `gemini-skills/scripts/bootstrap.ps1`; `scripts/export-ready-skill-packages.ps1`; the three `package/install-manifest.json`; `release-manifest.json`; `docs/skill-directory-review-2026-06-25.md`; `claude-skills/CLAUDE.md`; `gemini-skills/docs/skill-portability-notes.md`.
- **Cross-poll parity sweep (completed):** the 13 cross-poll Gemini skill bodies (`agent-report`, `build-gate`, `campaign-health`, `delegate`, `delegation-eval`, `docs-sync`, `schema-validator`, `session-stats`, `smart-test`, `telemetry-live-ops`, `token-audit`, `truthpack-drift`, `worktree-preflight`) were checked against their Claude/Codex siblings. Command contracts are preserved (deep-checked `delegate` = guidance/check/batch/`<task>`, `token-audit` = status/breakdown/budget/forecast/history, `worktree-preflight` = check/plan/dirty — all present). No `.claude`/`.codex` path leaks, no `$`-prefix (Codex) command leaks, no stray `@{}` includes anywhere under `gemini-skills/skills/`. Gemini's structural divergence (Core Mandate / Execution Rules / Output Contract instead of the Claude/Codex framing) is intentional per the documented "Lens Strategy" (`gemini-skills/docs/skill-portability-notes.md:13-14`), not drift.
- **Explicitly excluded (out of scope by agreement):** the untracked `gemini-skills/` ECC/JS import (`agents/`, `scripts/lib/`, multi-language `docs/`), the top-level reference `skills/` tree, `.antigravitycli/`. These are separate, larger integration decisions, not improvements to the shipped packages.

## Open Questions

- Does Gemini CLI's `@{}` resolver treat `..` as relative to the `.toml` file (Approach A correct) or as a workspace-root search (would prefer `@{.gemini/skills/<name>/SKILL.md}`)? Needs one live `gemini /skills reload` on a machine with Gemini CLI to settle definitively.
