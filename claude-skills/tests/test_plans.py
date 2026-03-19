"""Tests for task_runtime.plans — plan lifecycle pure logic and command handlers."""

from __future__ import annotations

import argparse
import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from task_runtime.plans import (  # noqa: E402
    cmd_plan_approve,
    cmd_plan_criteria,
    cmd_plan_finalize,
    cmd_plan_list,
    cmd_plan_preflight,
    cmd_plan_reject,
    cmd_plan_validate,
    default_plan_fields,
    empty_plan_elements,
    looks_like_full_plan,
    plan_planning_context,
    plan_summary,
    planning_context_conflict_zone_analysis,
    planning_context_integration_points,
    refresh_plan_elements,
    resolve_plan_summary,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _identity_normalize(items):
    if isinstance(items, list):
        return items
    if isinstance(items, str) and items:
        return [items]
    return []


def _empty_elements_factory(title=""):
    return empty_plan_elements(title)


# ---------------------------------------------------------------------------
# empty_plan_elements
# ---------------------------------------------------------------------------


class TestEmptyPlanElements(unittest.TestCase):
    def test_default_structure(self):
        result = empty_plan_elements()
        self.assertEqual(result["campaign_title"], "")
        self.assertEqual(result["goal_statement"], "")
        self.assertIsInstance(result["exit_criteria"], list)
        self.assertEqual(len(result["exit_criteria"]), 0)
        self.assertEqual(result["documentation_updates"], ["No documentation updates required."])

    def test_title_passed_through(self):
        result = empty_plan_elements("My Campaign")
        self.assertEqual(result["campaign_title"], "My Campaign")

    def test_default_verification_strategy(self):
        result = empty_plan_elements(default_verification_strategy=["Run tests", "Build"])
        self.assertEqual(result["verification_strategy"], ["Run tests", "Build"])

    def test_all_13_element_keys_present(self):
        result = empty_plan_elements()
        expected_keys = {
            "campaign_title",
            "goal_statement",
            "exit_criteria",
            "impact_assessment",
            "agent_roster",
            "dependency_graph",
            "file_ownership_map",
            "conflict_zone_analysis",
            "integration_points",
            "schema_changes",
            "risk_assessment",
            "verification_strategy",
            "documentation_updates",
        }
        self.assertEqual(set(result.keys()), expected_keys)


# ---------------------------------------------------------------------------
# plan_planning_context
# ---------------------------------------------------------------------------


class TestPlanPlanningContext(unittest.TestCase):
    def test_extracts_planning_context(self):
        plan = {"analysis_summary": {"planning_context": {"health": "ok"}}}
        self.assertEqual(plan_planning_context(plan), {"health": "ok"})

    def test_missing_analysis_summary(self):
        self.assertEqual(plan_planning_context({}), {})

    def test_missing_planning_context(self):
        self.assertEqual(plan_planning_context({"analysis_summary": {}}), {})

    def test_returns_copy(self):
        ctx = {"key": "value"}
        plan = {"analysis_summary": {"planning_context": ctx}}
        result = plan_planning_context(plan)
        result["new"] = "added"
        self.assertNotIn("new", ctx)


# ---------------------------------------------------------------------------
# planning_context_conflict_zone_analysis
# ---------------------------------------------------------------------------


class TestPlanningContextConflictZoneAnalysis(unittest.TestCase):
    def test_empty_context(self):
        self.assertEqual(planning_context_conflict_zone_analysis({}), [])

    def test_conflict_zone_with_two_files(self):
        ctx = {"conflict_zones": [{"files": ["a.py", "b.py"], "reason": "shared state"}]}
        result = planning_context_conflict_zone_analysis(ctx)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["files"], ["a.py", "b.py"])
        self.assertEqual(result[0]["reason"], "shared state")

    def test_conflict_zone_with_one_file_skipped(self):
        ctx = {"conflict_zones": [{"files": ["only-one.py"], "reason": "no conflict"}]}
        self.assertEqual(planning_context_conflict_zone_analysis(ctx), [])

    def test_hotspot_converted(self):
        ctx = {
            "coordination_hotspots": [
                {
                    "files": ["x.py", "y.py"],
                    "project": "core",
                    "entry": "main.py",
                    "reason": "entry point",
                    "kind": "entry-point",
                }
            ]
        }
        result = planning_context_conflict_zone_analysis(ctx)
        self.assertEqual(len(result), 1)
        self.assertIn("conflict_zone", result[0])
        self.assertIn("mitigation", result[0])

    def test_startup_hotspot_annotated(self):
        ctx = {
            "coordination_hotspots": [
                {
                    "files": ["a.py", "b.py"],
                    "project": "app",
                    "startup": True,
                    "reason": "startup",
                }
            ]
        }
        result = planning_context_conflict_zone_analysis(ctx)
        self.assertIn("(startup)", result[0]["affected"])

    def test_deduplication(self):
        ctx = {
            "conflict_zones": [
                {"files": ["a.py", "b.py"], "reason": "same"},
                {"files": ["a.py", "b.py"], "reason": "same"},
            ]
        }
        result = planning_context_conflict_zone_analysis(ctx)
        self.assertEqual(len(result), 1)


