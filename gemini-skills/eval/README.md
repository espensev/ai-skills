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
- `eval/responses.mock.json` is a deterministic passing fixture for package validation
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

For a deterministic fixture run, point the scorer at `eval/responses.mock.json`
instead of the blank template.

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

## Feedback Loop

Gemini does not yet ship a separate runtime feedback store in this package, so
use explicit artifacts:

1. capture the failure mode in the response `notes`
2. add or tighten a case in `eval/cases/light-skill-cases.json` when the issue
   is reusable
3. re-score with the shared scorer
4. only then decide whether the pattern also belongs in
   `continuous-learning-v2`

## Starter Eval Results

Use `eval/responses.mock.json` when you want a deterministic scorer run that
proves the package still satisfies the current light-eval contract without
depending on a live Gemini session transcript.
