---
name: memory-management
description: "Govern the agent memory store with a typed write schema, locality routing, and a hard index budget. Use when recording lessons or decisions, updating or pruning memory, auditing memory health, or deciding whether a fact belongs in memory, rules, code comments, or always-loaded context."
argument-hint: "<record|update|audit|route> — memory hygiene operation"
allowed-tools: Read, Glob, Grep, Bash, Edit, Write
user-invocable: true
extracted-from: jau123/claude-memory-manager
portable-since: 2026-07-02
---

# Memory Management — Typed Schema, Locality Routing, Index Budget

Keeps the auto-memory library searchable as it grows: a typed write spec, a
routing rule for where each fact belongs, and a character-accurate budget for
the index — plus an audit tool that flags drift before it costs recall.

**Scope:** `/observer` owns passive project intelligence (observation logs,
synthesis). Memory-management owns memory hygiene — schema, placement,
budget, and audits. Prefer `/observer` for "watch and record patterns over
time"; prefer this skill for "write, reorganize, or audit durable memory."

---

## Commands

| Command | Usage | Purpose |
|---------|-------|---------|
| `record` | `/memory-management record <lesson>` | Write a new memory entry through the schema |
| `update` | `/memory-management update <topic>` | Update or supersede an existing entry |
| `route` | `/memory-management route <fact>` | Decide placement: comment, rules, memory, or always-loaded |
| `audit` | `/memory-management audit` | Run the schema/budget audit and report compliance |

Default to `route` when the request is a bare fact, `record` when it is
explicitly a lesson to save.

---

## Discipline Core

> Mirrored section: this core is kept identical in the claude-skills,
> codex-skills, and antigravity-skills packages. Change all three together.

### 1. Decide whether it is worth recording

| Signal | Record? |
|---|---|
| Same trap hit a second time | Yes — mandatory |
| Non-obvious conclusion from an adversarial review or debugging session | Yes — record the Why |
| Reusable baseline numbers (benchmarks, limits, comparisons) | Yes |
| One-off bug, fixed, no reusable lesson | No — the commit message is enough |
| Transient state that will change soon | Only if it keeps mattering across sessions |
| Low-frequency but critical (untouched for months, still the only truth) | Keep — 30 days untouched does not mean stale; delete only when the topic is gone or superseded |

### 2. Typed schema — four types

| Type | Meaning | Required content |
|---|---|---|
| `user` | Who the user is: role, expertise, preferences | — |
| `feedback` | A lesson learned: SDK bug, platform limit, correction | A **Why** section AND a reuse trigger (a How-to-apply section, or scenario keywords in the description) |
| `project` | State snapshots: architecture, in-flight work, decisions | — |
| `reference` | Deep topic reference, SOPs, reusable pipelines | — |

The Why is mandatory for feedback because without the reasoning, the next
session re-litigates the same decision and often lands on the same wrong
conclusion.

### 3. Locality routing — write it where you'll trip over it

| Trigger | Destination |
|---|---|
| Staring at one line/block; the WHY fits in a sentence | Inline code comment, directly above the line |
| Multi-point contract over a known set of files | Path-scoped rules (see runtime mechanics) |
| A scenario, error class, or cross-file/platform pitfall | The memory store (this skill) |
| A rule every session must follow | Always-loaded context (see runtime mechanics) |

**File-bound feedback defaults to SPLIT**: the file-local kernel goes into an
inline code comment (grep that code first — an equivalent comment often
already exists); memory keeps only the cross-cutting principle plus a pointer
to the file.

Anti-over-migration guardrails (prefer memory when unsure):

- If removing the specific file still leaves a general lesson, it stays in memory.
- Platform/SDK behavior that reproduces across files stays in memory.
- Tombstones ("X retired — see Y"), investigation SOPs, and business/economics reasoning stay in memory.

### 4. Update before create

Prefer updating the existing topic file; create a new one only when the topic
is orthogonal. Split signals:

- existing file > 100 lines and the addition is orthogonal to its topic
- existing file already has 5 or more H2 sections
- total length crosses ~150 lines after the addition (evaluate a split)
- the addition does not match the file's declared title/description
- an index group reaches 15+ entries — build a hub file and point entries at it

Superseded protocol: when a conclusion is overturned, the old file gets
`⚠️ Superseded by [[new-slug]]` at the top and the new file states what it
replaces.

### 5. Index budget — a cache, not a log

The always-loaded index is a bounded cache (the bound is native on some
runtimes, discipline-imposed on others — see runtime mechanics). Budget tiers:

- Crown entries ("read this before touching X") ≤ 160 chars, placed near the top as truncation insurance.
- Normal entries ≤ 110 chars (advisory).
- Long-tail entries packed into aggregate lines: `topic → [a](f1.md) · [b](f2.md)` — 5–10 files per line.
- Short link labels: `[foo-bar](foo-bar.md)`, never the filename twice.

