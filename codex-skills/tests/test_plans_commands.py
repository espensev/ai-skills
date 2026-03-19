"""Focused command-handler tests for task_runtime.plans."""

from __future__ import annotations

import argparse
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from task_runtime.plans import (  # noqa: E402
    cmd_plan_add_agent,
    cmd_plan_create,
    cmd_plan_criteria,
    cmd_plan_execute,
    cmd_plan_go,
    cmd_plan_show,
)


def _plan(plan_id: str = "plan-001", *, status: str = "draft", agents: list[dict] | None = None) -> dict:
    return {
        "id": plan_id,
        "status": status,
        "description": "Example plan",
        "plan_file": f"data/plans/{plan_id}.json",
        "plan_doc": f"docs/{plan_id}.md",
        "agents": list(agents or []),
        "groups": {},
    }


class TestCmdPlanGo(unittest.TestCase):
    def test_preflight_errors_block_progression(self):
        with self.assertRaises(RuntimeError) as ctx:
            cmd_plan_go(
                argparse.Namespace(plan_id="plan-001", json=True),
                plan_preflight_payload_fn=lambda: {"errors": ["missing config"]},
                load_state_fn=lambda: {"plans": []},
                resolve_plan_summary_fn=lambda plans, pid: None,
                load_plan_from_summary_fn=lambda summary: {},
                finalize_plan_updates_fn=lambda plan, args: (plan, [], [], []),
                persist_plan_artifacts_fn=lambda plan: plan,
                upsert_plan_summary_fn=lambda state, plan: None,
                save_state_fn=lambda state: None,
                plan_approve_fn=lambda args: None,
                plan_execute_fn=lambda args: None,
                emit_json_fn=lambda payload: None,
            )

        self.assertIn("Plan preflight failed", str(ctx.exception))

    def test_requires_agents_before_progressing(self):
        with self.assertRaises(RuntimeError) as ctx:
            cmd_plan_go(
                argparse.Namespace(plan_id="plan-001", json=True),
                plan_preflight_payload_fn=lambda: {"errors": [], "warnings": [], "commands": {}},
                load_state_fn=lambda: {"plans": [{"id": "plan-001"}]},
                resolve_plan_summary_fn=lambda plans, pid: plans[0],
                load_plan_from_summary_fn=lambda summary: _plan(agents=[]),
                finalize_plan_updates_fn=lambda plan, args: (plan, [], [], []),
                persist_plan_artifacts_fn=lambda plan: plan,
                upsert_plan_summary_fn=lambda state, plan: None,
                save_state_fn=lambda state: None,
                plan_approve_fn=lambda args: None,
                plan_execute_fn=lambda args: None,
                emit_json_fn=lambda payload: None,
            )

        self.assertIn("has no agents", str(ctx.exception))

    def test_success_path_emits_json_payload(self):
        payloads: list[dict] = []
        approve_calls: list[str] = []
        execute_calls: list[str] = []
        finalized_plan = _plan(status="executed", agents=[{"letter": "a", "name": "alpha"}])
        state = {
            "plans": [{"id": "plan-001"}],
            "tasks": {"a": {"id": "a", "name": "alpha", "status": "ready"}},
        }

        cmd_plan_go(
            argparse.Namespace(plan_id="plan-001", json=True),
            plan_preflight_payload_fn=lambda: {"errors": [], "warnings": ["warn"], "commands": {"test": "pytest"}},
            load_state_fn=lambda: state,
            resolve_plan_summary_fn=lambda plans, pid: plans[0],
            load_plan_from_summary_fn=lambda summary: dict(finalized_plan),
            finalize_plan_updates_fn=lambda plan, args: (plan, ["goal"], [], ["warn"]),
            persist_plan_artifacts_fn=lambda plan: plan,
            upsert_plan_summary_fn=lambda current_state, plan: None,
            save_state_fn=lambda current_state: None,
            plan_approve_fn=lambda args: approve_calls.append(args.plan_id),
            plan_execute_fn=lambda args: execute_calls.append(args.plan_id),
            emit_json_fn=lambda payload: payloads.append(payload),
        )

        self.assertEqual(approve_calls, ["plan-001"])
        self.assertEqual(execute_calls, ["plan-001"])
        self.assertEqual(payloads[0]["plan_id"], "plan-001")
        self.assertEqual(payloads[0]["ready_agents"], [{"id": "a", "name": "alpha"}])


