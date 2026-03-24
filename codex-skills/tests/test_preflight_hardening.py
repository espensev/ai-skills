"""Tests for preflight hardening: --fix-safe remediation and command timeouts."""

from __future__ import annotations

import argparse
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
INSTALL_SKILLS_DIR = Path(".codex") / "skills"
sys.path.insert(0, str(ROOT / "scripts"))

import task_manager  # noqa: E402
from conftest import patch_env  # noqa: E402

# ---------------------------------------------------------------------------
# Helper: standard temp project layout
# ---------------------------------------------------------------------------


class _TempProject:
    """Create a temporary project directory with standard layout."""

    def __init__(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)
        self.agents_dir = self.root / "agents"
        self.agents_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir = self.root / "data"
        self.plans_dir = self.data_dir / "plans"
        self.plans_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.data_dir / "tasks.json"
        self.tracker_file = self.root / "custom-tracker.md"
        self.conventions_file = self.root / "AGENTS.md"
        self.skills_dir = self.root / INSTALL_SKILLS_DIR
        self.skills_dir.mkdir(parents=True, exist_ok=True)

    def cleanup(self):
        self._tmpdir.cleanup()


# ===========================================================================
# P0: --fix-safe remediation
# ===========================================================================


class TestPreflightSafeFixContract(unittest.TestCase):
    """Test the _preflight_safe_fix function directly."""

    def setUp(self):
        self._proj = _TempProject()

    def tearDown(self):
        self._proj.cleanup()

    def test_copies_planning_contract(self):
        # Place a planning-contract.md at the repo root (package source)
        source = self._proj.root / "planning-contract.md"
        source.write_text("# Planning Contract\nTest content.\n", encoding="utf-8")
        dest = self._proj.root / INSTALL_SKILLS_DIR / "planning-contract.md"
        self.assertFalse(dest.exists())

        with mock.patch.object(task_manager, "ROOT", self._proj.root):
            actions = task_manager._preflight_safe_fix()

        self.assertTrue(dest.exists())
        self.assertEqual(dest.read_text(encoding="utf-8"), "# Planning Contract\nTest content.\n")
        self.assertTrue(any("planning-contract" in a for a in actions))

    def test_skips_existing_planning_contract(self):
        source = self._proj.root / "planning-contract.md"
        source.write_text("source version\n", encoding="utf-8")
        dest = self._proj.root / INSTALL_SKILLS_DIR / "planning-contract.md"
        dest.write_text("existing version\n", encoding="utf-8")

        with mock.patch.object(task_manager, "ROOT", self._proj.root):
            actions = task_manager._preflight_safe_fix()

        # Should not overwrite existing file
        self.assertEqual(dest.read_text(encoding="utf-8"), "existing version\n")
        self.assertFalse(any("planning-contract" in a for a in actions))

    def test_skips_when_no_source_contract(self):
        # Pre-create AGENTS.md so conventions fix doesn't trigger
        self._proj.conventions_file.write_text("# Test\n", encoding="utf-8")

        with mock.patch.object(task_manager, "ROOT", self._proj.root), mock.patch.object(task_manager, "CONVENTIONS_FILE", "AGENTS.md"):
            actions = task_manager._preflight_safe_fix()

        dest = self._proj.root / INSTALL_SKILLS_DIR / "planning-contract.md"
        self.assertFalse(dest.exists())
        self.assertEqual(len(actions), 0)

    def test_creates_conventions_stub(self):
        with mock.patch.object(task_manager, "ROOT", self._proj.root), mock.patch.object(task_manager, "CONVENTIONS_FILE", "AGENTS.md"):
            # AGENTS.md doesn't exist, should create stub
            actions = task_manager._preflight_safe_fix()

        conventions = self._proj.root / "AGENTS.md"
        self.assertTrue(conventions.exists())
        self.assertIn("Conventions", conventions.read_text(encoding="utf-8"))
        self.assertTrue(any("conventions" in a.lower() for a in actions))

    def test_skips_conventions_if_exists(self):
        self._proj.conventions_file.write_text("# Existing\n", encoding="utf-8")

        with mock.patch.object(task_manager, "ROOT", self._proj.root), mock.patch.object(task_manager, "CONVENTIONS_FILE", "AGENTS.md"):
            actions = task_manager._preflight_safe_fix()

        self.assertEqual(self._proj.conventions_file.read_text(encoding="utf-8"), "# Existing\n")
        self.assertFalse(any("conventions" in a.lower() for a in actions))

    def test_skips_non_default_conventions(self):
        """Only creates stub for AGENTS.md, not arbitrary filenames."""
        with (
            mock.patch.object(task_manager, "ROOT", self._proj.root),
            mock.patch.object(task_manager, "CONVENTIONS_FILE", "docs/CONVENTIONS.md"),
        ):
            actions = task_manager._preflight_safe_fix()

        self.assertFalse((self._proj.root / "docs" / "CONVENTIONS.md").exists())
        self.assertFalse(any("conventions" in a.lower() for a in actions))

    def test_both_fixes_applied(self):
        source = self._proj.root / "planning-contract.md"
        source.write_text("# Contract\n", encoding="utf-8")

        with mock.patch.object(task_manager, "ROOT", self._proj.root), mock.patch.object(task_manager, "CONVENTIONS_FILE", "AGENTS.md"):
            actions = task_manager._preflight_safe_fix()

        self.assertEqual(len(actions), 2)


