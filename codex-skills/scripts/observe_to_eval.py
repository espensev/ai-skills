#!/usr/bin/env python3
"""Generate eval regression cases from observer observations.

Reads observations.jsonl for regression, blocker, test-fail, and build-error
categories and converts them into light-eval cases that prevent recurrence.

Usage:
    python scripts/observe_to_eval.py --observations data/observations.jsonl
    python scripts/observe_to_eval.py --observations data/observations.jsonl --out eval/cases/regression-cases.json
    python scripts/observe_to_eval.py --observations data/observations.jsonl --merge eval/cases/light-skill-cases.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OBS = ROOT / "data" / "observations.jsonl"
PROVIDER_LEAKAGE_TERMS = [
    ".claude/skills",
    ".codex/skills",
    ".gemini/commands",
    "CLAUDE.md",
    "AGENTS.md",
    "GEMINI.md",
]

# Observation categories that indicate skill failures worth capturing
REGRESSION_CATS = {"regression", "blocker", "test-fail", "build-error"}

# Map observation categories to the skill most likely responsible
CAT_TO_SKILL: dict[str, str] = {
    "test-fail": "qa",
    "build-error": "qa",
    "regression": "qa",
    "blocker": "manager",
}

# Map observation categories to checks that should catch the problem
CAT_TO_CHECKS: dict[str, dict[str, Any]] = {
    "test-fail": {
        "must_mention": ["test", "fail", "root cause"],
        "must_not_mention": PROVIDER_LEAKAGE_TERMS,
        "verification_any_of": ["pytest", "test"],
        "must_create": [],
    },
    "build-error": {
        "must_mention": ["build", "error", "fix"],
        "must_not_mention": PROVIDER_LEAKAGE_TERMS,
        "verification_any_of": ["build", "compile", "pytest"],
        "must_create": [],
    },
    "regression": {
        "must_mention": ["regression", "test", "root cause"],
        "must_not_mention": PROVIDER_LEAKAGE_TERMS,
        "verification_any_of": ["pytest", "test", "verify"],
        "must_create": [],
    },
    "blocker": {
        "must_mention": ["blocker", "resolve"],
        "must_not_mention": PROVIDER_LEAKAGE_TERMS,
        "verification_any_of": ["verify", "test", "check"],
        "must_create": [],
    },
}


def load_observations(path: Path) -> list[dict[str, Any]]:
    """Load JSONL observations file."""
    if not path.exists():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def filter_regressions(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep only observations that indicate skill failures."""
    return [
        obs for obs in observations
        if obs.get("cat") in REGRESSION_CATS
        and obs.get("status", "open") != "stale"
    ]


def observation_to_case(obs: dict[str, Any], index: int) -> dict[str, Any]:
    """Convert a single observation into an eval case."""
    cat = obs.get("cat", "regression")
    summary = obs.get("summary", "unknown failure")
    detail = obs.get("detail", "")
    files = obs.get("files", [])
    skill = obs.get("agent", "") or CAT_TO_SKILL.get(cat, "qa")

    # Build a prompt that would reproduce the scenario
    file_context = f" in {', '.join(files)}" if files else ""
    prompt = f"Investigate and resolve: {summary}{file_context}"
    if detail:
        prompt += f". Context: {detail[:120]}"

    checks = CAT_TO_CHECKS.get(cat, CAT_TO_CHECKS["regression"]).copy()

    case_id = f"{skill}-regression-{index:03d}"

    return {
        "id": case_id,
        "skill": skill,
        "prompt": prompt,
        "checks": checks,
        "source_observation": {
            "cat": cat,
            "summary": summary,
            "ts": obs.get("ts", ""),
            "severity": obs.get("severity", "info"),
        },
    }


def deduplicate_cases(
    new_cases: list[dict[str, Any]],
    existing_cases: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Remove cases whose prompt already exists in the existing set."""
    existing_prompts = {c["prompt"].lower() for c in existing_cases}
    existing_ids = {c["id"] for c in existing_cases}
    unique = []
    for case in new_cases:
        if case["prompt"].lower() not in existing_prompts and case["id"] not in existing_ids:
            unique.append(case)
    return unique


def load_json(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate eval cases from observer regression observations."
    )
    parser.add_argument(
        "--observations", type=Path, default=DEFAULT_OBS,
        help="Path to observations.jsonl",
    )
    parser.add_argument(
        "--out", type=Path,
        help="Write generated cases to this file (standalone output)",
    )
    parser.add_argument(
        "--merge", type=Path,
        help="Merge generated cases into an existing cases file (deduplicates)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print cases to stdout without writing files",
    )
    args = parser.parse_args()

    obs_path = args.observations if args.observations.is_absolute() else ROOT / args.observations
    observations = load_observations(obs_path)
    regressions = filter_regressions(observations)

    if not regressions:
        print("No regression/blocker/test-fail observations found.")
        return 0

    # Generate cases
    cases = [observation_to_case(obs, i + 1) for i, obs in enumerate(regressions)]
    print(f"Generated {len(cases)} regression case(s) from {len(regressions)} observation(s).")

    # Deduplicate against existing if merging
    if args.merge:
        merge_path = args.merge if args.merge.is_absolute() else ROOT / args.merge
        existing = load_json(merge_path) if merge_path.exists() else []
        cases = deduplicate_cases(cases, existing)
        if not cases:
            print("All generated cases already exist. Nothing to add.")
            return 0
        print(f"After dedup: {len(cases)} new case(s) to add.")
        if not args.dry_run:
            merged = existing + cases
            dump_json(merge_path, merged)
            print(f"Merged into {merge_path} (total: {len(merged)} cases)")
        else:
            print(json.dumps(cases, indent=2, ensure_ascii=False))
        return 0

    # Standalone output
    if args.dry_run:
        print(json.dumps(cases, indent=2, ensure_ascii=False))
    elif args.out:
        out_path = args.out if args.out.is_absolute() else ROOT / args.out
        dump_json(out_path, cases)
        print(f"Wrote {len(cases)} case(s) to {out_path}")
    else:
        print(json.dumps(cases, indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
