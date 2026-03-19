# ruff: noqa: E402
"""Plan lifecycle enforcement tests for scripts/task_manager.py."""

import argparse
import io
import json
import sys
import tempfile
import textwrap
import unittest
from contextlib import ExitStack, redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import task_manager


class PlanLifecycleEnforcementTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)
        self.agents_dir = self.root / "agents"
        self.agents_dir.mkdir(parents=True, exist_ok=True)
        self.docs_dir = self.root / "docs"
        self.docs_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir = self.root / "data"
        self.plans_dir = self.data_dir / "plans"
        self.plans_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.data_dir / "tasks.json"
        self.tracker_file = self.root / "custom-tracker.md"
        self.conventions_file = self.root / "CLAUDE.md"
        self.conventions_file.write_text("Lifecycle test conventions.\n", encoding="utf-8")

    def tearDown(self):
        self._tmpdir.cleanup()

    def _patch_env(self, *, tracker: bool = False, commands: dict | None = None):
        cfg = {
            "project": {"name": "Lifecycle Test", "conventions": "CLAUDE.md"},
            "commands": commands
            or {
                "compile": "python -m py_compile {files}",
                "test": "python -m pytest tests/ -q",
                "build": "dotnet build launcher/App.csproj -c Release",
            },
        }
        tracker_value = "custom-tracker.md" if tracker else ""
        if tracker:
            self.tracker_file.write_text("", encoding="utf-8")

        stack = ExitStack()
        stack.enter_context(mock.patch.object(task_manager, "ROOT", self.root))
        stack.enter_context(mock.patch.object(task_manager, "AGENTS_DIR", self.agents_dir))
        stack.enter_context(mock.patch.object(task_manager, "STATE_FILE", self.state_file))
        stack.enter_context(mock.patch.object(task_manager, "PLANS_DIR", self.plans_dir))
        stack.enter_context(mock.patch.object(task_manager, "TRACKER_FILE", self.tracker_file if tracker else None))
        stack.enter_context(mock.patch.object(task_manager, "_tracker_str", tracker_value))
        stack.enter_context(mock.patch.object(task_manager, "CONVENTIONS_FILE", "CLAUDE.md"))
        stack.enter_context(mock.patch.object(task_manager, "_CFG", cfg))
        return stack

    def _base_plan(self, plan_id: str = "plan-001") -> dict:
        plan = {
            "id": plan_id,
            "created_at": "2026-03-11T15:52:21+00:00",
            "status": "draft",
            "description": "Lifecycle enforcement test",
            "agents": [],
            "groups": {},
            "conflicts": [],
            "integration_steps": [],
            "analysis_summary": {
                "total_files": 1,
                "total_lines": 10,
                "conflict_zones": [],
                "modules": {},
            },
            "plan_elements": task_manager._empty_plan_elements("Lifecycle enforcement test"),
        }
        return task_manager._default_plan_fields(plan)

    def _valid_plan(self, plan_id: str = "plan-001", *, status: str = "draft") -> dict:
        plan = self._base_plan(plan_id)
        plan["status"] = status
        plan["agents"] = [
            {
                "letter": "a",
                "name": "alpha",
                "scope": "Implement alpha.",
                "deps": [],
                "files": ["alpha.py"],
                "group": 0,
                "complexity": "medium",
            }
        ]
        task_manager._plan_assign_groups(plan)
        plan["plan_elements"]["goal_statement"] = "Implement a validated lifecycle plan."
        plan["plan_elements"]["exit_criteria"] = ["Approval succeeds only for valid plans."]
        plan["plan_elements"]["verification_strategy"] = [
            "python -m py_compile scripts/task_manager.py",
            "python -m pytest tests/test_plan_lifecycle.py -q",
        ]
        plan["plan_elements"]["documentation_updates"] = ["No documentation updates required."]
        task_manager._refresh_plan_elements(plan)
        return plan

    def _register_plan(self, plan: dict) -> dict:
        persisted = task_manager._persist_plan_artifacts(plan)
        state = task_manager.load_state()
        task_manager._upsert_plan_summary(state, persisted)
        task_manager.save_state(state)
        return persisted

    def _write_spec(
        self,
        letter: str,
        name: str,
        *,
        with_exit_criteria: bool,
        placeholder: bool,
    ) -> Path:
        exit_block = ""
        if with_exit_criteria:
            exit_block = textwrap.dedent(
                """\
                ## Exit Criteria

                - Scope is implemented.
                - Verification passes.

                ---
                """
            )
        task_text = "TODO: finish this task." if placeholder else "Implement the scoped change."
        path = self.agents_dir / f"agent-{letter}-{name}.md"
        path.write_text(
            textwrap.dedent(
                f"""\
                # Agent Task - {name.title()}

                **Scope:** Implement {name}.

                **Depends on:** (none)

                **Output files:** `example.py`

                ---

                ## Context — read before doing anything

                1. `CLAUDE.md`

                ---

                ## Task

                {task_text}

                ---

                {exit_block}

                ## Verification

                ```powershell
                python -m pytest tests/ -q
                ```
                """
            ),
            encoding="utf-8",
        )
        return path

    def test_validate_plan_requires_goal_and_exit_criteria(self):
        plan = self._base_plan()
        errors = task_manager._validate_plan(plan, strict=True)

        self.assertIn("Missing required plan element: goal_statement", errors)
        self.assertIn("Missing required plan element: exit_criteria", errors)

    def test_validate_file_ownership_rejects_duplicate_claims(self):
        plan = self._valid_plan()
        plan["agents"].append(
            {
                "letter": "b",
                "name": "beta",
                "scope": "Implement beta.",
                "deps": ["a"],
                "files": ["alpha.py"],
                "group": 1,
                "complexity": "low",
            }
        )
        task_manager._plan_assign_groups(plan)

        errors = task_manager._validate_plan(plan, strict=True)

        self.assertIn("Duplicate file ownership: alpha.py claimed by A, B", errors)

    def test_plan_validate_json_reports_errors_and_warnings(self):
        with self._patch_env():
            plan = self._register_plan(self._base_plan())
            buf = io.StringIO()
            with redirect_stdout(buf), self.assertRaises(SystemExit) as exc:
                task_manager.cmd_plan_validate(argparse.Namespace(plan_id=plan["id"], json=True))

        payload = json.loads(buf.getvalue())
        self.assertEqual(exc.exception.code, 1)
        self.assertFalse(payload["valid"])
        self.assertIsInstance(payload["errors"], list)
        self.assertIsInstance(payload["warnings"], list)

    def test_extract_spec_exit_criteria_parses_markdown_section(self):
        text = textwrap.dedent(
            """\
            ## Exit Criteria

            - First criterion
            - Second criterion

            ## Verification
            """
        )
        self.assertEqual(
            task_manager._extract_spec_exit_criteria(text),
            ["First criterion", "Second criterion"],
        )

    def test_extract_spec_exit_criteria_parses_legacy_bold_block(self):
        text = textwrap.dedent(
            """\
            **Exit criteria:**
            - First criterion
            - Second criterion

            ## Verification
            """
        )
        self.assertEqual(
            task_manager._extract_spec_exit_criteria(text),
            ["First criterion", "Second criterion"],
        )

    def test_spec_has_placeholders_detects_todo(self):
        self.assertTrue(task_manager._spec_has_placeholders("TODO: finish this section"))
        self.assertFalse(task_manager._spec_has_placeholders("Scope is fully described."))

    def test_render_spec_template_includes_exit_criteria_and_no_todo(self):
        with self._patch_env():
            rendered = task_manager._render_spec_template(
                "aq",
                "lifecycle-guard",
                "Implement lifecycle guards.",
                deps=["a"],
                files=["scripts/task_manager.py"],
            )

        self.assertIn("## Exit Criteria", rendered)
        self.assertFalse(task_manager._spec_has_placeholders(rendered))

    def test_cmd_run_blocks_incomplete_specs(self):
        with self._patch_env():
            self._write_spec("a", "alpha", with_exit_criteria=False, placeholder=True)

            buf = io.StringIO()
            with redirect_stdout(buf):
                task_manager.cmd_run(argparse.Namespace(agents="a", json=True))

            state = task_manager.load_state()

        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["launched"], [])
        self.assertEqual(payload["skipped"][0]["reason"], "invalid_spec")
        self.assertNotEqual(state["tasks"]["a"]["status"], "running")

    def test_plan_approve_rejects_invalid_plan(self):
        with self._patch_env():
            plan = self._register_plan(self._base_plan())

            with self.assertRaises(task_manager.TaskManagerError):
                task_manager._plan_approve(argparse.Namespace(plan_id=plan["id"]))

            stored = json.loads((self.plans_dir / f"{plan['id']}.json").read_text(encoding="utf-8"))

        self.assertEqual(stored["status"], "draft")

    def test_plan_execute_rejects_unapproved_plan(self):
        with self._patch_env():
            plan = self._register_plan(self._valid_plan())

            with self.assertRaises(task_manager.TaskManagerError):
                task_manager._plan_execute(argparse.Namespace(plan_id=plan["id"]))

    def test_plan_execute_rejects_existing_agent_collisions_without_mutating_plan(self):
        with self._patch_env():
            plan = self._register_plan(self._valid_plan(status="approved"))
            state = task_manager.load_state()
            state["tasks"]["a"] = {
                "id": "a",
                "name": "existing-alpha",
                "spec_file": "agents/agent-a-existing-alpha.md",
                "scope": "Existing scope.",
                "status": "done",
                "deps": [],
                "files": ["existing.py"],
                "group": 0,
                "tracker_id": "",
                "started_at": "",
                "completed_at": "",
                "summary": "",
                "error": "",
            }
            task_manager.save_state(state)

            with self.assertRaises(task_manager.TaskManagerError) as exc:
                task_manager._plan_execute(argparse.Namespace(plan_id=plan["id"]))

            stored = json.loads((self.plans_dir / f"{plan['id']}.json").read_text(encoding="utf-8"))

        self.assertIn("already exist", str(exc.exception))
        self.assertEqual(stored["status"], "approved")
        self.assertFalse((self.agents_dir / "agent-a-alpha.md").exists())

    def test_plan_add_agent_allows_draft_out_of_order_dependencies(self):
        with self._patch_env():
            plan = self._register_plan(self._base_plan())

            with redirect_stdout(io.StringIO()):
                task_manager.cmd_plan_add_agent(
                    argparse.Namespace(
                        plan_id=plan["id"],
                        letter="b",
                        name="beta",
                        scope="Implement beta.",
                        deps="a",
                        files="beta.py",
                        group="",
                        complexity="medium",
                    )
                )

            first = json.loads((self.plans_dir / f"{plan['id']}.json").read_text(encoding="utf-8"))
            first_agents = {agent["letter"]: agent for agent in first["agents"]}

            with redirect_stdout(io.StringIO()):
                task_manager.cmd_plan_add_agent(
                    argparse.Namespace(
                        plan_id=plan["id"],
                        letter="a",
                        name="alpha",
                        scope="Implement alpha.",
                        deps="",
                        files="alpha.py",
                        group="",
                        complexity="medium",
                    )
                )

            stored = json.loads((self.plans_dir / f"{plan['id']}.json").read_text(encoding="utf-8"))

        self.assertEqual(first_agents["b"]["deps"], ["a"])
        self.assertEqual(first_agents["b"]["group"], 0)
        agents = {agent["letter"]: agent for agent in stored["agents"]}
        self.assertEqual(agents["a"]["group"], 0)
        self.assertEqual(agents["b"]["group"], 1)

    def test_render_plan_doc_contains_standard_and_refactor_sections(self):
        plan = self._valid_plan()
        plan["planner_kind"] = "refactor-planner"
        plan["phase"] = "2 — Seam extraction"
        plan["source_roadmap"] = "docs/refactor-roadmap.md"
        plan["behavioral_invariants"] = ["Existing tests remain green."]
        plan["rollback_strategy"] = "Revert the campaign commits."

        rendered = task_manager._render_plan_doc(plan)

        self.assertIn("## 1. Goal", rendered)
        self.assertIn("## 11. Verification Strategy", rendered)
        self.assertIn("## R1. Roadmap Phase", rendered)
        self.assertIn("## R2. Behavioral Invariants", rendered)
        self.assertIn("## R3. Rollback Strategy", rendered)

    def test_plan_criteria_outputs_canonical_exit_criteria(self):
        with self._patch_env():
            plan = self._valid_plan(status="executed")
            registered = self._register_plan(plan)
            buf = io.StringIO()
            with redirect_stdout(buf):
                task_manager.cmd_plan_criteria(argparse.Namespace(plan_id=registered["id"], json=True))

        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["plan_id"], registered["id"])
        self.assertEqual(payload["criteria"], ["Approval succeeds only for valid plans."])

    def test_refactor_metadata_round_trip_persists_in_json(self):
        with self._patch_env():
            plan = self._valid_plan()
            plan["planner_kind"] = "refactor-planner"
            plan["source_discovery_docs"] = ["docs/discovery-refactor.md"]
            plan["source_roadmap"] = "docs/refactor-roadmap.md"
            plan["phase"] = "2 — Seam extraction"
            plan["behavioral_invariants"] = ["Public API responses stay stable."]
            plan["rollback_strategy"] = "Revert the campaign commits."
            registered = self._register_plan(plan)
            stored = json.loads((self.plans_dir / f"{registered['id']}.json").read_text(encoding="utf-8"))

        self.assertEqual(stored["planner_kind"], "refactor-planner")
        self.assertEqual(stored["source_discovery_docs"], ["docs/discovery-refactor.md"])
        self.assertEqual(stored["phase"], "2 — Seam extraction")
        self.assertEqual(stored["behavioral_invariants"], ["Public API responses stay stable."])
        self.assertEqual(stored["rollback_strategy"], "Revert the campaign commits.")

    # --- Resolver tests ---

    def test_resolve_plan_for_verify_skips_empty_criteria(self):
        """Resolver skips executed plans with empty exit_criteria."""
        with self._patch_env():
            invalid = self._base_plan("plan-100")
            invalid["status"] = "executed"
            self._register_plan(invalid)

            valid = self._valid_plan("plan-101", status="executed")
            self._register_plan(valid)

            state = task_manager.load_state()
            result = task_manager._resolve_plan_for_verify(state)

        self.assertIsNotNone(result)
        self.assertEqual(result["id"], "plan-101")

    def test_resolve_plan_for_verify_returns_none_when_all_invalid(self):
        """Resolver returns None when all executed plans have empty criteria."""
        with self._patch_env():
            invalid = self._base_plan("plan-100")
            invalid["status"] = "executed"
            self._register_plan(invalid)

            state = task_manager.load_state()
            result = task_manager._resolve_plan_for_verify(state)

        self.assertIsNone(result)

    # --- Legacy backfill tests ---

    def test_mark_plan_needs_backfill_marks_empty_executed_plan(self):
        plan = self._base_plan()
        plan["status"] = "executed"
        result = task_manager._mark_plan_needs_backfill(task_manager._default_plan_fields(plan))
        self.assertEqual(result["legacy_status"], "needs_backfill")
        self.assertIn("empty goal_statement", result["backfill_reasons"])
        self.assertIn("empty exit_criteria", result["backfill_reasons"])

    def test_mark_plan_needs_backfill_skips_draft_plans(self):
        plan = self._base_plan()
        plan["status"] = "draft"
        result = task_manager._mark_plan_needs_backfill(task_manager._default_plan_fields(plan))
        self.assertEqual(result.get("legacy_status", ""), "")

    def test_mark_plan_needs_backfill_is_idempotent(self):
        plan = self._base_plan()
        plan["status"] = "executed"
        plan["legacy_status"] = "needs_backfill"
        plan["backfill_reasons"] = ["previously marked"]
        result = task_manager._mark_plan_needs_backfill(task_manager._default_plan_fields(plan))
        self.assertEqual(result["backfill_reasons"], ["previously marked"])

    def test_mark_plan_needs_backfill_skips_valid_plans(self):
        plan = self._valid_plan(status="executed")
        result = task_manager._mark_plan_needs_backfill(task_manager._default_plan_fields(plan))
        self.assertEqual(result.get("legacy_status", ""), "")

    # --- Template tests ---

    def test_render_spec_template_has_no_leading_indentation(self):
        with self._patch_env():
            rendered = task_manager._render_spec_template("zz", "test-agent", "Test scope.", files=["test.py"])
        self.assertFalse(rendered.startswith(" "), f"Template has leading whitespace: {repr(rendered[:30])}")
        self.assertIn("# Agent Task", rendered.splitlines()[0])

    def test_template_exit_criteria_parseable(self):
        with self._patch_env():
            rendered = task_manager._render_spec_template("zz", "test-agent", "Test scope.", files=["test.py"])
        criteria = task_manager._extract_spec_exit_criteria(rendered)
        self.assertTrue(len(criteria) > 0, "No exit criteria parsed from template")

    # --- JSON-first criteria path test ---

    def test_plan_criteria_json_skips_invalid_and_returns_valid(self):
        with self._patch_env():
            invalid = self._base_plan("plan-100")
            invalid["status"] = "executed"
            self._register_plan(invalid)

            valid = self._valid_plan("plan-099", status="executed")
            self._register_plan(valid)

            buf = io.StringIO()
            with redirect_stdout(buf):
                task_manager.cmd_plan_criteria(argparse.Namespace(plan_id=None, json=True))

        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["plan_id"], "plan-099")
        self.assertTrue(len(payload["criteria"]) > 0)

    def test_finalize_includes_cost_estimate(self):
        """_finalize_plan_updates should populate plan_elements['cost_estimate']."""
        with self._patch_env():
            plan = self._valid_plan()
            args = argparse.Namespace(
                goal="",
                exit_criterion=[],
                verification_step=[],
                documentation_update=[],
            )
            updated_plan, updated_fields, _errors, _warnings = task_manager._finalize_plan_updates(plan, args)

        self.assertIn("cost_estimate", updated_plan["plan_elements"])
        cost = updated_plan["plan_elements"]["cost_estimate"]
        self.assertIn("tiered_usd", cost)
        self.assertIn("opus_usd", cost)
        self.assertIn("savings_usd", cost)
        self.assertIn("savings_pct", cost)
        self.assertIn("cost_estimate", updated_fields)

    def test_finalize_skips_cost_estimate_when_no_agents(self):
        """_finalize_plan_updates should skip cost_estimate when plan has no agents."""
        with self._patch_env():
            plan = self._base_plan()
            plan["plan_elements"]["goal_statement"] = "Test plan with no agents."
            plan["plan_elements"]["exit_criteria"] = ["No agents means no cost estimate."]
            plan["plan_elements"]["verification_strategy"] = ["python -m pytest tests/ -q"]
            plan["plan_elements"]["documentation_updates"] = ["No documentation updates required."]
            task_manager._refresh_plan_elements(plan)
            args = argparse.Namespace(
                goal="",
                exit_criterion=[],
                verification_step=[],
                documentation_update=[],
            )
            updated_plan, updated_fields, _errors, _warnings = task_manager._finalize_plan_updates(plan, args)

        self.assertNotIn("cost_estimate", updated_plan["plan_elements"])
        self.assertNotIn("cost_estimate", updated_fields)

    def test_merge_backup_field_present(self):
        """_merge_runtime result dict should always include 'backup_method'."""
        with self._patch_env():
            payload = task_manager._merge_runtime()

        self.assertIn("backup_method", payload)
        self.assertIn(payload["backup_method"], {"git_stash", "file_copy", "none"})


if __name__ == "__main__":
    unittest.main()
