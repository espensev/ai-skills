# Skill Directory Review - 2026-06-25

> **Historical record (2026-06-25).** Counts and verification notes below
> reflect the repo at review time: the shipped total was 78 before the
> Antigravity package landed (now tracked in `README.md`), and
> `quick_validate.py` was a local helper that never landed in this repo. The
> current validation entry point is `scripts/Test-ReleaseReadiness.ps1`.

## Scope

Reviewed the shipped provider packages and the imported reference skill tree:

- `codex-skills/`
- `claude-skills/`
- `gemini-skills/`
- imported reference tree under `skills/`

The export surface remains manifest-driven. The imported `skills/` tree is a
reference source, not an exported package.

## Actions Taken

### Promoted a Portable `review` Skill

The imported `skills/skills/in-progress/review/SKILL.md` has a useful shape:
fail fast on bad or empty fixed points, review against both standards and spec,
and keep review findings separated by evidence.

Rather than copy that Claude-specific skill, this repo now ships a portable
`review` skill in all three provider packages:

- `codex-skills/skills/review/SKILL.md`
- `claude-skills/skills/review/SKILL.md`
- `gemini-skills/skills/review/SKILL.md`

The adapted skill writes durable findings to `docs/reviews/`, keeps source files
read-only, labels each finding by axis (`standards`, `spec`, `regression`), and
requires evidence for every finding.

### Fixed Gemini Command Wrapper Targets

The Gemini adapter manifest included command wrappers whose prompts referenced
`../../docs/instructions/*.md`, but that directory is absent in this checkout.
Matching skill files already exist under `gemini-skills/skills/`, so the wrappers
now point at those skill files instead.

Updated wrappers:

- `brief`
- `discover`
- `doc-weaver`
- `edit`
- `epic-refactor`
- `forensic-debugger`
- `guardrails`
- `loop`
- `loop-master`
- `manager`
- `planner`
- `qa`
- `ship`
- `ui-test-engineer`

Added `review.toml` for the new Gemini review command.

### Updated Manifests and Inventory Docs

Added `review` to:

- `codex-skills/package/install-manifest.json`
- `claude-skills/package/install-manifest.json`
- `gemini-skills/package/install-manifest.json`

Updated root and provider READMEs. Shipped skill count at that time was 78:

- `claude-skills`: 19
- `codex-skills`: 31
- `gemini-skills`: 28

## Not Promoted

Did not wholesale import the external `skills/` tree. Its taxonomy and invocation
model differ from this repo's manifest-driven provider packages, and much of it
would add overlap or non-portable assumptions. Future promotions should follow
the same pattern used for `review`: extract the behavior, adapt to the provider
surface, add it to manifests, and validate export paths.

## Verification

- `quick_validate.py codex-skills/skills/review` - pass
- `quick_validate.py claude-skills/skills/review` - pass
- `quick_validate.py gemini-skills/skills/review` - pass
- `python -m json.tool` on all package manifests - pass
- Gemini command wrapper target check - pass, no missing prompt targets
- `python -m pytest tests/test_skill_docs_contract.py -q` in `codex-skills/` - 9 passed
- `python -m pytest tests/test_skill_docs_contract.py -q` in `claude-skills/` - 9 passed
- `scripts/export-ready-skill-packages.ps1` to a temp target - pass, exported `review` for all three provider packages
