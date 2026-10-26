---
name: skill-authoring
description: "Use when adding a new SKILL.md, changing skill frontmatter or descriptions, tuning when a skill gets selected, splitting long instructions into references, or preparing Codex/Claude skill packages. Creates or revises Agent Skills with concise discovery metadata, progressive disclosure, and portable support files. Do not use for plugins, hooks, MCP servers, or product code that a skill merely mentions."
---

# Skill Authoring

Use this skill to create or maintain Agent Skills that load reliably and stay
portable across Codex and Claude.

## Scope

- Use for `SKILL.md` creation, review, and refactoring.
- Use for package manifest updates when a skill should ship.
- Use for discovery-trigger tuning when a skill is not invoked or triggers too
  broadly.
- Do not use for product plugins, MCP servers, or runtime code unless the
  skill instructions need supporting files for them.

## Current Format Baseline

- A skill is a directory with one `SKILL.md`.
- `SKILL.md` starts with YAML frontmatter containing `name` and
  `description`.
- The description is always-loaded metadata. Keep it concise, specific, and
  front-loaded with trigger words.
- The Markdown body loads only after the agent selects the skill.
- Put long examples, API notes, templates, and scripts in supporting files
  such as `references/`, `assets/`, or `scripts/`, and point to them from the
  body.
- Codex uses the open Agent Skills format and discovers repository/user skills
  from `.agents/skills` and `$HOME/.agents/skills`. This package still has a
  legacy campaign runtime config path under `.codex/skills/project.toml`; do
  not rewrite that runtime path casually.

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
- Keep the description at or under 1024 characters with no angle brackets:
  the Agent Skills spec caps it there, Codex truncates longer catalog lines,
  and skill validators reject angle brackets. Quote it when it contains a
  colon so the YAML still parses.

## Automatic Selection and Evidence

- Select the skill when the task matches its description; the user need not
  know its command name. Loading instructions does not grant extra authority.
- When a skill has subcommands, state how an ordinary request maps to them.
  A request to do work must map to the command that does the work, never to
  a passive default such as `status`.
- Keep ordinary development skills available for automatic selection. For
  Claude, omit `disable-model-invocation: true`; for Codex, do not set
  `policy.allow_implicit_invocation: false` in `agents/openai.yaml`.
- Both providers show the model only skill names and descriptions each turn,
  inside a small budget (Claude about one percent of the context window,
  Codex about two percent). Above it, descriptions are shortened or dropped
  without an error, so keep descriptions short and disable unused skills.
- Check the installed copy and provider settings as well as source metadata.
  A disabled skill cannot be repaired by rewriting its description. Preserve
  duplicate-copy disables and unrelated operator choices when enabling one.
- Resolve bundled scripts relative to the selected skill directory. Run the
  relevant helper within the authorized task, check its exit status, and
  inspect its output. Do not launch the skill recursively to run a helper.
- Test with ordinary requests that omit the skill name and nearby requests
  that should select another skill or none. Observe the selected skill and
  resulting actions in a fresh session; keyword fixtures alone do not test
  agent routing. Include explicit invocation as a compatibility check.
- Record provider, prompt, source revision, selection, observed result, and
  validation. Keep fixture scores separate from actual runs. Compare quality
  and effort on the same tasks before claiming an improvement.

## Portability Rules

- Keep provider-specific invocation syntax out of shared bodies unless the
  package needs it.
- Do not grant tool permissions by default; add provider-specific tool
  frontmatter only when the skill genuinely needs it.
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
