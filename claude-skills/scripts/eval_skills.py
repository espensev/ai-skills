#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CASES = ROOT / "eval" / "cases" / "light-skill-cases.json"
DEFAULT_TEMPLATE = ROOT / "eval" / "responses.template.json"


def resolve_path(path: Path | None) -> Path | None:
    if path is None:
        return None
    return path if path.is_absolute() else ROOT / path


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def as_case_map(payload: Any) -> dict[str, dict[str, Any]]:
    if isinstance(payload, list):
        return {str(item["id"]): item for item in payload}
    if isinstance(payload, dict):
        return {str(key): value for key, value in payload.items()}
    raise ValueError("Cases/responses must be a JSON array or object.")


def contains_all(text: str, patterns: list[str]) -> bool:
    lowered = text.lower()
    return all(pattern.lower() in lowered for pattern in patterns)


def contains_any(text: str, patterns: list[str]) -> bool:
    lowered = text.lower()
    return any(pattern.lower() in lowered for pattern in patterns)


def missing_items(expected: list[str], actual: list[str]) -> list[str]:
    actual_set = {item.lower() for item in actual}
    return [item for item in expected if item.lower() not in actual_set]


def score_acceptability(value: str) -> float:
    normalized = str(value or "").strip().lower()
    if normalized == "accept":
        return 1.0
    if normalized == "minor-fix":
        return 0.5
    return 0.0


def evaluate_case(case: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    checks = case.get("checks", {})
    output = str(response.get("output", "") or "")
    verification_text = "\n".join(response.get("verification_commands", []) or [])
    created_files = [str(item) for item in (response.get("created_files", []) or [])]

    expected_skill = str(case.get("skill", "") or "")
    selected_skill = str(response.get("selected_skill", "") or "")
    must_mention = [str(item) for item in (checks.get("must_mention", []) or [])]
    must_not_mention = [str(item) for item in (checks.get("must_not_mention", []) or [])]
    verification_any_of = [str(item) for item in (checks.get("verification_any_of", []) or [])]
    must_create = [str(item) for item in (checks.get("must_create", []) or [])]

    trigger_score = 1.0 if selected_skill == expected_skill else 0.0
    contract_ok = contains_all(output, must_mention) and not contains_any(output, must_not_mention)
    artifact_ok = not must_create or not missing_items(must_create, created_files)
    verification_ok = not verification_any_of or contains_any(output + "\n" + verification_text, verification_any_of)
    acceptability_score = score_acceptability(str(response.get("acceptability", "")))

    failures: list[str] = []
    if trigger_score == 0.0:
        failures.append(f"selected_skill={selected_skill!r} expected={expected_skill!r}")
    if not contains_all(output, must_mention):
        missing = [item for item in must_mention if item.lower() not in output.lower()]
        failures.append("missing required phrases: " + ", ".join(missing))
    present_banned = [item for item in must_not_mention if item.lower() in output.lower()]
    if present_banned:
        failures.append("contains banned phrases: " + ", ".join(present_banned))
    missing_created = missing_items(must_create, created_files)
    if missing_created:
        failures.append("missing created files: " + ", ".join(missing_created))
    if verification_any_of and not verification_ok:
        failures.append("missing verification signal: " + ", ".join(verification_any_of))
    if acceptability_score == 0.0:
        failures.append("acceptability is not acceptable")

    scores = {
        "trigger": trigger_score,
        "contract": 1.0 if contract_ok else 0.0,
        "artifact": 1.0 if artifact_ok else 0.0,
        "verification": 1.0 if verification_ok else 0.0,
        "acceptability": acceptability_score,
    }
    total = round(sum(scores.values()), 2)

    return {
        "id": case["id"],
        "skill": expected_skill,
        "scores": scores,
        "total": total,
        "max_total": 5.0,
        "pass": total >= 4.0 and scores["trigger"] == 1.0 and scores["contract"] == 1.0,
        "failures": failures,
        "notes": str(response.get("notes", "") or ""),
    }


def build_template(cases: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    template: list[dict[str, Any]] = []
    for case_id in sorted(cases):
        case = cases[case_id]
        template.append(
            {
                "id": case_id,
                "selected_skill": case.get("skill", ""),
                "output": "",
                "created_files": [],
                "verification_commands": [],
                "acceptability": "reject",
                "notes": "",
            }
        )
    return template


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    total_cases = len(results)
    passed = sum(1 for result in results if result["pass"])
    average = round(sum(float(result["total"]) for result in results) / total_cases, 2) if total_cases else 0.0
    by_skill: dict[str, dict[str, Any]] = {}
    for result in results:
        skill = result["skill"]
        bucket = by_skill.setdefault(skill, {"count": 0, "passed": 0, "total_score": 0.0})
        bucket["count"] += 1
        bucket["passed"] += 1 if result["pass"] else 0
        bucket["total_score"] += float(result["total"])
    for skill, bucket in by_skill.items():
        bucket["average_score"] = round(bucket["total_score"] / bucket["count"], 2)
        del bucket["total_score"]
    return {
        "total_cases": total_cases,
        "passed": passed,
        "failed": total_cases - passed,
        "average_score": average,
        "by_skill": by_skill,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Score lightweight skill eval responses.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES, help="Path to eval case JSON.")
    parser.add_argument("--responses", type=Path, help="Path to response JSON.")
    parser.add_argument("--out", type=Path, help="Optional path for scored results JSON.")
    parser.add_argument("--write-template", type=Path, help="Write a blank response template and exit.")
    args = parser.parse_args()

    cases_path = resolve_path(args.cases) or DEFAULT_CASES
    responses_path = resolve_path(args.responses)
    out_path = resolve_path(args.out)
    template_path = resolve_path(args.write_template)

    cases = as_case_map(load_json(cases_path))

    if template_path:
        dump_json(template_path, build_template(cases))
        print(f"Wrote template: {template_path}")
        return 0

    if not responses_path:
        parser.error("--responses is required unless --write-template is used.")

    responses = as_case_map(load_json(responses_path))
    results = []
    for case_id in sorted(cases):
        response = responses.get(case_id, {"id": case_id, "selected_skill": "", "output": "", "acceptability": "reject"})
        results.append(evaluate_case(cases[case_id], response))

    payload = {
        "cases": str(cases_path),
        "responses": str(responses_path),
        "summary": summarize(results),
        "results": results,
    }

    if out_path:
        dump_json(out_path, payload)
        print(f"Wrote results: {out_path}")
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
