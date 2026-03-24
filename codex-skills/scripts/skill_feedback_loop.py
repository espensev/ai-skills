#!/usr/bin/env python3
"""Analyze observer data + eval results to produce skill improvement recommendations.

Reads three data sources:
1. Observer observations (patterns, drift, debt, regressions)
2. Eval results (per-skill scores and failures)
3. Test results (pytest output or structured test data)

Produces a ranked list of skill improvement actions — which skills need
attention and what specifically to fix.

Usage:
    python scripts/skill_feedback_loop.py
    python scripts/skill_feedback_loop.py --observations data/observations.jsonl --eval eval/results/latest.json
    python scripts/skill_feedback_loop.py --out docs/skill-improvement-report.md
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OBS = ROOT / "data" / "observations.jsonl"
DEFAULT_EVAL = ROOT / "eval" / "results" / "latest.json"
DEFAULT_CASES = ROOT / "eval" / "cases" / "light-skill-cases.json"


@dataclass
class SkillHealth:
    """Aggregated health signal for a single skill."""
    name: str
    eval_score: float = 0.0
    eval_cases: int = 0
    eval_failures: list[str] = field(default_factory=list)
    observer_issues: list[dict[str, Any]] = field(default_factory=list)
    regression_count: int = 0
    drift_count: int = 0
    debt_count: int = 0
    churn_count: int = 0
    blocker_count: int = 0
    coverage_gaps: list[str] = field(default_factory=list)

    @property
    def priority_score(self) -> float:
        """Higher = needs more attention. Weighted composite."""
        score = 0.0
        # Eval failures are strong signals
        if self.eval_cases > 0:
            score += (1.0 - self.eval_score / 5.0) * 40
        # Regressions are critical
        score += self.regression_count * 15
        # Blockers are urgent
        score += self.blocker_count * 12
        # Drift suggests the skill spec is out of sync
        score += self.drift_count * 8
        # Debt accumulation
        score += self.debt_count * 5
        # Churn means instability
        score += self.churn_count * 3
        return round(score, 1)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def load_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def analyze_observations(observations: list[dict[str, Any]]) -> dict[str, SkillHealth]:
    """Group observations by skill/agent and count issue types."""
    skills: dict[str, SkillHealth] = defaultdict(lambda: SkillHealth(name="unknown"))

    # Categories that map to specific skills
    cat_skill_map = {
        "test-fail": "qa",
        "test-pass": "qa",
        "build-error": "qa",
        "regression": "qa",
        "blocker": "manager",
        "churn": "loop",
    }

    for obs in observations:
        cat = obs.get("cat", "")
        status = obs.get("status", "open")
        if status == "stale":
            continue

        # Determine which skill this observation relates to
        skill_name = obs.get("agent", "") or cat_skill_map.get(cat, "")
        if not skill_name:
            # Try to infer from files
            files = obs.get("files", [])
            for f in files:
                if "observer" in f.lower():
                    skill_name = "observer"
                    break
                if "planner" in f.lower() or "plan" in f.lower():
                    skill_name = "planner"
                    break
            if not skill_name:
                skill_name = cat  # Use category as fallback

        health = skills[skill_name]
        health.name = skill_name
        health.observer_issues.append(obs)

        if cat == "regression":
            health.regression_count += 1
        elif cat == "drift":
            health.drift_count += 1
        elif cat == "debt":
            health.debt_count += 1
        elif cat == "churn":
            health.churn_count += 1
        elif cat == "blocker":
            health.blocker_count += 1

    return dict(skills)


def analyze_eval_results(eval_data: dict[str, Any] | None) -> dict[str, SkillHealth]:
    """Extract per-skill scores and failures from eval results."""
    skills: dict[str, SkillHealth] = {}

    if not eval_data or "results" not in eval_data:
        return skills

    for result in eval_data["results"]:
        skill_name = result.get("skill", "")
        if not skill_name:
            continue

        if skill_name not in skills:
            skills[skill_name] = SkillHealth(name=skill_name)

        health = skills[skill_name]
        health.eval_cases += 1
        health.eval_score += result.get("total", 0.0)
        if result.get("failures"):
            health.eval_failures.extend(result["failures"])

    return skills


def find_coverage_gaps(cases: list[dict[str, Any]], skills_dir: Path) -> dict[str, list[str]]:
    """Find skills that have no eval cases."""
    covered_skills = {c["skill"] for c in cases}
    gaps: dict[str, list[str]] = {}

    if skills_dir.exists():
        for skill_dir in sorted(skills_dir.iterdir()):
            if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                skill_name = skill_dir.name
                if skill_name not in covered_skills:
                    gaps[skill_name] = [f"No eval cases for skill '{skill_name}'"]

    return gaps


def merge_health(
    obs_health: dict[str, SkillHealth],
    eval_health: dict[str, SkillHealth],
    coverage_gaps: dict[str, list[str]],
) -> list[SkillHealth]:
    """Merge all health signals into a single ranked list."""
    all_skills: dict[str, SkillHealth] = {}

    # Start with observer data
    for name, health in obs_health.items():
        all_skills[name] = health

    # Merge eval data
    for name, health in eval_health.items():
        if name in all_skills:
            existing = all_skills[name]
            existing.eval_score = health.eval_score
            existing.eval_cases = health.eval_cases
            existing.eval_failures = health.eval_failures
        else:
            all_skills[name] = health

    # Add coverage gaps
    for name, gaps in coverage_gaps.items():
        if name in all_skills:
            all_skills[name].coverage_gaps = gaps
        else:
            h = SkillHealth(name=name, coverage_gaps=gaps)
            all_skills[name] = h

    # Sort by priority (highest first)
    ranked = sorted(all_skills.values(), key=lambda h: h.priority_score, reverse=True)
    return ranked


def generate_recommendations(health: SkillHealth) -> list[str]:
    """Generate specific actionable recommendations for a skill."""
    recs = []

    if health.regression_count > 0:
        recs.append(
            f"Fix {health.regression_count} regression(s) — add regression eval cases "
            f"via `python scripts/observe_to_eval.py --merge eval/cases/light-skill-cases.json`"
        )

    if health.blocker_count > 0:
        recs.append(
            f"Resolve {health.blocker_count} blocker(s) before launching new campaigns"
        )

    if health.eval_failures:
        unique_failures = list(set(health.eval_failures))[:5]
        recs.append(
            f"Fix eval failures: {'; '.join(unique_failures)}"
        )

    if health.drift_count > 0:
        recs.append(
            f"SKILL.md may be out of sync — {health.drift_count} drift observation(s) found. "
            f"Review and update the spec."
        )

    if health.churn_count > 0:
        recs.append(
            f"High churn ({health.churn_count} observation(s)) suggests design instability. "
            f"Stabilize the interface before adding features."
        )

    if health.debt_count > 0:
        recs.append(
            f"Address {health.debt_count} technical debt item(s) — "
            f"run `/observe list --category debt` for details."
        )

    if health.coverage_gaps:
        recs.append(
            f"No eval cases exist for this skill — add baseline cases to "
            f"eval/cases/light-skill-cases.json"
        )

    if health.eval_cases > 0:
        avg = health.eval_score / health.eval_cases
        if avg < 4.0:
            recs.append(
                f"Average eval score is {avg:.1f}/5.0 (below pass threshold of 4.0)"
            )

    return recs


def format_report_markdown(ranked: list[SkillHealth]) -> str:
    """Produce a markdown improvement report."""
    lines = [
        "# Skill Improvement Report",
        "",
        "Generated from observer observations and eval results.",
        "Skills are ranked by priority (highest need for attention first).",
        "",
    ]

    actionable = [h for h in ranked if h.priority_score > 0 or h.coverage_gaps]

    if not actionable:
        lines.append("All skills are healthy. No improvements needed.")
        return "\n".join(lines)

    lines.append("| Rank | Skill | Priority | Regressions | Blockers | Drift | Eval Score |")
    lines.append("|------|-------|----------|-------------|----------|-------|------------|")

    for i, health in enumerate(actionable, 1):
        eval_display = (
            f"{health.eval_score:.1f}/{health.eval_cases * 5}"
            if health.eval_cases > 0
            else "no cases"
        )
        lines.append(
            f"| {i} | {health.name} | {health.priority_score} | "
            f"{health.regression_count} | {health.blocker_count} | "
            f"{health.drift_count} | {eval_display} |"
        )

    lines.append("")

    for health in actionable:
        recs = generate_recommendations(health)
        if not recs:
            continue
        lines.append(f"## {health.name}")
        lines.append("")
        for rec in recs:
            lines.append(f"- {rec}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Next Steps")
    lines.append("")
    lines.append("1. Fix regressions and blockers first (highest priority)")
    lines.append("2. Run `python scripts/observe_to_eval.py --merge eval/cases/light-skill-cases.json` to capture regressions as eval cases")
    lines.append("3. Add baseline eval cases for uncovered skills")
    lines.append("4. Address drift by updating SKILL.md specs to match actual behavior")
    lines.append("5. Run `/observe cycle` after improvements to track progress")
    lines.append("")

    return "\n".join(lines)


def format_report_json(ranked: list[SkillHealth]) -> str:
    """Produce a JSON improvement report for machine consumption."""
    actionable = [h for h in ranked if h.priority_score > 0 or h.coverage_gaps]
    payload = {
        "total_skills_analyzed": len(ranked),
        "skills_needing_attention": len(actionable),
        "skills": [
            {
                "name": h.name,
                "priority_score": h.priority_score,
                "eval_score": h.eval_score,
                "eval_cases": h.eval_cases,
                "regression_count": h.regression_count,
                "blocker_count": h.blocker_count,
                "drift_count": h.drift_count,
                "debt_count": h.debt_count,
                "churn_count": h.churn_count,
                "coverage_gaps": h.coverage_gaps,
                "recommendations": generate_recommendations(h),
            }
            for h in actionable
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze observer + eval data to recommend skill improvements."
    )
    parser.add_argument(
        "--observations", type=Path, default=DEFAULT_OBS,
        help="Path to observations.jsonl",
    )
    parser.add_argument(
        "--eval", type=Path, default=DEFAULT_EVAL,
        help="Path to eval results JSON",
    )
    parser.add_argument(
        "--cases", type=Path, default=DEFAULT_CASES,
        help="Path to eval cases JSON (for coverage gap analysis)",
    )
    parser.add_argument(
        "--skills-dir", type=Path, default=ROOT / "skills",
        help="Path to skills directory (for coverage gap analysis)",
    )
    parser.add_argument(
        "--out", type=Path,
        help="Write report to file",
    )
    parser.add_argument(
        "--format", choices=["markdown", "json"], default="markdown",
        help="Output format (default: markdown)",
    )
    args = parser.parse_args()

    # Resolve paths
    obs_path = args.observations if args.observations.is_absolute() else ROOT / args.observations
    eval_path = args.eval if args.eval.is_absolute() else ROOT / args.eval
    cases_path = args.cases if args.cases.is_absolute() else ROOT / args.cases
    skills_dir = args.skills_dir if args.skills_dir.is_absolute() else ROOT / args.skills_dir

    # Load data
    observations = load_jsonl(obs_path)
    eval_data = load_json(eval_path)
    cases = load_json(cases_path) or []

    # Analyze
    obs_health = analyze_observations(observations)
    eval_health = analyze_eval_results(eval_data)
    coverage_gaps = find_coverage_gaps(cases, skills_dir)

    # Merge and rank
    ranked = merge_health(obs_health, eval_health, coverage_gaps)

    # Format output
    if args.format == "json":
        report = format_report_json(ranked)
    else:
        report = format_report_markdown(ranked)

    # Output
    if args.out:
        out_path = args.out if args.out.is_absolute() else ROOT / args.out
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report + "\n", encoding="utf-8")
        print(f"Wrote report to {out_path}")
    else:
        print(report)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
