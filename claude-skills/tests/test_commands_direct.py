# ruff: noqa: E402
"""Tests for commands.py — timeout handling, encoding, placeholder expansion."""

import json
import os
import subprocess
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
from task_runtime.specs import configured_runtime_commands


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


class TestCompileFileArgSafety(unittest.TestCase):
    """Ensure configured_runtime_commands validates and quotes {files} safely."""

    def test_simple_paths_preserved(self):
        cmds = configured_runtime_commands(
            {"compile": "py -m py_compile {files}"},
            files=["a.py", "pkg/b.py"],
        )
        self.assertEqual(cmds, [("compile", "py -m py_compile a.py pkg/b.py")])

    def test_spaces_are_quoted(self):
        cmds = configured_runtime_commands(
            {"compile": "py -m py_compile {files}"},
            files=["src/my file.py"],
        )
        self.assertEqual(len(cmds), 1)
        expected = '"src/my file.py"' if sys.platform == "win32" else "'src/my file.py'"
        self.assertEqual(cmds[0][1], f"py -m py_compile {expected}")

    def test_shell_metacharacters_rejected(self):
        for bad in ("a.py & calc.exe", "a.py; rm -rf /", "$(whoami).py", "%PATH%.py", "a.py\nwhoami"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    configured_runtime_commands(
                        {"compile": "py -m py_compile {files}"},
                        files=[bad],
                    )


class TestSafetyGuardHook(unittest.TestCase):
    """Verify UTF-8 stdin decoding under cp1252 and expanded fail-closed blocks."""

    HOOK = ROOT / "scripts" / "hooks" / "safety_guard.py"

    def _run_hook(self, payload: bytes) -> subprocess.CompletedProcess[bytes]:
        env = os.environ.copy()
        env["PYTHONUTF8"] = "0"
        env["PYTHONIOENCODING"] = "cp1252"
        return subprocess.run(
            [sys.executable, str(self.HOOK)],
            input=payload,
            capture_output=True,
            env=env,
            check=False,
        )

    def test_utf8_non_ascii_safe_bash_allowed_under_cp1252(self):
        payload = json.dumps(
            {"tool_name": "Bash", "tool_input": {"command": "echo caf\u00e9 \u2014 ok"}},
            ensure_ascii=False,
        ).encode("utf-8")
        res = self._run_hook(payload)
        self.assertEqual(res.returncode, 0, res.stderr)

    def test_utf8_non_ascii_dangerous_bash_blocked_under_cp1252(self):
        payload = json.dumps(
            {"tool_name": "Bash", "tool_input": {"command": "echo caf\u00e9 \u2014 && git push origin +main"}},
            ensure_ascii=False,
        ).encode("utf-8")
        res = self._run_hook(payload)
        self.assertEqual(res.returncode, 2)

    def test_multiedit_protected_key_and_apikeys_blocked(self):
        for path in ("certs/prod.pfx", "ops/apikeys/token.json"):
            with self.subTest(path=path):
                payload = json.dumps(
                    {"tool_name": "MultiEdit", "tool_input": {"file_path": path}},
                ).encode("utf-8")
                res = self._run_hook(payload)
                self.assertEqual(res.returncode, 2)


if __name__ == "__main__":
    unittest.main()
