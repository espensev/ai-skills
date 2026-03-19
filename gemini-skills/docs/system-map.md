# System Map: Gemini Multi-Agent Adapter

## Current Architectural State
The project is a "docs-first" adapter implementing a multi-agent campaign orchestration layer for the Gemini CLI.

### Command Surface (`.gemini/commands/`)
The following specialized entry points are registered and constrained via `allowed_tools`:
- **Core Pipeline:** `/discover`, `/planner`, `/brief`, `/ship`, `/qa`.
- **Gemini Super-Skills:** `/epic-refactor`, `/forensic-debugger`, `/ui-test-engineer`, `/doc-weaver`.
- **Infrastructure:** `/manager`, `/loop-master`.

### Instruction Sets (`docs/instructions/`)
9 total persona files define the behavior and guardrails for each role.

### Documentation & Blueprints
- `docs/campaign-blueprints.md`: Generic campaign contracts.
- `docs/gemini-super-skill-campaigns.md`: Gemini-specific specialized contracts.
- `docs/gemini-enhancement-campaign.md`: Context-bridging contract.

## Identified Risks & Drifts
1. **Implicit Task Manager:** The `/manager` command expects `.gemini/run-state.json`, but currently, the manager is being simulated via manual intervention.

*(Note: The previously identified missing implementation commands for `/loop` and `/loop-master` and their contract inconsistencies have now been fully resolved.)*

## Next Phase: Finalization Plan
The formal `planning-contract.md` has been successfully executed, resolving the initial inconsistencies. The adapter is now declared "v1.0 Ready".
