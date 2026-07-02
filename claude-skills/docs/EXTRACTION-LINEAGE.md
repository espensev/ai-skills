# Extraction Lineage — Portable Skills from Project-Specific Origins

Tracks which skills were extracted from project-specific implementations,
what was parameterized, and when.

## Extracted Skills

| Skill | Origin Project | Extracted | Hardening | What Changed |
|-------|---------------|-----------|-----------|--------------|
| build-gate | WinOverSight | 2026-03-26 | stable | 3 hardcoded targets → multi-target `[build-gate.<name>]` with `depends`; PowerShell → platform-agnostic; added verify→plan→test→build pipeline |
| smart-test | WinOverSight | 2026-03-26 | stable | C/C#/Python three-stack mapping → 4-tier pluggable strategy (explicit → module → convention → import); added `[smart-test]` config |
| schema-validator | WinOverSight | 2026-03-26 | stable | Native C authority + C# consumer → 11 schema formats with configurable consumer layers; added `[schema-validator]` config |
| truthpack-drift | WinOverSight | 2026-03-26 | stable | `.vibecheck/truthpack/` with WinOverSight-specific grep patterns → 7 built-in extractors + custom regex; added `[truthpack-drift]` config |
| docs-sync | WinOverSight | 2026-03-26 | stable | 8 hardcoded doc surfaces → unlimited configurable surfaces + claim type framework; added `[docs-sync]` config |
| campaign-health | WinOverSight | 2026-03-26 | stable | `campaign.py` backend commands → auto-detect backend type (SQLite/JSON/file); added observation storage integration |
| worktree-preflight | WinOverSight | 2026-03-26 | stable | `scripts/worktree/*.ps1` → config-driven plan directory + conflict zones |

## Native Portable Skills (no extraction needed)

| Skill | Origin | Notes |
|-------|--------|-------|
| discover | AI-Skills repo | Portable from inception |
| planner | AI-Skills repo | Portable from inception |
| manager | AI-Skills repo | Portable from inception; chain fixes added 2026-03-26 (preflight + observer-test injection) |
| qa | AI-Skills repo | Portable from inception |
| ship | AI-Skills repo | Portable from inception |
| observer | AI-Skills repo | Portable from inception |
| observer-test | AI-Skills repo | Portable from inception |
| worktree-manager | AI-Skills repo | Portable from inception |
| refactor-planner | AI-Skills repo | Deprecated — use `/planner --mode refactor` |

## Chain Fixes Applied (2026-03-26)

During extraction, chain audit revealed 6 integration gaps that were fixed:

1. **manager → worktree-preflight**: manager now runs preflight before agent launch
2. **manager → observer-test**: manager now injects observer-test init into agent prompts
3. **observer → campaign-health**: campaign-health now reads `[observer].storage`
4. **smart-test ↔ qa ↔ build-gate**: documented as scope tiers, not sequential chain
5. **schema-validator + truthpack-drift + docs-sync**: documented as parallel drift family
6. **project.toml.template**: added 4 missing config sections (schema-validator, truthpack-drift, docs-sync, smart-test)

## Portabilization Pattern

When extracting a project-specific skill:

1. Identify every hardcoded path, file pattern, tool name, and threshold
2. Replace with a `[skill-name]` section in project.toml
3. Add auto-detection fallback for unconfigured projects
4. Verify chain contracts still match after parameterization
5. Add entry to this lineage doc
