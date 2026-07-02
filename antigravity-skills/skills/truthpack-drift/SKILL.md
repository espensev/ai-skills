---
name: truthpack-drift
description: Compare declared truth files (JSON/YAML/TOML fact stores) against the actual codebase to detect divergence. Catches stale single-source-of-truth references. Use when a project ships truth stores like routes.json, schemas.json, or features.toml.
---

# Truthpack Drift Protocol

## Core Mandate
Compare declared truth files (structured fact stores) against the actual codebase to detect divergence. When a project declares certain files as the "single source of truth" for routes, schemas, config, etc., verify those claims still hold. Read-only by design — never auto-modify truth files.

Not to be confused with `truthpack-validator`: that skill is a pre-implementation assumption guardrail (it gates work against fixed project tiers before you code), whereas truthpack-drift is a read-only code-vs-truth divergence scan you run against any project's declared truth stores.

## Execution Rules
1. **Follow the global guardrails in AGENTS.md.** This is a read-only ops skill — it does not gate on the Planning Contract.
2. **The codebase is always right:** truth files must reflect code, not the reverse.
3. **Never auto-modify truth files:** they are human-curated artifacts; `regen` only suggests changes.
4. **Read project.toml first:** all project-specific config lives in `.agents/skills/project.toml` under `[truthpack-drift]`.
5. **All commands run to completion autonomously.**
6. **Report all files even when most are clean** — visibility matters.

## Commands
- `/truthpack-drift` or `/truthpack-drift check` — full drift scan across all truth files (default)
- `/truthpack-drift file <name>` — check a single truth file (e.g. `/truthpack-drift file routes.json`)
- `/truthpack-drift regen` — suggest add/remove/update edits for drifted files (suggest only)

## Setup: Read Config
Before any command: read `.agents/skills/project.toml` and extract the `[truthpack-drift]` section.

### Config schema
```toml
[truthpack-drift]
# Directory containing truth files, or list of individual files.
# These are the declared sources of truth for the project.
directory = ".vibecheck/truthpack"
# - OR -
files = ["docs/routes.json", "docs/schema.yaml", "config/features.toml"]

# Each truth file can have a validation strategy.
# If not configured, truthpack-drift will auto-detect based on content.

[truthpack-drift.strategies]
# Key = filename (relative to directory or absolute), value = strategy config

[truthpack-drift.strategies."routes.json"]
# Where to find the real values in code
sources = ["src/routes/*.ts", "src/http.c"]
# What to extract from the source files
extract = "route-registrations"  # built-in extractor
# - OR -
pattern = "router\\.(get|post|put|delete)\\(['\"]([^'\"]+)"  # custom regex, group 2 = value

[truthpack-drift.strategies."schemas.json"]
sources = ["db/schema.sql", "prisma/schema.prisma"]
extract = "table-definitions"

[truthpack-drift.strategies."env.json"]
sources = ["src/**/*.py", "src/**/*.ts", "src/**/*.c"]
extract = "env-references"  # finds getenv, process.env, os.environ
```

### Fallback (no config)
If no `[truthpack-drift]` section:
1. Look for common truth-store locations: `.vibecheck/truthpack/`, `docs/truth/`, `docs/*.json` files that look like fact stores.
2. If found, auto-detect strategies based on file names and content.
3. If nothing found, report that no truth stores are configured.

## Built-in Extraction Strategies
| Strategy | What It Finds | Source Patterns |
|----------|---------------|----------------|
| `route-registrations` | HTTP route paths | `app.get("/foo")`, `router.post`, `mg_set_request_handler`, Express/Flask/etc. |
| `table-definitions` | DB tables + columns | `CREATE TABLE`, Prisma models, ORM classes |
| `env-references` | Environment variables | `getenv()`, `process.env.`, `os.environ`, `Environment.GetEnvironmentVariable` |
| `cli-commands` | CLI commands + flags | `argparse`, `commander`, `clap`, `cobra` parsers |
| `feature-flags` | Feature flag names | `isEnabled("flag")`, `feature_flags.`, config lookups |
| `api-contracts` | Request/response shapes | Endpoint handlers, serializers, Zod/Pydantic schemas |
| `config-keys` | Configuration keys | Config file parsers, settings accessors |

For unlisted strategies, use `pattern` with a custom regex.

## Command: check — Full Drift Scan
1. Inventory truth files (from config or auto-discovery).
2. For each truth file:
   a. Read and parse the truth file (JSON/YAML/TOML).
   b. Extract declared values (keys, entries, claims).
   c. Run the matching extraction strategy against source files.
   d. Compare: truth-only items, code-only items, matching items.
3. Score each file:

| Score | Meaning | Criteria |
|-------|---------|----------|
| **Clean** | No drift | All entries match code |
| **Minor** | Small drift | 1-3 mismatches |
| **Major** | Significant drift | 4+ mismatches |
| **Missing** | Truth file absent | Expected file not found |

### Report
```
Truthpack Drift - Check

  File              Entries   Matched   Truth-Only   Code-Only   Score
  routes.json       24        22        1            3           Minor
  schemas.json      8         8         0            0           Clean
  env.json          15        12        2            1           Minor
  features.toml     6         3         3            0           Major

  Detail:
    routes.json:
      Truth-only: /api/legacy-endpoint (removed from code)
      Code-only:  /api/v2/users, /api/v2/sessions, /api/health

    features.toml:
      Truth-only: dark-mode, beta-export, custom-themes (not in code)

  Result: WARN (1 Major, 2 Minor)
```

## Command: file — Single File Check
Same validation but scoped to one truth file. Faster for targeted checks. Usage: `/truthpack-drift file routes.json`.

## Command: regen — Regeneration Suggestions
After a drift scan, produce actionable suggestions:
1. **Entries to add** to truth files (code-only items).
2. **Entries to remove** from truth files (truth-only items).
3. **Entries to update** (value mismatches).

Does NOT auto-modify truth files — only suggests. Truth stores are human-curated artifacts; automated changes need review.

### Report
```
Truthpack Drift - Regen Suggestions

  routes.json:
    ADD:    /api/v2/users        (found in src/routes/users.ts:12)
    ADD:    /api/v2/sessions     (found in src/routes/sessions.ts:8)
    ADD:    /api/health          (found in src/routes/health.ts:3)
    REMOVE: /api/legacy-endpoint (no code reference found)

  features.toml:
    REMOVE: dark-mode            (no code reference found)
    REMOVE: beta-export          (no code reference found)
    REMOVE: custom-themes        (no code reference found)
```

## Drift Validation Family
Truthpack-drift is one of three parallel drift validators. They check different surfaces and can run independently or together:

| Skill | Checks | Surface |
|-------|--------|---------|
| `/schema-validator` | Code <-> Code | Schema authority vs consumer layers |
| `/truthpack-drift` | Truth <-> Code | Declared truth stores vs actual codebase |
| `/docs-sync` | Docs <-> Code + Docs <-> Docs | Documentation vs code and cross-doc consistency |

**Run all three together** for comprehensive drift detection.

## Integration
| Skill | How Truthpack Drift Helps |
|-------|--------------------------|
| `/manager verify` | Include truthpack validation in campaign exit criteria |
| `/schema-validator` | Parallel validator - both check drift from different angles |
| `/ship` | Quick drift check before commit catches stale references |
| `/docs-sync` | Parallel validator - truthpack checks truth-to-code; docs-sync checks docs |
| `/observer` | Record `drift` observations for truth store divergence |

## Output Contract
Report all truth files every run, even clean ones. Exit 0 if all files are Clean/Minor. Exit 1 if any file is Major or Missing.
