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
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timedelta, timezone

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
                "timestamp": "2026-01-01T00:00:06Z",
                "message": {"content": [_tool_use("Skill", skill="update-config", args="x")]},
            },
            {
                "type": "assistant",
                "timestamp": "2026-01-01T00:00:07Z",
                "message": {
                    "content": [
                        _tool_use("Agent", subagent_type="research-scout", model="claude-x")
                    ]
                },
            },
            {
                "type": "assistant",
                "timestamp": "2026-01-01T00:00:08Z",
                "message": {"content": [_tool_use("Agent", subagent_type="builder")]},
            },
        ]
        _write_jsonl(root / "projects" / "proj1" / "session1.jsonl", session)


class CodexFixtureMixin:
    """Builds one interactive, one subagent, and one exec Codex rollout."""

    MEMORY_TEXT = "## Memory\r\n\r\nYou have access to a memory folder."
    SKILLS_TEXT = "<skills_instructions>\n## Skills\n- handoff: resume work\n</skills_instructions>"
    PERMISSIONS_TEXT = "<permissions instructions>\nsandbox rules\n</permissions instructions>"

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

        main_meta = {
            "type": "session_meta",
            "payload": {"id": "main-1", "session_id": "main-1", "originator": "codex-tui", "source": "cli"},
            "timestamp": "2026-01-01T00:00:00Z",
        }

        # Interactive/main rollout: id == session_id, originator codex-tui.
        main_records = [
            main_meta,
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "developer",
                    "content": [{"type": "text", "text": "=== HANDOFF ===\nsome handoff text"}],
                },
                "timestamp": "2026-01-01T00:00:00Z",
            },
            # Real Codex startup message: memory, skills catalog, and other
            # instruction blocks arrive as separate items of one message.
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "developer",
                    "content": [
                        {"type": "input_text", "text": self.MEMORY_TEXT},
                        {"type": "input_text", "text": self.SKILLS_TEXT},
                        {"type": "input_text", "text": self.PERMISSIONS_TEXT},
                    ],
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

        # Subagent rollout: session_id (root) differs from its own id. Forked
        # subagents then carry a copy of the parent's session_meta.
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
            },
            main_meta,
            hook_prompt("2026-01-01T00:01:00Z"),
            task_complete("2026-01-01T00:01:03Z"),
        ]
        _write_jsonl(base_dir / "rollout-2026-01-01T00-01-00-sub-1.jsonl", sub_records)

        # Exec rollout: id == session_id, but originator/source say exec.
        exec_records = [
            {
                "type": "session_meta",
                "payload": {"id": "exec-1", "session_id": "exec-1", "originator": "codex_exec", "source": "exec"},
                "timestamp": "2026-01-01T00:02:00Z",
            },
            {"type": "event_msg", "payload": {"type": "task_started"},
             "timestamp": "2026-01-01T00:02:01Z"},
        ]
        _write_jsonl(base_dir / "rollout-2026-01-01T00-02-00-exec-1.jsonl", exec_records)


