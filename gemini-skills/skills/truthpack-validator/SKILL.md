---
name: truthpack-validator
description: Validates assumptions against truthpack JSON files before making changes, preventing hallucinations of features, tiers, flags, and routes.
---

# Truthpack Validator Protocol

## Core Mandate
Before implementing any feature, route, CLI command, or tier-specific logic, you MUST validate your assumptions against the single source of truth: the Truthpack.

## Truthpack Location
`.vibecheck/truthpack/`

## Validation Steps
1. **Identify Needs:** Determine what data your task requires (e.g., tier names, CLI flags, API routes).
2. **Consult Truthpack:** Read the corresponding JSON file from the list below using file reading tools.
3. **Verify:** Ensure your planned implementation strictly adheres to the data found.

### Key Truthpack Files
- `product.json`: Tiers (Free/Pro/Team/Enterprise), prices, features, entitlements. NEVER invent tier names.
- `monorepo.json`: Packages, dependencies, entry points. NEVER guess package names.
- `cli-commands.json`: CLI commands, flags, subcommands. NEVER invent CLI flags.
- `error-codes.json`: Error codes, HTTP status codes. NEVER invent error codes.
- `routes.json`: Verified API routes. NEVER hallucinate API routes.
- `env.json`: Verified environment variables. NEVER fabricate env vars.
- `copy.json`: Brand name, UI copy. NEVER invent UI copy.

## Conflict Resolution
If the truthpack disagrees with your assumption or user request, the truthpack wins. You must inform the user of the conflict and rely on the truthpack data.
