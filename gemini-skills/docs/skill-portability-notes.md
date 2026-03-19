# Gemini Skill Adapter Portability Notes

Current portability status for the experimental `gemini-skills` package.

## Intent

This folder is a Gemini adapter, not a full runtime fork.

The current Claude and Codex packages already duplicate a large amount of
source. Gemini should stay a thin provider layer until the shared planning
contract, runtime modules, and tests are extracted into a neutral core.

### Execution Path Divergence
While this package aims to reuse the neutral core's planning schemas and contracts, Gemini's execution model intentionally diverges from Claude and Codex. Instead of relying on a simulated multi-agent "swarm" (e.g., passing state between isolated `Planner`, `Manager`, and `Loop` agents to overcome context limits), `gemini-skills` optimizes for "The Lens Strategy." It natively uses its large context window to process the entire repository at once, directly executing the `Plan -> Run -> Verify` lifecycle as guided by the 13-element contract.

## Provider-Specific Surface

Gemini-specific behavior should be expressed through:

- hierarchical `GEMINI.md` context files for persistent repo instructions
- project or global `.gemini/commands/*.toml` files for reusable command
  entrypoints
- Gemini-specific instruction files that define artifacts, stop conditions, and
  guardrails for those commands

That is the smallest provider-specific surface that can expose the existing
generic skills on Gemini CLI.

## Package Layout

This package currently owns only adapter assets:

- `README.md`
- `GEMINI.md`
- `.gemini/commands/`
- `docs/instructions/`
- `docs/skill-portability-notes.md`
- `docs/gemini-context-skills.md`
- `eval/`

These files define scope and guardrails. They do not imply that a separate
Gemini runtime already exists.

## Installed Target Layout

After the adapter is implemented in a consumer repo, the expected Gemini-facing
surface should look like:

- `GEMINI.md`
- `.gemini/commands/discover.toml`
- `.gemini/commands/planner.toml`
- `.gemini/commands/manager.toml`
- `.gemini/commands/qa.toml`
- `.gemini/commands/ship.toml`
- `.gemini/commands/loop.toml`
- `.gemini/commands/loop-master.toml`

Those command files should wrap a shared backend rather than a Gemini-only
runtime fork.

## Current Prototype Commands

The package currently ships prototype wrappers for the generic orchestration commands:
- `.gemini/commands/brief.toml`
- `.gemini/commands/manager.toml`
- `.gemini/commands/ship.toml`
- `.gemini/commands/qa.toml`
- `.gemini/commands/loop.toml`
- `.gemini/commands/loop-master.toml`

As well as the specialized Gemini skills:
- `.gemini/commands/discover.toml`
- `.gemini/commands/planner.toml`
- `.gemini/commands/epic-refactor.toml`
- `.gemini/commands/forensic-debugger.toml`
- `.gemini/commands/ui-test-engineer.toml`
- `.gemini/commands/doc-weaver.toml`
- `.gemini/commands/guardrails.toml`
- `.gemini/commands/edit.toml`

## Documentation Rules

- Package docs must describe package-root files when talking about this folder.
- Consumer runtime docs may describe `GEMINI.md` and `.gemini/commands/...`
  when talking about an installed target repo.
- Do not describe a Gemini backend runtime that does not exist yet.
- Do not copy inherited `.claude` or `.codex` runtime paths into
  consumer-facing Gemini examples or command templates.
- Keep command instructions artifact-driven so they can later be wrapped by a
  shared backend without re-interpreting vague personas.

## Remaining Gaps

- no shared-core extraction yet
- no generic Gemini orchestration wrappers yet
- no package-local runtime scripts

## Verification Expectations

Before calling the Gemini adapter usable, verify:

- the command mapping is documented and internally consistent
- consumer-facing examples and command templates do not inherit `.claude` or
  `.codex` runtime paths
- each implemented command has explicit output artifacts and stop conditions
- the starter Gemini eval cases can be scored by the shared light scorer
  pattern without custom Gemini-only logic

## Eval Reuse Rule

Do not copy the full scorer into this package while the shared core is still
missing. Reuse `../codex-skills/scripts/eval_skills.py` or the equivalent
Claude script against Gemini case files until the scorer moves into the neutral
core.

## References

- Gemini CLI custom commands:
  `https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/custom-commands.md`
- Gemini CLI context files:
  `https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/gemini-md.md`
