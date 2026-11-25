# Review - Grok handoff phrase enhancements

**Date:** 2026-11-25
**Surface:** installed learn edits from run `20261123-163442` (A1, A2, A3) against Ai-Skills `skills-src/handoff`
**Spec source:** learn report `GROK_HOME/learn/runs/20261123-163442/report.md` actions A1–A3, picked in session `01a20929-1370-7ef0-876b-af4d32ce020f`
**Standards sources:** `skills-src` package build, `claude-skills/tests/test_skill_docs_contract.py` description limit, skill-design trigger list
**Verdict:** PASS WITH NOTES

## Findings

### Low
- [axis: spec] `skills-src/handoff/SKILL.src.md:3` - The open-work trigger keeps the typed spelling `adessing`.
  Evidence: three recorded prompts quote `review and find open work!, then continue adessing` in the learn report, section 1.
  Impact: the description matches those prompts. A corrected spelling would miss them.
  Recommendation: leave the spelling. It is the selection key, not a procedure.

- [axis: regression] `GROK_HOME/skills/expert-team/SKILL.md:7` - The `use super groks esxperts` trigger is live and has no Git remote.
  Evidence: DevHome `.gitignore` ignores `state/grok/skills/expert-team/SKILL.md`. The live line contains the phrase. The pre-edit copy is `GROK_HOME/learn/trash/20261123-163442/originals/expert-team.md`.
  Impact: Grok already loads this file. A later bundle or home reset can drop the line, and this pull request cannot carry it.
  Recommendation: keep the live file. Do not force-add ignored Grok state into DevHome.

## Verification

- `scripts/Build-ProviderSkillPackages.ps1 -Check` - pass (43 files, 12 skills)
- `python -m pytest tests/test_skill_docs_contract.py -q` in `claude-skills` - 22 passed
- `python -m pytest tests/test_skill_docs_contract.py -q` in `codex-skills` - 24 passed
- Installed SHA-256 of Codex, agents, and Claude `handoff/SKILL.md` matches the generated package for that provider
- Description length 571, under the 1024-character contract, no angle brackets

## Coverage Notes

- Files reviewed deeply: `skills-src/handoff/SKILL.src.md`, generated Claude and Codex `skills/handoff/SKILL.md`, installed copies under `state/codex/skills`, `state/claude/skills`, and `state/agents/skills`, and `state/grok/skills/expert-team/SKILL.md`.
- Before this change, the agents copy had A1 and A2 plus a stale `$ship` route. The Codex and Claude installs had neither phrase. The package now has both phrases and `$land` / `/land`, and those three installs match it.
- Files sampled or excluded: learn actions A4–A15 were not picked. They stay deferred.

## Open Questions

- A4–A11 (`workspace-memory`, `discover`) and A12–A15 (zero-use retirements) were not selected. They are not part of this delivery.
