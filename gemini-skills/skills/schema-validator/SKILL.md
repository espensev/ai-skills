---
name: schema-validator
description: Validate that schema/data-model changes are reflected across all consuming layers. Cross-language and cross-layer contract checking. Use when schema changes might leak to data access, API, or test layers.
---

# Schema Validator Protocol

## Core Mandate
Validate that the authoritative schema definition is correctly consumed by all downstream layers — data access code, API contracts, and contract tests. Catch cross-layer drift before it becomes a runtime failure. All commands run to completion autonomously.

## Execution Rules
1. **Follow the global guardrails** defined in GEMINI.md.
2. **Read project.toml first:** Extract the `[schema-validator]` section before any command.
3. **The authority is always right:** consumers and tests must match it — never modify schema or consumer code, only report.
4. **Evidence over intuition:** every flagged drift cites the consumer file:line and the missing/orphaned entity.
5. **Report all entities** even when most pass — visibility matters.

## Commands
- `/schema-validator drift` — quick drift detection, tables and columns only (Grep-reliable; the recommended primary entry point for hooks and CI gates)
- `/schema-validator check` — full cross-layer validation (default if no command given)
- `/schema-validator` — same as `check`
- `/schema-validator report` — generate cross-reference report to docs/

## Setup: Read Config
Read `project.toml` and extract the `[schema-validator]` section.

### Config schema
```toml
[schema-validator]
# The authoritative schema source — the single point of truth.
# Supported types: sql, prisma, drizzle, typeorm, sqlalchemy, django, proto,
#                  json-schema, openapi, graphql, toml, custom
authority-type = "sql"

# Files that define the schema (source of truth)
authority = ["db/schema.sql", "db/migrations/*.sql"]

# Consumer layers — code that reads or writes against the schema.
# Each is a table: [schema-validator.consumers.<name>]

[schema-validator.consumers.data-access]
files = ["src/services/*DataService.*", "src/repositories/*.ts"]
# What to extract: query strings, column bindings, type mappings
extract = "queries"

[schema-validator.consumers.api-layer]
files = ["src/routes/*.ts", "src/controllers/*.py"]
extract = "endpoints"

[schema-validator.consumers.contract-tests]
files = ["tests/contract/*.py", "tests/integration/schema.test.ts"]
extract = "assertions"

# Optional: version tracking
version-source = "src/config.h"
version-pattern = "SCHEMA_VERSION\\s+(\\d+)"
```

### Fallback (no config)
If no `[schema-validator]` section exists:
1. Auto-detect schema type from project files: `*.sql` → SQL, `prisma/schema.prisma` → Prisma, `drizzle.config.ts` → Drizzle, `*.proto` → Protobuf, `openapi.yaml/json` → OpenAPI.
2. Scan for data access patterns in source code.
3. Report what was found and suggest config.

## Schema Surfaces
Three layers are reconciled:
- **Authority (source of truth)** — schema definition files. Extract table/entity names, column/field names+types, constraints, relations, endpoint paths, required fields.
- **Consumers (downstream code)** — query strings (`SELECT`/`INSERT`/`UPDATE` column refs), column bindings (ORM field mappings, result-set accessors), type mappings, API request/response field expectations.
- **Contract tests** — table/column assertions ("table X exists", "column Y is type Z"), endpoint assertions, relationship assertions ("FK from A.b to B.id").

## Command: `drift` — Quick Check (primary entry point)
Tables and columns only — no query parsing, no test coverage analysis. Grep-reliable and fast for hooks and CI gates.
1. Extract table+column list from authority.
2. Grep consumers for table/column name references.
3. Flag any consumer reference not in authority.
4. Flag any authority table with zero consumer references.

Exit 0 if no FAIL items, exit 1 if any.

