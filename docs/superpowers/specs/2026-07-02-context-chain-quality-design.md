# Context-Chain Quality: Design

**Date:** 2026-07-02
**Goal:** Improve the quality of "first Claude" — the context a fresh Claude
session boots with on every machine — by fixing drift across the layered
CLAUDE.md chain, making its volatile facts generated + drift-checked, and
introducing agents as a repo product line whose first member serves the
context system itself.

## Background

The context chain has three tiers:

| Tier | File | Scope |
|---|---|---|
| Machine | `~/.claude/CLAUDE.md` → `D:\DevHome\state\claude\CLAUDE.md` | Per-machine identity + pointers |
| Shared | `OneDrive\common\common_dev\CLAUDE.md` | All machines: inventory, skills, infra |
| Project | `Ai-Skills/*/CLAUDE.md` (claude-skills, skills, cc-workflow, provider AGENTS.md/GEMINI.md) | Per-package conventions |

Verified drift (2026-07-02):

- Machine tier says "Machine: MAINDESK"; `machines.json` (declared single
  source of truth) says machine=`SND-DESK`, alias=`maindesk`. "MAINDESK" is an
  invented name that appears nowhere in the truth store.
- Shared tier's machine table lists the alias for SND-DESK as `SND-DESK`;
  truth is `maindesk`. Its "Connect:" line propagates the same error.
- Shared tier's provider-target counts ("20 install-ready (24 in source)") and
  ready-package paths are the known-stale category (see memory
  `ai-skills-onedrive-export-refresh`).
- Auto-memory files also use "MAINDESK" and reinforce the wrong name each
  session.
- Every custom-agent directory (`~/.claude/agents`, DevHome state, all five
  repo `agents/` dirs) is empty — "agents" today means plugin-provided only.

## Decisions (user-confirmed)

1. **Scope:** whole chain — machine + shared + repo tiers.
2. **Maintenance:** generate volatile facts from truth sources + drift-check;
   hand-written prose stays hand-written.
3. **Agents:** become repo products shipped like skills; first candidates
   serve the context system.
