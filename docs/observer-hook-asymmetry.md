# Observer Hook Integration vs Automation — Expiry Condition

## The asymmetry

`skills-src/observer/SKILL.src.md` renders one section under two headings:

- Claude gets **Hook Integration** — the hook catalogue, recording vs read-only
  hooks, graceful degradation, output format, and the
  `scripts/hooks/settings-hooks.template.json` configuration.
- Codex gets **Automation** — a short statement that the package ships no
  observer hook layer, and that periodic collection is run manually with
  `$observer cycle --auto` or `$loop`.

The Non-Interference Contract has the matching shape: rules 7 and 8 (hooks
record automatically, hook traceability) exist in a `{{#claude}}` block only.

## Why it is allowed

This is a capability-backed one-sided addition, not contract drift. The
mechanism exists on exactly one side: `claude-skills/scripts/hooks/` ships
portable observer hook scripts and a settings template; `codex-skills` ships no
equivalent. An obligation cannot be stated for a provider that has no mechanism
to discharge it, and stating it anyway would be a false claim in the skill.

The same reasoning covers the other observer asymmetries: `observe_to_eval.py`
and `skill_feedback_loop.py` are Codex-only runtime scripts, so the lines that
invoke them live in `{{#codex}}` blocks.

## Expiry condition

**This asymmetry is defensible only while `codex-skills` ships no portable
observer hook layer.**

If `codex-skills` ever gains one — portable hook scripts plus a way for a
consumer repo to install them — then the justification is gone and the
following must be revisited together:

1. `skills-src/observer/SKILL.src.md` — the `{{#claude}}` Hook Integration
   block and the `{{#codex}}` Automation block, plus Non-Interference Contract
   rules 7 and 8, should collapse back into shared canon.
2. `README.md`, Architecture section — the sentence describing shared skills
   keeping an equivalent workflow contract while provider runtime details may
   differ.
3. This document — delete it once the asymmetry is gone.

Until then, `Build-ProviderSkillPackages.ps1 -Check` enforces only that both
provider copies match the canon; it cannot tell a capability-backed asymmetry
from an obligation someone quietly dropped. That judgement stays with the
reviewer, which is why the condition is written down here rather than left
implicit.
