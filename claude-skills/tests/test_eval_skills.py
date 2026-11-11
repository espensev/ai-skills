"""Regression tests for the light eval acceptance gate."""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

SCORER_PATH = Path(__file__).resolve().parent.parent / "scripts" / "eval_skills.py"
ROOT = SCORER_PATH.parent.parent
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


class TestEvalFixtures(unittest.TestCase):
    def setUp(self):
        self.cases = json.loads((ROOT / "eval/cases/light-skill-cases.json").read_text(encoding="utf-8"))
        self.responses = json.loads((ROOT / "eval/responses.mock.json").read_text(encoding="utf-8"))

    def test_cases_mock_and_template_have_matching_unique_ids(self):
        case_ids = [case["id"] for case in self.cases]
        response_ids = [response["id"] for response in self.responses]
        self.assertEqual(len(case_ids), len(set(case_ids)))
        self.assertEqual(len(response_ids), len(set(response_ids)))
        self.assertEqual(set(case_ids), set(response_ids))
        template = json.loads((ROOT / "eval/responses.template.json").read_text(encoding="utf-8"))
        self.assertEqual(template, scorer.build_template(scorer.as_case_map(self.cases)))

    def test_boundary_cases_reject_wrong_routes_and_scope_violations(self):
        boundaries = {
            "handoff-stale-state-001": ("ship", "reset --hard"),
            "browser-control-isolated-001": ("qa", "launched providerbrowser"),
            "docs-sync-check-only-001": ("review", "edited README.md"),
            "review-controller-product-001": ("review", "implemented fixes"),
            "smart-test-map-only-001": ("qa", "ran the full suite"),
            "usage-stats-estimate-001": ("telemetry-live-ops", "billed cost is exact"),
        }
        cases = scorer.as_case_map(self.cases)
        responses = scorer.as_case_map(self.responses)
        for case_id, (wrong_skill, violation) in boundaries.items():
            with self.subTest(case=case_id):
                case, response = cases[case_id], responses[case_id]
                self.assertTrue(scorer.evaluate_case(case, response)["pass"])
                self.assertFalse(scorer.evaluate_case(case, {**response, "selected_skill": wrong_skill})["pass"])
                self.assertFalse(scorer.evaluate_case(case, {**response, "output": "Finished."})["pass"])
                rejected = scorer.evaluate_case(case, {**response, "output": response["output"] + " " + violation})
                self.assertFalse(rejected["pass"])
                self.assertIn("contains banned phrases: " + violation, rejected["failures"])

    def test_isolated_browser_fixture_does_not_require_provider_lane_gate(self):
        case = scorer.as_case_map(self.cases)["browser-control-isolated-001"]
        response = scorer.as_case_map(self.responses)["browser-control-isolated-001"]
        self.assertNotIn("ProfileOwnerVerified", json.dumps(case))
        self.assertNotIn("ProfileOwnerVerified", response["output"])
        self.assertNotIn("devbrowser -Status", "\n".join(response["verification_commands"]))


if __name__ == "__main__":
    unittest.main()
