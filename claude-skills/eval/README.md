# Claude Light Eval

Lightweight eval harness for `claude-skills`.

Reuses the shared scorer from `codex-skills` to avoid duplication. Cases test
that Claude skill invocations select the right skill, produce required
artifacts and language, and avoid provider leakage (`.codex`, `.gemini` paths).

## Files

- `eval/cases/light-skill-cases.json` — eval cases for all Claude skills
- `eval/responses.template.json` — blank response template
- `eval/responses.mock.json` — deterministic passing fixture for package validation
- `eval/results/` — scored output directory
- `eval/results/.gitkeep` — placeholder

## Scoring

Each case scores skill selection, required language, artifacts, verification,
and manual acceptability. `accept` contributes `1.0`, `minor-fix` contributes
`0.5`, and other labels contribute `0.0`, for a maximum total of `5.0`.
A pass requires a total of at least `4.0`, correct skill selection, all language
checks, and an `accept` or `minor-fix` label. Missing, unknown, and `reject`
labels fail even when the other checks total `4.0`.

The mock fixture checks package contracts; its score does not measure live
skill selection or effectiveness. Use recorded runs with reviewed labels for
those conclusions.

Run the shared scorer from a sibling package:

```powershell
$repo = (Resolve-Path .).Path
python ..\codex-skills\scripts\eval_skills.py `
  --cases "$repo\eval\cases\light-skill-cases.json" `
  --responses "$repo\eval\responses.template.json" `
  --out "$repo\eval\results\latest.json"
```

Or from bash:

```bash
python ../codex-skills/scripts/eval_skills.py \
  --cases eval/cases/light-skill-cases.json \
  --responses eval/responses.template.json \
  --out eval/results/latest.json
```

For a deterministic fixture run:

```bash
python ../codex-skills/scripts/eval_skills.py \
  --cases eval/cases/light-skill-cases.json \
  --responses eval/responses.mock.json \
  --out "${TMPDIR:-/tmp}/claude-skills-eval-latest.json"
```

## Response Format

Same as the shared scorer contract:

```json
[
  {
    "id": "discover-basic-001",
    "selected_skill": "discover",
    "output": "text output from the run",
    "created_files": [],
    "verification_commands": [],
    "acceptability": "accept",
    "notes": "optional reviewer notes"
  }
]
```

## Extension Rules

- Add cases for new Claude skills before broadening the package surface.
- Prefer deterministic phrase checks over open-ended judging.
- Reuse the shared scorer contract unless the neutral core changes it.
- Provider leakage: ban `.codex` and `.gemini` paths in `must_not_mention`.