Slimming priority when over budget (compressing descriptions FIRST is the
worst move — it self-harms recall):

1. Migrate file-local entries out (to code comments / rules) — the index shrinks AND hit rate rises.
2. Delete true tombstones (topic gone or replaced, no resurrection risk).
3. Move crown entries to the top.
4. Tier the budgets (crown / normal / aggregate).
5. Compress individual descriptions — last resort.

### 6. Description quality — the description IS the hit rate

Recall is an index scan, not semantic search. Every description must pack
scenario keywords + the core conclusion:

| Good | Bad |
|---|---|
| `browser-side supabase.from() mutation deadlocks after tab switch — use fetch() against the REST API` | `Supabase issues` |
| `RLS policies must wrap auth.uid() in (SELECT ...) or it re-evaluates per row` | `RLS performance` |

The test: can you imagine the future question that would match this
description? If not, it isn't done.

### 7. Write flow

When the trigger is vague ("record what's worth keeping from this session"):
list candidates, apply the gate in item 1, then **propose the
add/update/split list and wait for user confirmation before writing**.

Grouping evolution as the index grows: fewer than 15 entries — flat list;
15–25 — introduce 3–5 groups; more than 25 — freeze groups (new entries join
existing groups; cross-theme entries get an "also see" pointer).

### 8. Self-check after writing

- Type correct? Naming correct? Frontmatter complete?
- feedback → Why present + reuse trigger?
- Description passes the future-question test?
- Indexed under an existing group (no new groups)?
- Split thresholds respected?
- Index still under budget?

---

## Claude Code Mechanics

### Where memory lives

Auto-memory is per project: `~/.claude/projects/<slug>/memory/`, where the
slug is the absolute project path with `:`/`\`/`/` characters replaced by `-`
(worktrees share the main repo's directory). `MEMORY.md` is the index loaded
at session start; topic files are read on demand when an index description
matches the task.

### The hard wall

Only the first **200 lines or 25,000 characters** of MEMORY.md load per
session — whichever comes first. Overflow is silently dropped: your newest
entries, usually appended at the bottom, quietly stop existing. Monitor in
**characters** (Python `len()` on decoded text), never bytes — UTF-8
multibyte text makes byte counts overestimate remaining headroom. Keep crown
entries near the top as truncation insurance.

### Canonical file schema

- Filename: kebab-case slug matching `name:` — `ai-skills-share-topology.md`. No `type_` prefix.
- Required frontmatter:

  ```yaml
  ---
  name: kebab-case-slug
  description: scenario keywords + core conclusion
  metadata:
    type: user | feedback | project | reference
  ---
  ```

  Legacy flat `type:` is accepted by the audit tool as input but never written.
- `feedback` bodies carry `## Why` (or `## Root cause`, or bold-inline `**Why:**`).
- Index lines: `- [short-label](file.md) — hook`.

### Path-scoped rules caveats

`.claude/rules/*.md` with `paths:` frontmatter injects on **Read** of a
matching file only — not on Write or file creation (anthropics/claude-code
issue #23478) — and only project-level rules work; user-level `~/.claude/rules/`
paths are ignored (#21858). Contracts that must hold at file-creation time
stay in the always-loaded conventions file.

### Enforcement philosophy

Soft warnings and after-the-fact audits only. Do not add blocking hooks:
exit-2 PreToolUse hooks abort batch writes with no retry.

### Audit tool

```bash
python scripts/memory_audit.py            # audit the cwd-derived project memory
python scripts/memory_audit.py --dir <path-to-memory-dir>
```

Resolution precedence: `--dir` > `CLAUDE_MEMORY_DIR` env > cwd-derived
default. Exit 0 = audit ran (violations are report-only); exit 2 = memory dir
missing. Target: hard-rule compliance ≥ 95%. Full check reference:
`references/audit-tool.md` in this skill directory.

The tool installs with the package runtime files (per-project install copies
it next to `task_manager.py`). From a skills-only global install, run it from
the package checkout with `--dir`.

---

## Integration

| Skill | How Memory Management Helps |
|-------|------------------------------|
| `/observer` | Observer records observations; memory-management routes durable lessons into schema-clean memory |
| `/docs-sync` | Docs drift checks complement memory audits — different truth surfaces |
| `/review` | Review findings worth keeping become `feedback` entries with a Why |
| `/qa` | Repeated QA findings are second-hit signals — record them |

---

## Conventions

- Propose-then-confirm for vague triggers; never bulk-write memory unprompted.
- Update before create; no new index groups once grouping is frozen.
- Descriptions carry scenario keywords + conclusion, ≤ 160 chars.
- The audit tool is read-only; violations are reported, never auto-fixed.
- The Discipline Core section is mirrored across the three provider packages — change all three together.
