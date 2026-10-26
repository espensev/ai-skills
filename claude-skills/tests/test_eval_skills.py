"""Regression tests for the light eval acceptance gate."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

SCORER_PATH = Path(__file__).resolve().parent.parent / "scripts" / "eval_skills.py"
SPEC = importlib.util.spec_from_file_location("package_eval_skills", SCORER_PATH)
assert SPEC is not None and SPEC.loader is not None
scorer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scorer)


class TestEvalAcceptance(unittest.TestCase):
    def setUp(self):
        self.case = {
            "id": "review-acceptance",
            "skill": "review",
            "checks": {"must_mention": ["findings"], "verification_any_of": ["pytest"]},
        }
        self.response = {
            "selected_skill": "review",
            "output": "findings",
            "verification_commands": ["python -m pytest"],
            "acceptability": "accept",
        }

    def test_rejected_or_unknown_acceptability_cannot_pass_four_other_checks(self):
        for label in ("reject", "", "unknown", None):
            with self.subTest(label=label):
                result = scorer.evaluate_case(self.case, {**self.response, "acceptability": label})
                self.assertEqual(result["total"], 4.0)
                self.assertFalse(result["pass"])
                self.assertIn("acceptability is not acceptable", result["failures"])

    def test_missing_acceptability_cannot_pass(self):
        del self.response["acceptability"]

        result = scorer.evaluate_case(self.case, self.response)

        self.assertEqual(result["total"], 4.0)
        self.assertFalse(result["pass"])

    def test_accept_passes_at_four_point_threshold(self):
        self.response["verification_commands"] = []

        result = scorer.evaluate_case(self.case, self.response)

        self.assertEqual(result["total"], 4.0)
        self.assertTrue(result["pass"])

    def test_minor_fix_must_still_reach_four_point_threshold(self):
        self.response["acceptability"] = "minor-fix"
        self.assertTrue(scorer.evaluate_case(self.case, self.response)["pass"])

        self.response["verification_commands"] = []
        result = scorer.evaluate_case(self.case, self.response)

        self.assertEqual(result["total"], 3.5)
        self.assertFalse(result["pass"])

    def test_trigger_and_contract_remain_required(self):
        for field, value in (("selected_skill", "qa"), ("output", "summary only")):
            with self.subTest(field=field):
                result = scorer.evaluate_case(self.case, {**self.response, field: value})
                self.assertEqual(result["total"], 4.0)
                self.assertFalse(result["pass"])


if __name__ == "__main__":
    unittest.main()
