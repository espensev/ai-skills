# Light Skill Eval

This is the lightweight eval harness for the Codex skill package.

It does not run Codex automatically. It scores saved skill outputs against a
small deterministic rubric so the package can track basic quality without
building a full judge system first.

## What It Measures

Each case is scored on five checks:

- `trigger`: did the selected skill match the intended skill
- `contract`: did the output include required language and avoid banned terms
- `artifact`: did it create the expected files, if any
- `verification`: did it include the expected validation step
- `acceptability`: manual label: `accept`, `minor-fix`, or `reject`

The total score is the sum of those five checks. `acceptability` is weighted as:

- `accept` = `1.0`
- `minor-fix` = `0.5`
- `reject` = `0.0`

## Files

- `eval/cases/light-skill-cases.json` contains the starter cases
- `eval/results/` is where scored results can be written
- `scripts/eval_skills.py` is the scorer

## Response Format

The scorer expects a response file shaped like this:

```json
[
  {
    "id": "planner-basic-001",
    "selected_skill": "planner",
    "output": "text output from the run",
    "created_files": ["agents/agent-a-example.md"],
    "verification_commands": ["python -m pytest -q"],
    "acceptability": "accept",
    "notes": "optional human notes"
  }
]
```

## Usage

Write a starter response file:

```bash
python scripts/eval_skills.py --write-template eval/responses.template.json
```

Score responses:

```bash
python scripts/eval_skills.py ^
  --cases eval/cases/light-skill-cases.json ^
  --responses eval/responses.template.json ^
  --out eval/results/latest.json
```

## Starter Workflow

1. Run or simulate one output per eval case.
2. Paste the outputs into a response file.
3. Set `selected_skill` and `acceptability`.
4. Run the scorer.
5. Review the failures list before changing the skills.
