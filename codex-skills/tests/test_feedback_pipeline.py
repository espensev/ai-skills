"""Tests for the Codex feedback-to-eval helper pipeline."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from observe_to_eval import PROVIDER_LEAKAGE_TERMS, observation_to_case  # noqa: E402
from skill_feedback_loop import SkillHealth, analyze_observations, generate_recommendations  # noqa: E402


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