class CollectClaudeTests(ClaudeFixtureMixin, unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self._build_claude_root(self.root)
        self.cutoff = 0.0  # accept all valid event timestamps

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

    def test_old_events_are_skipped_even_in_recently_modified_file(self):
        session_path = self.root / "projects" / "proj1" / "session1.jsonl"
        os.utime(session_path, (2_000_000_000, 2_000_000_000))
        cutoff = datetime.fromisoformat("2026-01-02T00:00:00+00:00").timestamp()
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
        self.assertEqual(stats["n"], 2)
        self.assertEqual(stats["max"], 7.0)
        # main: total=250-100=150; noncached_in=(150-50)-(80-20)=40; out=70-20=50
        # sub: no token_count records, so it adds 0 to both totals.
        self.assertEqual(stats["noncached_input_tokens_total"], 40)
        self.assertEqual(stats["output_tokens_total"], 50)
        self.assertEqual(stats["token_measured_n"], 1)
        self.assertEqual(stats["token_unmeasured_n"], 1)
        self.assertEqual(result["continuations_by_kind"], {"interactive": 1, "subagent": 1})

    def test_injected_context(self):
        result = mhc.collect_codex(self.root, self.cutoff)
        handoff = result["injected_context"]["handoff"]
        self.assertEqual(handoff["count"], 1)
        self.assertEqual(handoff["bytes"], len("=== HANDOFF ===\nsome handoff text".encode("utf-8")))

    def test_injected_context_splits_combined_developer_message(self):
        result = mhc.collect_codex(self.root, self.cutoff)
        ictx = result["injected_context"]
        self.assertEqual(ictx["memory"], {"count": 1, "bytes": len(self.MEMORY_TEXT.encode("utf-8"))})
        self.assertEqual(
            ictx["skills_instructions"], {"count": 1, "bytes": len(self.SKILLS_TEXT.encode("utf-8"))}
        )
        self.assertEqual(ictx["other"], {"count": 1, "bytes": len(self.PERMISSIONS_TEXT.encode("utf-8"))})

    def test_skill_usage_from_tool_call(self):
        result = mhc.collect_codex(self.root, self.cutoff)
        self.assertEqual(result["skill_usage"], {"handoff": 1})

    def test_missing_root_returns_empty(self):
        result = mhc.collect_codex(self.root / "does-not-exist", self.cutoff)
        self.assertEqual(result, mhc._empty_codex_result())


class TimestampWindowTests(unittest.TestCase):
    OLD = "2026-01-01T23:59:50Z"
    START = "2026-01-02T00:00:00Z"
    END = "2026-01-02T00:00:05Z"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.cutoff = datetime.fromisoformat(self.START.replace("Z", "+00:00")).timestamp()

    def _collect(self, provider, records, mtime=None, name="session"):
        directory = "sessions" if provider == "codex" else "projects/project"
        path = self.root / directory / f"{name}.jsonl"
        _write_jsonl(path, records)
        if mtime is not None:
            os.utime(path, (mtime, mtime))
        return getattr(mhc, f"collect_{provider}")(self.root, self.cutoff)

    def _codex_call(self, timestamp, path="skills/current/SKILL.md"):
        return {"type": "response_item", "timestamp": timestamp,
                "payload": {"type": "function_call", "name": "shell",
                            "arguments": json.dumps({"cmd": f"cat {path}"})}}

    def _claude_call(self, timestamp, skill="current"):
        return {"type": "assistant", "timestamp": timestamp,
                "message": {"content": [_tool_use("Skill", skill=skill)]}}

    def _codex_hook(self, timestamp):
        return {"type": "response_item", "timestamp": timestamp,
                "payload": {"type": "message", "role": "user",
                            "content": [{"text": "<hook_prompt>continue</hook_prompt>"}]}}

    def _tokens(self, timestamp, count):
        return {"type": "event_msg", "timestamp": timestamp,
                "payload": {"type": "token_count", "info": {"total_token_usage": {
                    "total_tokens": count * 3, "input_tokens": count * 2,
                    "cached_input_tokens": count, "output_tokens": count}}}}

    def _complete(self, timestamp):
        return {"type": "event_msg", "timestamp": timestamp,
                "payload": {"type": "task_complete"}}

    def _claude_stop(self, timestamp, kind):
        return {"type": "attachment", "timestamp": timestamp,
                "attachment": {"type": kind, "hookEvent": "Stop"}}

    def test_codex_skill_paths_include_windows_and_nested_json_escapes(self):
        for path in ("skills/review/SKILL.md", r"skills\review\SKILL.md",
                     r"skills\\review\\SKILL.md"):
            with self.subTest(path=path):
                result = self._collect("codex", [self._codex_call(self.START, path)])
                self.assertEqual(result["skill_usage"], {"review": 1})

    def test_event_time_controls_window_independently_of_file_mtime(self):
        for provider in ("codex", "claude"):
            call = getattr(self, f"_{provider}_call")
            for mtime in (1, self.cutoff + 86400):
                with self.subTest(provider=provider, mtime=mtime):
                    result = self._collect(provider, [call(self.OLD), call(self.START)], mtime)
                    self.assertEqual(result["skill_usage"], {"current": 1})
                    result = self._collect(provider, [call(self.OLD)], mtime)
                    key = "sessions_by_kind" if provider == "codex" else "sessions_by_entrypoint"
                    self.assertEqual(result[key], {})
                    self.assertEqual(result["skill_usage"], {})

    def test_first_old_codex_metadata_classifies_current_events(self):
        records = [
            {"type": "session_meta", "timestamp": self.OLD,
             "payload": {"id": "child", "session_id": "parent"}},
            {"type": "session_meta", "timestamp": self.START,
             "payload": {"id": "parent", "session_id": "parent"}},
            self._codex_call(self.START),
        ]
        result = self._collect("codex", records, mtime=1)
        self.assertEqual(result["sessions_by_kind"], {"subagent": 1})
        result = self._collect("codex", records[:2])
        self.assertEqual(result["sessions_by_kind"], {})

    def test_old_claude_entrypoint_classifies_current_events(self):
        result = self._collect("claude", [
            {"type": "user", "timestamp": self.OLD, "entrypoint": "sdk-cli"},
            self._claude_call(self.START),
        ], mtime=1)
        self.assertEqual(result["sessions_by_entrypoint"], {"sdk-cli": 1})

    def test_missing_malformed_and_naive_timestamps_do_not_count(self):
        for provider in ("codex", "claude"):
            call = getattr(self, f"_{provider}_call")
            records = [call(ts) for ts in (None, "", "invalid", 123, [], {},
                                          "2026-01-02", "2026-01-02T00:00:00")]
            missing = call(self.START)
            del missing["timestamp"]
            records.append(missing)
            with self.subTest(provider=provider):
                result = self._collect(provider, records)
                self.assertEqual(result["skill_usage"], {})
                key = "sessions_by_kind" if provider == "codex" else "sessions_by_entrypoint"
                self.assertEqual(result[key], {})

    def test_timestamp_offsets_are_compared_as_instants(self):
        for provider in ("codex", "claude"):
            call = getattr(self, f"_{provider}_call")
            with self.subTest(provider=provider):
                result = self._collect(provider, [call("2026-01-02T01:00:00+01:00"),
                                                  call("2026-01-02T00:30:00+01:00")])
                self.assertEqual(result["skill_usage"], {"current": 1})

    def test_codex_context_and_claude_hook_and_agent_metrics_are_windowed(self):
        codex_records, claude_records = [], []
        for timestamp in (self.OLD, self.START):
            codex_records.append({"type": "response_item", "timestamp": timestamp,
                                  "payload": {"type": "message", "role": "developer",
                                              "content": [{"text": "## Memory"}]}})
            claude_records.extend([
                self._claude_stop(timestamp, "hook_non_blocking_error"),
                {"type": "assistant", "timestamp": timestamp,
                 "message": {"content": [_tool_use("Agent", subagent_type="builder")]}}
            ])
        codex = self._collect("codex", codex_records)
        claude = self._collect("claude", claude_records)
        self.assertEqual(codex["injected_context"], {"memory": {"count": 1, "bytes": 9}})
        self.assertEqual(claude["hook_outcomes"][0]["count"], 1)
        self.assertEqual(claude["non_success_top15"][0]["count"], 1)
        self.assertEqual(claude["agent_launches"][0]["count"], 1)

    def test_codex_continuation_crossing_cutoff_is_excluded(self):
        result = self._collect("codex", [
            self._tokens(self.OLD, 100), self._codex_hook(self.OLD),
            self._tokens(self.START, 1000), self._complete(self.START),
            self._codex_hook(self.START), self._tokens(self.END, 1010),
            self._complete(self.END),
        ])
        stats = result["stop_continuations"]
        self.assertEqual(stats["n"], 1)
        self.assertEqual(stats["max"], 5.0)
        self.assertEqual(stats["noncached_input_tokens_total"], 10)
        self.assertEqual(stats["output_tokens_total"], 10)

    def test_codex_tokens_require_in_window_baseline(self):
        result = self._collect("codex", [
            self._tokens(self.OLD, 100), self._codex_hook(self.START),
            self._tokens(self.END, 1000), self._complete(self.END),
        ])
        self.assertEqual(result["stop_continuations"]["n"], 1)
        self.assertEqual(result["stop_continuations"]["noncached_input_tokens_total"], 0)
        self.assertEqual(result["stop_continuations"]["output_tokens_total"], 0)
        self.assertEqual(result["stop_continuations"]["token_measured_n"], 0)
        self.assertEqual(result["stop_continuations"]["token_unmeasured_n"], 1)

    def test_codex_empty_token_snapshots_do_not_fabricate_baseline(self):
        for info in (None, {}, {"total_token_usage": None}, {"total_token_usage": {}}):
            with self.subTest(info=info):
                empty = {"type": "event_msg", "timestamp": self.START,
                         "payload": {"type": "token_count", "info": info}}
                result = self._collect("codex", [
                    self._tokens(self.OLD, 100), empty, self._codex_hook(self.START),
                    self._tokens(self.END, 1000), self._complete(self.END),
                ])
                stats = result["stop_continuations"]
                self.assertEqual(stats["n"], 1)
                self.assertEqual(stats["output_tokens_total"], 0)
                self.assertEqual(stats["noncached_input_tokens_total"], 0)
                self.assertEqual(stats["token_measured_n"], 0)
                self.assertEqual(stats["token_unmeasured_n"], 1)

    def test_codex_malformed_token_counters_are_unmeasured(self):
        for field in ("total_tokens", "input_tokens", "cached_input_tokens", "output_tokens"):
            for value in (None, "10", True, -1, 1.5):
                with self.subTest(field=field, value=value):
                    baseline = self._tokens(self.START, 10)
                    baseline["payload"]["info"]["total_token_usage"][field] = value
                    result = self._collect("codex", [baseline, self._codex_hook(self.START),
                                                    self._tokens(self.END, 100), self._complete(self.END)])
                    self.assertEqual(result["stop_continuations"]["output_tokens_total"], 0)
                    self.assertEqual(result["stop_continuations"]["token_unmeasured_n"], 1)

    def test_codex_counter_reset_does_not_produce_negative_token_totals(self):
        result = self._collect("codex", [
            self._tokens(self.START, 1000), self._codex_hook(self.START),
            self._tokens(self.END, 10), self._complete(self.END),
        ])
        self.assertEqual(result["stop_continuations"]["n"], 1)
        self.assertEqual(result["stop_continuations"]["noncached_input_tokens_total"], 0)
        self.assertEqual(result["stop_continuations"]["output_tokens_total"], 0)
        self.assertEqual(result["stop_continuations"]["token_unmeasured_n"], 1)

    def test_codex_counter_reset_then_recovery_is_still_unmeasured(self):
        result = self._collect("codex", [
            self._tokens(self.START, 100), self._codex_hook(self.START),
            self._tokens(self.END, 10), self._tokens(self.END, 1000),
            self._complete(self.END),
        ])
        self.assertEqual(result["stop_continuations"]["output_tokens_total"], 0)
        self.assertEqual(result["stop_continuations"]["token_unmeasured_n"], 1)

    def test_codex_missing_post_hook_snapshot_is_unmeasured(self):
        result = self._collect("codex", [
            self._tokens(self.START, 10), self._codex_hook(self.START), self._complete(self.END),
        ])
        self.assertEqual(result["stop_continuations"]["output_tokens_total"], 0)
        self.assertEqual(result["stop_continuations"]["token_measured_n"], 0)
        self.assertEqual(result["stop_continuations"]["token_unmeasured_n"], 1)

    def test_codex_measured_zero_tokens_are_distinct_from_missing_coverage(self):
        result = self._collect("codex", [
            self._tokens(self.START, 10), self._codex_hook(self.START),
            self._tokens(self.END, 10), self._complete(self.END),
        ])
        stats = result["stop_continuations"]
        self.assertEqual(stats["output_tokens_total"], 0)
        self.assertEqual(stats["token_measured_n"], 1)
        self.assertEqual(stats["token_unmeasured_n"], 0)
        text = mhc.render_text({"codex": result}, 1)
        self.assertIn("token_measured_n=1", text)
        self.assertIn("token_unmeasured_n=0", text)

    def test_codex_excluded_completion_cannot_leave_pending_continuation(self):
        for excluded in (self.OLD, "invalid", None):
            with self.subTest(excluded=excluded):
                result = self._collect("codex", [
                    self._tokens(self.START, 10), self._codex_hook(self.START),
                    self._tokens(excluded, 1000), self._complete(excluded),
                    self._complete(self.END),
                ])
                self.assertEqual(result["stop_continuations"]["n"], 0)
                self.assertEqual(result["stop_continuations"]["output_tokens_total"], 0)

    def test_claude_continuation_crossing_cutoff_is_excluded(self):
        result = self._collect("claude", [
            self._claude_stop(self.OLD, "hook_additional_context"),
            self._claude_stop(self.START, "hook_success"),
            self._claude_stop(self.START, "hook_additional_context"),
            self._claude_stop(self.END, "hook_success"),
        ])
        self.assertEqual(result["stop_continuations"]["n"], 1)
        self.assertEqual(result["stop_continuations"]["max"], 5.0)

    def test_claude_excluded_completion_cannot_leave_pending_continuation(self):
        for excluded in (self.OLD, "invalid", None):
            with self.subTest(excluded=excluded):
                result = self._collect("claude", [
                    self._claude_stop(self.START, "hook_additional_context"),
                    self._claude_stop(excluded, "hook_success"),
                    self._claude_stop(self.END, "hook_success"),
                ])
                self.assertEqual(result["stop_continuations"]["n"], 0)

    def test_reversed_continuation_endpoints_are_excluded(self):
        codex = self._collect("codex", [self._codex_hook(self.END), self._complete(self.START)])
        claude = self._collect("claude", [
            self._claude_stop(self.END, "hook_additional_context"),
            self._claude_stop(self.START, "hook_success"),
        ])
        self.assertEqual(codex["stop_continuations"]["n"], 0)
        self.assertEqual(claude["stop_continuations"]["n"], 0)

    def test_cli_days_uses_event_time_for_both_providers(self):
        now = datetime.now(timezone.utc)
        current, old = now.isoformat(), (now - timedelta(days=2)).isoformat()
        codex_path = self.root / "sessions" / "session.jsonl"
        claude_path = self.root / "projects" / "project" / "session.jsonl"
        _write_jsonl(codex_path, [
            {"type": "session_meta", "timestamp": old,
             "payload": {"id": "exec", "originator": "codex_exec"}},
            self._codex_call(old, "skills/old/SKILL.md"),
            self._codex_call(current, r"skills\current\SKILL.md"),
        ])
        _write_jsonl(claude_path, [
            {"type": "user", "timestamp": old, "entrypoint": "sdk-cli"},
            self._claude_call(old, "old"), self._claude_call(current),
        ])
        for path in (codex_path, claude_path):
            os.utime(path, (1, 1))
        proc = subprocess.run(
            [sys.executable, "-B", str(_REPO_ROOT / "scripts" / "measure_hook_cost.py"),
             "--days", "1", "--provider", "both", "--claude-root", str(self.root),
             "--codex-root", str(self.root), "--json"],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual(result["codex"]["skill_usage"], {"current": 1})
        self.assertEqual(result["claude"]["skill_usage"], {"current": 1})
        self.assertEqual(result["codex"]["sessions_by_kind"], {"exec": 1})
        self.assertEqual(result["claude"]["sessions_by_entrypoint"], {"sdk-cli": 1})


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