class TestPreflightFixSafeIntegration(unittest.TestCase):
    """Test --fix-safe through the CLI path."""

    def setUp(self):
        self._proj = _TempProject()

    def tearDown(self):
        self._proj.cleanup()

    def test_fix_safe_json_includes_actions(self):
        source = self._proj.root / "planning-contract.md"
        source.write_text("# Contract\n", encoding="utf-8")

        with patch_env(self._proj, project_name="Test") as stack:
            stack.enter_context(mock.patch.object(task_manager, "ROOT", self._proj.root))
            stack.enter_context(mock.patch.object(task_manager, "CONVENTIONS_FILE", "AGENTS.md"))
            # Create AGENTS.md so preflight doesn't error on it — we test fix_actions, not full ready
            self._proj.conventions_file.write_text("# Test\n", encoding="utf-8")

            buf = io.StringIO()
            with redirect_stdout(buf):
                task_manager.cmd_plan_preflight(argparse.Namespace(fix_safe=True, json=True))

        payload = json.loads(buf.getvalue())
        self.assertIn("fix_actions", payload)
        self.assertTrue(any("planning-contract" in a for a in payload["fix_actions"]))

    def test_no_fix_safe_no_actions(self):
        with patch_env(self._proj, project_name="Test") as stack:
            stack.enter_context(mock.patch.object(task_manager, "ROOT", self._proj.root))
            self._proj.conventions_file.write_text("# Test\n", encoding="utf-8")

            buf = io.StringIO()
            with redirect_stdout(buf):
                try:
                    task_manager.cmd_plan_preflight(argparse.Namespace(fix_safe=False, json=True))
                except SystemExit:
                    pass  # May fail preflight — that's OK, we just check no fix_actions

        payload = json.loads(buf.getvalue())
        self.assertNotIn("fix_actions", payload)


# ===========================================================================
# P4: Command timeouts
# ===========================================================================


class TestResolveCommandTimeout(unittest.TestCase):
    """Test _resolve_command_timeout reads config correctly."""

    def test_default_compile_timeout(self):
        with mock.patch.object(task_manager, "_CFG", {}):
            result = task_manager._resolve_command_timeout("compile")
        self.assertEqual(result, 120)

    def test_default_test_timeout(self):
        with mock.patch.object(task_manager, "_CFG", {}):
            result = task_manager._resolve_command_timeout("test")
        self.assertEqual(result, 600)

    def test_default_test_fast_timeout(self):
        with mock.patch.object(task_manager, "_CFG", {}):
            result = task_manager._resolve_command_timeout("test_fast")
        self.assertEqual(result, 300)

    def test_default_build_timeout(self):
        with mock.patch.object(task_manager, "_CFG", {}):
            result = task_manager._resolve_command_timeout("build")
        self.assertEqual(result, 300)

    def test_config_override(self):
        cfg = {"timeouts": {"test": 180}}
        with mock.patch.object(task_manager, "_CFG", cfg):
            result = task_manager._resolve_command_timeout("test")
        self.assertEqual(result, 180)

    def test_config_partial_override(self):
        """Unconfigured labels still get defaults."""
        cfg = {"timeouts": {"test": 90}}
        with mock.patch.object(task_manager, "_CFG", cfg):
            compile_t = task_manager._resolve_command_timeout("compile")
            test_t = task_manager._resolve_command_timeout("test")
        self.assertEqual(compile_t, 120)  # default
        self.assertEqual(test_t, 90)  # overridden

    def test_invalid_config_value_uses_default(self):
        cfg = {"timeouts": {"test": "not-a-number"}}
        with mock.patch.object(task_manager, "_CFG", cfg):
            result = task_manager._resolve_command_timeout("test")
        self.assertEqual(result, 600)  # fallback to default

    def test_zero_timeout_uses_default(self):
        cfg = {"timeouts": {"test": 0}}
        with mock.patch.object(task_manager, "_CFG", cfg):
            result = task_manager._resolve_command_timeout("test")
        self.assertEqual(result, 600)

    def test_negative_timeout_uses_default(self):
        cfg = {"timeouts": {"test": -10}}
        with mock.patch.object(task_manager, "_CFG", cfg):
            result = task_manager._resolve_command_timeout("test")
        self.assertEqual(result, 600)

    def test_unknown_label_uses_global_default(self):
        with mock.patch.object(task_manager, "_CFG", {}):
            result = task_manager._resolve_command_timeout("custom_command")
        self.assertEqual(result, 600)  # _RUNTIME_COMMAND_TIMEOUT