# ---------------------------------------------------------------------------
# planning_context_integration_points
# ---------------------------------------------------------------------------


class TestPlanningContextIntegrationPoints(unittest.TestCase):
    def test_empty_context(self):
        result = planning_context_integration_points({}, normalize_string_list=_identity_normalize)
        self.assertEqual(result, [])

    def test_startup_projects(self):
        ctx = {"priority_projects": {"startup": ["app"]}}
        result = planning_context_integration_points(ctx, normalize_string_list=_identity_normalize)
        self.assertTrue(any("startup" in item.lower() for item in result))
        self.assertTrue(any("app" in item for item in result))

    def test_packaging_projects(self):
        ctx = {"priority_projects": {"packaging": ["installer"]}}
        result = planning_context_integration_points(ctx, normalize_string_list=_identity_normalize)
        self.assertTrue(any("packaging" in item.lower() for item in result))

    def test_unassigned_files_warning(self):
        ctx = {"ownership_summary": {"unassigned_file_count": 5}}
        result = planning_context_integration_points(ctx, normalize_string_list=_identity_normalize)
        self.assertTrue(any("5" in item and "unassigned" in item.lower() for item in result))

    def test_coordination_hotspots(self):
        ctx = {
            "coordination_hotspots": [
                {
                    "files": ["a.py", "b.py"],
                    "kind": "entry-point",
                    "entry": "main.py",
                    "reason": "entry point",
                }
            ]
        }
        result = planning_context_integration_points(ctx, normalize_string_list=_identity_normalize)
        self.assertTrue(any("main.py" in item for item in result))

    def test_conflict_zone_kind_skipped(self):
        ctx = {
            "coordination_hotspots": [
                {
                    "files": ["a.py", "b.py"],
                    "kind": "conflict-zone",
                    "reason": "skip me",
                }
            ]
        }
        result = planning_context_integration_points(ctx, normalize_string_list=_identity_normalize)
        self.assertEqual(len(result), 0)

    def test_deduplication(self):
        ctx = {
            "priority_projects": {"startup": ["app"], "packaging": []},
            "coordination_hotspots": [],
        }
        # Call twice with same data to check dedup within one call
        result = planning_context_integration_points(ctx, normalize_string_list=_identity_normalize)
        seen = set()
        for item in result:
            self.assertNotIn(item, seen)
            seen.add(item)


# ---------------------------------------------------------------------------
# refresh_plan_elements
# ---------------------------------------------------------------------------


class TestRefreshPlanElements(unittest.TestCase):
    def test_creates_elements_if_missing(self):
        plan = {"description": "Test plan"}
        refresh_plan_elements(
            plan,
            empty_plan_elements_factory=_empty_elements_factory,
            normalize_string_list=_identity_normalize,
        )
        self.assertIn("plan_elements", plan)
        self.assertEqual(plan["plan_elements"]["campaign_title"], "Test plan")

    def test_populates_agent_roster(self):
        plan = {
            "id": "plan-001",
            "agents": [
                {"letter": "a", "name": "alpha", "scope": "do stuff", "deps": [], "files": ["a.py"], "group": 0, "complexity": "low"},
            ],
            "groups": {"0": ["a"]},
        }
        refresh_plan_elements(
            plan,
            empty_plan_elements_factory=_empty_elements_factory,
            normalize_string_list=_identity_normalize,
        )
        roster = plan["plan_elements"]["agent_roster"]
        self.assertEqual(len(roster), 1)
        self.assertEqual(roster[0]["letter"], "a")

    def test_populates_file_ownership_map(self):
        plan = {
            "agents": [
                {"letter": "a", "name": "alpha", "files": ["x.py", "y.py"]},
            ],
            "groups": {},
        }
        refresh_plan_elements(
            plan,
            empty_plan_elements_factory=_empty_elements_factory,
            normalize_string_list=_identity_normalize,
        )
        ownership = plan["plan_elements"]["file_ownership_map"]
        self.assertEqual(len(ownership), 2)
        self.assertEqual(ownership[0]["file"], "x.py")
        self.assertEqual(ownership[0]["owner"], "a")

    def test_preserves_existing_conflict_zones(self):
        plan = {
            "agents": [],
            "groups": {},
            "plan_elements": {
                "conflict_zone_analysis": [{"existing": True}],
            },
        }
        refresh_plan_elements(
            plan,
            empty_plan_elements_factory=_empty_elements_factory,
            normalize_string_list=_identity_normalize,
        )
        self.assertEqual(plan["plan_elements"]["conflict_zone_analysis"], [{"existing": True}])


