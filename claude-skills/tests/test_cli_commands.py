# ruff: noqa: E402
"""Tests for CLI commands and TaskManagerError error paths in scripts/task_manager.py."""

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


class CLICommandTests(unittest.TestCase):
    """Tests for cmd_add, cmd_complete, cmd_fail, cmd_graph, cmd_next,
    cmd_reset, cmd_status, and cmd_sync."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)
        self.agents_dir = self.root / "agents"
        self.agents_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir = self.root / "data"
        self.plans_dir = self.data_dir / "plans"
        self.plans_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.data_dir / "tasks.json"
        self.tracker_file = self.root / "custom-tracker.md"
        self.conventions_file = self.root / "CLAUDE.md"
        self.conventions_file.write_text("CLI test conventions.\n", encoding="utf-8")

    def tearDown(self):
        self._tmpdir.cleanup()

    def _patch_env(self, *, tracker: bool = False, commands: dict | None = None):
        cfg = {
            "project": {"name": "CLI Test", "conventions": "CLAUDE.md"},
            "commands": commands
            or {
                "compile": "python -m py_compile {files}",
                "test": "python -m pytest tests/ -q",
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

    def _write_spec(
        self,
        letter: str,
        name: str,
        *,
        deps: str = "(none)",
        files: str = "`example.py`",
    ) -> Path:
        path = self.agents_dir / f"agent-{letter}-{name}.md"
        path.write_text(
            textwrap.dedent(
                f"""\
                # Agent Task - {name.replace("-", " ").title()}

                **Scope:** Implement {name}.

                **Depends on:** {deps}

                **Output files:** {files}

                ---

                ## Context -- read before doing anything

                1. `CLAUDE.md`

                ---

                ## Task

                Implement the scoped change.

                ---

                ## Exit Criteria

                - Scope is implemented.
                - Verification passes.

                ---

                ## Verification

                ```powershell
                python -m pytest tests/ -q
                ```
                """
            ),
            encoding="utf-8",
        )
        return path

    # ---- cmd_sync ----

    def test_cmd_sync_discovers_specs(self):
        with self._patch_env():
            self._write_spec("a", "alpha")
            buf = io.StringIO()
            with redirect_stdout(buf):
                task_manager.cmd_sync(argparse.Namespace())
            output = buf.getvalue()

        self.assertIn("1 tasks", output)
        self.assertIn("Synced", output)

    # ---- cmd_status ----

    def test_cmd_status_shows_tasks(self):
        with self._patch_env():
            self._write_spec("a", "alpha")
            task_manager.sync_state()
            buf = io.StringIO()
            with redirect_stdout(buf):
                task_manager.cmd_status(argparse.Namespace())
            output = buf.getvalue()

        self.assertIn("Agent A", output)
        self.assertIn("alpha", output)

    def test_cmd_status_json_reports_lifecycle_snapshot(self):
        with self._patch_env():
            self._write_spec("a", "alpha")
            self._write_spec("b", "beta", deps="Agent A")
            state = task_manager.sync_state()
            state["tasks"]["a"]["status"] = "running"
            state["execution_manifest"] = task_manager._empty_execution_manifest()
            state["execution_manifest"]["plan_id"] = "plan-001"
            state["execution_manifest"]["status"] = "awaiting_results"
            state["execution_manifest"]["updated_at"] = "2026-03-12T12:00:00+00:00"
            state["execution_manifest"]["launch"].update(
                {
                    "status": "awaiting_results",
                    "launched": ["a"],
                    "running": ["a"],
                    "failed": [],
                }
            )
            task_manager.save_state(state)
            # Invalidate sync_state mtime cache so the next sync_state()
            # re-reads from disk (avoids Windows mtime resolution race).
            task_manager._last_sync_state = None
            task_manager._state_file_mtime = None

            buf = io.StringIO()
            with redirect_stdout(buf):
                task_manager.cmd_status(argparse.Namespace(json=True))
            payload = json.loads(buf.getvalue())

        self.assertEqual(payload["project"], "CLI Test")
        self.assertEqual(payload["plan_id"], "plan-001")
        self.assertEqual(payload["status"], "awaiting_results")
        self.assertEqual(payload["next_action"], "await_results")
        self.assertEqual(payload["counts"]["running"], 1)
        self.assertEqual(payload["counts"]["blocked"], 1)
        self.assertEqual(payload["counts"]["total"], 2)
        self.assertEqual(payload["agents"]["running"][0]["id"], "a")
        self.assertEqual(payload["agents"]["blocked"][0]["id"], "b")
        self.assertEqual(payload["launch"]["running"], ["a"])

    def test_cmd_status_json_recommends_merge_when_all_tasks_are_done(self):
        with self._patch_env():
            self._write_spec("a", "alpha")
            state = task_manager.sync_state()
            state["tasks"]["a"]["status"] = "done"
            task_manager.save_state(state)

            buf = io.StringIO()
            with redirect_stdout(buf):
                task_manager.cmd_status(argparse.Namespace(json=True))
            payload = json.loads(buf.getvalue())

        self.assertEqual(payload["status"], "ready_for_merge")
        self.assertEqual(payload["next_action"], "merge")
        self.assertEqual(payload["counts"]["done"], 1)

    def test_cmd_status_json_recommends_verify_after_merge(self):
        with self._patch_env():
            self._write_spec("a", "alpha")
            state = task_manager.sync_state()
            state["tasks"]["a"]["status"] = "done"
            state["execution_manifest"] = task_manager._empty_execution_manifest()
            state["execution_manifest"]["plan_id"] = "plan-001"
            state["execution_manifest"]["merge"].update(
                {
                    "status": "merged",
                    "completed_at": "2026-03-12T12:30:00+00:00",
                    "merged_agents": ["a"],
                }
            )
            state["execution_manifest"]["verify"].update(
                {
                    "status": "failed",
                    "completed_at": "2026-03-12T12:45:00+00:00",
                    "passed": False,
                    "failed_commands": ["test"],
                }
            )
            task_manager.save_state(state)

            buf = io.StringIO()
            with redirect_stdout(buf):
                task_manager.cmd_status(argparse.Namespace(json=True))
            payload = json.loads(buf.getvalue())

        self.assertEqual(payload["status"], "verification_failed")
        self.assertEqual(payload["next_action"], "verify")
        self.assertEqual(payload["merge"]["status"], "merged")
        self.assertEqual(payload["verify"]["failed_commands"], ["test"])

    # ---- cmd_add ----

    def test_cmd_add_registers_new_task(self):
        with self._patch_env():
            self._write_spec("a", "alpha")
            task_manager.sync_state()
            buf = io.StringIO()
            with redirect_stdout(buf):
                task_manager.cmd_add(
                    argparse.Namespace(
                        letter="b",
                        name="beta",
                        scope="Implement beta feature.",
                        deps="a",
                        files="beta.py",
                    )
                )
            state = task_manager.load_state()

        self.assertIn("b", state["tasks"])
        self.assertEqual(state["tasks"]["b"]["name"], "beta")
        self.assertEqual(state["tasks"]["b"]["deps"], ["a"])

    def test_cmd_add_duplicate_exits(self):
        with self._patch_env():
            self._write_spec("a", "alpha")
            task_manager.sync_state()
            with self.assertRaises(SystemExit) as exc:
                buf = io.StringIO()
                with redirect_stdout(buf):
                    task_manager.cmd_add(
                        argparse.Namespace(
                            letter="a",
                            name="alpha-dup",
                            scope="Duplicate.",
                            deps="",
                            files="",
                        )
                    )
            self.assertEqual(exc.exception.code, 1)

    # ---- cmd_complete ----

    def test_cmd_complete_marks_done(self):
        with self._patch_env():
            self._write_spec("a", "alpha")
            state = task_manager.sync_state()
            # Move to running first
            state["tasks"]["a"]["status"] = "running"
            task_manager.save_state(state)

            buf = io.StringIO()
            with redirect_stdout(buf):
                task_manager.cmd_complete(argparse.Namespace(agent="a", summary="All tests pass."))
            state = task_manager.load_state()

        self.assertEqual(state["tasks"]["a"]["status"], "done")
        self.assertEqual(state["tasks"]["a"]["summary"], "All tests pass.")

    def test_cmd_complete_not_found_exits(self):
        with self._patch_env():
            with self.assertRaises(SystemExit) as exc:
                buf = io.StringIO()
                with redirect_stdout(buf):
                    task_manager.cmd_complete(argparse.Namespace(agent="z", summary=""))
            self.assertEqual(exc.exception.code, 1)

    # ---- cmd_fail ----

    def test_cmd_fail_marks_failed(self):
        with self._patch_env():
            self._write_spec("a", "alpha")
            state = task_manager.sync_state()
            state["tasks"]["a"]["status"] = "running"
            task_manager.save_state(state)

            buf = io.StringIO()
            with redirect_stdout(buf):
                task_manager.cmd_fail(argparse.Namespace(agent="a", reason="Build broke."))
            state = task_manager.load_state()

        self.assertEqual(state["tasks"]["a"]["status"], "failed")
        self.assertEqual(state["tasks"]["a"]["error"], "Build broke.")

    # ---- cmd_reset ----

    def test_cmd_reset_clears_state(self):
        with self._patch_env():
            self._write_spec("a", "alpha")
            state = task_manager.sync_state()
            state["tasks"]["a"]["status"] = "failed"
            state["tasks"]["a"]["error"] = "something"
            task_manager.save_state(state)

            buf = io.StringIO()
            with redirect_stdout(buf):
                task_manager.cmd_reset(argparse.Namespace(agent="a"))
            state = task_manager.load_state()

        self.assertIn(state["tasks"]["a"]["status"], ("ready", "pending"))
        self.assertEqual(state["tasks"]["a"]["error"], "")

    # ---- cmd_graph ----

    def test_cmd_graph_renders_output(self):
        with self._patch_env():
            self._write_spec("a", "alpha")
            self._write_spec("b", "beta", deps="Agent A")
            task_manager.sync_state()

            buf = io.StringIO()
            with redirect_stdout(buf):
                task_manager.cmd_graph(argparse.Namespace())
            output = buf.getvalue()

        self.assertIn("Dependency Graph", output)
        self.assertIn("Grp 0", output)
        self.assertIn("Grp 1", output)

    # ---- cmd_next ----

    def test_cmd_next_shows_progress(self):
        with self._patch_env():
            self._write_spec("a", "alpha")
            task_manager.sync_state()

            buf = io.StringIO()
            with redirect_stdout(buf):
                task_manager.cmd_next(argparse.Namespace())
            output = buf.getvalue()

        self.assertIn("Progress:", output)
        self.assertIn("Ready to launch", output)


class TaskManagerErrorPathTests(unittest.TestCase):
    """Tests for TaskManagerError raise sites — state corruption, missing
    plan, invalid agent ID, duplicate agent, missing spec, etc."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)
        self.agents_dir = self.root / "agents"
        self.agents_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir = self.root / "data"
        self.plans_dir = self.data_dir / "plans"
        self.plans_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.data_dir / "tasks.json"
        self.tracker_file = self.root / "custom-tracker.md"
        self.conventions_file = self.root / "CLAUDE.md"
        self.conventions_file.write_text("Error path test conventions.\n", encoding="utf-8")

    def tearDown(self):
        self._tmpdir.cleanup()

    def _patch_env(self, *, tracker: bool = False, commands: dict | None = None):
        cfg = {
            "project": {"name": "Error Test", "conventions": "CLAUDE.md"},
            "commands": commands
            or {
                "compile": "python -m py_compile {files}",
                "test": "python -m pytest tests/ -q",
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

    # ---- _validate_agent_id ----

    def test_invalid_agent_id_rejects_non_lowercase(self):
        for bad_id in ("ABC", "a1", "a-b", ""):
            with self.assertRaises(task_manager.TaskManagerError, msg=f"Expected error for '{bad_id}'"):
                task_manager._validate_agent_id(bad_id)

    # ---- _safe_resolve path traversal ----

    def test_safe_resolve_rejects_path_traversal(self):
        with self._patch_env():
            with self.assertRaises(task_manager.TaskManagerError) as exc:
                task_manager._safe_resolve("../../etc/passwd")
            self.assertIn("escapes", str(exc.exception).lower())

    # ---- load_state with corrupt state file ----

    def test_load_state_corrupt_json(self):
        with self._patch_env():
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            self.state_file.write_text("NOT VALID JSON {{{", encoding="utf-8")
            with self.assertRaises(task_manager.TaskManagerError) as exc:
                task_manager.load_state()
            self.assertIn("Cannot read state file", str(exc.exception))

    # ---- _resolve_plan_summary_for_runtime: no plans ----

    def test_resolve_plan_no_plans_available(self):
        with self._patch_env():
            with self.assertRaises(task_manager.TaskManagerError) as exc:
                task_manager._resolve_plan_summary_for_runtime()
            self.assertIn("No plans available", str(exc.exception))

    # ---- _resolve_plan_summary_for_runtime: plan not found ----

    def test_resolve_plan_not_found(self):
        with self._patch_env():
            # Create a minimal state with one plan so "no plans" doesn't trigger
            state = task_manager.load_state()
            state["plans"] = [{"id": "plan-001", "status": "draft", "plan_file": "", "plan_doc": ""}]
            task_manager.save_state(state)

            with self.assertRaises(task_manager.TaskManagerError) as exc:
                task_manager._resolve_plan_summary_for_runtime("plan-999")
            self.assertIn("not found", str(exc.exception))

    # ---- _load_plan_from_summary: no readable plan file ----

    def test_load_plan_no_readable_file(self):
        with self._patch_env():
            summary = {
                "id": "plan-missing",
                "plan_file": "data/plans/plan-missing.json",
                "status": "draft",
            }
            with self.assertRaises(task_manager.TaskManagerError) as exc:
                task_manager._load_plan_from_summary(summary)
            self.assertIn("no readable plan file", str(exc.exception))

    # ---- _load_plan_from_summary: corrupt plan JSON ----

    def test_load_plan_corrupt_json(self):
        with self._patch_env():
            plan_file = self.plans_dir / "plan-corrupt.json"
            plan_file.write_text("{INVALID", encoding="utf-8")
            summary = {
                "id": "plan-corrupt",
                "plan_file": "data/plans/plan-corrupt.json",
                "status": "draft",
            }
            with self.assertRaises(task_manager.TaskManagerError) as exc:
                task_manager._load_plan_from_summary(summary)
            self.assertIn("Cannot read plan file", str(exc.exception))

    # ---- sync_state: duplicate agent IDs in specs ----

    def test_sync_state_duplicate_agent_ids(self):
        with self._patch_env():
            # Create two specs with the same letter
            (self.agents_dir / "agent-a-first.md").write_text(
                textwrap.dedent(
                    """\
                    # Agent Task - First

                    **Scope:** First scope.

                    **Depends on:** (none)

                    **Output files:** `first.py`
                    """
                ),
                encoding="utf-8",
            )
            (self.agents_dir / "agent-a-second.md").write_text(
                textwrap.dedent(
                    """\
                    # Agent Task - Second

                    **Scope:** Second scope.

                    **Depends on:** (none)

                    **Output files:** `second.py`
                    """
                ),
                encoding="utf-8",
            )
            with self.assertRaises(task_manager.TaskManagerError) as exc:
                task_manager.sync_state()
            self.assertIn("Duplicate agent IDs", str(exc.exception))

    # ---- cmd_attach: agent not found ----

    def test_cmd_attach_agent_not_found(self):
        with self._patch_env():
            with self.assertRaises(task_manager.TaskManagerError) as exc:
                task_manager.cmd_attach(argparse.Namespace(agent="z", worktree_path="/tmp/wt", branch="feat-z", json=False))
            self.assertIn("not found", str(exc.exception))

    # ---- cmd_result: agent not found ----

    def test_cmd_result_agent_not_found(self):
        with self._patch_env():
            with self.assertRaises(task_manager.TaskManagerError) as exc:
                task_manager.cmd_result(
                    argparse.Namespace(
                        agent="z",
                        payload_json="",
                        payload='{"status": "done"}',
                        payload_file="",
                    )
                )
            self.assertIn("not found", str(exc.exception))

    def test_cmd_result_accepts_inline_positional_payload(self):
        with self._patch_env():
            state = task_manager.load_state()
            state["tasks"]["a"] = task_manager._new_task_record(
                "a",
                "alpha",
                spec_file="agents/agent-a-alpha.md",
                scope="Implement alpha.",
                status="running",
                deps=[],
                files=["example.py"],
                group=0,
            )
            task_manager.save_state(state)
            buf = io.StringIO()
            with redirect_stdout(buf):
                task_manager.cmd_result(
                    argparse.Namespace(
                        agent="a",
                        payload_json='{"id":"A","status":"done","summary":"Finished.","files_modified":["example.py"]}',
                        payload="",
                        payload_file="",
                        json=True,
                    )
                )
            payload = json.loads(buf.getvalue())

        self.assertEqual(payload["agent"], "a")
        self.assertEqual(payload["status"], "done")
        self.assertEqual(payload["agent_result"]["summary"], "Finished.")

    # ---- dependency cycle detection ----

    def test_dependency_cycle_detected(self):
        deps_map = {"a": ["b"], "b": ["a"]}
        with self.assertRaises(task_manager.TaskManagerError) as exc:
            task_manager._compute_dependency_depths(deps_map, "test cycle")
        self.assertIn("cycle", str(exc.exception).lower())


class GoPollTests(unittest.TestCase):
    """Tests for cmd_go --poll mode."""

    def test_go_poll_exits_on_terminal(self):
        """Poll loop exits after one iteration when status is terminal (verified)."""
        terminal_payload = {
            "status": "verified",
            "tasks": {},
        }
        call_count = 0

        def fake_go_runtime(args):
            nonlocal call_count
            call_count += 1
            return terminal_payload

        args = argparse.Namespace(plan_id=None, poll=5, json=False)
        buf = io.StringIO()
        with mock.patch.object(task_manager, "_go_runtime", fake_go_runtime):
            with mock.patch("task_manager.time") as mock_time:
                with redirect_stdout(buf):
                    task_manager.cmd_go(args)

        # Should only call _go_runtime once — terminal on first iteration
        self.assertEqual(call_count, 1)
        # Should NOT sleep because it terminated immediately
        mock_time.sleep.assert_not_called()
        output = buf.getvalue()
        self.assertIn("terminal status 'verified'", output)

    def test_go_poll_waits_on_non_terminal_then_exits(self):
        """Poll loop sleeps and retries when status is non-terminal, stops on terminal."""
        responses = [
            {"status": "awaiting_results", "tasks": {}},
            {"status": "verified", "tasks": {}},
        ]
        call_count = 0

        def fake_go_runtime(args):
            nonlocal call_count
            result = responses[min(call_count, len(responses) - 1)]
            call_count += 1
            return result

        args = argparse.Namespace(plan_id=None, poll=3, json=False)
        buf = io.StringIO()
        with mock.patch.object(task_manager, "_go_runtime", fake_go_runtime):
            with mock.patch("task_manager.time") as mock_time:
                with redirect_stdout(buf):
                    task_manager.cmd_go(args)

        self.assertEqual(call_count, 2)
        mock_time.sleep.assert_called_once_with(3)
        output = buf.getvalue()
        self.assertIn("waiting 3s", output)
        self.assertIn("terminal status 'verified'", output)

    def test_go_poll_treats_blocked_as_terminal(self):
        payload = {
            "status": "blocked",
            "blocked_agents": [{"id": "a", "name": "alpha", "status": "blocked"}],
        }
        call_count = 0

        def fake_go_runtime(args):
            nonlocal call_count
            call_count += 1
            return payload

        args = argparse.Namespace(plan_id=None, poll=4, json=False)
        buf = io.StringIO()
        with mock.patch.object(task_manager, "_go_runtime", fake_go_runtime):
            with mock.patch("task_manager.time") as mock_time:
                with redirect_stdout(buf):
                    task_manager.cmd_go(args)

        self.assertEqual(call_count, 1)
        mock_time.sleep.assert_not_called()
        self.assertIn("terminal status 'blocked'", buf.getvalue())

    def test_go_poll_json_emits_only_final_json(self):
        responses = [
            {"status": "awaiting_results", "tasks": {}},
            {"status": "blocked", "tasks": {}, "blocked_agents": [{"id": "a", "name": "alpha", "status": "blocked"}]},
        ]
        call_count = 0

        def fake_go_runtime(args):
            nonlocal call_count
            result = responses[min(call_count, len(responses) - 1)]
            call_count += 1
            return result

        args = argparse.Namespace(plan_id=None, poll=2, json=True)
        buf = io.StringIO()
        with mock.patch.object(task_manager, "_go_runtime", fake_go_runtime):
            with mock.patch("task_manager.time") as mock_time:
                with redirect_stdout(buf):
                    task_manager.cmd_go(args)

        self.assertEqual(call_count, 2)
        mock_time.sleep.assert_called_once_with(2)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["blocked_agents"][0]["id"], "a")


class PlanDiffTests(unittest.TestCase):
    """Tests for _plan_diff and cmd_plan_diff."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)
        self.agents_dir = self.root / "agents"
        self.agents_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir = self.root / "data"
        self.plans_dir = self.data_dir / "plans"
        self.plans_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.data_dir / "tasks.json"
        self.tracker_file = self.root / "custom-tracker.md"
        self.conventions_file = self.root / "CLAUDE.md"
        self.conventions_file.write_text("Diff test conventions.\n", encoding="utf-8")

    def tearDown(self):
        self._tmpdir.cleanup()

    def _patch_env(self):
        cfg = {
            "project": {"name": "Diff Test", "conventions": "CLAUDE.md"},
            "commands": {},
        }
        from contextlib import ExitStack

        stack = ExitStack()
        stack.enter_context(mock.patch.object(task_manager, "ROOT", self.root))
        stack.enter_context(mock.patch.object(task_manager, "AGENTS_DIR", self.agents_dir))
        stack.enter_context(mock.patch.object(task_manager, "STATE_FILE", self.state_file))
        stack.enter_context(mock.patch.object(task_manager, "PLANS_DIR", self.plans_dir))
        stack.enter_context(mock.patch.object(task_manager, "TRACKER_FILE", None))
        stack.enter_context(mock.patch.object(task_manager, "_tracker_str", ""))
        stack.enter_context(mock.patch.object(task_manager, "CONVENTIONS_FILE", "CLAUDE.md"))
        stack.enter_context(mock.patch.object(task_manager, "_CFG", cfg))
        return stack

    def _make_plan(self, plan_id: str, agents: list[dict]) -> dict:
        plan = {
            "id": plan_id,
            "created_at": "2026-03-14T00:00:00+00:00",
            "status": "approved",
            "description": "Diff test plan",
            "agents": agents,
            "groups": {},
            "conflicts": [],
            "integration_steps": [],
            "analysis_summary": {
                "total_files": 1,
                "total_lines": 10,
                "conflict_zones": [],
                "modules": {},
            },
            "plan_elements": task_manager._empty_plan_elements("Diff test plan"),
        }
        plan = task_manager._default_plan_fields(plan)
        return plan

    def test_plan_diff_detects_added_agent(self):
        """Agents in plan but not in state show up as 'added'."""
        with self._patch_env():
            plan = self._make_plan(
                "plan-diff-001",
                agents=[
                    {
                        "letter": "a",
                        "name": "alpha",
                        "scope": "Implement alpha.",
                        "deps": [],
                        "files": ["alpha.py"],
                        "group": 0,
                        "complexity": "low",
                    }
                ],
            )
            persisted = task_manager._persist_plan_artifacts(plan)
            state = task_manager.load_state()
            task_manager._upsert_plan_summary(state, persisted)
            # Deliberately leave state tasks empty — no tasks registered
            task_manager.save_state(state)

            diff = task_manager._plan_diff("plan-diff-001")

        self.assertEqual(diff["plan_id"], "plan-diff-001")
        added_ids = [entry["id"] for entry in diff["added"]]
        self.assertIn("a", added_ids)
        self.assertEqual(diff["removed"], [])

    def test_plan_diff_detects_removed_task(self):
        """Tasks in state but not in plan show up as 'removed'."""
        with self._patch_env():
            plan = self._make_plan("plan-diff-002", agents=[])
            persisted = task_manager._persist_plan_artifacts(plan)
            state = task_manager.load_state()
            task_manager._upsert_plan_summary(state, persisted)
            # Add a task to state that is not in the plan
            state["tasks"]["z"] = task_manager._new_task_record(
                "z",
                "zeta",
                spec_file="agents/agent-z-zeta.md",
                scope="Implement zeta.",
                status="pending",
                deps=[],
                files=[],
                group=0,
            )
            task_manager.save_state(state)

            diff = task_manager._plan_diff("plan-diff-002")

        removed_ids = [entry["id"] for entry in diff["removed"]]
        self.assertIn("z", removed_ids)
        self.assertEqual(diff["added"], [])

    def test_plan_diff_summary_format(self):
        """Summary string reports counts correctly."""
        with self._patch_env():
            plan = self._make_plan(
                "plan-diff-003",
                agents=[
                    {
                        "letter": "b",
                        "name": "beta",
                        "scope": "Implement beta.",
                        "deps": [],
                        "files": ["beta.py"],
                        "group": 0,
                        "complexity": "low",
                    }
                ],
            )
            persisted = task_manager._persist_plan_artifacts(plan)
            state = task_manager.load_state()
            task_manager._upsert_plan_summary(state, persisted)
            task_manager.save_state(state)

            diff = task_manager._plan_diff("plan-diff-003")

        self.assertIn("added", diff["summary"])
        self.assertIn("removed", diff["summary"])
        self.assertIn("changed", diff["summary"])


if __name__ == "__main__":
    unittest.main()
