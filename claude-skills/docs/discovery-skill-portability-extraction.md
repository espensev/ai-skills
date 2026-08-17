# Discovery — Skill Portability Extraction from WinOverSight

**Goal:** Map WinOverSight project-specific skills against portable AI-Skills repo — what was extracted, what chains depend on, and what the ideal portabilization workflow looks like.
**Date:** 2026-03-26
**Status:** complete
**Recommended next:** Create EXTRACTION-LINEAGE.md and add provenance markers to extracted skills.

> Historical note (2026-08-09): this audit records the March extraction state.
> The standalone `observer-test` skill was later retired; current observation
> capture is provided by the `observer` skill and its standalone hooks, while
> `manager` promotes any worktree-local `observations.jsonl` files.

---

## Questions

1. What project-specific hardcoding existed in WinOverSight skills, and how was it parameterized?
2. Are all config sections present in project.toml.template?
3. What are the actual chain integration contracts — do outputs match inputs?
4. What provenance data is missing?

---

## Findings

### Q1: Hardcoding → Parameterization Map

7 skills were extracted from WinOverSight. Each had project-specific surfaces that were replaced with config-driven alternatives:

| Skill | WinOverSight Hardcoding | Portable Strategy | Config Section |
|-------|------------------------|-------------------|----------------|
| **smart-test** | C/C#/Python three-stack; native/launcher/scripts paths; explicit file-to-test tables | Pluggable 4-tier mapping: explicit → module → convention → import-based | `[smart-test]` |
| **schema-validator** | `native/src/schema.c` authority, C# SqliteDataService consumer, Python contract tests | Multi-format authority (11 types), configurable consumer layers | `[schema-validator]` |
| **truthpack-drift** | `.vibecheck/truthpack/` with `mg_set_request_handler` grep, C# env var patterns | 7 built-in extraction strategies + custom regex | `[truthpack-drift]` |
| **docs-sync** | 8 hardcoded doc files, `enforce_conflict_markers.py`, `cov.h` schema version | Unlimited user-configurable surfaces + claim type framework | `[docs-sync]` |
| **build-gate** | 3 targets (native/launcher/mixed), PowerShell scripts, `WinOverSight.exe` paths | Multi-target with `depends`, pluggable build/verify/test per target | `[build-gate.<name>]` |
| **campaign-health** | `campaign.py` backend commands, hardcoded 50K/100K line thresholds | Auto-detect backend type (SQLite/JSON/file), generic metrics | `[paths]` + `[observer]` |
| **worktree-preflight** | `scripts/worktree/*.ps1`, implicit path assumptions | Config-driven plan directory + conflict zones | `[paths]` + `[conflict-zones]` |