## Command: `check` — Full Validation
1. **Extract authority schema** from configured authority files into a normalized list: `{table, column, type, constraints}` (or `{entity, field, type, metadata}` for non-SQL).
2. **Extract consumer references** from each consumer layer via Grep: `{file, entity, field, usage-type}`.
3. **Extract contract test coverage** from test files: `{test-file, entity, field, assertion-type}`.
4. **Cross-reference all three layers:**

   | Check | Rule |
   |-------|------|
   | Consumer → Authority | Every column a consumer references must exist in schema |
   | Authority → Consumer | Every table should have at least one consumer (warn if orphaned) |
   | Authority → Tests | Every table should have contract test coverage |
   | Consumer → Tests | Every consumer query pattern should be tested |
   | Version sync | Schema version in authority matches all doc references |

5. **Report** per entity: pass/fail per layer.

### Report
```
Schema Validator — Check

  Entity         Authority   Consumers   Tests      Status
  users          PASS        3 refs      2 tests    PASS
  sessions       PASS        2 refs      1 test     PASS
  audit_log      PASS        0 refs      0 tests    WARN (orphaned)
  events         PASS        1 ref       0 tests    WARN (untested)
  (unknown)      —           1 ref       —          FAIL (consumer refs missing entity)

  Detail:
    FAIL: src/services/DataService.ts:42 references column "events.metadata"
          which does not exist in schema.sql

  Schema version: 12 (authority) — all docs match

  Result: FAIL (1 missing entity reference)
```

## Command: `report` — Documentation
Same analysis as `check` but writes a detailed markdown report. Always exits 0 (report generation never fails the gate).

Output: `docs/artifacts/schema-contract-report.md`

Contents: entity inventory with column details, consumer reference map (which files touch which entities), test coverage matrix, drift items, recommendations.

## Supported Schema Types
| Type | Authority Files | Extraction Method |
|------|----------------|-------------------|
| SQL | `*.sql`, migrations | Parse CREATE TABLE, ALTER TABLE |
| Prisma | `schema.prisma` | Parse model blocks |
| Drizzle | `schema.ts` | Parse table definitions |
| SQLAlchemy | `models.py` | Parse class definitions with Column() |
| Django | `models.py` | Parse class definitions with fields |
| TypeORM | `*.entity.ts` | Parse @Entity/@Column decorators |
| Protobuf | `*.proto` | Parse message definitions |
| OpenAPI | `openapi.yaml/json` | Parse components/schemas |
| GraphQL | `schema.graphql` | Parse type definitions |
| JSON Schema | `*.schema.json` | Parse properties |
| Custom | User-configured | Regex-based extraction |

## Drift Validation Family
Schema-validator is one of three parallel drift validators that can run independently or together:

| Skill | Checks | Surface |
|-------|--------|---------|
| `/schema-validator` | Code ↔ Code | Schema authority vs consumer layers |
| `/truthpack-drift` | Truth ↔ Code | Declared truth stores vs actual codebase |
| `/docs-sync` | Docs ↔ Code + Docs ↔ Docs | Documentation vs code and cross-doc consistency |

Run all three together for comprehensive drift detection. They share exit code semantics (0 = pass/warn, 1 = fail) and all record `drift` observations to `/observer`.

## Integration
| Skill | How Schema Validator Helps |
|-------|--------------------------|
| `/build-gate` | Build-gate checks compilation; schema-validator checks data contracts |
| `/smart-test` | When schema files change, add contract tests to the test set |
| `/planner` | Campaigns touching schema should include schema-validator as exit criterion |
| `/truthpack-drift` | Parallel validator — schema checks code-to-code; truthpack checks truth-to-code |
| `/docs-sync` | Parallel validator — schema checks code-to-code; docs-sync checks code-to-docs |
| `/observer` | Record `drift` observations for schema divergence |
| `/qa` | Schema validation complements test-based quality checks |

## Output Contract
Report all entities every run — never hide passing entities. The authority is always right; consumers and tests must match it. Exit 0 on PASS/WARN, exit 1 on FAIL. Never modify schema or consumer code — only report.