# ---------------------------------------------------------------------------
# plan_summary
# ---------------------------------------------------------------------------


class TestPlanSummary(unittest.TestCase):
    def test_extracts_summary_fields(self):
        plan = {
            "id": "plan-001",
            "status": "approved",
            "description": "Test",
            "created_at": "2026-01-01",
            "updated_at": "2026-01-02",
            "next_letter": "c",
            "agents": [{"letter": "a"}, {"letter": "b"}],
            "plan_file": "data/plans/plan-001.json",
            "plan_doc": "docs/campaign-plan-001.md",
            "legacy_status": "",
        }
        result = plan_summary(
            plan,
            relative_path=lambda p: str(p),
            plan_file_path=lambda pid: Path(f"data/plans/{pid}.json"),
            plan_doc_path=lambda p: f"docs/campaign-{p['id']}.md",
        )
        self.assertEqual(result["id"], "plan-001")
        self.assertEqual(result["status"], "approved")
        self.assertEqual(result["agent_count"], 2)

    def test_defaults_for_missing_fields(self):
        plan = {"id": "plan-002"}
        result = plan_summary(
            plan,
            relative_path=lambda p: str(p),
            plan_file_path=lambda pid: Path(f"data/plans/{pid}.json"),
            plan_doc_path=lambda p: f"docs/campaign-{p['id']}.md",
        )
        self.assertEqual(result["status"], "draft")
        self.assertEqual(result["agent_count"], 0)


# ---------------------------------------------------------------------------
# looks_like_full_plan
# ---------------------------------------------------------------------------


class TestLooksLikeFullPlan(unittest.TestCase):
    def test_full_plan(self):
        self.assertTrue(looks_like_full_plan({"agents": [], "groups": {}}))

    def test_summary_only(self):
        self.assertFalse(looks_like_full_plan({"id": "plan-001", "status": "draft"}))

    def test_with_analysis_summary(self):
        self.assertTrue(looks_like_full_plan({"analysis_summary": {}}))

    def test_with_plan_elements(self):
        self.assertTrue(looks_like_full_plan({"plan_elements": {}}))

    def test_empty_dict(self):
        self.assertFalse(looks_like_full_plan({}))


# ---------------------------------------------------------------------------
# default_plan_fields
# ---------------------------------------------------------------------------


def _test_slugify(text):
    return text.lower().replace(" ", "-")[:30]


class TestDefaultPlanFields(unittest.TestCase):
    def _call(self, plan):
        return default_plan_fields(
            plan,
            empty_plan_elements_factory=_empty_elements_factory,
            plan_default_verification_strategy=lambda: ["Run tests"],
            slugify=_test_slugify,
            relative_path=lambda p: str(p),
            plan_file_path=lambda pid: Path(f"data/plans/{pid}.json"),
            plan_doc_path=lambda p: f"docs/campaign-{p.get('id', '')}.md",
            normalize_string_list=_identity_normalize,
        )

    def test_sets_schema_defaults(self):
        result = self._call({"id": "plan-001"})
        self.assertEqual(result["schema_version"], 1)
        self.assertEqual(result["planner_kind"], "planner")
        self.assertIn("slug", result)

    def test_normalizes_elements(self):
        result = self._call({"id": "plan-001", "description": "Test"})
        elements = result["plan_elements"]
        self.assertIsInstance(elements["exit_criteria"], list)
        self.assertIsInstance(elements["agent_roster"], list)

    def test_default_verification_strategy_applied(self):
        result = self._call({"id": "plan-001"})
        self.assertEqual(result["plan_elements"]["verification_strategy"], ["Run tests"])

    def test_default_documentation_updates(self):
        result = self._call({"id": "plan-001"})
        self.assertEqual(
            result["plan_elements"]["documentation_updates"],
            ["No documentation updates required."],
        )

    def test_agent_deps_normalized(self):
        plan = {"id": "plan-001", "agents": [{"letter": "a", "deps": "b", "files": "f.py"}]}
        result = self._call(plan)
        # _identity_normalize converts string to list
        self.assertIsInstance(result["agents"][0]["deps"], list)

    def test_preserves_existing_plan_elements(self):
        existing = empty_plan_elements("Existing")
        existing["goal_statement"] = "Keep this"
        plan = {"id": "plan-001", "plan_elements": existing}
        result = self._call(plan)
        self.assertEqual(result["plan_elements"]["goal_statement"], "Keep this")


