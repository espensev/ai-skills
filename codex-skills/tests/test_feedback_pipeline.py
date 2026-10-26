"""Tests for the Codex feedback-to-eval helper pipeline."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from observe_to_eval import PROVIDER_LEAKAGE_TERMS, observation_to_case  # noqa: E402
from skill_feedback_loop import (  # noqa: E402
    SkillHealth,
    analyze_eval_results,
    analyze_observations,
    format_report_json,
    format_report_markdown,
    generate_recommendations,
    merge_health,
)


class TestObserveToEval(unittest.TestCase):
    def test_generated_cases_block_provider_specific_leakage_terms(self):
        case = observation_to_case(
            {
                "cat": "regression",
                "summary": "search endpoint returns stale cache data",
                "detail": "response ignored invalidation path",
                "files": ["src/search.py"],
            },
            1,
        )

        self.assertEqual(case["checks"]["must_not_mention"], PROVIDER_LEAKAGE_TERMS)
        self.assertIn(".codex/skills", case["checks"]["must_not_mention"])
        self.assertIn("AGENTS.md", case["checks"]["must_not_mention"])
        self.assertIn(".gemini/commands", case["checks"]["must_not_mention"])


class TestSkillFeedbackLoop(unittest.TestCase):
    def test_no_actionable_data_does_not_establish_effectiveness(self):
        for ranked in ([], [SkillHealth(name="review", eval_score=5.0, eval_cases=1)]):
            with self.subTest(ranked=ranked):
                report = format_report_markdown(ranked)
                self.assertIn("No actionable issues found in supplied data", report)
                self.assertIn("does not establish real-world effectiveness", report)
                self.assertNotIn("All skills are healthy", report)

    def test_eval_priority_depends_on_average_not_case_count(self):
        for count in (1, 2, 5):
            with self.subTest(count=count):
                health = analyze_eval_results({"results": [
                    {"skill": "review", "total": 3.0, "failures": ["missing verification"]}
                    for _ in range(count)
                ]})["review"]

                self.assertEqual(health.priority_score, 16.0)
                self.assertIn("| 1 | review | 16.0 |", format_report_markdown([health]))
                report = json.loads(format_report_json([health]))
                self.assertEqual(report["skills_needing_attention"], 1)
                self.assertEqual(report["skills"][0]["name"], "review")
                self.assertIn("Fix eval failures", " ".join(report["skills"][0]["recommendations"]))

    def test_perfect_eval_cases_do_not_hide_observed_regression(self):
        observations = analyze_observations([{"cat": "regression", "agent": "review"}])
        evaluations = analyze_eval_results({"results": [
            {"skill": "review", "total": 5.0, "failures": []},
            {"skill": "review", "total": 5.0, "failures": []},
        ]})

        ranked = merge_health(observations, evaluations, {})

        self.assertEqual(ranked[0].priority_score, 15.0)
        self.assertIn("Fix 1 regression(s)", format_report_markdown(ranked))
        self.assertEqual(json.loads(format_report_json(ranked))["skills_needing_attention"], 1)

    def test_analyze_observations_maps_worktree_agent_names_to_skill_categories(self):
        health = analyze_observations(
            [
                {
                    "cat": "test-fail",
                    "summary": "api smoke test fails",
                    "agent": "agent-a-api",
                },
                {
                    "cat": "drift",
                    "summary": "plan and code disagree on auth flow",
                },
            ]
        )

        self.assertIn("qa", health)
        self.assertEqual(health["qa"].observer_issues[0]["summary"], "api smoke test fails")
        self.assertIn("observer", health)
        self.assertEqual(health["observer"].drift_count, 1)
        self.assertNotIn("agent-a-api", health)

    def test_generate_recommendations_uses_repo_artifacts_not_claude_commands(self):
        recs = generate_recommendations(SkillHealth(name="observer", debt_count=2))
        joined = "\n".join(recs)

        self.assertIn("data/observations.jsonl", joined)
        self.assertIn("docs/observer/project-intelligence.md", joined)
        self.assertNotIn("run `/observe", joined)


if __name__ == "__main__":
    unittest.main()