class TestCmdPlanCreate(unittest.TestCase):
    def test_json_output_includes_planning_context_and_existing_tasks(self):
        payloads: list[dict] = []
        saved: list[dict] = []
        state = {
            "tasks": {"a": {"name": "alpha", "status": "done"}},
            "plans": [],
        }
        analysis = {
            "totals": {"files": 3, "lines": 30},
            "conflict_zones": [{"files": ["a.py", "b.py"], "reason": "shared"}],
            "modules": {"core": {"total_lines": 30}},
            "detected_stacks": ["python"],
            "project_graph": {"nodes": [], "edges": []},
            "analysis_v2": {
                "schema_version": 2,
                "providers": [{"name": "basic"}],
                "planning_context": {"analysis_health": {"confidence": "medium"}},
            },
        }

        cmd_plan_create(
            argparse.Namespace(
                description="Create plan",
                planner_kind="planner",
                discovery_doc=["docs/discovery.md"],
                roadmap="docs/roadmap.md",
                phase="Phase 1",
                behavioral_invariant=["No regressions"],
                json=True,
            ),
            sync_state_fn=lambda: state,
            next_plan_id_fn=lambda current_state: "plan-001",
            next_agent_letter_fn=lambda current_state: "c",
            analyze_project_fn=lambda: analysis,
            now_iso_fn=lambda: "2026-03-12T10:00:00+00:00",
            slugify_fn=lambda text: text.lower().replace(" ", "-"),
            empty_plan_elements_factory=lambda description: {"campaign_title": description},
            persist_plan_artifacts_fn=lambda plan: plan,
            upsert_plan_summary_fn=lambda current_state, plan: current_state.setdefault("plans", []).append(plan),
            save_state_fn=lambda current_state: saved.append(current_state),
            emit_json_fn=lambda payload: payloads.append(payload),
        )

        plan = payloads[0]["plan"]
        self.assertEqual(plan["analysis_summary"]["analysis_health"], {"confidence": "medium"})
        self.assertEqual(payloads[0]["existing_tasks"]["a"]["status"], "done")
        self.assertEqual(saved[-1]["plans"][0]["id"], "plan-001")

    def test_text_output_prints_bootstrap_instructions(self):
        buf = io.StringIO()
        state = {"tasks": {}, "plans": []}

        with redirect_stdout(buf):
            cmd_plan_create(
                argparse.Namespace(
                    description="",
                    planner_kind="planner",
                    discovery_doc=[],
                    roadmap="",
                    phase="",
                    behavioral_invariant=[],
                    json=False,
                ),
                sync_state_fn=lambda: state,
                next_plan_id_fn=lambda current_state: "plan-001",
                next_agent_letter_fn=lambda current_state: "a",
                analyze_project_fn=lambda: {
                    "totals": {"files": 1, "lines": 10},
                    "conflict_zones": [],
                    "modules": {"core": {"total_lines": 10}},
                    "detected_stacks": [],
                    "project_graph": {"nodes": [], "edges": []},
                    "analysis_v2": {"schema_version": 1, "providers": [], "planning_context": {}},
                },
                now_iso_fn=lambda: "2026-03-12T10:00:00+00:00",
                slugify_fn=lambda text: text,
                empty_plan_elements_factory=lambda description: {"campaign_title": description},
                persist_plan_artifacts_fn=lambda plan: {**plan, "plan_file": "data/plans/plan-001.json"},
                upsert_plan_summary_fn=lambda current_state, plan: None,
                save_state_fn=lambda current_state: None,
                emit_json_fn=lambda payload: None,
            )

        output = buf.getvalue()
        self.assertIn("(no description)", output)
        self.assertIn("plan-add-agent", output)
        self.assertIn("Use --json flag", output)


