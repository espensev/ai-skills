# Design: `memory-management` skill port (jau123/claude-memory-manager → three runtime packages)

**Date:** 2026-07-02
**Status:** Approved design, pending implementation plan
**Upstream:** <https://github.com/jau123/claude-memory-manager> @ `c766942` (MIT, © 2026 jau123), local clone at `D:\Development\Ai-Skills\claude-memory-manager` (reference-only; all edits happen in this repo)

## 1. Context and intent

`claude-memory-manager` is a third-party Claude Code skill (`memory-management`) that adds discipline to built-in auto-memory: a typed write schema, locality routing (where a fact belongs), and a hard index budget against `MEMORY.md`'s native load limit (first 200 lines or 25,000 **characters**, silently truncated), plus a bash audit script.

We are porting it into this repo's three "ready" packages — `claude-skills`, `codex-skills`, `antigravity-skills` — as a **shared discipline core + thin per-runtime mechanics** skill ("③-lite"). Claude is the reference implementation.

### Decisions (user-confirmed)

| Decision | Choice |
|---|---|
| Canonical schema | The house 4-type schema (`user`/`feedback`/`project`/`reference`) with **nested `metadata.type`** frontmatter — matches live memory and the global CLAUDE.md protocol. Upstream's 3-type flat form is noted as accepted-legacy, not taught. |
| Language | English-only. Upstream Chinese trigger phrases and body are not carried. |
| Runtime scope | All three ready packages (claude, codex, antigravity). gemini-skills is legacy — skipped. |
| Work scope | Repo source only. No global CLAUDE.md edits, no local install, no OneDrive export in this change. |
| Architecture | Shared-core + per-runtime mechanics, maintained by convention (no codegen). Upstream becomes a cherry-pick reference, never a merge parent (divergence is already total). |

## 2. Skill identity

- Directory name **`memory-management`** in all three packages. Parity grouping and the antigravity workflow check key off the exact directory name.
- **Byte-identical description** across all three SKILL.md files — single physical line, double-quoted, runtime-neutral, containing the mandatory discovery trigger (`Use when`):

  > `"Govern the agent memory store with a typed write schema, locality routing, and a hard index budget. Use when recording lessons or decisions, updating or pruning memory, auditing memory health, or deciding whether a fact belongs in memory, rules, code comments, or always-loaded context."`

  Target parity report: `DescriptionVariants=1`, `BodyVariants=3` (body drift across providers is the repo norm).
- Scope separation from `observer` (which owns "durable project memory" as passive observation): each body carries an explicit routing line — observer = passive project intelligence; memory-management = memory hygiene (schema, routing, budget, audit).
- Claude frontmatter adds house keys: `argument-hint`, `allowed-tools`, `user-invocable: true`, and provenance `extracted-from: jau123/claude-memory-manager` + `portable-since`. Codex and antigravity keep minimal `name` + `description` frontmatter per their house styles.
- **Attribution:** each skill dir ships a short `ATTRIBUTION.md` (upstream URL, commit, MIT notice). Any file derived substantially from upstream text or the audit script keeps the MIT copyright notice.

## 3. Shared discipline core (near-identical across all three bodies)

Maintained by convention: each body carries a maintainer note — "this section mirrors the other two packages; change all three together."

1. **Record-worthiness gate** — decision table before any write: same trap hit a second time → must record; adversarial-review insight → record the Why; reusable baseline numbers → record; one-off fixed bug → commit message suffices; transient state → only if it persists. "30 days untouched ≠ stale" — deletion requires the topic to be gone or superseded.
2. **Typed schema** — 4 types: `user` (who the user is), `feedback` (lesson learned — **must** carry a Why: without the reasoning the next session re-litigates and often re-derives the same wrong conclusion), `project` (state snapshots), `reference` (deep topic reference / SOPs).
3. **Locality routing** — write it where you'll trip over it: (a) staring at one line and the WHY fits in a sentence → inline code comment; (b) multi-point contract over a known file set → path-scoped rules; (c) scenario / error class / cross-file or platform pitfall → memory store; (d) every-session rule → always-loaded context. Anti-over-migration guardrails: if removing the specific file still leaves a general lesson, it stays in memory; platform/SDK behavior stays in memory; tombstones and investigation SOPs stay in memory.
4. **Update-vs-create** — prefer updating the existing topic file; create only when the topic is orthogonal. Split thresholds: file > 100 lines with orthogonal addition, or ≥ 5 H2 sections, or index group ≥ 15 entries → hub file. Superseded protocol: old file gets `⚠️ Superseded by [[new-slug]]` at top.
5. **Index budget as cache, not log** — tiered entry budgets (crown entries ≤ 160 chars near the top as truncation insurance; normal ≤ 110; long tail packed into aggregate multi-link lines). Slimming priority when over budget: migrate file-local entries out → delete true tombstones → move crowns to top → tier the budgets → compress descriptions **last** (compressing first self-harms recall).
6. **Description quality** — scenario keywords + core conclusion; the test is "can you imagine the future question that would match this?". Recall is index-scan only (no semantic search) — the description *is* the hit rate.
7. **Self-check checklist** — type correct, naming correct, frontmatter complete, Why present for feedback, description passes the future-question test, indexed under an existing group, no new groups, split thresholds respected, index still under budget.