# ---------------------------------------------------------------------------
# resolve_plan_summary
# ---------------------------------------------------------------------------


class TestResolvePlanSummary(unittest.TestCase):
    def test_empty_list(self):
        self.assertIsNone(resolve_plan_summary([], None))

    def test_returns_latest_when_no_id(self):
        plans = [{"id": "plan-001"}, {"id": "plan-002"}]
        result = resolve_plan_summary(plans, None)
        self.assertEqual(result["id"], "plan-002")

    def test_finds_by_id(self):
        plans = [{"id": "plan-001"}, {"id": "plan-002"}]
        result = resolve_plan_summary(plans, "plan-001")
        self.assertEqual(result["id"], "plan-001")

    def test_not_found(self):
        plans = [{"id": "plan-001"}]
        self.assertIsNone(resolve_plan_summary(plans, "plan-999"))


# ---------------------------------------------------------------------------
# cmd_plan_preflight
# ---------------------------------------------------------------------------


class TestCmdPlanPreflight(unittest.TestCase):
    def test_json_output(self):
        payload = {"ready": True, "errors": [], "warnings": [], "commands": {"test": "echo ok"}}
        captured = []

        cmd_plan_preflight(
            argparse.Namespace(json=True),
            plan_preflight_payload_fn=lambda: payload,
            emit_json_fn=lambda p: captured.append(p),
        )
        self.assertEqual(len(captured), 1)
        self.assertTrue(captured[0]["ready"])

    def test_text_output_ready(self):
        payload = {"ready": True, "errors": [], "warnings": [], "commands": {"test": "echo ok"}}
        buf = io.StringIO()
        with redirect_stdout(buf):
            cmd_plan_preflight(
                argparse.Namespace(json=False),
                plan_preflight_payload_fn=lambda: payload,
                emit_json_fn=lambda p: None,
            )
        self.assertIn("ready", buf.getvalue())

    def test_text_output_blocked_raises(self):
        payload = {"ready": False, "errors": ["missing config"], "warnings": [], "commands": {}}
        with self.assertRaises(SystemExit):
            buf = io.StringIO()
            with redirect_stdout(buf):
                cmd_plan_preflight(
                    argparse.Namespace(json=False),
                    plan_preflight_payload_fn=lambda: payload,
                    emit_json_fn=lambda p: None,
                )


# ---------------------------------------------------------------------------
# cmd_plan_finalize
# ---------------------------------------------------------------------------


class TestCmdPlanFinalize(unittest.TestCase):
    def _make_deps(self, plan):
        state = {"plans": [{"id": plan["id"], "status": plan.get("status", "draft")}]}
        return {
            "load_state_fn": lambda: state,
            "resolve_plan_summary_fn": lambda plans, pid: plans[0] if plans else None,
            "load_plan_from_summary_fn": lambda s: dict(plan),
            "finalize_plan_updates_fn": lambda p, a: (p, ["goal"], [], []),
            "persist_plan_artifacts_fn": lambda p: p,
            "upsert_plan_summary_fn": lambda s, p: None,
            "save_state_fn": lambda s: None,
            "emit_json_fn": lambda p: None,
        }

    def test_json_output(self):
        plan = {"id": "plan-001", "status": "draft"}
        captured = []
        deps = self._make_deps(plan)
        deps["emit_json_fn"] = lambda p: captured.append(p)

        cmd_plan_finalize(argparse.Namespace(plan_id="plan-001", json=True), **deps)
        self.assertEqual(captured[0]["plan_id"], "plan-001")

    def test_executed_plan_raises(self):
        plan = {"id": "plan-001", "status": "executed"}
        deps = self._make_deps(plan)
        with self.assertRaises(RuntimeError):
            cmd_plan_finalize(argparse.Namespace(plan_id="plan-001", json=True), **deps)


