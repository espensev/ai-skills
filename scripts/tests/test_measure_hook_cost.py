"""Tests for scripts/measure_hook_cost.py.

Run from the repo root:
    python -m unittest scripts.tests.test_measure_hook_cost
or directly:
    python scripts/tests/test_measure_hook_cost.py

Both forms work: this file inserts the repo root onto sys.path itself, so
`import scripts.measure_hook_cost` resolves either way, and no
scripts/__init__.py is required for the `-m` form (implicit namespace
packages).
"""

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts import measure_hook_cost as mhc  # noqa: E402


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec) + "\n")


def _tool_use(name: str, **input_kwargs) -> dict:
    return {"type": "tool_use", "id": f"tu-{name}", "name": name, "input": input_kwargs}


class ClaudeFixtureMixin:
    """Builds one synthetic Claude project with a single sdk-cli session."""

    def _build_claude_root(self, root: Path) -> None:
        session = [
            {"type": "user", "entrypoint": "sdk-cli", "message": {"content": []}},
            {
                "type": "attachment",
                "attachment": {
                    "type": "hook_success",
                    "hookName": "SessionStart:startup",
                    "hookEvent": "SessionStart",
                },
                "timestamp": "2026-01-01T00:00:00Z",
            },
            {
                "type": "attachment",
                "attachment": {
                    "type": "hook_non_blocking_error",
                    "hookName": "UserPromptSubmit",
                    "hookEvent": "UserPromptSubmit",
                    "exitCode": 1,
                    "command": "some-hook-command",
                    "stderr": "boom",
                },
                "timestamp": "2026-01-01T00:00:01Z",
            },
            {
                "type": "attachment",
                "attachment": {
                    "type": "hook_additional_context",
                    "hookName": "Stop",
                    "hookEvent": "Stop",
                    "content": ["continue"],
                },
                "timestamp": "2026-01-01T00:00:00Z",
            },
            {
                "type": "attachment",
                "attachment": {
                    "type": "hook_success",
                    "hookName": "Stop",
                    "hookEvent": "Stop",
                    "content": "",
                },
                "timestamp": "2026-01-01T00:00:05Z",
            },
            {
                "type": "assistant",
                "message": {"content": [_tool_use("Skill", skill="update-config", args="x")]},
            },
            {
                "type": "assistant",
                "message": {
                    "content": [
                        _tool_use("Agent", subagent_type="research-scout", model="claude-x")
                    ]
                },
            },
            {
                "type": "assistant",
                "message": {"content": [_tool_use("Agent", subagent_type="builder")]},
            },
        ]
        _write_jsonl(root / "projects" / "proj1" / "session1.jsonl", session)


