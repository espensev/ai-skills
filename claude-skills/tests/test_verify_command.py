# ruff: noqa: E402
"""Tests for verify.py — profile handling, pass/fail logic, warning generation."""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from task_runtime.verify import cmd_verify, verify_runtime

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _base_plan(plan_id: str = "plan-001") -> dict:
    return {
        "id": plan_id,
        "status": "executing",
        "agents": [],
        "groups": {},
        "conflicts": [],
        "exit_criteria": ["All tests pass", "No regressions"],
    }


def _base_state(tasks: dict | None = None) -> dict:
    return {"tasks": tasks or {}}


def _done_task(task_id: str = "a", *, merge_status: str = "merged") -> dict:
    return {
        "id": task_id,
        "name": f"agent-{task_id}",
        "status": "done",
        "merge": {"status": merge_status, "conflicts": []},
    }


def _failed_task(task_id: str = "b") -> dict:
    return {
        "id": task_id,
        "name": f"agent-{task_id}",
        "status": "failed",
    }


def _pending_task(task_id: str = "c") -> dict:
    return {
        "id": task_id,
        "name": f"agent-{task_id}",
        "status": "pending",
    }


def _make_verify_kwargs(plan: dict, state: dict, **overrides) -> dict:
    """Build full kwargs for verify_runtime with sensible defaults."""
    return {
        "recover_runtime_fn": lambda **kw: {"recovered": True},
        "sync_state_fn": lambda: state,
        "resolve_plan_summary_for_runtime_fn": lambda pid: {"plan_id": pid},
        "load_plan_from_summary_fn": lambda summary: plan,
        "resolve_plan_for_verify_fn": lambda s: plan,
        "explain_verify_resolution_failure_fn": lambda s: "no plan found",
        "normalize_verify_profile_fn": lambda p: p or "default",
        "plan_owned_files_fn": lambda p, s: ["src/main.py"],
        "commands_cfg_fn": lambda: {
            "compile": "python -m py_compile {files}",
            "test": "python -m pytest tests/ -q",
        },
        "configured_runtime_commands_fn": lambda **kw: [
            ("compile", "python -m py_compile src/main.py"),
            ("test", "python -m pytest tests/ -q"),
        ],
        "placeholder_command_reason_fn": lambda cmd: "",
        "run_runtime_command_fn": lambda label, cmd: {"label": label, "command": cmd, "passed": True, "output": "ok"},
        "plan_exit_criteria_fn": lambda p: p.get("exit_criteria", []),
        "persist_execution_manifest_fn": lambda *a, **kw: None,
        "save_state_fn": lambda s: None,
        "now_iso_fn": lambda: "2026-03-18T00:00:00Z",
        **overrides,
    }


# ---------------------------------------------------------------------------
# verify_runtime unit tests
# ---------------------------------------------------------------------------


class TestVerifyAllPass(unittest.TestCase):
    """When all commands pass and all tasks are done+merged, verify passes."""

    def test_all_pass(self):
        plan = _base_plan()
        state = _base_state({"a": _done_task("a")})
        result = verify_runtime(plan_id="plan-001", **_make_verify_kwargs(plan, state))

        self.assertTrue(result["passed"])
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["plan_id"], "plan-001")
        self.assertEqual(len(result["commands"]), 2)
        self.assertEqual(len(result["failed_tasks"]), 0)
        self.assertEqual(len(result["incomplete_tasks"]), 0)
        self.assertEqual(len(result["merge_blockers"]), 0)


class TestVerifyCommandFailure(unittest.TestCase):
    """When a runtime command fails, verify fails."""

    def test_compile_failure(self):
        plan = _base_plan()
        state = _base_state({"a": _done_task("a")})

        def run_cmd(label, cmd):
            return {"label": label, "command": cmd, "passed": label != "compile", "output": "error" if label == "compile" else "ok"}

        kwargs = _make_verify_kwargs(plan, state, run_runtime_command_fn=run_cmd)
        result = verify_runtime(plan_id="plan-001", **kwargs)

        self.assertFalse(result["passed"])
        self.assertEqual(result["status"], "failed")

    def test_test_failure(self):
        plan = _base_plan()
        state = _base_state({"a": _done_task("a")})

        def run_cmd(label, cmd):
            return {"label": label, "command": cmd, "passed": label != "test", "output": "FAILED" if label == "test" else "ok"}

        kwargs = _make_verify_kwargs(plan, state, run_runtime_command_fn=run_cmd)
        result = verify_runtime(plan_id="plan-001", **kwargs)

        self.assertFalse(result["passed"])

    def test_all_commands_fail(self):
        plan = _base_plan()
        state = _base_state({"a": _done_task("a")})

        def run_cmd(label, cmd):
            return {"label": label, "command": cmd, "passed": False, "output": "error"}

        kwargs = _make_verify_kwargs(plan, state, run_runtime_command_fn=run_cmd)
        result = verify_runtime(plan_id="plan-001", **kwargs)

        self.assertFalse(result["passed"])
        self.assertEqual(len([c for c in result["commands"] if not c["passed"]]), 2)


