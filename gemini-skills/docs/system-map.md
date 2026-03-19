# System Map: Gemini Multi-Agent Adapter

## Current Architectural State
The project is a "docs-first" adapter implementing a multi-agent campaign orchestration layer for the Gemini CLI.

### Command Surface (`.gemini/commands/`)
The following specialized entry points are registered and constrained via `allowed_tools`:
- **Core Pipeline:** `/discover`, `/planner`, `/brief`, `/ship`, `/qa`.
- **Gemini Super-Skills:** `/epic-refactor`, `/forensic-debugger`, `/ui-test-engineer`, `/doc-weaver`.
- **Infrastructure:** `/manager`, `/loop-master`.

### Skill And Guardrail Surface
The packaged `skills/`, `.gemini/commands/`, and `GEMINI.md` files define the
behavior, entrypoints, and guardrails for the adapter.

### Documentation & Blueprints
- `docs/campaign-blueprints.md`: Generic campaign contracts.
- `docs/gemini-super-skill-campaigns.md`: Gemini-specific specialized contracts.
- `docs/gemini-enhancement-campaign.md`: Context-bridging contract.

## Identified Risks & Drifts
1. **Implicit Task Manager:** The `/manager` command expects `.gemini/run-state.json`, but currently, the manager is being simulated via manual intervention.

*(Note: The previously identified missing implementation commands for `/loop` and `/loop-master` and their contract inconsistencies have now been fully resolved.)*

## Status
The formal `planning-contract.md` has been executed, resolving the initial
consistency issues. The adapter is currently packaged as "v1.0 Ready".
