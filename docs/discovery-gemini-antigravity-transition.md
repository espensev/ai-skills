# Discovery - Gemini / Antigravity Transition

**Goal:** Investigate whether `gemini-skills` is still really a Gemini package.
**Date:** 2026-06-26
**Status:** complete
**Implementation update:** split completed on 2026-06-26. `antigravity-skills`
is now the ready Google-facing package, and `gemini-skills` is retained as a
legacy Gemini CLI source package.
**Recommended next:** verify the Antigravity workflow layout against a live
Antigravity CLI install when available.

---

## Questions

1. What did Google change about Gemini CLI externally?
2. What does this repo currently ship from `gemini-skills`?
3. What local files make `gemini-skills` look non-Gemini or hybrid?
4. Does the ready-package export still stay bounded?
5. What should the repo do next?

---

## Findings

### Implementation Update - 2026-06-26

The recommendation in this discovery has been applied as a split rather than a
rename:

- `release-manifest.json` now marks `antigravity-skills` as `ready` with
  strategy `antigravity-adapter`.
- `release-manifest.json` keeps `gemini-skills` as `legacy`, so it remains in
  the repo but is not part of the default ready export.
- `antigravity-skills/scripts/bootstrap.ps1` installs manifest-listed skills
  into `.agents/skills/`, workflows into `.agent/workflows/`, and appends
  package guardrails into `AGENTS.md`.
- `scripts\Test-ReadyPackages.ps1` and
  `scripts\export-ready-skill-packages.ps1` now understand the Antigravity
  adapter shape.

### Q1: What did Google change about Gemini CLI externally?

**Answer:** Google has publicly moved consumer Gemini CLI usage toward Antigravity CLI. That means a package named only `gemini-skills` is now at least a legacy label for consumer users, even if enterprise/API-key Gemini CLI support remains relevant.

**Evidence:**
- Official Google Developers Blog, "Transitioning Gemini CLI to Antigravity CLI", dated 2026-05-19, says Google is unifying efforts into Google Antigravity and a new terminal experience, Antigravity CLI: <https://developers.googleblog.com/an-important-update-transitioning-gemini-cli-to-antigravity-cli/>.
- The same announcement says Gemini CLI and Gemini Code Assist IDE extensions stop serving requests for Google AI Pro, Ultra, and free individual use on 2026-06-18, while enterprise/API-key access remains supported.
- Google Antigravity migration docs exist at <https://antigravity.google/docs/gcli-migration>. The shell/browser view here did not expose extractable lines, so treat that page as an implementation source to verify exact target paths before edits.

**Implications:**
- Current docs saying only "Gemini CLI" are stale for consumer-facing usage.
- This repo should either preserve `gemini-skills` as a legacy/enterprise Gemini package or move the active package identity to Antigravity.

### Q2: What does this repo currently ship from `gemini-skills`?

**Answer:** The ready export still ships a manifest-bounded Gemini adapter: 29 manifest skills and 29 `.gemini/commands` wrappers. It does not ship the large ignored ECC mirror or the unmanifested folders.

**Evidence:**
- `release-manifest.json:21-25` marks `gemini-skills` as ready, strategy `gemini-adapter`, audience `Gemini`.
- `gemini-skills/package/install-manifest.json:2-33` defines `delivery: bootstrap-adapter` and the 29 skills that ship.
- `gemini-skills/package/install-manifest.json:34-63` defines the 29 command wrappers that ship.
- `scripts/export-ready-skill-packages.ps1:95-113` copies only `README.md`, `GEMINI.md`, `scripts/bootstrap.ps1`, `docs/skill-portability-notes.md`, manifest-listed skills, manifest-listed wrappers, and the install manifest.
- Export smoke to `dist/investigate-gemini-export` produced only `.gemini/`, `docs/`, `package/`, `scripts/`, `skills/`, `GEMINI.md`, and `README.md` under the exported `gemini-skills` package.

**Implications:**
- The packaging boundary is still healthy.
- The naming and adapter target are the stale parts, not the export selection logic.

### Q3: What local files make `gemini-skills` look non-Gemini or hybrid?

**Answer:** The source tree is already a hybrid of Gemini, ECC, Antigravity, and ignored upstream reference material.

**Evidence:**
- `gemini-skills/README.md:1-8` presents the package as "Gemini Campaign Skills" for Gemini CLI.
- `gemini-skills/README.md:68-73` says significant capabilities were ported from `everything-claude-code`, including domain skills and continuous learning.
- `gemini-skills/README.md:116-119` still calls the package "v1.0 Ready" for Gemini CLI.
- `gemini-skills/GEMINI.md:3-7` calls the folder an experimental Gemini adapter and warns against copying from Claude/Codex.
- `gemini-skills/GEMINI.md:24-34` still contains Gemini-specific guardrails such as avoiding `.claude` and `.codex` paths.
- Inventory command output found 53 `gemini-skills/skills/*/SKILL.md` directories on disk, but only 29 are manifest-listed.
- Inventory command output found 32 `.gemini/commands/*.toml` files on disk, but only 29 are manifest-listed; extra wrappers are `continuous-learning.toml`, `tdd.toml`, and `telemetry-live-ops.toml`.
- `.gitignore:44-49` explicitly describes an ECC ecosystem mirror under `gemini-skills/` and says the raw fork is local reference material, not vendored into the monorepo.
- `.gitignore:50-79` ignores `gemini-skills/agents/`, `commands/`, `hooks/`, `manifests/`, `mcp-configs/`, `rules/`, `schemas/`, and many imported docs/scripts.
- `gemini-skills/everything-claude-code/` is ignored by `.gitignore:42` and contains `.agents/`, `.claude/`, `.codex/`, `.cursor/`, `.opencode/`, `commands/`, `hooks/`, `plugins/`, and other multi-target upstream material.
- `gemini-skills/.claude/settings.local.json:1-7` exists locally and grants Claude-style read permissions for this folder; it is ignored by `**/.claude/settings.local.json`.

