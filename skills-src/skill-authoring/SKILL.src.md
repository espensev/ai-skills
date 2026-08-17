---
name: skill-authoring
description: "Create or revise Agent Skills with concise discovery metadata, progressive disclosure, and portable support files. Use when adding a new SKILL.md, changing skill frontmatter, splitting long instructions into references, or preparing Codex/Claude skill packages."
{{#claude}}
disable-model-invocation: true
argument-hint: "<new|revise|audit> <skill-name>"
user-invocable: true
{{/claude}}
---

# Skill Authoring

Use this skill to create or maintain Agent Skills that load reliably and stay
portable across {{Provider}} and {{Provider-other}}.

## Scope

- Use for `SKILL.md` creation, review, and refactoring.
- Use for package manifest updates when a skill should ship.
- Use for discovery-trigger tuning when a skill is not invoked or triggers too
  broadly.
{{#claude}}
- Do not use for plugins, MCP servers, hooks, or runtime code unless the skill
  instructions need supporting files for them.
{{/claude}}
{{#codex}}
- Do not use for product plugins, MCP servers, or runtime code unless the
  skill instructions need supporting files for them.
{{/codex}}

## Current Format Baseline

- A skill is a directory with one `SKILL.md`.
- `SKILL.md` starts with YAML frontmatter containing `name` and
  `description`.
- The description is always-loaded metadata. Keep it concise, specific, and
  front-loaded with trigger words.
{{#claude}}
- The Markdown body loads only after Claude selects the skill or the user
  invokes it directly.
{{/claude}}
{{#codex}}
- The Markdown body loads only after the agent selects the skill.
{{/codex}}
- Put long examples, API notes, templates, and scripts in supporting files
  such as `references/`, `assets/`, or `scripts/`, and point to them from the
  body.
{{#claude}}
- Claude Code discovers project skills from `.claude/skills/`; project skill
  permissions such as `allowed-tools` matter only after the workspace is
  trusted.
{{/claude}}
{{#codex}}
- Codex uses the open Agent Skills format and discovers repository/user skills
  from `.agents/skills` and `$HOME/.agents/skills`. This package still has a
  legacy campaign runtime config path under `.codex/skills/project.toml`; do
  not rewrite that runtime path casually.
{{/codex}}

## Workflow

1. Decide whether a new skill is warranted:
   - repeated workflow, checklist, or project convention
   - long prompt that should be reusable
   - specialized procedure that benefits from on-demand loading
2. Pick one narrow name:
   - kebab-case
   - action or domain oriented
   - stable across providers when the behavior is portable
3. Write frontmatter:
   - `name` exactly matches the folder name
   - `description` says what the skill does and when to use it
   - include exclusions or boundaries when trigger overlap is likely
{{#claude}}
   - add Claude-specific fields only when needed, such as `argument-hint`,
     `user-invocable`, `allowed-tools`, `disallowed-tools`, `agent`, or
     `context`
{{/claude}}
4. Keep the body operational:
   - scope
   - required context to inspect
   - ordered workflow
   - rules and failure modes
   - expected output shape
5. Move bulky or rarely used material out of `SKILL.md`:
   - `references/` for docs and deep background
   - `examples/` for sample outputs
   - `scripts/` for executable helpers
6. Update package surfaces:
   - add the skill to `package/install-manifest.json` only if it should ship
   - update package README skill tables
   - update root README counts after manifest changes
   - add or adjust tests for new package guarantees
7. Validate:
   - run the ready-package validator
   - run focused skill docs contract tests
   - compare installed roots when local sync matters

## Description Rules

- Start with the highest-signal use case.
- Include `Use when...` language for discovery.
- Avoid generic words alone: "improve", "help", "manage", "workflow".
- Include concrete trigger nouns: `SKILL.md`, frontmatter, manifest, package,
  provider, docs, eval, hooks.
- Keep the first sentence useful if later text is truncated.

## Portability Rules

- Keep provider-specific invocation syntax out of shared bodies unless the
  package needs it.
{{#claude}}
- Do not grant tool permissions by default; add `allowed-tools` only when the
  skill genuinely needs pre-approved tools.
{{/claude}}
{{#codex}}
- Do not grant tool permissions by default; add provider-specific tool
  frontmatter only when the skill genuinely needs it.
{{/codex}}
- Treat runtime path changes as API changes. Update tests, package docs, and
  installation docs together.
- Do not mention unavailable local tools as required dependencies.
- If support scripts are referenced, make sure package validation bundles them.

## Output

When authoring or revising a skill, report:

1. skill name and trigger scope
2. files added or changed
3. manifest/package changes
4. validation run
5. any provider-specific caveats
