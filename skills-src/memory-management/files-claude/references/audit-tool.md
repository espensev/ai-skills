# Memory Audit Tool Reference

`claude-skills/scripts/memory_audit.py` is the canonical, stdlib-only source
for auditing a Claude Code auto-memory directory against the memory-management
schema. Installed `scripts/memory_audit.py` files are projections: validate and
edit the Ai-Skills source, then refresh projections through the installer.
Adapted from the jau123/claude-memory-manager bash audit template — see
`../ATTRIBUTION.md`.

## Running

```bash
# From the Ai-Skills repository root
python claude-skills/scripts/memory_audit.py                 # cwd-derived memory
python claude-skills/scripts/memory_audit.py --dir <path>    # explicit directory
CLAUDE_MEMORY_DIR=<path> python claude-skills/scripts/memory_audit.py
```

On a legacy Windows console, set `PYTHONIOENCODING=utf-8` for the invocation;
the current source does not reconfigure stdout or stderr itself.

Resolution precedence: `--dir` > `CLAUDE_MEMORY_DIR` > cwd-derived
`~/.claude/projects/<slug>/memory` (slug = absolute cwd with `:`/`\`/`/`
replaced by `-`).

Exit codes: `0` — audit ran (violations are report-only); `2` — memory
directory missing or unreadable. An existing-but-empty directory is valid: it
reports 0 files at 100% compliance.

## Checks

| Check | Class |
|---|---|
| Frontmatter present (`---` on line 1) | hard |
| Required fields: `name`, `description`, `metadata.type` (flat `type:` accepted as legacy input) | hard |
| `metadata.type` in {user, feedback, project, reference} | hard |
| `feedback` files carry a Why section (`## Why`, `## Root cause`, `**Why:**`, `**Root cause:**`) | hard |
| Filename kebab-case and matching `name:` | hard |
| MEMORY.md links resolve to existing files (exact match, digits allowed) | hard |
| Prose-body `[[wikilinks]]` resolve; frontmatter, MEMORY.md, inline code, and fenced code examples are ignored | hard |
| Memory files missing from the MEMORY.md index (exact match) | soft |
| Oversize file: > 100 lines or ≥ 5 H2 sections | soft |
| Index group with ≥ 15 entries | soft |
| Index budget: warn > 23,000 chars or > 190 lines (native cap: 25,000 chars / 200 lines, character-counted) | soft |
| Entry line > 160 chars — lines with ≥ 2 markdown links are aggregate lines and exempt; the 110-char normal budget is advisory, unenforced | soft |
| Untouched > 30 days (filesystem mtime, best-effort — unreliable under file-sync tools) | info |

## Compliance

`compliance = 100 × (files with zero hard violations) / max(total files, 1)` (an empty directory reports 100%)
— per-file boolean, so one bad file counts once.

| Band | Meaning |
|---|---|
| ≥ 95% | Healthy |
| 85–95% | Marginal — schedule a cleanup pass |
| < 85% | Out of control — audit before writing anything new |

## FAQ

- **A file untouched for 30+ days shows in the report — delete it?** No. It
  is a signal, not a violation. Delete only when the topic is gone or
  superseded.
- **How do I fix an over-budget index?** In order: migrate file-local
  entries to code comments/rules, delete true tombstones, move crown entries
  to the top, tier the budgets, and only then compress descriptions.
