---
name: docs-clean
description: Aggressively reduce a repository's documentation to concise, current, useful docs. Use when the user asks to clean, prune, consolidate, shrink, or de-bloat docs. Applies changes directly. Not for source code, and not a substitute for diff or PR review.
---

# Docs Clean

`[scope]` is a docs tree or repository. Default: `docs/` in the current repo.

Keep only concise, current, useful documentation. History has no value unless it
contains facts, decisions, commands, constraints, or unresolved work.

## Before touching anything

1. Read the repo instruction files (`AGENTS.md`, `CLAUDE.md`, root `README.md`)
   and list every doc they cite by path. Those survive under the same path —
   tighten only, never rename or delete.
2. Run `git ls-files [scope]` and diff it against the files on disk.
   **Untracked docs are not recoverable from Git history — never delete them.**
   Compress or merge them in place instead.
3. Read `.gitignore`. If it is deny-all plus an allowlist, moving a tracked file
   untracks it; prefer delete or merge over archiving.
4. Preserve unrelated dirty working-tree changes.

## Per-doc action, in preference order

1. **Delete** — Git history preserves it; no ongoing reference value.
2. **Merge** into a canonical doc.
3. **Replace** with a short factual summary.
4. **Move to `[scope]/archive/`** — only if superseded but still referenced.
5. **Keep and tighten.**

## Survivors answer only

- What is this? How is it used?
- Constraints, decisions in force, unresolved work.

## Rules

- Preserve exactly: commands, paths, config values, interfaces, decisions,
  requirements, warnings, open issues. Rationale only if it affects future work.
- Compress reviews, investigations, and status reports to factual bullets.
- Cut filler, narration, repetition, changelog prose, duplicate intros and
  summaries.
- Do not invent, speculate, or expand scope. Do not polish concise docs into
  essays.
- Closed campaign directories (plan → reviews → gate report → task packets):
  read only the final gate or result doc, harvest unresolved work into the
  canonical doc, then delete the directory.
- Fix cross-references your changes break. Grep the whole repo, not just
  `[scope]`, for each deleted basename. Touch source only to fix a doc
  reference.
- Target: most docs under ~100 lines. A doc that cannot justify its length is
  cut.
- Apply changes directly. Do not commit unless asked.

## Output

A bullet list of files kept / merged / summarized / archived / deleted.
No review report.
