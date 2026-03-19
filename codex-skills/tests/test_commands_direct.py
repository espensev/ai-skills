# ruff: noqa: E402
"""Tests for commands.py — timeout handling, encoding, placeholder expansion."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from task_runtime.commands import (
    command_payload_entry,
    resolve_command_timeout,
    run_runtime_command,
)


class TestResolveCommandTimeout(unittest.TestCase):
    """Timeout resolution from config and defaults."""

    def test_default_timeout_for_unknown_label(self):
        result = resolve_command_timeout("custom_step", cfg={})
        self.assertEqual(result, 600)

    def test_default_timeout_for_test(self):
        result = resolve_command_timeout("test", cfg={})
        self.assertEqual(result, 600)

    def test_default_timeout_for_compile(self):
        result = resolve_command_timeout("compile", cfg={})
        self.assertEqual(result, 120)

    def test_config_override(self):
        result = resolve_command_timeout("compile", cfg={"timeouts": {"compile": 60}})
        self.assertEqual(result, 60)

    def test_invalid_config_timeout_falls_back(self):
        result = resolve_command_timeout("compile", cfg={"timeouts": {"compile": "not_a_number"}})
        self.assertEqual(result, 120)

    def test_zero_config_timeout_falls_back(self):
        result = resolve_command_timeout("compile", cfg={"timeouts": {"compile": 0}})
        self.assertEqual(result, 120)

    def test_negative_config_timeout_falls_back(self):
        result = resolve_command_timeout("compile", cfg={"timeouts": {"compile": -10}})
        self.assertEqual(result, 120)

    def test_non_dict_timeouts_ignored(self):
        result = resolve_command_timeout("compile", cfg={"timeouts": "invalid"})
        self.assertEqual(result, 120)


class TestCommandPayloadEntry(unittest.TestCase):
    """Payload entry construction."""

    def test_basic_success(self):
        class FakeResult:
            returncode = 0
            stdout = "ok"
            stderr = ""
        entry = command_payload_entry("test", "pytest", FakeResult())
        self.assertTrue(entry["passed"])
        self.assertEqual(entry["returncode"], 0)
        self.assertEqual(entry["label"], "test")

    def test_failure_entry(self):
        class FakeResult:
            returncode = 1
            stdout = ""
            stderr = "fail"
        entry = command_payload_entry("compile", "make", FakeResult())
        self.assertFalse(entry["passed"])
        self.assertEqual(entry["returncode"], 1)


class TestRunRuntimeCommand(unittest.TestCase):
    """Integration tests for run_runtime_command."""

    def test_simple_echo(self):
        result = run_runtime_command(
            "test",
            "echo hello",
            root=Path("."),
            cfg={},
        )
        self.assertTrue(result["passed"])
        self.assertIn("hello", result["stdout"])
        self.assertFalse(result["timed_out"])

    def test_failing_command(self):
        result = run_runtime_command(
            "test",
            "exit 1",
            root=Path("."),
            cfg={},
        )
        self.assertFalse(result["passed"])
        self.assertEqual(result["returncode"], 1)

    def test_timeout_produces_timed_out_entry(self):
        result = run_runtime_command(
            "slow",
            "sleep 10" if sys.platform != "win32" else "ping -n 11 127.0.0.1",
            root=Path("."),
            cfg={"timeouts": {"slow": 1}},
        )
        self.assertTrue(result["timed_out"])
        self.assertFalse(result["passed"])
        self.assertEqual(result["returncode"], -1)


if __name__ == "__main__":
    unittest.main()