class TestVerifyFailedTasks(unittest.TestCase):
    """Tasks in failed state should cause verify to fail."""

    def test_failed_task_causes_failure(self):
        plan = _base_plan()
        state = _base_state({"a": _done_task("a"), "b": _failed_task("b")})
        result = verify_runtime(plan_id="plan-001", **_make_verify_kwargs(plan, state))

        self.assertFalse(result["passed"])
        self.assertEqual(len(result["failed_tasks"]), 1)
        self.assertEqual(result["failed_tasks"][0]["id"], "b")


class TestVerifyIncompleteTasks(unittest.TestCase):
    """Tasks not yet done/failed should cause verify to fail."""

    def test_pending_task_causes_failure(self):
        plan = _base_plan()
        state = _base_state({"a": _done_task("a"), "c": _pending_task("c")})
        result = verify_runtime(plan_id="plan-001", **_make_verify_kwargs(plan, state))

        self.assertFalse(result["passed"])
        self.assertEqual(len(result["incomplete_tasks"]), 1)
        self.assertEqual(result["incomplete_tasks"][0]["id"], "c")
        self.assertEqual(result["incomplete_tasks"][0]["status"], "pending")

    def test_running_task_is_incomplete(self):
        plan = _base_plan()
        running = {"id": "d", "name": "agent-d", "status": "running"}
        state = _base_state({"d": running})
        result = verify_runtime(plan_id="plan-001", **_make_verify_kwargs(plan, state))

        self.assertFalse(result["passed"])
        self.assertEqual(len(result["incomplete_tasks"]), 1)


class TestVerifyMergeBlockers(unittest.TestCase):
    """Tasks done but not merged should block verification."""

    def test_unmerged_task_is_blocker(self):
        plan = _base_plan()
        task = _done_task("a", merge_status="pending")
        state = _base_state({"a": task})
        result = verify_runtime(plan_id="plan-001", **_make_verify_kwargs(plan, state))

        self.assertFalse(result["passed"])
        self.assertEqual(len(result["merge_blockers"]), 1)
        self.assertEqual(result["merge_blockers"][0]["id"], "a")

    def test_conflict_merge_is_blocker(self):
        plan = _base_plan()
        task = _done_task("a", merge_status="conflict")
        task["merge"]["conflicts"] = ["src/main.py"]
        state = _base_state({"a": task})
        result = verify_runtime(plan_id="plan-001", **_make_verify_kwargs(plan, state))

        self.assertFalse(result["passed"])
        self.assertEqual(len(result["merge_blockers"]), 1)

    def test_noop_merge_is_not_blocker(self):
        plan = _base_plan()
        task = _done_task("a", merge_status="noop")
        state = _base_state({"a": task})
        result = verify_runtime(plan_id="plan-001", **_make_verify_kwargs(plan, state))

        self.assertTrue(result["passed"])
        self.assertEqual(len(result["merge_blockers"]), 0)


class TestVerifyProfiles(unittest.TestCase):
    """Profile handling: fast, full, default fallbacks and warnings."""

    def test_fast_profile_warns_when_test_fast_missing(self):
        plan = _base_plan()
        state = _base_state({"a": _done_task("a")})
        kwargs = _make_verify_kwargs(
            plan, state,
            normalize_verify_profile_fn=lambda p: "fast",
            commands_cfg_fn=lambda: {"test": "pytest", "compile": ""},
        )
        result = verify_runtime(plan_id="plan-001", **kwargs)

        fast_warnings = [w for w in result["warnings"] if "test_fast" in w]
        self.assertEqual(len(fast_warnings), 1)

    def test_full_profile_warns_when_test_full_missing(self):
        plan = _base_plan()
        state = _base_state({"a": _done_task("a")})
        kwargs = _make_verify_kwargs(
            plan, state,
            normalize_verify_profile_fn=lambda p: "full",
            commands_cfg_fn=lambda: {"test": "pytest", "compile": ""},
        )
        result = verify_runtime(plan_id="plan-001", **kwargs)

        full_warnings = [w for w in result["warnings"] if "test_full" in w]
        self.assertEqual(len(full_warnings), 1)

    def test_default_profile_no_fallback_warnings(self):
        plan = _base_plan()
        state = _base_state({"a": _done_task("a")})
        result = verify_runtime(plan_id="plan-001", **_make_verify_kwargs(plan, state))

        fallback_warnings = [w for w in result["warnings"] if "test_fast" in w or "test_full" in w]
        self.assertEqual(len(fallback_warnings), 0)

    def test_fast_profile_no_warning_when_test_fast_configured(self):
        plan = _base_plan()
        state = _base_state({"a": _done_task("a")})
        kwargs = _make_verify_kwargs(
            plan, state,
            normalize_verify_profile_fn=lambda p: "fast",
            commands_cfg_fn=lambda: {"test": "pytest", "test_fast": "pytest -x", "compile": ""},
        )
        result = verify_runtime(plan_id="plan-001", **kwargs)

        fast_warnings = [w for w in result["warnings"] if "test_fast" in w]
        self.assertEqual(len(fast_warnings), 0)