class CodexFixtureMixin:
    """Builds one interactive, one subagent, and one exec Codex rollout."""

    def _build_codex_root(self, root: Path) -> None:
        base_dir = root / "sessions" / "2026" / "01" / "01"

        def token_count(total, inp, cached, out):
            return {
                "type": "event_msg",
                "payload": {
                    "type": "token_count",
                    "info": {
                        "total_token_usage": {
                            "total_tokens": total,
                            "input_tokens": inp,
                            "cached_input_tokens": cached,
                            "output_tokens": out,
                        }
                    },
                },
                "timestamp": "2026-01-01T00:00:00Z",
            }

        def hook_prompt(ts):
            return {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "text", "text": '<hook_prompt hook_run_id="r1">go</hook_prompt>'}],
                },
                "timestamp": ts,
            }

        def task_complete(ts):
            return {"type": "event_msg", "payload": {"type": "task_complete"}, "timestamp": ts}

        # Interactive/main rollout: id == session_id, originator codex-tui.
        main_records = [
            {
                "type": "session_meta",
                "payload": {"id": "main-1", "session_id": "main-1", "originator": "codex-tui", "source": "cli"},
                "timestamp": "2026-01-01T00:00:00Z",
            },
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "developer",
                    "content": [{"type": "text", "text": "=== HANDOFF ===\nsome handoff text"}],
                },
                "timestamp": "2026-01-01T00:00:00Z",
            },
            token_count(100, 80, 20, 20),
            hook_prompt("2026-01-01T00:00:00Z"),
            token_count(250, 150, 50, 70),
            task_complete("2026-01-01T00:00:07Z"),
            {
                "type": "response_item",
                "payload": {
                    "type": "function_call",
                    "name": "shell",
                    "arguments": "cat skills/handoff/SKILL.md",
                },
                "timestamp": "2026-01-01T00:00:08Z",
            },
        ]
        _write_jsonl(base_dir / "rollout-2026-01-01T00-00-00-main-1.jsonl", main_records)

        # Subagent rollout: session_id (root) differs from its own id.
        sub_records = [
            {
                "type": "session_meta",
                "payload": {
                    "id": "sub-1",
                    "session_id": "main-1",
                    "originator": "codex-tui",
                    "source": {"subagent": {"thread_spawn": {"parent_thread_id": "main-1"}}},
                },
                "timestamp": "2026-01-01T00:01:00Z",
            }
        ]
        _write_jsonl(base_dir / "rollout-2026-01-01T00-01-00-sub-1.jsonl", sub_records)

        # Exec rollout: id == session_id, but originator/source say exec.
        exec_records = [
            {
                "type": "session_meta",
                "payload": {"id": "exec-1", "session_id": "exec-1", "originator": "codex_exec", "source": "exec"},
                "timestamp": "2026-01-01T00:02:00Z",
            }
        ]
        _write_jsonl(base_dir / "rollout-2026-01-01T00-02-00-exec-1.jsonl", exec_records)