class TestCmdPlanShowAndCriteria(unittest.TestCase):
    def test_cmd_plan_show_handles_empty_json_and_text_paths(self):
        empty_buf = io.StringIO()
        with redirect_stdout(empty_buf):
            cmd_plan_show(
                argparse.Namespace(plan_id=None, json=False),
                load_state_fn=lambda: {"plans": []},
                resolve_plan_summary_fn=lambda plans, pid: None,
                load_plan_from_summary_fn=lambda summary: {},
                emit_json_fn=lambda payload: None,
                print_plan_fn=lambda plan: None,
            )
        self.assertIn("No plans.", empty_buf.getvalue())

        payloads: list[dict] = []
        plan = _plan()
        cmd_plan_show(
            argparse.Namespace(plan_id="plan-001", json=True),
            load_state_fn=lambda: {"plans": [{"id": "plan-001"}]},
            resolve_plan_summary_fn=lambda plans, pid: plans[0],
            load_plan_from_summary_fn=lambda summary: plan,
            emit_json_fn=lambda payload: payloads.append(payload),
            print_plan_fn=lambda current_plan: None,
        )
        self.assertEqual(payloads[0]["id"], "plan-001")

        printed: list[dict] = []
        cmd_plan_show(
            argparse.Namespace(plan_id="plan-001", json=False),
            load_state_fn=lambda: {"plans": [{"id": "plan-001"}]},
            resolve_plan_summary_fn=lambda plans, pid: plans[0],
            load_plan_from_summary_fn=lambda summary: plan,
            emit_json_fn=lambda payload: None,
            print_plan_fn=lambda current_plan: printed.append(current_plan),
        )
        self.assertEqual(printed[0]["id"], "plan-001")

    def test_cmd_plan_criteria_prints_when_no_criteria_are_present(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            cmd_plan_criteria(
                argparse.Namespace(plan_id="plan-001", json=False),
                load_state_fn=lambda: {"plans": [{"id": "plan-001"}]},
                resolve_plan_summary_fn=lambda plans, pid: plans[0],
                load_plan_from_summary_fn=lambda summary: _plan(status="executed"),
                resolve_plan_for_verify_fn=lambda state: None,
                explain_verify_resolution_failure_fn=lambda state: "no plan",
                plan_exit_criteria_fn=lambda plan: [],
                emit_json_fn=lambda payload: None,
            )

        self.assertIn("No exit criteria recorded.", buf.getvalue())


class TestCmdPlanExecute(unittest.TestCase):
    def test_returns_when_summary_is_missing(self):
        cmd_plan_execute(
            argparse.Namespace(plan_id="plan-001"),
            load_state_fn=lambda: {"plans": []},
            resolve_plan_summary_fn=lambda plans, pid: None,
            load_plan_from_summary_fn=lambda summary: {},
            validate_plan_fn=lambda plan, strict: [],
            new_task_factory=lambda *args, **kwargs: {},
            agents_dir=Path("."),
            write_spec_template_fn=lambda path, agent: None,
            assign_groups_fn=lambda state: None,
            recompute_ready_fn=lambda state: None,
            now_iso_fn=lambda: "",
            refresh_plan_elements_fn=lambda plan: None,
            persist_plan_artifacts_fn=lambda plan: plan,
            upsert_plan_summary_fn=lambda state, plan: None,
            save_state_fn=lambda state: None,
            sym_map={},
        )

    def test_rejects_missing_agents_and_validation_errors(self):
        with self.assertRaises(RuntimeError):
            cmd_plan_execute(
                argparse.Namespace(plan_id="plan-001"),
                load_state_fn=lambda: {"plans": [{"id": "plan-001"}], "tasks": {}},
                resolve_plan_summary_fn=lambda plans, pid: plans[0],
                load_plan_from_summary_fn=lambda summary: _plan(status="approved", agents=[]),
                validate_plan_fn=lambda plan, strict: [],
                new_task_factory=lambda *args, **kwargs: {},
                agents_dir=Path("."),
                write_spec_template_fn=lambda path, agent: None,
                assign_groups_fn=lambda state: None,
                recompute_ready_fn=lambda state: None,
                now_iso_fn=lambda: "",
                refresh_plan_elements_fn=lambda plan: None,
                persist_plan_artifacts_fn=lambda plan: plan,
                upsert_plan_summary_fn=lambda state, plan: None,
                save_state_fn=lambda state: None,
                sym_map={},
            )

        with self.assertRaises(RuntimeError):
            cmd_plan_execute(
                argparse.Namespace(plan_id="plan-001"),
                load_state_fn=lambda: {"plans": [{"id": "plan-001"}], "tasks": {}},
                resolve_plan_summary_fn=lambda plans, pid: plans[0],
                load_plan_from_summary_fn=lambda summary: _plan(status="approved", agents=[{"letter": "a", "name": "alpha"}]),
                validate_plan_fn=lambda plan, strict: ["Missing goal"],
                new_task_factory=lambda *args, **kwargs: {},
                agents_dir=Path("."),
                write_spec_template_fn=lambda path, agent: None,
                assign_groups_fn=lambda state: None,
                recompute_ready_fn=lambda state: None,
                now_iso_fn=lambda: "",
                refresh_plan_elements_fn=lambda plan: None,
                persist_plan_artifacts_fn=lambda plan: plan,
                upsert_plan_summary_fn=lambda state, plan: None,
                save_state_fn=lambda state: None,
                sym_map={},
            )

    def test_registers_tasks_writes_missing_specs_and_prints_ready_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            agents_dir = Path(tmp)
            existing_spec = agents_dir / "agent-a-alpha.md"
            existing_spec.write_text("existing\n", encoding="utf-8")
            saved: list[dict] = []
            written_specs: list[tuple[Path, dict]] = []
            state = {"plans": [{"id": "plan-001"}], "tasks": {}}
            plan = _plan(
                status="approved",
                agents=[
                    {"letter": "a", "name": "alpha", "scope": "A", "deps": [], "files": ["a.py"], "group": 0, "complexity": "medium"},
                    {"letter": "b", "name": "beta", "scope": "B", "deps": ["a"], "files": ["b.py"], "group": 1, "complexity": "high"},
                ],
            )
            buf = io.StringIO()

            def new_task_factory(letter, name, **kwargs):
                return {"id": letter, "name": name, **kwargs}

            def assign_groups_fn(current_state):
                current_state["groups"] = {"0": ["a"], "1": ["b"]}

            def recompute_ready_fn(current_state):
                current_state["tasks"]["a"]["status"] = "ready"
                current_state["tasks"]["b"]["status"] = "blocked"

            with redirect_stdout(buf):
                cmd_plan_execute(
                    argparse.Namespace(plan_id="plan-001"),
                    load_state_fn=lambda: state,
                    resolve_plan_summary_fn=lambda plans, pid: plans[0],
                    load_plan_from_summary_fn=lambda summary: plan,
                    validate_plan_fn=lambda current_plan, strict: [],
                    new_task_factory=new_task_factory,
                    agents_dir=agents_dir,
                    write_spec_template_fn=lambda path, agent: written_specs.append((path, agent)),
                    assign_groups_fn=assign_groups_fn,
                    recompute_ready_fn=recompute_ready_fn,
                    now_iso_fn=lambda: "2026-03-12T10:30:00+00:00",
                    refresh_plan_elements_fn=lambda current_plan: current_plan.update({"refreshed": True}),
                    persist_plan_artifacts_fn=lambda current_plan: current_plan,
                    upsert_plan_summary_fn=lambda current_state, current_plan: None,
                    save_state_fn=lambda current_state: saved.append(current_state),
                    sym_map={"ready": "o", "blocked": "x"},
                )

        self.assertEqual(state["tasks"]["a"]["status"], "ready")
        self.assertEqual(state["tasks"]["b"]["status"], "blocked")
        self.assertEqual(plan["status"], "executed")
        self.assertEqual(plan["executed_at"], "2026-03-12T10:30:00+00:00")
        self.assertEqual(written_specs[0][0].name, "agent-b-beta.md")
        self.assertEqual(written_specs[0][1]["_plan"]["id"], "plan-001")
        self.assertIn("Ready to launch: python scripts/task_manager.py run a", buf.getvalue())
        self.assertEqual(saved[-1]["groups"], {"0": ["a"], "1": ["b"]})


class TestCmdPlanAddAgent(unittest.TestCase):
    def test_returns_when_summary_missing_or_plan_not_draft_or_duplicate(self):
        cmd_plan_add_agent(
            argparse.Namespace(plan_id="plan-001", letter="a", name="alpha", scope="", deps="", files="", group="", complexity="medium"),
            load_state_fn=lambda: {"plans": []},
            resolve_plan_summary_fn=lambda plans, pid: None,
            load_plan_from_summary_fn=lambda summary: {},
            validate_agent_id_fn=lambda letter: None,
            default_plan_fields_fn=lambda plan: plan,
            plan_assign_groups_fn=lambda plan, strict: None,
            validate_plan_fn=lambda plan, strict: [],
            next_agent_letter_fn=lambda state: "b",
            persist_plan_artifacts_fn=lambda plan: plan,
            upsert_plan_summary_fn=lambda state, plan: None,
            save_state_fn=lambda state: None,
        )

        with self.assertRaises(RuntimeError) as ctx:
            cmd_plan_add_agent(
                argparse.Namespace(
                    plan_id="plan-001",
                    letter="a",
                    name="alpha",
                    scope="",
                    deps="",
                    files="",
                    group="",
                    complexity="medium",
                ),
                load_state_fn=lambda: {"plans": [{"id": "plan-001"}], "tasks": {}},
                resolve_plan_summary_fn=lambda plans, pid: plans[0],
                load_plan_from_summary_fn=lambda summary: _plan(status="approved"),
                validate_agent_id_fn=lambda letter: None,
                default_plan_fields_fn=lambda plan: plan,
                plan_assign_groups_fn=lambda plan, strict: None,
                validate_plan_fn=lambda plan, strict: [],
                next_agent_letter_fn=lambda state: "b",
                persist_plan_artifacts_fn=lambda plan: plan,
                upsert_plan_summary_fn=lambda state, plan: None,
                save_state_fn=lambda state: None,
            )
        self.assertIn("can only add agents to draft plans", str(ctx.exception))

        buf = io.StringIO()
        with redirect_stdout(buf):
            cmd_plan_add_agent(
                argparse.Namespace(
                    plan_id="plan-001",
                    letter="a",
                    name="alpha",
                    scope="",
                    deps="",
                    files="",
                    group="",
                    complexity="medium",
                ),
                load_state_fn=lambda: {"plans": [{"id": "plan-001"}], "tasks": {}},
                resolve_plan_summary_fn=lambda plans, pid: plans[0],
                load_plan_from_summary_fn=lambda summary: _plan(status="draft", agents=[{"letter": "a"}]),
                validate_agent_id_fn=lambda letter: None,
                default_plan_fields_fn=lambda plan: plan,
                plan_assign_groups_fn=lambda plan, strict: None,
                validate_plan_fn=lambda plan, strict: [],
                next_agent_letter_fn=lambda state: "b",
                persist_plan_artifacts_fn=lambda plan: plan,
                upsert_plan_summary_fn=lambda state, plan: None,
                save_state_fn=lambda state: None,
            )
        self.assertIn("already in plan", buf.getvalue())

    def test_rejects_task_state_collisions_and_validation_failures(self):
        with self.assertRaises(RuntimeError):
            cmd_plan_add_agent(
                argparse.Namespace(
                    plan_id="plan-001",
                    letter="a",
                    name="alpha",
                    scope="",
                    deps="",
                    files="",
                    group="",
                    complexity="medium",
                ),
                load_state_fn=lambda: {"plans": [{"id": "plan-001"}], "tasks": {"a": {}}},
                resolve_plan_summary_fn=lambda plans, pid: plans[0],
                load_plan_from_summary_fn=lambda summary: _plan(status="draft"),
                validate_agent_id_fn=lambda letter: None,
                default_plan_fields_fn=lambda plan: plan,
                plan_assign_groups_fn=lambda plan, strict: None,
                validate_plan_fn=lambda plan, strict: [],
                next_agent_letter_fn=lambda state: "b",
                persist_plan_artifacts_fn=lambda plan: plan,
                upsert_plan_summary_fn=lambda state, plan: None,
                save_state_fn=lambda state: None,
            )

        with self.assertRaises(RuntimeError):
            cmd_plan_add_agent(
                argparse.Namespace(
                    plan_id="plan-001",
                    letter="a",
                    name="alpha",
                    scope="",
                    deps="",
                    files="",
                    group="",
                    complexity="medium",
                ),
                load_state_fn=lambda: {"plans": [{"id": "plan-001"}], "tasks": {}},
                resolve_plan_summary_fn=lambda plans, pid: plans[0],
                load_plan_from_summary_fn=lambda summary: _plan(status="draft"),
                validate_agent_id_fn=lambda letter: None,
                default_plan_fields_fn=lambda plan: plan,
                plan_assign_groups_fn=lambda plan, strict: None,
                validate_plan_fn=lambda plan, strict: ["Missing goal"],
                next_agent_letter_fn=lambda state: "b",
                persist_plan_artifacts_fn=lambda plan: plan,
                upsert_plan_summary_fn=lambda state, plan: None,
                save_state_fn=lambda state: None,
            )

    def test_successfully_adds_agent_and_updates_next_letter(self):
        saved: list[dict] = []
        persisted: list[dict] = []
        upserted: list[dict] = []
        plan = _plan(status="draft", agents=[])
        buf = io.StringIO()

        with redirect_stdout(buf):
            cmd_plan_add_agent(
                argparse.Namespace(
                    plan_id="plan-001",
                    letter="A",
                    name="Alpha",
                    scope="Ship",
                    deps="b,c",
                    files="one.py,two.py",
                    group="2",
                    complexity="high",
                ),
                load_state_fn=lambda: {"plans": [{"id": "plan-001"}], "tasks": {}},
                resolve_plan_summary_fn=lambda plans, pid: plans[0],
                load_plan_from_summary_fn=lambda summary: plan,
                validate_agent_id_fn=lambda letter: None,
                default_plan_fields_fn=lambda current_plan: current_plan,
                plan_assign_groups_fn=lambda current_plan, strict: None,
                validate_plan_fn=lambda current_plan, strict: [],
                next_agent_letter_fn=lambda state: "d",
                persist_plan_artifacts_fn=lambda current_plan: persisted.append(dict(current_plan)) or current_plan,
                upsert_plan_summary_fn=lambda state, current_plan: upserted.append(current_plan),
                save_state_fn=lambda state: saved.append(state),
            )

        self.assertEqual(plan["agents"][0]["letter"], "a")
        self.assertEqual(plan["agents"][0]["deps"], ["b", "c"])
        self.assertEqual(plan["agents"][0]["files"], ["one.py", "two.py"])
        self.assertEqual(plan["next_letter"], "d")
        self.assertTrue(persisted)
        self.assertTrue(upserted)
        self.assertTrue(saved)
        self.assertIn("Added Agent A", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