**Implications:**
- The source checkout looks "not Gemini" because it is carrying local and tracked cross-poll material.
- The README is mixing three concepts: legacy Gemini CLI, curated Gemini adapter, and ECC/Antigravity future direction.
- The tracked extra skills and wrappers should either be manifest-promoted, quarantined as source-only, or moved to a separate reference/package area.

### Q4: Does the ready-package export still stay bounded?

**Answer:** Yes. The actual ready export remains bounded to the manifest. The root validation script reports the wrapper drift as a warning, not an export failure.

**Evidence:**
- `scripts/Test-ReadyPackages.ps1` output in the previous validation pass: `gemini-skills` had 29 skills, 29 wrappers, and 3 extra source wrappers; validation passed with a warning.
- Export inspection showed the exported `gemini-skills/.gemini/commands/` contained only manifest-listed wrappers such as `diagnosing-bugs.toml`, `discover.toml`, `qa.toml`, `review.toml`, and did not include `continuous-learning.toml`, `tdd.toml`, or `telemetry-live-ops.toml`.
- `gemini-skills/scripts/bootstrap.ps1:28-31` still installs into `.gemini/skills` and `.gemini/commands`.
- `gemini-skills/scripts/bootstrap.ps1:79-85` rewrites source wrapper includes from `@{../../skills/...}` to installed `@{../skills/...}`.

**Implications:**
- Current release risk is mostly mislabeling and future incompatibility, not accidental export of the full ECC mirror.
- If the active target is now Antigravity, the bootstrap installer is likely the central file that must change because it hardcodes `.gemini`.

### Q5: What should the repo do next?

**Answer:** Decide whether `gemini-skills` is legacy Gemini or the active Google/Antigravity provider package. The evidence favors creating an Antigravity migration path rather than pretending the current package is still purely Gemini.

**Recommended direction:**
- Short term: relabel docs as "Gemini CLI legacy adapter / Antigravity migration pending" so current README claims are accurate.
- Medium term: add a new `antigravity-skills` package or rename `gemini-skills` after verifying exact Antigravity CLI project layout from official docs.
- Keep `gemini-skills` only if this repo intentionally supports enterprise/API-key Gemini CLI users.
- Convert the bootstrap target deliberately: `.gemini/skills`, `.gemini/commands`, and `GEMINI.md` should not be mechanically renamed without checking Antigravity's current `.agent`/`.agents` conventions.
- Move or quarantine unmanifested tracked skills/wrappers so the source folder stops looking like a half-imported everything-package.

---

## Cross-Cutting Analysis

### Constraints

- Ready export is manifest-driven and should stay that way.
- `gemini-skills/scripts/bootstrap.ps1` hardcodes `.gemini` install paths today.
- Official Antigravity migration details need to be treated as the source of truth before changing install paths.
- The worktree is dirty and contains unrelated imported/reference material; any rename or split should stage explicit paths only.

### Risks

| Risk | Likelihood | Impact | Notes |
|---|---:|---:|---|
| Keeping "Gemini CLI" labels misleads consumer users after Google's transition | High | Medium | Official announcement moved consumer tiers to Antigravity CLI. |
| Mechanical rename to Antigravity breaks real Gemini enterprise/API-key users | Medium | Medium | Google announcement says enterprise/API-key Gemini CLI remains supported. |
| Adopting Antigravity paths incorrectly | Medium | High | Local ignored mirror uses `.agents` and `.agent`-looking surfaces; verify official docs before edits. |
| Source/package drift worsens if ignored ECC mirror and manifest package stay in one folder | High | Medium | 53 skill dirs on disk vs 29 manifest skills. |

### Open Questions

- Does this repo want to support legacy/enterprise Gemini CLI as a first-class package?
- Should the active Google package become `antigravity-skills`, or should `gemini-skills` be renamed in place?
- What is the exact current Antigravity CLI project install layout for skills, commands/workflows, and context files?

---

## Recommendation

Do not keep calling the active package simply "Gemini CLI" without a caveat. The next implementation pass should be a provider-boundary cleanup:

1. Update docs to mark `gemini-skills` as legacy Gemini plus Antigravity migration candidate.
2. Verify Antigravity CLI layout from official docs.
3. Choose either split (`gemini-skills` legacy + new `antigravity-skills`) or rename (`gemini-skills` -> `antigravity-skills`).
4. Only after that, change `release-manifest.json`, bootstrap paths, package docs, and wrapper directories.
