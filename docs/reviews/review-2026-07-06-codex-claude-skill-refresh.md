# Review - Codex and Claude Skill Refresh

**Date:** 2026-07-06
**Scope:** Codex and Claude ready packages only. Antigravity was not changed.
**Method:** Official-doc spot check, package manifest inspection, focused
validation before edits.
**Verdict:** UPDATE APPLIED

## Current-Docs Basis

- OpenAI Codex Agent Skills are directories with `SKILL.md`, optional
  supporting files, and `name` / `description` frontmatter. Codex uses
  progressive disclosure and discovers user skills from `$HOME/.agents/skills`.
  Source: https://developers.openai.com/codex/skills
- OpenAI API Skills also use a versioned bundle plus a `SKILL.md` manifest, and
  frontmatter validation follows the Agent Skills specification.
  Source: https://developers.openai.com/api/docs/guides/tools-skills
- Claude Code skills are `SKILL.md` files that load on demand, can be invoked
  directly, and are project-discovered from `.claude/skills/`.
  Source: https://code.claude.com/docs/en/skills
- Claude platform docs describe skills as filesystem-based resources with
  progressive disclosure across metadata, instructions, and supporting files.
  Source: https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview

## Findings

### High

- None.

### Medium

- [axis: skill coverage] The Codex and Claude packages did not have a portable
  skill for maintaining the skill catalog itself. This made current guidance
  about discovery metadata, progressive disclosure, and support-file boundaries
  live only in ad hoc docs or external references.
  Resolution: added `skill-authoring` to both `codex-skills` and
  `claude-skills`, and listed it in both install manifests.

- [axis: Codex local sync] The local sync scripts targeted legacy/workstation
  Codex roots but not the current documented user skill root
  `$HOME/.agents/skills`.
  Resolution: did not add that shared-agent root to the Codex package installer.
  It has a distinct ownership and synchronization lifecycle, and blindly
  writing the Codex package there would overwrite deliberately divergent shared
  skills. The installer instead canonicalizes junction aliases so each managed
  Codex root is processed once.

### Low

- [axis: package docs] README counts and package skill tables needed manifest
  alignment after the new Codex/Claude skill.
  Resolution: refreshed manifest-derived root counts and updated package
  README install lists.

## Changes Made

- Added `codex-skills/skills/skill-authoring/SKILL.md`.
- Added `claude-skills/skills/skill-authoring/SKILL.md`.
- Added `skill-authoring` to Codex and Claude install manifests.
- Updated root and package READMEs for counts, skill tables, and install lists.
- Updated local sync/compare path handling to canonicalize junction aliases and
  avoid processing the same managed root twice.
- Updated docs contract tests for the new skill.

## Notes

- The Codex package runtime still uses `.codex/skills/project.toml` as its
  campaign config path. That is an existing runtime API and was not migrated in
  this pass.
- Antigravity package contents were left untouched by request.
