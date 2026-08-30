# Claude agent definitions

Provider-owned subagent definitions for Claude Code, installed to
`~/.claude/agents/` (`D:\DevHome\state\claude\agents\` on snd-desk).

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
| `review-specialist.md` | Bounded worker for the `review-controller` skill |

`review-specialist.md` is duplicated by design: `review-controller` bundles its
own copy at `skills/review-controller/agent-definitions/review-specialist.md`
so the skill is self-contained. The two must stay byte-identical.

Directory name: `agent-definitions/`, not `agents/`. `claude-skills/.gitignore`
excludes `agents/` as local package runtime state, so anything placed there is
silently untracked - and it matches the name the `review-controller` skill
already uses for its bundled copy.

Added 2026-08-30; before that these existed only on snd-desk with no source.
