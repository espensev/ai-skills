# Design: `memory-management` skill port (jau123/claude-memory-manager → three runtime packages)

**Date:** 2026-07-02
**Status:** Historical design; implemented, then superseded by the 2026-08-09 provider cleanup
**Upstream:** <https://github.com/jau123/claude-memory-manager> @ `c766942` (MIT, © 2026 jau123), local clone at `D:\Development\Ai-Skills\claude-memory-manager` (reference-only; all edits happen in this repo)

> The three-provider paths and local clone location below describe the July
> implementation context. The current ready surface contains only Claude and
> Codex packages.

## 1. Context and intent

`claude-memory-manager` is a third-party Claude Code skill (`memory-management`) that adds discipline to built-in auto-memory: a typed write schema, locality routing (where a fact belongs), and a hard index budget against `MEMORY.md`'s native load limit (first 200 lines or 25,000 **characters**, silently truncated), plus a bash audit script.

We are porting it into this repo's three "ready" packages — `claude-skills`, `codex-skills`, `antigravity-skills` — as a **shared discipline core + thin per-runtime mechanics** skill ("③-lite"). Claude is the reference implementation.

### Decisions (user-confirmed and design-resolved)

| Decision | Choice |
|---|---|
| Canonical schema | The house 4-type schema (`user`/`feedback`/`project`/`reference`) with **nested `metadata.type`** frontmatter and kebab-case filenames — matches live memory and the global CLAUDE.md protocol. Upstream's core taught schema is 3-type flat (`user` already appears there as an optional/legacy fourth type in `references/schema.md` and the audit regex); the house change is the nested frontmatter + kebab-case naming, and making `user` first-class. Flat `type:` is accepted-legacy input, never written. |
| Language | English-only. Upstream Chinese trigger phrases and body are not carried. English Why-synonyms (`## Root cause`) **are** carried. |
| Runtime scope | All three ready packages (claude, codex, antigravity). gemini-skills is legacy — skipped. |
| Work scope | Repo source only. No global CLAUDE.md edits, no local install, no OneDrive export in this change. |
| Architecture | Shared-core + per-runtime mechanics, maintained by convention (no codegen). Upstream becomes a cherry-pick reference, never a merge parent (divergence is already total). |
| Upstream workflow modes | Not carried as named modes. The durable parts are folded into the shared core: the candidate-evaluation flow's **propose-then-confirm** step and the **grouping-evolution thresholds** (see §3.8). Mode 4's hook-pitfall checklist is condensed to the soft-warning philosophy note in §4.1; its remaining items are upstream-project-specific. |
| Upstream `references/` and `examples/` | Not carried as files. `schema.md` is superseded by §4.1 (the SKILL.md schema section becomes authoritative); `design-philosophy.md` rationale is distilled into inline Why-notes; `audit-tool-guide.md` becomes `references/audit-tool.md` **inside the claude skill dir** (extra skill-dir files are supported by all copiers). `examples/` dropped — exemplar snippets (good/bad description table, feedback file shape) are inlined in the SKILL.md bodies instead. |
| Eval cases | In scope: trigger eval cases for `memory-management` in claude and codex `eval/cases/` (claude eval README's own extension rule requires cases for new skills; codex CI validates the case file). |

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
2. **Typed schema** — 4 types: `user` (who the user is), `feedback` (lesson learned — **must** carry a Why *and* a reuse trigger: a How-to-apply section or scenario keywords in the description, normally satisfied via item 6; without the reasoning the next session re-litigates and often re-derives the same wrong conclusion), `project` (state snapshots), `reference` (deep topic reference / SOPs).
3. **Locality routing** — write it where you'll trip over it: (a) staring at one line and the WHY fits in a sentence → inline code comment; (b) multi-point contract over a known file set → path-scoped rules; (c) scenario / error class / cross-file or platform pitfall → memory store; (d) every-session rule → always-loaded context. **File-bound feedback defaults to SPLIT**: the file-local kernel goes into an inline code comment (grep that code first — an equivalent comment often already exists); memory keeps only the cross-cutting principle plus a pointer to the file. Anti-over-migration guardrails: if removing the specific file still leaves a general lesson, it stays in memory; platform/SDK behavior stays in memory; tombstones, investigation SOPs, and business/economics reasoning stay in memory.
4. **Update-vs-create** — prefer updating the existing topic file; create only when the topic is orthogonal. Split signals: file > 100 lines with an orthogonal addition; ≥ 5 H2 sections; total length crossing ~150 lines after an addition (evaluate); new content not matching the file's declared title/description; index group ≥ 15 entries → hub file. Superseded protocol: old file gets `⚠️ Superseded by [[new-slug]]` at top.
5. **Index budget as cache, not log** — the always-loaded index surface is a bounded cache (Claude's bound is native and hard, §4.1; codex/antigravity bounds are discipline-imposed, §4.2–4.3). Tiered entry budgets: crown entries ≤ 160 chars near the top as truncation insurance; normal ≤ 110 (advisory); long tail packed into aggregate multi-link lines. Slimming priority when over budget: migrate file-local entries out → delete true tombstones → move crowns to top → tier the budgets → compress descriptions **last** (compressing first self-harms recall).
6. **Description quality** — scenario keywords + core conclusion; the test is "can you imagine the future question that would match this?". Recall is index-scan only (no semantic search) — the description *is* the hit rate.
7. **Self-check checklist** — type correct, naming correct, frontmatter complete, Why present for feedback, description passes the future-question test, indexed under an existing group, no new groups, split thresholds respected, index still under budget.
8. **Write flow** — when the trigger is vague ("record what's worth keeping from this session"): list candidates, apply the gate (item 1), then **propose the add/update/split list and wait for user confirmation before writing**. Grouping evolution for a growing index: < 15 entries flat list; 15–25 introduce 3–5 groups; > 25 freeze groups (new entries join existing groups; cross-theme entries get an "also see" pointer).

## 4. Per-runtime mechanics (the thin divergent section)

### 4.1 claude-skills (reference implementation)

- Auto-memory mechanics: `~/.claude/projects/<slug>/memory/`, `MEMORY.md` index loaded at session start, topic files read on demand via index descriptions.
- The hard wall: first **200 lines or 25,000 characters** of MEMORY.md load per session, whichever first; overflow is silently dropped. Budget monitoring must count **characters** (not bytes — UTF-8 multibyte text overestimates remaining headroom by ~3× per CJK char).
- Crown-entry placement near the top of MEMORY.md as truncation insurance.
- `.claude/rules/*.md` + `paths:` caveats (verified upstream against anthropics/claude-code issues): path rules inject on **Read** only, not Write/new-file (#23478); user-level `~/.claude/rules/` paths are ignored, project-level only (#21858). Contracts that must hold at file creation stay in CLAUDE.md.
- Canonical file schema (house wins over upstream): filename = kebab-case slug matching `name:` (e.g. `ai-skills-share-topology.md`), **no** `type_` prefix; required frontmatter `name` / `description` / `metadata.type` (nested; flat `type:` accepted as legacy input by the audit tool, never written).
- Enforcement philosophy: soft warnings and after-the-fact audit only — no blocking hooks (upstream verified that exit-2 PreToolUse hooks abort batch writes with no retry).
- Audit tool: `python scripts/memory_audit.py` (see §5). Usage doc: `skills/memory-management/references/audit-tool.md`.

### 4.2 codex-skills

- Codex has no MEMORY.md-style auto-memory. Mechanics target: repo `AGENTS.md` (project conventions; `[project].conventions` in `.codex/skills/project.toml`), `~/.codex/AGENTS.md` for user-global scope, and **explicit repo-owned note/index artifacts** (`docs/…`, `data/…`) when a project needs a topic store. The four-level routing maps to: code comment → AGENTS.md section scoped to a component → repo-owned notes file → top of AGENTS.md.
- Budget analog: AGENTS.md has no native truncation wall — the budget is discipline-imposed. The always-loaded conventions surface should stay within roughly one screen (~100 lines); the entry-tier budgets from §3.5 apply as the whole discipline, with overflow routed to repo-owned topic files.
- House format: `$name` sibling references (never `/name`), body sections `## Scope` (explicit routing against `$observer`), `## Dependencies`, `## Workflow`, `## Rules`, `## Output`.
- **Guidance-only** — no audit script. The validator fails any `scripts/…` substring not whitelisted in the codex manifest's `runtime_files`/`runtime_directories`; since `memory_audit.py` will not be in the codex manifest, any mention fails — and we additionally avoid *all* `scripts/` mentions to preserve the package README's claim that optional skills add no runtime scripts. The audit is expressed as a short manual checklist.

### 4.3 antigravity-skills

- Persona house format: `# Memory Management Agent`, `You are the Memory Management Agent.`, `## Core Mandate`, `## Allowed Writes` (exact writable surfaces: consumer-repo `AGENTS.md`, consumer-declared rule files, explicitly declared `docs/` artifacts — never an invented hidden store), numbered `## Execution Rules`, `## Output Contract`.
- Budget analog: as codex — no native wall; discipline-imposed budget on the consumer `AGENTS.md` guidance surface, entry tiers per §3.5.
- Discipline alignment: follows `rules-distill`'s promotion protocol — **user approval before any durable rule write** — and stays consistent with injected guardrail 8 ("Feedback before memory": explicit corrections outrank remembered conventions).
- Audit expressed as an LLM procedure (deterministic collection + judgment), matching the package's docs-first, no-runtime nature.
- Paired workflow shim `.agent/workflows/memory-management.md` using the uniform template; body must contain the literal string `.agents/skills/memory-management/SKILL.md`. (The validator only **warns** when this string is missing — warnings don't affect exit code — so review checks the shim body manually; the hard failure is a workflow file whose basename has no matching manifest skill.)

## 5. Audit tool: single stdlib-Python implementation

Replace upstream's bash template (Git-Bash-only, documented "Windows untested") with **`claude-skills/scripts/memory_audit.py`** — stdlib-only, cross-platform, consistent with the package's existing Python runtime. Listed in the claude manifest `runtime_files` (which is also what makes `scripts/memory_audit.py` references in the SKILL.md body legal for the validator). No bash variant is shipped; upstream's script is credited in ATTRIBUTION.md as the design source.

### Runtime story (mirrors the `task_manager.py` precedent)

- **Per-project install** (the primary mode): `memory_audit.py` is copied into the consumer repo's `scripts/` alongside `task_manager.py` — the claude README per-project snippet gains a `cp` line, and the SKILL.md body invokes it as `python scripts/memory_audit.py`.
- **Global install** (skills-only): no scripts are copied; the SKILL.md notes the fallback — run it from the package checkout (or any copy) with `--dir` pointing at the target memory dir.

### CLI contract

- **Dir resolution precedence:** `--dir <path>` > `CLAUDE_MEMORY_DIR` env > cwd-derived default.
- **Slug derivation (default mode):** absolute cwd path with `:`, `\`, and `/` each mapped to `-`, prefixed per Claude Code convention (verified against the real entry `D--Development-Ai-Skills` for `D:\Development\Ai-Skills`); worktrees resolve to the main repo's slug is **not** attempted — auto-resolution is best-effort, and the tool must **error loudly (exit 2) when the resolved dir does not exist** rather than reporting a perfect score on zero files.
- **Exit codes:** `0` = audit ran (violations are report-only, per the soft-warning philosophy); `2` = unusable input (memory dir missing/unreadable). An existing-but-empty dir is valid: report "0 files", compliance 100%, with an explicit zero-files note.
- **Compliance formula (fixes the upstream negative-compliance bug):** `compliance = 100 × (files with zero hard violations) / max(total files, 1)` — per-file boolean, so one bad file can't count three times.

### Checks (keyed to the §4.1 canonical schema)

| Check | Class |
|---|---|
| Frontmatter present; required fields `name`/`description`/`metadata.type` (flat `type:` accepted as legacy input) | hard |
| `metadata.type` ∈ {user, feedback, project, reference} | hard |
| `feedback` files contain a Why section — `## Why` or `## Root cause` heading, or bold-inline `**Why:**` / `**Root cause:**` (English synonyms carried from upstream; Chinese synonyms dropped per the language decision) | hard |
| Filename is kebab-case slug matching `name:` | hard |
| MEMORY.md links resolve to existing files (exact-filename match, digits allowed) | hard |
| Memory files not referenced from MEMORY.md (exact-filename match, no substring passes) | soft |
| Oversize file (> 100 lines or ≥ 5 H2) | soft |
| Index group overload (≥ 15 entries under one `##`) | soft |
| Index budget: warn **> 23,000** chars or **> 190** lines (hard native cap 25,000 chars / 200 lines); counted as decoded characters (`len()` on `str`) | soft (warn) |
| Entry line > 160 chars — a line containing ≥ 2 markdown links counts as an aggregate line and is exempt; the 110-char normal-entry budget is advisory-only, unenforced | soft |
| Untouched > 30 days — basis: filesystem mtime, best-effort (noted unreliable under file-sync tools); a signal, explicitly not a violation | info |

Upstream bugs fixed in the rewrite (verified against the upstream script): division-by-zero on an empty memory dir; broken-link regex excluding digits that the naming rule allows; index-membership check passing on substring collisions; CRLF breaking frontmatter detection; locale-dependent `wc -m` character counting (Python `len()` on decoded text is exact); one file able to log 3 violations and drive compliance negative (fixed by the per-file formula above).

Output mirrors upstream: per-check listings + `Hard-rule compliance: X% (N clean files / M files)`, target ≥ 95%, read-only.

**Code gates:** Python 3.10-compatible (package CI matrix runs 3.10–3.13); passes `ruff check` (E,F,W,I — import sorting included) and `mypy scripts --ignore-missing-imports`.

Tests: `claude-skills/tests/test_memory_audit.py` in the package pytest suite — fixture memory dirs covering each hard check, the empty-dir and missing-dir cases (exit codes), CRLF files, budget boundaries (23,000/190 exact values pass; +1 warns), aggregate-line exemption, and legacy flat-`type:` acceptance.

## 6. Wiring checklist (verified against manifests and validators)

| # | Change | File(s) |
|---|---|---|
| 1 | Skill body | `claude-skills/skills/memory-management/SKILL.md` (+ `references/audit-tool.md` in the skill dir) |
| 2 | Skill body | `codex-skills/skills/memory-management/SKILL.md` |
| 3 | Skill body | `antigravity-skills/skills/memory-management/SKILL.md` |
| 4 | Workflow shim | `antigravity-skills/.agent/workflows/memory-management.md` |
| 5 | Attribution | `ATTRIBUTION.md` in each of the three skill dirs |
| 6 | Manifest | claude `optional_skills[]` — insert between `docs-sync` and `observer`; add `scripts/memory_audit.py` to `runtime_files[]` |
| 7 | Manifest | codex `optional_skills[]` — insert between `mcp-server-patterns` and `observer` |
| 8 | Manifest | antigravity `skills[]` (between `manager` and `planner`) **and** `workflows[]` (`memory-management.md`) |
| 9 | Audit tool | `claude-skills/scripts/memory_audit.py` + `claude-skills/tests/test_memory_audit.py` |
| 10 | Root README counts | run `.\scripts\Update-ReadmePackageCounts.ps1` (81→84 total; rows 20→21, 32→33, 29→30); never hand-edit the count phrase; row blurbs updated manually if desired |
| 11 | Package README (claude) | `claude-skills/README.md` — Skills table row; both install-loop snippets; **Package Layout path-table row and per-project `cp` line for `scripts/memory_audit.py`** |
| 12 | Claude runtime-file doc surfaces | `claude-skills/docs/file-map.md`, `claude-skills/docs/skill-portability-notes.md` layout lists, `claude-skills/CLAUDE.md` Consumer Sync Workflow step 3 — all enumerate runtime files and go silently stale otherwise |
| 13 | Package README (codex) | `codex-skills/README.md` — Optional Engineering Skills table row (Trigger `auto`) + both install loops |
| 14 | Package README (antigravity) | `antigravity-skills/README.md` — Included Skills table row + status line "29 curated skills and 29 workflows" → 30/30 (unchecked by tooling; goes stale silently) |
| 15 | Eval cases | `claude-skills/eval/cases/` and `codex-skills/eval/cases/` — trigger case(s) for memory-management (codex CI validates the case file) |

**Not touched:** `release-manifest.json`, all `scripts/*.ps1`, both `test_skill_docs_contract.py` files (manifests are the real gate; deliberate assertions are a possible follow-up, see §8), historical docs under `docs/` (point-in-time records), `gemini-skills` (legacy).

## 7. Validation plan

1. `.\scripts\Test-ReadyPackages.ps1` — the machine gate; must exit 0. (Use its own exit code: `Test-ReleaseReadiness.ps1` does not propagate child failures.) `-Skip*Smoke` switches for fast iteration; full run before shipping (includes install/export/bootstrap smokes into temp dirs). Note: the antigravity shim-body reference check is warn-only — inspect the warning list, not just the exit code.
2. Package pytest suites (claude + codex), including the new `test_memory_audit.py`.
3. Claude package Python gates: `python -m ruff check scripts tests` and `python -m mypy scripts --ignore-missing-imports` (CI parity per `claude-skills/CLAUDE.md`; CI matrix is Python 3.10–3.13).
4. `.\scripts\Update-ReadmePackageCounts.ps1 -Check` clean.
5. `.\scripts\Compare-ProviderSkillParity.ps1` — informational; expect the new row at `DescriptionVariants=1`, `BodyVariants=3`.
6. Package CI conventions (claude/codex `validate.yml`, run when packages are exported to their own repos — mirrored locally by review): frontmatter `---` at line 1, column-0 `name:`/`description:` keys; markdownlint-cli2 on all `*.md` (MD013/MD033/MD041/MD024/MD032/MD040 disabled).
7. Run `python scripts/memory_audit.py --dir <live memory dir>` manually against the real Ai-Skills memory dir as an end-to-end sanity check (read-only).

### Known trap lines (enforced in review)

- No `scripts/…` substring anywhere in the codex SKILL.md body; in the claude body only `scripts/memory_audit.py` (bundled). The validator regex has no left anchor — even `skills/x/scripts/y` inside prose extracts and fails; only manifest-whitelisted paths pass.
- Description on one physical line in all three files; no YAML block scalars.
- No `/`- **or `$`-prefixed** references to source-only skills: claude body must avoid `observer-test`, `refactor-planner`, `telemetry-live-ops`, `worktree-manager` in either sigil form; codex body must avoid `telemetry-live-ops` in either form.
- Workflow shim filename must exactly equal the skill dir name + `.md`.
- Don't quote a "N install-ready skills" phrase in any new root-README prose (count updater requires the phrase exactly once).

## 8. Out of scope (follow-ups, user-triggered)

- Slimming the global `~/.claude/CLAUDE.md` memory block to a pointer at the installed skill (removes method duplication/drift).
- Local install (`Install-AgentSkills.ps1`) and OneDrive export refresh (`export-ready-skill-packages.ps1 -Force`). Until run, `Compare-AgentSkillRoots.ps1 -FailOnMissingOrStale` reporting Missing is expected.
- Optional regression assertions for the new skill in the two `test_skill_docs_contract.py` files.
- Any gemini-skills adaptation.
- Upstream sync policy: jau123 repo is a cherry-pick reference going forward; record this as a project memory once the port lands.
- Landing conventions (branch → PR to `main`, full gate before PR) are specified in the implementation plan, not here.