# ---------------------------------------------------------------------------
# cmd_plan_list
# ---------------------------------------------------------------------------


class TestCmdPlanList(unittest.TestCase):
    def test_no_plans(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            cmd_plan_list(
                argparse.Namespace(json=False),
                load_state_fn=lambda: {"plans": []},
                emit_json_fn=lambda p: None,
            )
        self.assertIn("No plans", buf.getvalue())

    def test_json_output(self):
        plans = [{"id": "plan-001", "status": "draft", "description": "Test", "created_at": "2026-01-01T00:00:00", "agent_count": 2}]
        captured = []
        cmd_plan_list(
            argparse.Namespace(json=True),
            load_state_fn=lambda: {"plans": plans},
            emit_json_fn=lambda p: captured.append(p),
        )
        self.assertEqual(len(captured[0]), 1)
        self.assertEqual(captured[0][0]["id"], "plan-001")


# ---------------------------------------------------------------------------
# cmd_plan_validate
# ---------------------------------------------------------------------------


class TestCmdPlanValidate(unittest.TestCase):
    def test_valid_plan(self):
        plan = {"id": "plan-001", "status": "draft"}
        captured = []
        cmd_plan_validate(
            argparse.Namespace(plan_id="plan-001", json=True),
            load_state_fn=lambda: {"plans": [{"id": "plan-001"}]},
            resolve_plan_summary_fn=lambda plans, pid: plans[0],
            load_plan_from_summary_fn=lambda s: plan,
            validate_plan_fn=lambda p, strict: [],
            plan_validation_warnings_fn=lambda p: [],
            emit_json_fn=lambda p: captured.append(p),
        )
        self.assertTrue(captured[0]["valid"])

    def test_invalid_plan_raises(self):
        plan = {"id": "plan-001", "status": "draft"}
        with self.assertRaises(SystemExit):
            buf = io.StringIO()
            with redirect_stdout(buf):
                cmd_plan_validate(
                    argparse.Namespace(plan_id="plan-001", json=False),
                    load_state_fn=lambda: {"plans": [{"id": "plan-001"}]},
                    resolve_plan_summary_fn=lambda plans, pid: plans[0],
                    load_plan_from_summary_fn=lambda s: plan,
                    validate_plan_fn=lambda p, strict: ["Missing goal"],
                    plan_validation_warnings_fn=lambda p: [],
                    emit_json_fn=lambda p: None,
                )


# ---------------------------------------------------------------------------
# cmd_plan_approve
# ---------------------------------------------------------------------------


class TestCmdPlanApprove(unittest.TestCase):
    def test_approve_valid_plan(self):
        plan = {"id": "plan-001", "status": "draft", "agents": [{"letter": "a"}]}
        saved = []

        buf = io.StringIO()
        with redirect_stdout(buf):
            cmd_plan_approve(
                argparse.Namespace(plan_id="plan-001"),
                load_state_fn=lambda: {"plans": [{"id": "plan-001"}]},
                resolve_plan_summary_fn=lambda plans, pid: plans[0],
                load_plan_from_summary_fn=lambda s: plan,
                validate_plan_fn=lambda p, strict: [],
                now_iso_fn=lambda: "2026-01-01T00:00:00+00:00",
                persist_plan_artifacts_fn=lambda p: p,
                upsert_plan_summary_fn=lambda s, p: None,
                save_state_fn=lambda s: saved.append(s),
            )
        self.assertEqual(plan["status"], "approved")
        self.assertEqual(len(saved), 1)

    def test_approve_no_agents_raises(self):
        plan = {"id": "plan-001", "status": "draft", "agents": []}
        with self.assertRaises(RuntimeError):
            cmd_plan_approve(
                argparse.Namespace(plan_id="plan-001"),
                load_state_fn=lambda: {"plans": [{"id": "plan-001"}]},
                resolve_plan_summary_fn=lambda plans, pid: plans[0],
                load_plan_from_summary_fn=lambda s: plan,
                validate_plan_fn=lambda p, strict: [],
                now_iso_fn=lambda: "2026-01-01T00:00:00+00:00",
                persist_plan_artifacts_fn=lambda p: p,
                upsert_plan_summary_fn=lambda s, p: None,
                save_state_fn=lambda s: None,
            )

    def test_approve_validation_failure_raises(self):
        plan = {"id": "plan-001", "status": "draft", "agents": [{"letter": "a"}]}
        with self.assertRaises(RuntimeError):
            cmd_plan_approve(
                argparse.Namespace(plan_id="plan-001"),
                load_state_fn=lambda: {"plans": [{"id": "plan-001"}]},
                resolve_plan_summary_fn=lambda plans, pid: plans[0],
                load_plan_from_summary_fn=lambda s: plan,
                validate_plan_fn=lambda p, strict: ["Missing goal"],
                now_iso_fn=lambda: "2026-01-01T00:00:00+00:00",
                persist_plan_artifacts_fn=lambda p: p,
                upsert_plan_summary_fn=lambda s, p: None,
                save_state_fn=lambda s: None,
            )


# ---------------------------------------------------------------------------
# cmd_plan_reject
# ---------------------------------------------------------------------------


class TestCmdPlanReject(unittest.TestCase):
    def test_reject_sets_status(self):
        plan = {"id": "plan-001", "status": "draft"}
        buf = io.StringIO()
        with redirect_stdout(buf):
            cmd_plan_reject(
                argparse.Namespace(plan_id="plan-001"),
                load_state_fn=lambda: {"plans": [{"id": "plan-001"}]},
                resolve_plan_summary_fn=lambda plans, pid: plans[0],
                load_plan_from_summary_fn=lambda s: plan,
                persist_plan_artifacts_fn=lambda p: p,
                upsert_plan_summary_fn=lambda s, p: None,
                save_state_fn=lambda s: None,
            )
        self.assertEqual(plan["status"], "rejected")


# ---------------------------------------------------------------------------
# cmd_plan_criteria
# ---------------------------------------------------------------------------


class TestCmdPlanCriteria(unittest.TestCase):
    def test_json_output_with_plan_id(self):
        plan = {"id": "plan-001", "status": "executed", "plan_file": "f.json", "plan_doc": "d.md"}
        captured = []
        cmd_plan_criteria(
            argparse.Namespace(plan_id="plan-001", json=True),
            load_state_fn=lambda: {"plans": [{"id": "plan-001"}]},
            resolve_plan_summary_fn=lambda plans, pid: plans[0],
            load_plan_from_summary_fn=lambda s: plan,
            resolve_plan_for_verify_fn=lambda s: None,
            explain_verify_resolution_failure_fn=lambda s: "no plan",
            plan_exit_criteria_fn=lambda p: ["Tests pass", "Build succeeds"],
            emit_json_fn=lambda p: captured.append(p),
        )
        self.assertEqual(captured[0]["plan_id"], "plan-001")
        self.assertEqual(len(captured[0]["criteria"]), 2)

    def test_no_plan_id_uses_verify_resolution(self):
        plan = {"id": "plan-002", "status": "executed"}
        captured = []
        cmd_plan_criteria(
            argparse.Namespace(plan_id=None, json=True),
            load_state_fn=lambda: {"plans": [{"id": "plan-002"}]},
            resolve_plan_summary_fn=lambda plans, pid: None,
            load_plan_from_summary_fn=lambda s: plan,
            resolve_plan_for_verify_fn=lambda s: plan,
            explain_verify_resolution_failure_fn=lambda s: "no plan",
            plan_exit_criteria_fn=lambda p: [],
            emit_json_fn=lambda p: captured.append(p),
        )
        self.assertEqual(captured[0]["plan_id"], "plan-002")

    def test_no_plan_available_raises(self):
        with self.assertRaises(RuntimeError):
            cmd_plan_criteria(
                argparse.Namespace(plan_id=None, json=True),
                load_state_fn=lambda: {"plans": []},
                resolve_plan_summary_fn=lambda plans, pid: None,
                load_plan_from_summary_fn=lambda s: None,
                resolve_plan_for_verify_fn=lambda s: None,
                explain_verify_resolution_failure_fn=lambda s: "No executable plan found.",
                plan_exit_criteria_fn=lambda p: [],
                emit_json_fn=lambda p: None,
            )


if __name__ == "__main__":
    unittest.main()
