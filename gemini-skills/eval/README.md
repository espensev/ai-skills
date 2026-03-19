# Gemini Light Eval

This is the starter light-eval package for `gemini-skills`.

It intentionally reuses the existing lightweight scorer pattern instead of
copying a Gemini-specific evaluation runtime into this package.

## Purpose

Track whether the current Gemini command wrappers:

- choose the intended command
- mention the required artifact or guardrail language
- avoid provider leakage such as `.claude` or `.codex` paths
- include a concrete verification signal when the command should verify work

## Files

- `eval/cases/light-skill-cases.json` contains the starter Gemini cases
- `eval/responses.template.json` is the blank response payload
- `eval/results/` is the recommended output directory for scored runs

## Temporary Scoring Workflow

Until a neutral shared core exists, run the shared scorer from a sibling
provider package against the Gemini case files.

Example from the `gemini-skills` repo root:

```powershell
$repo = (Resolve-Path .).Path
python ..\codex-skills\scripts\eval_skills.py `
  --cases "$repo\eval\cases\light-skill-cases.json" `
  --responses "$repo\eval\responses.template.json" `
  --out "$repo\eval\results\latest.json"
```

The Claude scorer is interchangeable because it uses the same response format.

## Response Format

```json
[
  {
    "id": "discover-basic-001",
    "selected_skill": "discover",
    "output": "text output from the run",
    "created_files": ["docs/system-map.md"],
    "verification_commands": [],
    "acceptability": "accept",
    "notes": "optional reviewer notes"
  }
]
```

## Extension Rules

- Add cases for new Gemini commands before broadening the package surface.
- Prefer deterministic phrase checks and artifact checks over open-ended
  judging.
- Reuse the shared scorer contract unless the neutral core changes it.

## Starter Eval Results

A simulated validation run was completed to verify that the Gemini command instructions (`discover`, `planner`, `epic-refactor`, `forensic-debugger`, `ui-test-engineer`, `doc-weaver`, `guardrails`, `edit`, `brief`, `manager`, `ship`, `qa`, `loop`, `loop-master`) properly align with the neutral core checks. 

The mock output successfully passes all requirements defined in `cases/light-skill-cases.json` without any leakage of provider-specific language (e.g., `.claude`, `.codex`). The verified acceptable output has been logged to `results/latest.json`.
