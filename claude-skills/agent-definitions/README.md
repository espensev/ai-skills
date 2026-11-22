# Claude agent definitions

Claude Code loads these subagent definitions from the `agents` directory
under `CLAUDE_CONFIG_DIR`.

These are **not** generated. `scripts/Build-ProviderSkillPackages.ps1` only
touches skills listed in `skills-src/manifest.json` under `generated_skills`;
everything here is authored directly and edited in place.

| Agent | Role |
|---|---|
| `builder.md` | Implementation worker, test-first, returns an evidence-backed handoff |
| `qa-engineer.md` | Independent verification against frozen acceptance criteria, PASS/FAIL |
| `adversarial-critic.md` | Audits a diff + handoff for fake progress, bloat, scope drift; ACCEPT/REJECT |
| `research-scout.md` | Read-only reconnaissance, returns cited findings |
| `system-fixer.md` | Scoped repairs to Claude Code plumbing (hooks, settings, skills, junctions) |
| `review-specialist.md` | Reviews a specific product question against a supplied evidence packet |

Keep definition sources in `agent-definitions/`. The package reserves `agents/`
for generated campaign task specifications and ignores that directory in Git.

Added 2026-08-30; before that these existed only on snd-desk with no source.
