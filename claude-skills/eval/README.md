# Claude Light Eval

Lightweight eval harness for `claude-skills`.

The package scorer checks recorded skill selections, artifacts and required
language, including restrictions on provider-specific paths.

## Files

- `eval/cases/light-skill-cases.json` — eval cases for every default and optional Claude skill in the install manifest
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

Coverage includes stale-handoff reconciliation, isolated browser routing,
read-only documentation checks, test mapping without
execution, and estimated usage reporting. Contract tests require every portable
skill to have a case, keep case/mock/template IDs aligned, and verify that these
boundary cases reject wrong skill selections and prohibited actions or claims.
Source-only skills are outside this portable coverage gate.

Run the following commands from the Claude package root. Start a response
file, fill in the observed outputs and selections, then record the reviewer's
acceptability label. Leave unobserved selections and missing labels blank.

```sh
python scripts/eval_skills.py --write-template eval/responses.run.json
```

Score that run after recording the evidence.

```sh
python scripts/eval_skills.py --responses eval/responses.run.json --out eval/results/run.json
```

To replay the packaged mock fixture and print its scores, run the following.

```sh
python scripts/eval_skills.py --responses eval/responses.mock.json
```

## Response Format

Same as the shared scorer contract:

```json
[
  {
    "id": "qa-basic-001",
    "selected_skill": "qa",
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