## 4. Per-runtime mechanics (the thin divergent section)

### 4.1 claude-skills (reference implementation)

- Auto-memory mechanics: `~/.claude/projects/<slug>/memory/`, `MEMORY.md` index loaded at session start, topic files read on demand via index descriptions.
- The hard wall: first **200 lines or 25,000 characters** of MEMORY.md load per session, whichever first; overflow is silently dropped. Budget monitoring must count **characters** (not bytes — UTF-8 multibyte text overestimates remaining headroom by ~3× per CJK char).
- Crown-entry placement near the top of MEMORY.md as truncation insurance.
- `.claude/rules/*.md` + `paths:` caveats (verified upstream against anthropics/claude-code issues): path rules inject on **Read** only, not Write/new-file (#23478); user-level `~/.claude/rules/` paths are ignored, project-level only (#21858). Contracts that must hold at file creation stay in CLAUDE.md.
- Canonical file schema (house wins over upstream): filename = kebab-case slug matching `name:` (e.g. `ai-skills-share-topology.md`), **no** `type_` prefix; required frontmatter `name` / `description` / `metadata.type` (nested; flat `type:` accepted as legacy input by the audit tool, never written).
- Audit tool: `python scripts/memory_audit.py` (see §5).

### 4.2 codex-skills

- Codex has no MEMORY.md-style auto-memory. Mechanics target: repo `AGENTS.md` (project conventions; `[project].conventions` in `.codex/skills/project.toml`), `~/.codex/AGENTS.md` for user-global scope, and **explicit repo-owned note/index artifacts** (`docs/…`, `data/…`) when a project needs a topic store. The four-level routing maps to: code comment → AGENTS.md section scoped to a component → repo-owned notes file → top of AGENTS.md.
- House format: `$name` sibling references (never `/name`), body sections `## Scope` (explicit routing against `$observer`), `## Dependencies`, `## Workflow`, `## Rules`, `## Output`.
- **Guidance-only** — no audit script and no `scripts/…` substrings anywhere in the body (validator extracts any such substring and fails it as an unbundled path; also preserves the package README claim that optional skills add no runtime scripts). The audit is expressed as a short manual checklist.

### 4.3 antigravity-skills

- Persona house format: `# Memory Management Agent`, `You are the Memory Management Agent.`, `## Core Mandate`, `## Allowed Writes` (exact writable surfaces: consumer-repo `AGENTS.md`, consumer-declared rule files, explicitly declared `docs/` artifacts — never an invented hidden store), numbered `## Execution Rules`, `## Output Contract`.
- Discipline alignment: follows `rules-distill`'s promotion protocol — **user approval before any durable rule write** — and stays consistent with injected guardrail 8 ("Feedback before memory": explicit corrections outrank remembered conventions).
- Audit expressed as an LLM procedure (deterministic collection + judgment), matching the package's docs-first, no-runtime nature.
- Paired workflow shim `.agent/workflows/memory-management.md` using the uniform template; body must contain the literal string `.agents/skills/memory-management/SKILL.md`.

## 5. Audit tool: single stdlib-Python implementation

Replace upstream's bash template (Git-Bash-only, documented "Windows untested") with **`claude-skills/scripts/memory_audit.py`** — stdlib-only, cross-platform, consistent with the package's existing Python runtime. Listed in the claude manifest `runtime_files` (which is also what makes `scripts/memory_audit.py` references in the SKILL.md body legal for the validator). No bash variant is shipped; upstream's script is credited in ATTRIBUTION.md as the design source.

Checks ported 1:1 but keyed to the §4.1 canonical schema:

| Check | Class |
|---|---|
| Frontmatter present; required fields `name`/`description`/`metadata.type` (flat `type:` accepted as legacy input) | hard |
| `metadata.type` ∈ {user, feedback, project, reference} | hard |
| `feedback` files contain a Why section (`## Why` heading or bold inline `**Why:**`) | hard |
| Filename is kebab-case slug matching `name:` | hard |
| MEMORY.md links resolve to existing files | hard |
| Memory files not referenced from MEMORY.md | soft |
| Oversize file (> 100 lines or ≥ 5 H2) | soft |
| Index group overload (≥ 15 entries under one `##`) | soft |
| Index budget: warn ≥ 23,000 chars or ≥ 190 lines (hard native cap 25,000 chars / 200 lines); counted as decoded characters | soft (warn) |
| Entry line > 160 chars (aggregate multi-link lines exempt) | soft |
| Untouched > 30 days (signal, explicitly not a violation) | info |

Upstream bugs fixed in the rewrite (verified against the upstream script): division-by-zero on an empty memory dir; broken-link regex excluding digits that the naming rule allows; index-membership check passing on substring collisions; CRLF breaking frontmatter detection; locale-dependent `wc -m` character counting (Python `len()` on decoded text is exact); one file able to log 3 violations and drive compliance negative.

Output mirrors upstream: per-check listings + `Hard-rule compliance: X% (N violations / M files)`, target ≥ 95%, read-only, exit 0 always (soft-warning philosophy — no hook blocking). `--dir` flag overrides the memory dir (default resolves `~/.claude/projects/<slug>/memory/` from the cwd; `CLAUDE_MEMORY_DIR` env respected).

Tests: `claude-skills/tests/test_memory_audit.py` in the package pytest suite — fixture memory dirs covering each hard check, the empty-dir case, CRLF files, budget boundaries, and legacy flat-`type:` acceptance.

## 6. Wiring checklist (verified against manifests and validators)

| # | Change | File(s) |
|---|---|---|
| 1 | Skill body | `claude-skills/skills/memory-management/SKILL.md` |
| 2 | Skill body | `codex-skills/skills/memory-management/SKILL.md` |
| 3 | Skill body | `antigravity-skills/skills/memory-management/SKILL.md` |
| 4 | Workflow shim | `antigravity-skills/.agent/workflows/memory-management.md` |
| 5 | Attribution | `ATTRIBUTION.md` in each of the three skill dirs |
| 6 | Manifest | claude `optional_skills[]` — insert between `docs-sync` and `observer`; add `scripts/memory_audit.py` to `runtime_files[]` |
| 7 | Manifest | codex `optional_skills[]` — insert between `mcp-server-patterns` and `observer` |
| 8 | Manifest | antigravity `skills[]` (between `manager` and `planner`) **and** `workflows[]` (`memory-management.md`) |
| 9 | Audit tool | `claude-skills/scripts/memory_audit.py` + `claude-skills/tests/test_memory_audit.py` |
| 10 | Root README counts | run `.\scripts\Update-ReadmePackageCounts.ps1` (81→84 total; rows 20→21, 32→33, 29→30); never hand-edit the count phrase; row blurbs updated manually if desired |
| 11 | Package README | `claude-skills/README.md` — Skills table row + both install-loop snippets |
| 12 | Package README | `codex-skills/README.md` — Optional Engineering Skills table row (Trigger `auto`) + both install loops |
| 13 | Package README | `antigravity-skills/README.md` — Included Skills table row + status line "29 curated skills and 29 workflows" → 30/30 (unchecked by tooling; goes stale silently) |

**Not touched:** `release-manifest.json`, all `scripts/*.ps1`, both `test_skill_docs_contract.py` files (no assertions needed; manifests are the real gate — optional deliberate assertions may be added for regression protection), historical docs under `docs/` (point-in-time records), `gemini-skills` (legacy).

## 7. Validation plan

1. `.\scripts\Test-ReadyPackages.ps1` — the machine gate; must exit 0. (Use its own exit code: `Test-ReleaseReadiness.ps1` does not propagate child failures.) `-Skip*Smoke` switches for fast iteration; full run before shipping (includes install/export/bootstrap smokes into temp dirs).
2. Package pytest suites (claude + codex), including the new `test_memory_audit.py`.
3. `.\scripts\Update-ReadmePackageCounts.ps1 -Check` clean.
4. `.\scripts\Compare-ProviderSkillParity.ps1` — informational; expect the new row at `DescriptionVariants=1`, `BodyVariants=3`.
5. Markdownlint conventions: frontmatter `---` at line 1, column-0 `name:`/`description:` keys.
6. Run `python scripts/memory_audit.py --dir <live memory dir>` manually against the real Ai-Skills memory dir as an end-to-end sanity check (read-only).

### Known trap lines (enforced in review)

- No `scripts/…` substring anywhere in the codex SKILL.md body; in the claude body only `scripts/memory_audit.py` (bundled). The validator regex has no left anchor — even `skills/x/scripts/y` inside prose extracts and fails.
- Description on one physical line in all three files; no YAML block scalars.
- No `/observer-test`, `/refactor-planner`, `/telemetry-live-ops`, `/worktree-manager` references in the claude body; no `/telemetry-live-ops` (or `$telemetry-live-ops`) in codex.
- Workflow shim filename must exactly equal the skill dir name + `.md`.
- Don't quote a "N install-ready skills" phrase in any new root-README prose (count updater requires the phrase exactly once).

## 8. Out of scope (follow-ups, user-triggered)

- Slimming the global `~/.claude/CLAUDE.md` memory block to a pointer at the installed skill (removes method duplication/drift).
- Local install (`Install-AgentSkills.ps1`) and OneDrive export refresh (`export-ready-skill-packages.ps1 -Force`). Until run, `Compare-AgentSkillRoots.ps1 -FailOnMissingOrStale` reporting Missing is expected.
- Any gemini-skills adaptation.
- Upstream sync policy: jau123 repo is a cherry-pick reference going forward; record this as a project memory once the port lands.
