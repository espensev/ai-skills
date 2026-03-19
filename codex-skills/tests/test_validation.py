"""Direct tests for task_runtime.validation helper functions."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from task_runtime.validation import (  # noqa: E402
    backfill_legacy_plan,
    command_signature,
    mark_plan_needs_backfill,
    plan_validation_warnings,
    validate_agent_roster,
    validate_file_ownership,
    validate_plan,
    validate_plan_elements,
    validation_contains_command,
)


def _normalize(value):
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [value] if value else []
    return []


def _default_plan(plan: dict) -> dict:
    plan = dict(plan)
    plan.setdefault(
        "plan_elements",
        {
            "campaign_title": plan.get("description", "") or plan.get("id", ""),
            "goal_statement": "Goal",
            "exit_criteria": ["Done"],
            "impact_assessment": [],
            "agent_roster": [],
            "dependency_graph": [],
            "file_ownership_map": [],
            "conflict_zone_analysis": [],
            "integration_points": [],
            "schema_changes": [],
            "risk_assessment": [],
            "verification_strategy": ["python -m pytest tests -q"],
            "documentation_updates": ["None"],
        },
    )
    return plan


class TestCommandSignature(unittest.TestCase):
    def test_command_signature_handles_empty_and_single_token_commands(self):
        self.assertEqual(command_signature(""), "")
        self.assertEqual(command_signature("pytest"), "pytest")

    def test_command_signature_normalizes_known_multi_token_commands(self):
        self.assertEqual(command_signature("python -m pytest tests/ -q"), "python -m pytest")
        self.assertEqual(command_signature("python -m py_compile app.py"), "python -m py_compile")
        self.assertEqual(command_signature("dotnet build src/App.csproj"), "dotnet build")
        self.assertEqual(command_signature("npm test -- --watch"), "npm test")

    def test_validation_contains_command_handles_empty_and_matches_signatures(self):
        self.assertFalse(validation_contains_command(["python -m pytest tests -q"], ""))
        self.assertTrue(
            validation_contains_command(
                ["python -m pytest tests -q -k smoke"],
                "python -m pytest tests -q",
            )
        )


class TestValidatePlanElements(unittest.TestCase):
    def test_validate_plan_elements_reports_missing_required_fields_and_test_command(self):
        plan = {
            "id": "plan-001",
            "plan_elements": {
                "campaign_title": "",
                "goal_statement": "",
                "exit_criteria": [],
                "verification_strategy": ["python -m py_compile app.py"],
                "documentation_updates": [],
            },
        }

        errors = validate_plan_elements(
            plan,
            default_plan_fields=_default_plan,
            normalize_string_list=_normalize,
            commands_cfg=lambda: {"test": "python -m pytest tests -q"},
        )

        self.assertIn("Missing required plan element: campaign_title", errors)
        self.assertIn("Missing required plan element: goal_statement", errors)
        self.assertIn("Missing required plan element: exit_criteria", errors)
        self.assertIn("Missing required plan element: documentation_updates", errors)
        self.assertIn("verification_strategy missing configured test command", errors)

    def test_validate_plan_elements_skips_test_command_requirement_when_unconfigured(self):
        errors = validate_plan_elements(
            _default_plan({"id": "plan-001"}),
            default_plan_fields=_default_plan,
            normalize_string_list=_normalize,
            commands_cfg=lambda: {"test": ""},
        )

        self.assertEqual(errors, [])


class TestValidateAgentRoster(unittest.TestCase):
    def test_validate_agent_roster_reports_missing_letter_name_and_duplicates(self):
        plan = {
            "id": "plan-001",
            "agents": [
                {"letter": "", "name": "alpha", "deps": []},
                {"letter": "a", "name": "", "deps": []},
                {"letter": "a", "name": "again", "deps": []},
            ],
        }

        errors = validate_agent_roster(
            plan,
            default_plan_fields=_default_plan,
            normalize_string_list=_normalize,
            compute_dependency_depths=lambda deps, subject: {},
            error_type=RuntimeError,
            strict=True,
        )

        self.assertIn("Agent roster contains an entry with no letter", errors)
        self.assertIn("Agent A is missing a name", errors)
        self.assertIn("Duplicate agent ID in plan: A", errors)

    def test_validate_agent_roster_filters_unknown_dependencies_in_non_strict_mode(self):
        observed: list[dict[str, list[str]]] = []

        errors = validate_agent_roster(
            {
                "id": "plan-001",
                "agents": [
                    {"letter": "a", "name": "alpha", "deps": ["b", "missing"]},
                    {"letter": "b", "name": "beta", "deps": []},
                ],
            },
            default_plan_fields=_default_plan,
            normalize_string_list=_normalize,
            compute_dependency_depths=lambda deps, subject: observed.append(deps) or {"a": 1, "b": 0},
            error_type=RuntimeError,
            strict=False,
        )

        self.assertEqual(errors, [])
        self.assertEqual(observed[0], {"a": ["b"], "b": []})

    def test_validate_agent_roster_surfaces_dependency_errors(self):
        errors = validate_agent_roster(
            {"id": "plan-001", "agents": [{"letter": "a", "name": "alpha", "deps": ["b"]}]},
            default_plan_fields=_default_plan,
            normalize_string_list=_normalize,
            compute_dependency_depths=lambda deps, subject: (_ for _ in ()).throw(RuntimeError("cycle found")),
            error_type=RuntimeError,
            strict=True,
        )

        self.assertEqual(errors, ["cycle found"])


class TestValidateFileOwnership(unittest.TestCase):
    def test_validate_file_ownership_reports_duplicate_claims(self):
        errors = validate_file_ownership(
            {
                "id": "plan-001",
                "agents": [
                    {"letter": "a", "files": ["shared.py"]},
                    {"letter": "b", "files": ["shared.py"]},
                ],
            },
            default_plan_fields=_default_plan,
            normalize_string_list=_normalize,
        )

        self.assertEqual(errors, ["Duplicate file ownership: shared.py claimed by A, B"])


class TestPlanValidationWarnings(unittest.TestCase):
    def test_plan_validation_warnings_reports_missing_files_commands_and_analysis_health(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            existing_doc = root / "docs" / "existing.md"
            existing_doc.parent.mkdir(parents=True, exist_ok=True)
            existing_doc.write_text("ok\n", encoding="utf-8")

            plan = _default_plan(
                {
                    "id": "plan-001",
                    "legacy_status": "needs_backfill",
                    "source_discovery_docs": ["docs/existing.md", "docs/missing.md"],
                    "source_roadmap": "docs/roadmap.md",
                    "analysis_summary": {
                        "planning_context": {
                            "analysis_health": {"warnings": ["heuristic-only"]},
                            "ownership_summary": {"unassigned_file_count": 2},
                        }
                    },
                }
            )
            plan["plan_elements"]["verification_strategy"] = ["python -m pytest tests -q"]

            warnings = plan_validation_warnings(
                plan,
                default_plan_fields=_default_plan,
                normalize_string_list=_normalize,
                commands_cfg=lambda: {"compile": "python -m py_compile app.py", "build": "dotnet build"},
                safe_resolve=lambda rel: root / rel,
                plan_planning_context=lambda payload: payload["analysis_summary"]["planning_context"],
            )

        self.assertIn("Plan marked as legacy: needs_backfill", warnings)
        self.assertIn("Plan element is empty: impact_assessment", warnings)
        self.assertIn("Plan element is empty: integration_points", warnings)
        self.assertIn("verification_strategy does not mention configured compile command", warnings)
        self.assertIn("verification_strategy does not mention configured build command", warnings)
        self.assertIn("Referenced discovery doc not found: docs/missing.md", warnings)
        self.assertIn("Referenced roadmap not found: docs/roadmap.md", warnings)
        self.assertIn("Analysis health: heuristic-only", warnings)
        self.assertIn("Analysis shows 2 unassigned files; verify ownership before approval", warnings)


class TestValidationComposition(unittest.TestCase):
    def test_validate_plan_aggregates_all_validation_layers(self):
        errors = validate_plan(
            {"id": "plan-001"},
            validate_plan_elements_fn=lambda plan, strict: ["elements"],
            validate_agent_roster_fn=lambda plan, strict: ["agents"],
            validate_file_ownership_fn=lambda plan: ["ownership"],
            strict=False,
        )

        self.assertEqual(errors, ["elements", "agents", "ownership"])

    def test_mark_plan_needs_backfill_marks_non_draft_plans_and_dedupes_reasons(self):
        plan = {
            "id": "plan-001",
            "status": "executed",
            "plan_elements": {
                "goal_statement": "",
                "exit_criteria": [],
                "verification_strategy": [],
                "documentation_updates": [],
            },
        }

        result = mark_plan_needs_backfill(
            plan,
            normalize_string_list=_normalize,
            validate_plan_fn=lambda payload, strict: ["empty goal_statement", "custom error"],
        )

        self.assertEqual(result["legacy_status"], "needs_backfill")
        self.assertIn("custom error", result["backfill_reasons"])
        self.assertEqual(result["backfill_reasons"].count("empty goal_statement"), 1)

    def test_mark_plan_needs_backfill_skips_draft_plans(self):
        result = mark_plan_needs_backfill(
            {
                "id": "plan-001",
                "status": "draft",
                "plan_elements": {
                    "goal_statement": "",
                    "exit_criteria": [],
                    "verification_strategy": [],
                    "documentation_updates": [],
                },
            },
            normalize_string_list=_normalize,
            validate_plan_fn=lambda payload, strict: ["custom error"],
        )

        self.assertNotIn("legacy_status", result)

    def test_backfill_legacy_plan_applies_defaults_refresh_and_marking(self):
        calls: list[str] = []

        result = backfill_legacy_plan(
            {"id": "plan-001"},
            default_plan_fields=lambda plan: calls.append("defaults") or _default_plan(plan),
            refresh_plan_elements=lambda plan: calls.append("refresh") or plan["plan_elements"].update({"goal_statement": ""}),
            mark_plan_needs_backfill_fn=lambda plan: calls.append("mark") or {**plan, "legacy_status": "needs_backfill"},
        )

        self.assertEqual(calls, ["defaults", "refresh", "mark"])
        self.assertEqual(result["legacy_status"], "needs_backfill")


if __name__ == "__main__":
    unittest.main()
