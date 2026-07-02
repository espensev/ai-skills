---
name: memory-management
description: "Govern the agent memory store with a typed write schema, locality routing, and a hard index budget. Use when recording lessons or decisions, updating or pruning memory, auditing memory health, or deciding whether a fact belongs in memory, rules, code comments, or always-loaded context."
---

# Memory Management — Durable Memory Hygiene

Keeps durable project memory searchable as it grows: a typed write spec, a
routing rule for where each fact belongs, and budget discipline for the
always-loaded surface.

## Scope

$observer owns passive project intelligence (observation logs, synthesized
health notes). Memory-management owns memory hygiene — schema, placement,
and budget for durable conventions and lessons. Prefer $observer when the
ask is "watch and record patterns over time"; prefer this skill when the ask
is "write, reorganize, or audit durable memory."

## Dependencies

- Required: none.
- Optional: $observer for the observation log this skill promotes lessons from.

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

## Codex Mechanics

Codex has no per-project auto-memory directory. Durable memory maps onto:

| Discipline concept | Codex surface |
|---|---|
| Always-loaded context | Repo `AGENTS.md` (the `[project].conventions` file in `.codex/skills/project.toml`) |
| User-global always-loaded context | `~/.codex/AGENTS.md` |
| Path-scoped rules | A component-scoped section inside `AGENTS.md` naming the files it governs |
| Memory store (topic files + index) | Repo-owned note artifacts: `docs/memory/<kebab-slug>.md` topic files with a `docs/memory/INDEX.md` index, or the project's existing notes location |

Routing therefore becomes: inline code comment → component-scoped AGENTS.md
section → repo-owned topic file → top of AGENTS.md.

Budget analog: AGENTS.md has no native truncation wall — the budget is
discipline-imposed. Keep the always-loaded conventions surface within roughly
one screen (~100 lines); apply the entry-tier budgets from the core to any
index file, and route overflow into topic files.

Topic files use the same 4-type schema and frontmatter as the core describes
(kebab-case filename matching `name:`, nested `metadata.type`).

## Workflow

1. Classify the request: bare fact → route it; explicit lesson → record;
   correction of an existing note → update; "clean up memory" → audit.
2. For `route`: apply the locality table; state the destination and why.
3. For `record`: apply the record-worthiness gate; pick the type; write the
   file through the schema; add the index line; run the self-check.
4. For `update`: find the existing topic (grep the index); prefer update over
   create; apply the superseded protocol when a conclusion is overturned.
5. For `audit`: run the manual checklist below and report per-file findings
   plus an overall compliance estimate.

Manual audit checklist (guidance-only in this package):

- Every topic file has frontmatter with `name`, `description`, and `metadata.type` in {user, feedback, project, reference}.
- Every `feedback` file has a Why section and a reuse trigger.
- Filenames are kebab-case and match `name:`.
- Every index link resolves; every topic file is indexed (exact filename match).
- No index group holds 15+ entries; no single-link entry line exceeds 160 chars.
- The always-loaded surface is within its discipline budget (~one screen).

## Rules

- Do not write memory without applying the record-worthiness gate first.
- Do not bulk-write on a vague trigger — propose the candidate list and wait
  for user confirmation.
- Do not create a second topic file for an existing theme — update it.
- Do not invent hidden storage: memory lives in AGENTS.md and repo-owned,
  user-visible artifacts only.
- Do not delete entries for staleness alone — delete only when the topic is
  gone or superseded.

## Output

Default response shape:

1. Placement decision (or audit findings) with the rule that drove it.
2. The written/updated file and its index line, when a write happened.
3. Self-check results.
4. Anything deferred for user confirmation.