class CollectClaudeTests(ClaudeFixtureMixin, unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self._build_claude_root(self.root)
        self.cutoff = 0.0  # accept all mtimes

    def test_sessions_by_entrypoint(self):
        result = mhc.collect_claude(self.root, self.cutoff)
        self.assertEqual(result["sessions_by_entrypoint"], {"sdk-cli": 1})

    def test_hook_outcomes(self):
        result = mhc.collect_claude(self.root, self.cutoff)
        outcomes = {(r["event"], r["type"]): r["count"] for r in result["hook_outcomes"]}
        self.assertEqual(outcomes[("SessionStart", "hook_success")], 1)
        self.assertEqual(outcomes[("UserPromptSubmit", "hook_non_blocking_error")], 1)
        self.assertEqual(outcomes[("Stop", "hook_additional_context")], 1)
        self.assertEqual(outcomes[("Stop", "hook_success")], 1)

    def test_non_success_top15(self):
        result = mhc.collect_claude(self.root, self.cutoff)
        rows = {(r["type"], r["exit_code"], r["command"]): r["count"] for r in result["non_success_top15"]}
        self.assertEqual(rows[("hook_non_blocking_error", 1, "some-hook-command")], 1)
        self.assertEqual(rows[("hook_additional_context", None, "")], 1)
        self.assertNotIn(("hook_success", None, ""), rows)

    def test_stop_continuation_duration(self):
        result = mhc.collect_claude(self.root, self.cutoff)
        stats = result["stop_continuations"]
        self.assertEqual(stats["n"], 1)
        self.assertEqual(stats["max"], 5.0)
        self.assertEqual(stats["p50"], 5.0)
        self.assertEqual(result["continuations_by_project"], {"proj1": 1})

    def test_skill_usage(self):
        result = mhc.collect_claude(self.root, self.cutoff)
        self.assertEqual(result["skill_usage"], {"update-config": 1})

    def test_agent_launches(self):
        result = mhc.collect_claude(self.root, self.cutoff)
        launches = {(r["subagent_type"], r["model"]): r["count"] for r in result["agent_launches"]}
        self.assertEqual(launches[("research-scout", "claude-x")], 1)
        self.assertEqual(launches[("builder", "(default)")], 1)

    def test_old_file_is_skipped(self):
        import os
        import time

        session_path = self.root / "projects" / "proj1" / "session1.jsonl"
        old_time = time.time() - 90 * 86400
        os.utime(session_path, (old_time, old_time))
        cutoff = time.time() - 30 * 86400
        result = mhc.collect_claude(self.root, cutoff)
        self.assertEqual(result["sessions_by_entrypoint"], {})

    def test_malformed_line_is_tolerated(self):
        session_path = self.root / "projects" / "proj1" / "session1.jsonl"
        with open(session_path, "a", encoding="utf-8") as fh:
            fh.write("{not valid json\n")
        result = mhc.collect_claude(self.root, self.cutoff)
        self.assertEqual(result["sessions_by_entrypoint"], {"sdk-cli": 1})

    def test_missing_root_returns_empty(self):
        result = mhc.collect_claude(self.root / "does-not-exist", self.cutoff)
        self.assertEqual(result, mhc._empty_claude_result())


class CollectCodexTests(CodexFixtureMixin, unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self._build_codex_root(self.root)
        self.cutoff = 0.0

    def test_sessions_by_kind(self):
        result = mhc.collect_codex(self.root, self.cutoff)
        self.assertEqual(
            result["sessions_by_kind"],
            {"interactive": 1, "subagent": 1, "exec": 1},
        )

    def test_stop_continuation_duration_and_tokens(self):
        result = mhc.collect_codex(self.root, self.cutoff)
        stats = result["stop_continuations"]
        self.assertEqual(stats["n"], 1)
        self.assertEqual(stats["max"], 7.0)
        # total=250-100=150; noncached_in=(150-50)-(80-20)=40; out=70-20=50
        self.assertEqual(stats["noncached_input_tokens_total"], 40)
        self.assertEqual(stats["output_tokens_total"], 50)
        self.assertEqual(result["continuations_by_kind"], {"interactive": 1})

    def test_injected_context(self):
        result = mhc.collect_codex(self.root, self.cutoff)
        handoff = result["injected_context"]["handoff"]
        self.assertEqual(handoff["count"], 1)
        self.assertEqual(handoff["bytes"], len("=== HANDOFF ===\nsome handoff text".encode("utf-8")))

    def test_skill_usage_from_tool_call(self):
        result = mhc.collect_codex(self.root, self.cutoff)
        self.assertEqual(result["skill_usage"], {"handoff": 1})

    def test_missing_root_returns_empty(self):
        result = mhc.collect_codex(self.root / "does-not-exist", self.cutoff)
        self.assertEqual(result, mhc._empty_codex_result())


class CliJsonTests(ClaudeFixtureMixin, CodexFixtureMixin, unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self._build_claude_root(self.root / "claude")
        self._build_codex_root(self.root / "codex")

    def test_json_output_matches_collect(self):
        expected_claude = mhc.collect_claude(self.root / "claude", 0.0)
        expected_codex = mhc.collect_codex(self.root / "codex", 0.0)
        proc = subprocess.run(
            [
                sys.executable,
                str(_REPO_ROOT / "scripts" / "measure_hook_cost.py"),
                "--days",
                "36500",
                "--provider",
                "both",
                "--claude-root",
                str(self.root / "claude"),
                "--codex-root",
                str(self.root / "codex"),
                "--json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["claude"]["sessions_by_entrypoint"], expected_claude["sessions_by_entrypoint"])
        self.assertEqual(payload["codex"]["sessions_by_kind"], expected_codex["sessions_by_kind"])

    def test_main_returns_zero_for_text_report(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            rc = mhc.main(
                [
                    "--days",
                    "36500",
                    "--provider",
                    "claude",
                    "--claude-root",
                    str(self.root / "claude"),
                ]
            )
        self.assertEqual(rc, 0)
        self.assertIn("sdk-cli", out.getvalue())


if __name__ == "__main__":
    unittest.main()