4. **Blend:** Approach C (split on the privacy boundary) as spine; adopt B's
   fix-first sequencing and A's genericize-later ambition as a final optional
   phase. Rejected: generation logic living in the public repo from day one
   (privacy), agents staying share-only forever (contradicts #3).

## Architecture

The privacy boundary decides where every piece lands:

- **Private side (OneDrive `common_dev`)** — generation of personal facts,
  drift-check config. Sibling scripts `Update-SharedLive.ps1` /
  `Update-OpsSurfaces.ps1` already establish the pattern.
- **Public side (Ai-Skills repo)** — generic, portable agent definitions and
  the install/export pipeline. No personal data; specifics come from private
  config (the `truthpack-drift` pattern: generic engine, `project.toml`
  config).

Producer→consumer direction is preserved: the repo produces, OneDrive
distributes, DevHome junctions consume. Generation runs only on SND-DESK
(where the repo lives); OneDrive sync distributes results to other machines.

Edit surfaces: `D:\Development\Ai-Skills` is read-only for Claude — all repo
changes (Phase 4, and Phase 5 if promoted) land via a DevHome worktree branch
and PR. OneDrive `common_dev` and DevHome state files are not repos and are
edited in place (Phases 1–3).

## Phases

### Phase 1 — Fix now (hand-edit, no tooling prerequisite)

- Standardize naming on `machines.json` fields everywhere: machine=`SND-DESK`,
  alias=`maindesk`. Retire "MAINDESK".
- Machine tier: fix identity block; keep the DevHome-vs-Development role-split
  prose (deliberately duplicated 2026-07-02; keep short-pointer form).
- Shared tier: fix alias column + Connect line; fix provider-target counts
  against current reality; verify/fix every referenced path.
- Auto-memory: update memory files that assert "MAINDESK" (at minimum
  `MEMORY.md` index lines and any memory whose body names the machine).

### Phase 2 — Generate (`Update-SharedContext.ps1`, OneDrive side)

Idempotent PowerShell script rewriting marked blocks in the shared CLAUDE.md:

```markdown
<!-- BEGIN GENERATED: machines (source: machines.json; regen: Update-SharedContext.ps1) -->
| Machine | Alias | Endpoint | User | Role |
| ...one row per machines.json entry... |
Connect: `ssh maindesk`, `ssh host`, `ssh remote`
<!-- END GENERATED: machines -->
```

Blocks (exactly three; everything else stays hand-written):

| Block | Source |
|---|---|
| `machines` | `machines.json` (table + connect line). Requires adding a `role` field per machine to machines.json |
| `provider-targets` | repo `release-manifest.json` + counting actual skill dirs in source packages |
| `shared-set-count` | counting OneDrive `.claude\skills\` dirs; emitted with an as-of date |

The curated core-workflow skill table remains editorial (hand-written).

Script contract:

- In-place rewrite between markers; idempotent (re-run → no diff).
- `-CheckOnly` exits non-zero and prints a diff when any block is stale —
  this flag is the drift-check primitive consumed by Phase 3.
- Repo path parameterized with default `D:\Development\Ai-Skills`.
- Machine tier is **checked, not generated**: identity facts must match the
  `machines.json` entry for the current hostname. Repo-tier CLAUDE.mds:
  checked only (they are already good quality).

### Phase 3 — Drift-check wiring

- `[docs-sync]` surface config (OneDrive-side `project.toml`) declaring the
  three tiers as surfaces, so `/docs-sync check` catches cross-tier
  contradictions and stale paths.
- qa cadence includes `Update-SharedContext.ps1 -CheckOnly`.

### Phase 4 — Agents pipeline (public side)

Repo layout: `claude-skills/agents/<name>.md`, mirroring
`claude-skills/skills/`. Standard Claude Code subagent format (frontmatter:
`name`, `description`, `tools`; body = system prompt). Claude-only for now.

Distribution:

```
repo claude-skills/agents/ ──Install-AgentSkills.ps1 (extended)──► OneDrive\common_dev\.claude\agents\ (new)
                                                                        ▼ junction (new)
                                      ~/.claude/agents ◄── DevHome\state\claude\agents
```

- Junction created on SND-DESK immediately; other machines via the existing
  `pending/` queue + `Run-Pending.ps1` (or next bootstrap run).
- Register the junction in DevHome `manifests/` exactly like the skills
  junction, so relink automation defends rather than fights it.
- Export to ready-packages stays manual-with-`-Force`, same as today.
- README + release-manifest notes updated to mention the agents surface.

First agent — `context-auditor` (report-only, never edits):

- Frontmatter tools: `Read, Glob, Grep, Bash` — enough to check, not to
  quietly rewrite.
- Generic engine, private config: the definition audits "a layered context
  chain declared in config"; the private config (tier locations,
  machines.json path) lives OneDrive-side. No personal data in the repo.
- Procedure: (1) run `Update-SharedContext.ps1 -CheckOnly`; (2) cross-tier
  scan — machine-tier identity vs machines.json for current hostname, shared
  tier claims vs release-manifest, existence of every referenced path;
  (3) memory-index scan for contradictions with truth sources; (4) output a
  drift table with severity + suggested fix per row.

### Phase 5 — Promote (later, optional)

Once Phases 1–4 are proven in use, genericize the Phase-2 generator into a
public repo product (config-driven skill or script, `extracted-from`
convention), joining `docs-sync`/`truthpack-drift` as portable
context-hygiene tooling. Explicitly out of scope for the initial
implementation.

## Error handling

- `Update-SharedContext.ps1` refuses to write when markers are missing,
  unbalanced, or duplicated (fail loud; never guess block boundaries).
- OneDrive sync conflicts: script writes atomically (temp file + move) and
  never runs from two machines by design (repo lives only on SND-DESK).
- `context-auditor` degrades gracefully off-SND-DESK: repo-sourced checks
  report "repo not present on this machine" instead of failing the audit.

## Testing

- Generator: golden-file test — run twice on a fixture CLAUDE.md, assert
  idempotency; corrupt-marker fixtures assert refusal. `-CheckOnly` exit
  codes asserted for clean/stale fixtures.
- Pipeline: `Install-AgentSkills.ps1` extension covered the same way its
  skill-copy behavior is covered today; `Test-ReadyPackages.ps1` /
  release-readiness checks extended to know about `agents/`.
- End-to-end: fresh session on SND-DESK after Phase 1 answers "what machine
  is this?" with SND-DESK/maindesk; `/docs-sync check` runs clean.

## Success criteria

1. No tier contradicts `machines.json` or `release-manifest.json`.
2. Re-running the generator is a no-op when nothing changed.
3. A deliberate edit to `machines.json` is flagged by `-CheckOnly` within the
   qa cadence and by the `context-auditor` agent on demand.
4. `~/.claude/agents/context-auditor.md` resolves on SND-DESK via the new
   junction, sourced from the repo.
