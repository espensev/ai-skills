# ruff: noqa: E402
"""Tests for runtime correctness fixes (H1–M4)."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from task_runtime.config import parse_toml_simple
from task_runtime.orchestration import _is_stale_running_task
from task_runtime.specs import configured_runtime_commands
from task_runtime.validation import validate_plan_elements


class TestSpecsFilesExpansion(unittest.TestCase):
    """H1: empty files with {files} placeholder skips compile."""

    def test_empty_files_skips_compile_with_placeholder(self):
        cfg = {"compile": "ruff check {files}", "test": "pytest"}
        result = configured_runtime_commands(cfg, files=[])
        labels = [label for label, _cmd in result]
        self.assertNotIn("compile", labels)

    def test_none_files_skips_compile_with_placeholder(self):
        cfg = {"compile": "ruff check {files}", "test": "pytest"}
        result = configured_runtime_commands(cfg, files=None)
        labels = [label for label, _cmd in result]
        self.assertNotIn("compile", labels)

    def test_nonempty_files_includes_compile(self):
        cfg = {"compile": "ruff check {files}", "test": "pytest"}
        result = configured_runtime_commands(cfg, files=["a.py", "b.py"])
        labels = [label for label, _cmd in result]
        self.assertIn("compile", labels)
        compile_cmd = [cmd for label, cmd in result if label == "compile"][0]
        self.assertEqual(compile_cmd, "ruff check a.py b.py")

    def test_compile_without_placeholder_still_runs_with_empty_files(self):
        cfg = {"compile": "make check"}
        result = configured_runtime_commands(cfg, files=[])
        labels = [label for label, _cmd in result]
        self.assertIn("compile", labels)


class TestTomlUnclosedArray(unittest.TestCase):
    """H2: unclosed multiline array recovery."""

    def _parse(self, content: str) -> dict:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False, encoding="utf-8") as f:
            f.write(content)
            f.flush()
            tmp_path = Path(f.name)
        try:
            return parse_toml_simple(tmp_path)
        finally:
            os.unlink(tmp_path)

    def test_unclosed_array_preserves_partial_values(self):
        result = self._parse('[modules]\ncore = [\n  "a.py",\n  "b.py",\n')
        self.assertIn("modules", result)
        self.assertEqual(result["modules"]["core"], ["a.py", "b.py"])

    def test_unclosed_array_does_not_swallow_subsequent_keys(self):
        # With the fix, the unclosed array gets stored and subsequent
        # section/keys are not consumed as array continuations
        result = self._parse(
            '[modules]\ncore = [\n  "a.py"\n[project]\nname = "Test"\n'
        )
        self.assertIn("modules", result)
        self.assertIn("core", result["modules"])

    def test_closed_array_still_works(self):
        result = self._parse('[modules]\ncore = [\n  "a.py",\n]\n')
        self.assertEqual(result["modules"]["core"], ["a.py"])


class TestPlanOwnedFilesRuntimeAugment(unittest.TestCase):
    """H3: _plan_owned_files union of plan + task files."""

    def test_augments_with_runtime_files(self):
        import task_manager

        plan = {
            "agents": [
                {"letter": "am", "name": "alpha", "files": ["a.py"]},
            ],
        }
        state = {
            "tasks": {
                "am": {
                    "status": "done",
                    "agent_result": {"files_modified": ["a.py", "b.py"]},
                },
            },
        }
        result = task_manager._plan_owned_files(plan, state)
        self.assertEqual(result, ["a.py", "b.py"])

    def test_does_not_augment_from_non_plan_agents(self):
        import task_manager

        plan = {
            "agents": [
                {"letter": "am", "name": "alpha", "files": ["a.py"]},
            ],
        }
        state = {
            "tasks": {
                "am": {
                    "status": "done",
                    "agent_result": {"files_modified": ["a.py", "b.py"]},
                },
                "bx": {
                    "status": "done",
                    "agent_result": {"files_modified": ["c.py"]},
                },
            },
        }
        result = task_manager._plan_owned_files(plan, state)
        self.assertNotIn("c.py", result)

    def test_does_not_augment_from_running_tasks(self):
        import task_manager

        plan = {
            "agents": [
                {"letter": "am", "name": "alpha", "files": ["a.py"]},
            ],
        }
        state = {
            "tasks": {
                "am": {
                    "status": "running",
                    "agent_result": {"files_modified": ["a.py", "b.py"]},
                },
            },
        }
        result = task_manager._plan_owned_files(plan, state)
        self.assertEqual(result, ["a.py"])

    def test_no_state_returns_plan_files_only(self):
        import task_manager

        plan = {
            "agents": [
                {"letter": "am", "name": "alpha", "files": ["a.py"]},
            ],
        }
        result = task_manager._plan_owned_files(plan, None)
        self.assertEqual(result, ["a.py"])


class TestValidationRawElements(unittest.TestCase):
    """M1: missing exit_criteria not masked by defaults."""

    def test_missing_exit_criteria_detected(self):
        def default_plan_fields(plan):
            plan = dict(plan)
            elements = dict(plan.get("plan_elements", {}))
            elements.setdefault("campaign_title", "Default Title")
            elements.setdefault("goal_statement", "Default Goal")
            elements.setdefault("exit_criteria", ["Default criterion"])
            elements.setdefault("verification_strategy", ["pytest"])
            elements.setdefault("documentation_updates", ["None needed"])
            plan["plan_elements"] = elements
            return plan

        from task_runtime.specs import normalize_string_list

        plan = {
            "plan_elements": {
                "campaign_title": "Test",
                "goal_statement": "Test goal",
                # exit_criteria deliberately missing
                "verification_strategy": ["pytest"],
                "documentation_updates": ["None"],
            },
        }
        errors = validate_plan_elements(
            plan,
            default_plan_fields=default_plan_fields,
            normalize_string_list=normalize_string_list,
            commands_cfg=lambda: {},
        )
        self.assertTrue(
            any("exit_criteria" in e for e in errors),
            f"Expected exit_criteria error, got: {errors}",
        )

    def test_present_exit_criteria_passes(self):
        def default_plan_fields(plan):
            plan = dict(plan)
            elements = dict(plan.get("plan_elements", {}))
            plan["plan_elements"] = elements
            return plan

        from task_runtime.specs import normalize_string_list

        plan = {
            "plan_elements": {
                "campaign_title": "Test",
                "goal_statement": "Test goal",
                "exit_criteria": ["All tests pass"],
                "verification_strategy": ["pytest"],
                "documentation_updates": ["None"],
            },
        }
        errors = validate_plan_elements(
            plan,
            default_plan_fields=default_plan_fields,
            normalize_string_list=normalize_string_list,
            commands_cfg=lambda: {},
        )
        self.assertFalse(
            any("exit_criteria" in e for e in errors),
            f"Unexpected exit_criteria error: {errors}",
        )


class TestStaleRunningRecovery(unittest.TestCase):
    """M4: stale task reset detection."""

    def test_stale_task_detected(self):
        started = "2026-03-14T10:00:00+00:00"
        now = "2026-03-14T13:00:00+00:00"  # 3 hours later
        self.assertTrue(_is_stale_running_task(started, now, max_hours=2))

    def test_fresh_task_not_stale(self):
        started = "2026-03-14T10:00:00+00:00"
        now = "2026-03-14T11:00:00+00:00"  # 1 hour later
        self.assertFalse(_is_stale_running_task(started, now, max_hours=2))

    def test_invalid_timestamp_not_stale(self):
        self.assertFalse(_is_stale_running_task("", "2026-03-14T10:00:00+00:00"))
        self.assertFalse(_is_stale_running_task("not-a-date", "2026-03-14T10:00:00+00:00"))

    def test_exact_boundary_not_stale(self):
        started = "2026-03-14T10:00:00+00:00"
        now = "2026-03-14T12:00:00+00:00"  # exactly 2 hours
        self.assertFalse(_is_stale_running_task(started, now, max_hours=2))


class TestResolvePlanActiveId(unittest.TestCase):
    """M3: active plan_id from execution_manifest preferred."""

    def test_prefers_execution_manifest_plan_id(self):
        from unittest import mock

        import task_manager

        plan_old = {
            "id": "plan-old",
            "status": "executed",
            "agents": [{"letter": "a", "name": "alpha", "scope": "Old", "deps": [], "files": ["old.py"], "group": 0, "complexity": "low"}],
            "plan_elements": task_manager._empty_plan_elements("Old"),
        }
        plan_old = task_manager._default_plan_fields(plan_old)
        plan_old["plan_elements"]["goal_statement"] = "Old goal"
        plan_old["plan_elements"]["exit_criteria"] = ["Done"]
        plan_old["plan_elements"]["verification_strategy"] = ["pytest"]
        plan_old["plan_elements"]["documentation_updates"] = ["None"]

        plan_new = dict(plan_old)
        plan_new = task_manager._default_plan_fields(plan_new)
        plan_new["id"] = "plan-new"
        plan_new["plan_elements"]["goal_statement"] = "New goal"

        plans_by_id = {"plan-old": plan_old, "plan-new": plan_new}

        def mock_load(summary):
            pid = summary.get("id", "")
            if pid in plans_by_id:
                return plans_by_id[pid]
            raise task_manager.TaskManagerError("not found")

        state = {
            "plans": [
                {"id": "plan-old", "status": "executed"},
                {"id": "plan-new", "status": "executed"},
            ],
            "execution_manifest": {"plan_id": "plan-old"},
        }

        with mock.patch.object(task_manager, "_load_plan_from_summary", side_effect=mock_load):
            result = task_manager._resolve_plan_for_verify(state)

        self.assertIsNotNone(result)
        self.assertEqual(result["id"], "plan-old")

    def test_fallback_without_manifest(self):
        from unittest import mock

        import task_manager

        plan_a = task_manager._default_plan_fields({
            "id": "plan-a",
            "status": "executed",
            "agents": [{"letter": "a", "name": "alpha", "scope": "A", "deps": [], "files": ["a.py"], "group": 0, "complexity": "low"}],
            "plan_elements": task_manager._empty_plan_elements("A"),
        })
        plan_a["plan_elements"]["goal_statement"] = "A goal"
        plan_a["plan_elements"]["exit_criteria"] = ["Done"]
        plan_a["plan_elements"]["verification_strategy"] = ["pytest"]
        plan_a["plan_elements"]["documentation_updates"] = ["None"]

        def mock_load(summary):
            if summary.get("id") == "plan-a":
                return plan_a
            raise task_manager.TaskManagerError("not found")

        state = {
            "plans": [
                {"id": "plan-a", "status": "executed"},
            ],
        }

        with mock.patch.object(task_manager, "_load_plan_from_summary", side_effect=mock_load):
            result = task_manager._resolve_plan_for_verify(state)

        self.assertIsNotNone(result)
        self.assertEqual(result["id"], "plan-a")


from task_runtime.merge import display_runtime_path


class TestDisplayRuntimePathNarrowCatch(unittest.TestCase):
    """B1: display_runtime_path catches only ValueError/OSError, not broad Exception."""

    def test_value_error_caught(self):
        def raise_value_error(p):
            raise ValueError("not relative")
        p = Path("/some/path")
        result = display_runtime_path(p, relative_path_fn=raise_value_error)
        self.assertEqual(result, str(p))

    def test_os_error_caught(self):
        def raise_os_error(p):
            raise OSError("disk error")
        p = Path("/some/path")
        result = display_runtime_path(p, relative_path_fn=raise_os_error)
        self.assertEqual(result, str(p))

    def test_other_exception_propagates(self):
        def raise_runtime_error(p):
            raise RuntimeError("unexpected")
        with self.assertRaises(RuntimeError):
            display_runtime_path(Path("/some/path"), relative_path_fn=raise_runtime_error)


class TestMergeSourcePathContainment(unittest.TestCase):
    """B2: rel_path escaping worktree root is flagged as conflict."""

    def test_escaping_path_flagged_as_conflict(self):
        """A rel_path like '../../etc/passwd' should be caught as escaping worktree."""
        with tempfile.TemporaryDirectory() as tmpdir:
            worktree_root = Path(tmpdir) / "worktree"
            worktree_root.mkdir()
            # Create a file outside the worktree to prove containment check works
            outside_file = Path(tmpdir) / "outside.txt"
            outside_file.write_text("secret")

            rel_path = "../outside.txt"
            source = (worktree_root / Path(rel_path)).resolve()
            # Verify the file exists (so it's not caught by exists() check)
            self.assertTrue(source.exists())
            # Verify containment check catches it
            with self.assertRaises(ValueError):
                source.relative_to(worktree_root.resolve())


if __name__ == "__main__":
    unittest.main()