class TestVerifyCompileFilesWarning(unittest.TestCase):
    """Compile command with {files} placeholder and no plan files."""

    def test_warns_when_compile_uses_files_but_plan_has_none(self):
        plan = _base_plan()
        state = _base_state({"a": _done_task("a")})
        kwargs = _make_verify_kwargs(
            plan, state,
            plan_owned_files_fn=lambda p, s: [],
            commands_cfg_fn=lambda: {"compile": "python -m py_compile {files}", "test": "pytest"},
        )
        result = verify_runtime(plan_id="plan-001", **kwargs)

        file_warnings = [w for w in result["warnings"] if "{files}" in w]
        self.assertEqual(len(file_warnings), 1)

    def test_no_warning_when_compile_has_no_placeholder(self):
        plan = _base_plan()
        state = _base_state({"a": _done_task("a")})
        kwargs = _make_verify_kwargs(
            plan, state,
            plan_owned_files_fn=lambda p, s: [],
            commands_cfg_fn=lambda: {"compile": "make build", "test": "pytest"},
        )
        result = verify_runtime(plan_id="plan-001", **kwargs)

        file_warnings = [w for w in result["warnings"] if "{files}" in w]
        self.assertEqual(len(file_warnings), 0)


class TestVerifyPlanResolution(unittest.TestCase):
    """Plan resolution: explicit ID vs auto-resolve from state."""

    def test_explicit_plan_id(self):
        plan = _base_plan("plan-042")
        state = _base_state({"a": _done_task("a")})
        result = verify_runtime(plan_id="plan-042", **_make_verify_kwargs(plan, state))

        self.assertEqual(result["plan_id"], "plan-042")

    def test_auto_resolve_when_no_plan_id(self):
        plan = _base_plan("plan-auto")
        state = _base_state({"a": _done_task("a")})
        result = verify_runtime(**_make_verify_kwargs(plan, state))

        self.assertEqual(result["plan_id"], "plan-auto")

    def test_raises_when_no_plan_found(self):
        state = _base_state({})
        kwargs = _make_verify_kwargs(_base_plan(), state, resolve_plan_for_verify_fn=lambda s: None)
        with self.assertRaises(RuntimeError) as ctx:
            verify_runtime(**kwargs)
        self.assertIn("No valid executable plan", str(ctx.exception))


class TestVerifyExitCriteria(unittest.TestCase):
    """Exit criteria from plan are included in result."""

    def test_criteria_from_plan(self):
        plan = _base_plan()
        state = _base_state({"a": _done_task("a")})
        result = verify_runtime(plan_id="plan-001", **_make_verify_kwargs(plan, state))

        self.assertEqual(len(result["criteria"]), 2)
        self.assertTrue(all(c["passed"] for c in result["criteria"]))

    def test_criteria_marked_failed_on_failure(self):
        plan = _base_plan()
        state = _base_state({"a": _done_task("a"), "b": _failed_task("b")})
        result = verify_runtime(plan_id="plan-001", **_make_verify_kwargs(plan, state))

        self.assertFalse(any(c["passed"] for c in result["criteria"]))

    def test_empty_criteria(self):
        plan = _base_plan()
        plan["exit_criteria"] = []
        state = _base_state({"a": _done_task("a")})
        result = verify_runtime(plan_id="plan-001", **_make_verify_kwargs(plan, state))

        self.assertEqual(result["criteria"], [])
        self.assertTrue(result["passed"])