class TestRunRuntimeCommandTimeout(unittest.TestCase):
    """Test _run_runtime_command handles timeouts correctly."""

    def test_normal_command_includes_timeout_fields(self):
        with mock.patch.object(task_manager, "_CFG", {}):
            result = task_manager._run_runtime_command("test", "python -c \"print('ok')\"")
        self.assertIn("timed_out", result)
        self.assertFalse(result["timed_out"])
        self.assertIn("timeout_seconds", result)
        self.assertGreater(result["timeout_seconds"], 0)

    def test_timeout_returns_failure_entry(self):
        with (
            mock.patch.object(task_manager, "_CFG", {"timeouts": {"slow": 1}}),
            mock.patch("task_manager.subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="sleep", timeout=1)),
        ):
            result = task_manager._run_runtime_command("slow", "sleep 999")

        self.assertTrue(result["timed_out"])
        self.assertFalse(result["passed"])
        self.assertEqual(result["returncode"], -1)
        self.assertIn("timed out", result["stderr"])
        self.assertEqual(result["timeout_seconds"], 1)

    def test_uses_configured_timeout(self):
        cfg = {"timeouts": {"test": 42}}
        with mock.patch.object(task_manager, "_CFG", cfg), mock.patch("task_manager.subprocess.run") as mock_run:
            mock_run.return_value = mock.MagicMock(returncode=0, stdout="ok", stderr="")
            task_manager._run_runtime_command("test", "python -c \"print('ok')\"")

        # Verify subprocess.run was called with timeout=42
        call_kwargs = mock_run.call_args[1]
        self.assertEqual(call_kwargs["timeout"], 42)

    def test_missing_executable_returns_failure_entry(self):
        with (
            mock.patch.object(task_manager, "_CFG", {}),
            mock.patch("task_manager.subprocess.run", side_effect=FileNotFoundError("missing")),
        ):
            result = task_manager._run_runtime_command("test", "missing-command --flag")

        self.assertFalse(result["passed"])
        self.assertFalse(result["timed_out"])
        self.assertEqual(result["returncode"], -1)
        self.assertIn("missing", result["stderr"])


class TestDefaultCommandTimeouts(unittest.TestCase):
    """Verify the default timeout constants are sane."""

    def test_compile_shortest(self):
        self.assertEqual(task_manager._DEFAULT_COMMAND_TIMEOUTS["compile"], 120)

    def test_build_medium(self):
        self.assertEqual(task_manager._DEFAULT_COMMAND_TIMEOUTS["build"], 300)

    def test_test_full_longest(self):
        self.assertEqual(task_manager._DEFAULT_COMMAND_TIMEOUTS["test_full"], 600)

    def test_test_fast_shorter_than_test(self):
        self.assertLess(
            task_manager._DEFAULT_COMMAND_TIMEOUTS["test_fast"],
            task_manager._DEFAULT_COMMAND_TIMEOUTS["test"],
        )

    def test_all_positive(self):
        for label, value in task_manager._DEFAULT_COMMAND_TIMEOUTS.items():
            self.assertGreater(value, 0, f"{label} timeout must be positive")


if __name__ == "__main__":
    unittest.main()
