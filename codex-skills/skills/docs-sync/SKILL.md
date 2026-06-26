---
name: docs-sync
description: "Detect documentation drift, stale claims, path mismatches, and merge conflict markers. Use when checking README, docs, status, or architecture consistency."
---

# Docs Sync - Documentation Surface Consistency

Detects when key documentation surfaces have diverged from each other or from
the actual codebase state. Catches contradictions, stale claims, merge conflict
markers, and version mismatches across the documentation surface.

**All commands run to completion autonomously.**

**Config:** `.codex/skills/project.toml` - doc surfaces in `[docs-sync]`

---

## Commands

| Command | Usage | Purpose |
|---------|-------|---------|
| `check` | `$docs-sync` or `$docs-sync check` | Full consistency scan |
| `surface` | `$docs-sync surface README.md` | Check a single doc against code |
| `fix` | `$docs-sync fix` | Auto-fix trivial inconsistencies |

Default to `check` if no command given.

---

## Setup: Read Config

Before any command:

1. Read `.codex/skills/project.toml`
2. Extract `[docs-sync]` section if present

### Config schema

```toml
[docs-sync]
# Documentation surfaces to monitor. Grouped by priority tier.

[docs-sync.tier1]
# High-traffic docs - checked thoroughly
files = ["AGENTS.md", "README.md", "STATUS.md", "CONTRIBUTING.md"]

[docs-sync.tier2]
# Planning and architecture docs - checked for key claims
files = ["docs/architecture/*.md", "docs/planning/*.md"]

# Claims to cross-reference across all surfaces.
# Each claim type maps to a source of truth in code.
[docs-sync.claims]
version = { source = "package.json:version", pattern = "version.*?(\\d+\\.\\d+\\.\\d+)" }
schema-version = { source = "src/config.h", pattern = "SCHEMA_VERSION\\s+(\\d+)" }
api-routes = { source = "src/routes/**", extract = "route-registrations" }
build-commands = { source = "Makefile", extract = "targets" }
```

### Fallback (no config)

If no `[docs-sync]` section:
1. Auto-discover documentation files:
   - Tier 1: `README.md`, `AGENTS.md`, `CONTRIBUTING.md`, `STATUS.md`
   - Tier 2: `docs/**/*.md`, `*.md` in project root
2. Auto-detect claim types from document content
3. Report what was found and suggest config

---

## Documentation Surfaces

### Tier 1 - High-traffic (checked thoroughly)

These docs are frequently read by humans and AI agents. Contradictions here
cause the most damage.

Common surfaces:
- `README.md` - setup instructions, feature list, build commands
- `AGENTS.md` - AI agent instructions, project conventions
- `STATUS.md` - current state, metrics, build status
- `CONTRIBUTING.md` - build/test commands, dev setup

### Tier 2 - Planning docs (checked for key claims)

These inform architecture decisions. Stale claims lead to bad plans.

Common surfaces:
- `docs/architecture/*.md` - system design, module descriptions
- `docs/planning/*.md` - roadmaps, contracts, tech specs
- `docs/api/*.md` - endpoint documentation

---

## Claim Types and Verification

### Path existence

Every file path mentioned in a doc must exist on disk.
```
Pattern: backtick-wrapped paths, code blocks with paths
Check: file/directory exists via `rg --files` or direct path checks
```

### Version references

Version numbers must match across all surfaces.
```
Source: package.json, Cargo.toml, pyproject.toml, or configured source
Check: grep all docs for version patterns, compare against source
```

### Build/test commands

Commands documented must actually work.
```
Source: Makefile, package.json scripts, configured commands
Check: command/script exists (not executed - just verify it's defined)
```

### API routes

Routes documented must exist in code.
```
Source: route registration files
Check: grep for route patterns, compare against documented routes
```

### Cross-doc consistency

The same fact stated in multiple docs must agree.
```
Check: extract key claims from each surface, cross-reference for contradictions
```

### Conflict markers