**Detail lost:** Language-specific extraction guidance (C# ORM patterns, MSVC setup, dotnet SDK detection, Mongoose HTTP handler syntax). These are project-specific and belong in project.toml config, not in the portable skill.

**Detail gained:** Multi-language support, auto-detection fallbacks, custom regex extraction, unlimited targets/surfaces/consumers.

**Evidence:**
- WinOverSight smart-test: hardcoded `native/src/*.c → native/tests/test_*.c` table
- Portable smart-test: `[smart-test.mappings]` config with user-provided globs
- WinOverSight build-gate: `build.ps1 -Target native`, `dist/native/WinOverSight.exe`
- Portable build-gate: `[build-gate.backend].build`, `[build-gate.backend].artifacts`

**Implications:** The portable versions are strictly more capable but less prescriptive. Projects with unusual stacks need to configure their `[skill-name]` sections; the auto-detection fallback covers common cases.

### Q2: project.toml.template Coverage

**Answer:** 100% complete after fixes. All 14 config sections are present.

**Evidence:** Template sections verified (line counts from current file):
- `[project]`, `[paths]`, `[commands]` — required, uncommented
- `[modules]`, `[conflict-zones]`, `[analysis]`, `[smoke-test]`, `[ship]` — optional, commented
- `[build-gate.<name>]`, `[schema-validator]`, `[truthpack-drift]`, `[docs-sync]`, `[smart-test]`, `[observer]` — optional, commented with sub-table examples

**Implications:** No skill will fail due to missing template section. Auto-detection fallbacks provide graceful degradation.

### Q3: Chain Integration Contracts

Three chains were audited:

**Chain 1: Campaign Lifecycle** (discover → planner → manager → observer-test → observer → campaign-health)
- discover outputs `docs/discovery-{name}.md` → planner scans `docs/discovery-*.md` — **PASS**
- planner outputs `data/plans/{plan-id}.json` → manager reads `[paths].plans` — **PASS**
- manager injects observer-test init into agent prompts → observer-test creates `observations.jsonl` — **PASS** (fixed during chain audit)
- observer-test exports JSON array → manager merge promotes via `/observe note` — **PASS**
- observer stores to `[observer].storage` → campaign-health reads same path — **PASS** (fixed during chain audit)

**Chain 2: Build/Test** (build-gate → smart-test → qa)
- These are **scope tiers**, not a sequential chain:
  - smart-test = changed files only (fast)
  - qa = full suite (comprehensive)
  - build-gate test = per-build-target (pipeline-scoped)
- All report compatible pass/fail/count/time format — **PASS**
- Documented as scope hierarchy in smart-test Integration section — **PASS** (fixed during chain audit)

**Chain 3: Drift Detection** (schema-validator + truthpack-drift + docs-sync)
- **Parallel family**, not sequential. All share:
  - Exit codes: 0 = PASS/WARN, 1 = FAIL
  - Observer category: `drift`
  - Status semantics: PASS/FAIL/WARN per entity
- Documented as "Drift Validation Family" in all three skills — **PASS** (fixed during chain audit)

**Implications:** All chains are now compatible. 6 gaps were found and fixed during the audit phase.

### Q4: Provenance Missing

**Answer:** No extraction lineage is documented anywhere.

**Evidence:**
- No `UPSTREAM.md` in portable repo
- No `EXTRACTION-LINEAGE.md`
- No `extracted-from` field in any SKILL.md frontmatter
- `docs/skill-portability-notes.md` documents the artifact model but not per-skill origins
- WinOverSight has `UPSTREAM.md` in its skills dir but it references `Workflow-standardized`, not AI-Skills

**Implications:** Future maintainers can't trace which skills came from WinOverSight, what was parameterized, or when. Divergence between project-specific and portable versions will be invisible.

---

## Cross-Cutting Analysis

### Constraints
- Portable skills must work with zero config (auto-detection fallback)
- Each skill's config section must be independently optional
- project.toml.template is the single source of config schema documentation
- Skills in `~/.claude/skills/` are junctioned via OneDrive — changes sync across 3 machines

### Risks
| Risk | Likelihood | Impact | Notes |
|------|-----------|--------|-------|
| WinOverSight skills diverge from portable versions | High | Medium | No sync mechanism between project-specific and portable |
| Config schema changes break existing project.toml files | Low | High | Template is append-only; new sections are commented out |
| Chain contracts drift as skills are updated independently | Medium | High | No integration tests verify handoff compatibility |

### Open Questions
All questions answered.

---

## Recommendation

Findings support proceeding. Two immediate actions:

1. **Create `EXTRACTION-LINEAGE.md`** in `D:/Development/Ai-Skills/claude-skills/docs/` documenting the 7 extracted skills, their WinOverSight origins, extraction date, and what was parameterized.

2. **Add provenance to SKILL.md frontmatter** — `extracted-from` and `portable-since` fields for the 7 extracted skills.

Longer-term: add chain integration tests to the CI pipeline (`validate.yml`) to catch handoff drift.

---

## Appendix: Ideal Portabilization Workflow

For future skill extractions from any project:

```
1. /discover "map <project> skills for portability"
   → findings doc identifying hardcoded surfaces, chain deps, config needs

2. /planner "portabilize N skills + install M existing"
   → plan with template updates as explicit task, one creation pass

3. /observe-test start
   → observations recorded throughout

4. Create all skills + template updates in ONE pass
   → no partial installs

5. Chain audit BEFORE individual validation
   → integration > structure

6. Fix gaps found in chain audit

7. One install to ~/.claude/skills/

8. /observe-test report → score
   → final validation with structured results
```