class TestVerifyPlaceholderCommands(unittest.TestCase):
    """Placeholder commands are skipped with a warning."""

    def test_placeholder_skipped(self):
        plan = _base_plan()
        state = _base_state({"a": _done_task("a")})
        kwargs = _make_verify_kwargs(
            plan, state,
            placeholder_command_reason_fn=lambda cmd: "is a placeholder" if "py_compile" in cmd else "",
        )
        result = verify_runtime(plan_id="plan-001", **kwargs)

        skip_warnings = [w for w in result["warnings"] if "placeholder" in w.lower() or "Skipped" in w]
        self.assertEqual(len(skip_warnings), 1)
        # Only one command actually ran (the non-placeholder one)
        self.assertEqual(len(result["commands"]), 1)


class TestVerifyEmptyCommands(unittest.TestCase):
    """Empty command strings are filtered out."""

    def test_empty_commands_skipped(self):
        plan = _base_plan()
        state = _base_state({"a": _done_task("a")})
        kwargs = _make_verify_kwargs(
            plan, state,
            configured_runtime_commands_fn=lambda **kw: [("compile", ""), ("test", "pytest")],
        )
        result = verify_runtime(plan_id="plan-001", **kwargs)

        self.assertEqual(len(result["commands"]), 1)
        self.assertEqual(result["commands"][0]["label"], "test")


class TestVerifyManifestPersistence(unittest.TestCase):
    """Execution manifest is persisted with correct status."""

    def test_passed_persists_verified(self):
        plan = _base_plan()
        state = _base_state({"a": _done_task("a")})
        persisted = {}

        def persist_fn(s, *, plan_id, status, verify):
            persisted.update({"plan_id": plan_id, "status": status, "verify": verify})

        kwargs = _make_verify_kwargs(plan, state, persist_execution_manifest_fn=persist_fn)
        verify_runtime(plan_id="plan-001", **kwargs)

        self.assertEqual(persisted["status"], "verified")
        self.assertTrue(persisted["verify"]["passed"])

    def test_failed_persists_verification_failed(self):
        plan = _base_plan()
        state = _base_state({"a": _done_task("a"), "b": _failed_task("b")})
        persisted = {}

        def persist_fn(s, *, plan_id, status, verify):
            persisted.update({"plan_id": plan_id, "status": status, "verify": verify})

        kwargs = _make_verify_kwargs(plan, state, persist_execution_manifest_fn=persist_fn)
        verify_runtime(plan_id="plan-001", **kwargs)

        self.assertEqual(persisted["status"], "verification_failed")
        self.assertFalse(persisted["verify"]["passed"])


# ---------------------------------------------------------------------------
# cmd_verify tests
# ---------------------------------------------------------------------------


class TestCmdVerify(unittest.TestCase):
    """cmd_verify CLI wrapper: JSON output and exit code."""

    def test_json_output(self):
        payload = {"plan_id": "plan-001", "passed": True, "commands": [], "warnings": []}
        emitted = {}

        def emit(data):
            emitted.update(data)

        args = MagicMock(plan_id="plan-001", profile="default", json=True)
        cmd_verify(args, verify_runtime_fn=lambda *a, **kw: payload, emit_json_fn=emit)

        self.assertEqual(emitted["plan_id"], "plan-001")

    def test_exit_code_on_failure(self):
        payload = {"plan_id": "plan-001", "passed": False, "commands": [], "warnings": []}
        args = MagicMock(plan_id="plan-001", profile="default", json=False)

        with self.assertRaises(SystemExit) as ctx:
            cmd_verify(args, verify_runtime_fn=lambda *a, **kw: payload, emit_json_fn=lambda d: None)
        self.assertEqual(ctx.exception.code, 1)

    def test_no_exit_on_success(self):
        payload = {"plan_id": "plan-001", "passed": True, "commands": [], "warnings": []}
        args = MagicMock(plan_id="plan-001", profile="default", json=False)

        # Should not raise
        cmd_verify(args, verify_runtime_fn=lambda *a, **kw: payload, emit_json_fn=lambda d: None)


class TestVerifyRecoveryIncluded(unittest.TestCase):
    """Recovery data is included in result."""

    def test_recovery_in_result(self):
        plan = _base_plan()
        state = _base_state({"a": _done_task("a")})
        recovery_data = {"recovered": True, "pruned": 0}
        kwargs = _make_verify_kwargs(plan, state, recover_runtime_fn=lambda **kw: recovery_data)
        result = verify_runtime(plan_id="plan-001", **kwargs)

        self.assertEqual(result["recovery"], recovery_data)


if __name__ == "__main__":
    unittest.main()