Merge conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`) must not exist.
```
Check: grep all doc files for conflict marker patterns
```

---

## Command: `check` - Full Consistency Scan

### Steps

1. **Conflict markers**: Search all doc files for `<<<<<<<`, `=======`, `>>>>>>>`
   - Any found = immediate FAIL

2. **Path existence**: Extract all file paths from docs, verify each exists
   - Missing path = FAIL
   - Path with different case = WARN (case-sensitive filesystems)

3. **Version sync**: Extract version from source of truth, grep all docs
   - Mismatch = FAIL

4. **Build command validity**: Extract documented commands, verify scripts exist
   - Missing script = FAIL
   - Deprecated flag = WARN

5. **API route consistency** (if routes configured): Compare doc routes vs code
   - Doc-only route = WARN (possibly removed)
   - Code-only route = WARN (undocumented)

6. **Cross-doc contradictions**: Extract key claims from each surface,
   compare across all surfaces
   - Contradiction = FAIL

7. **Staleness**: Check last-modified dates of status/metrics docs
   - > 7 days with dynamic claims = WARN

### Report

```
Docs Sync - Check

  Conflict Markers:
    PASS - no conflict markers found

  Path Existence:
    FAIL - README.md:45 references "src/old-module.py" (does not exist)
    PASS - 23/24 paths verified

  Version Sync:
    PASS - version 2.1.0 consistent across 4 surfaces

  Build Commands:
    PASS - all documented commands exist

  Cross-Doc Consistency:
    FAIL - AGENTS.md says port 8080, CONTRIBUTING.md says port 3000

  Staleness:
    WARN - STATUS.md last updated 12 days ago

  Result: FAIL (2 failures, 1 warning)
```

Exit 0 if no FAIL items, exit 1 if any FAIL.

---

## Command: `surface` - Single Document Check

Runs all checks scoped to one file. Faster for targeted verification.

Usage: `$docs-sync surface CONTRIBUTING.md`

Checks:
- Conflict markers in that file
- All paths referenced in that file
- All version claims in that file
- All commands documented in that file
- Cross-reference that file's claims against other surfaces

---

## Command: `fix` - Auto-Fix Trivial Issues

Auto-fixes:
- **Version numbers**: Update stale version references to match source of truth
- **Path corrections**: If file was renamed and new path is unambiguous, update
- **Conflict markers**: Remove obvious resolved markers (all-ours or all-theirs)

Does NOT auto-fix:
- Cross-doc contradictions (need human judgment on which is correct)
- Missing paths where destination is ambiguous
- Stale statistics or metrics
- Build command changes

Reports what was fixed and what needs manual attention.

---

## Drift Validation Family

Docs-sync is one of three parallel drift validators. They check
different surfaces and can run independently or together:

| Skill | Checks | Surface |
|-------|--------|---------|
| `$schema-validator` | Code <-> Code | Schema authority vs consumer layers |
| `$truthpack-drift` | Truth <-> Code | Declared truth stores vs actual codebase |
| `$docs-sync` | Docs <-> Code + Docs <-> Docs | Documentation vs code and cross-doc consistency |

**Run all three together** for comprehensive drift detection.

## Integration

| Skill | How Docs Sync Helps |
|-------|---------------------|
| `$manager verify` | Include docs-sync check in campaign exit criteria |
| `$schema-validator` | Parallel validator - schema checks code-to-code; docs-sync checks code-to-docs |
| `$truthpack-drift` | Parallel validator - truthpack checks truth-to-code; docs-sync checks docs |
| `$ship` | Quick check before commit catches stale doc references |
| `$observer` | Record `drift` observations for documentation divergence |
| `$qa` | Docs-sync complements code quality with documentation quality |

---

## Conventions

- Read project.toml for all project-specific config
- Never delete documentation - only update or flag
- Conflict markers are always FAIL (highest severity)
- Cross-doc contradictions are always FAIL
- Staleness and undocumented items are WARN
- Report all surfaces even when most are clean
- Auto-fix only when the correct value is unambiguous
