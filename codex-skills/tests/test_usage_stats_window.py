"""Tests for the native Codex rolling-window usage collector."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "usage-stats" / "scripts" / "codex_usage_window.py"
sys.dont_write_bytecode = True


def load_collector():
    spec = importlib.util.spec_from_file_location("codex_usage_window", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def token_event(timestamp: str, total: dict[str, int]) -> dict[str, object]:
    return {
        "timestamp": timestamp,
        "type": "event_msg",
        "payload": {
            "type": "token_count",
            "info": {
                "total_token_usage": total,
                "last_token_usage": total,
            },
            "rate_limits": {
                "limit_id": "codex",
                "plan_type": "pro",
            },
        },
    }


class TestCodexUsageWindow(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.codex_home = Path(self.tempdir.name)
        self.sessions = self.codex_home / "sessions" / "2026" / "08" / "25"
        self.sessions.mkdir(parents=True)
        self.now = datetime(2026, 8, 26, 6, 0, tzinfo=timezone.utc)

    def write_session(self, name: str, events: list[dict[str, object]]) -> Path:
        path = self.sessions / name
        path.write_text(
            "".join(json.dumps(event) + "\n" for event in events),
            encoding="utf-8",
        )
        os.utime(path, (self.now.timestamp(), self.now.timestamp()))
        return path

    def test_collects_cumulative_deltas_and_ignores_duplicates(self):
        first = {
            "input_tokens": 100,
            "cached_input_tokens": 80,
            "cache_write_input_tokens": 10,
            "output_tokens": 10,
            "reasoning_output_tokens": 4,
            "total_tokens": 110,
        }
        second = {
            "input_tokens": 150,
            "cached_input_tokens": 120,
            "cache_write_input_tokens": 10,
            "output_tokens": 15,
            "reasoning_output_tokens": 6,
            "total_tokens": 165,
        }
        third = {
            "input_tokens": 225,
            "cached_input_tokens": 180,
            "cache_write_input_tokens": 20,
            "output_tokens": 22,
            "reasoning_output_tokens": 9,
            "total_tokens": 247,
        }
        self.write_session(
            "rollout-2026-08-25T05-00-00-01a00000-0000-0000-0000-000000000001.jsonl",
            [
                token_event("2026-08-25T05:00:00Z", first),
                token_event("2026-08-25T07:00:00Z", second),
                token_event("2026-08-25T07:01:00Z", second),
                token_event("2026-08-25T08:00:00Z", third),
            ],
        )

        collector = load_collector()
        result = collector.collect_usage(self.codex_home, hours=24, now=self.now)

        self.assertEqual(125, result["totals"]["input_tokens"])
        self.assertEqual(100, result["totals"]["cached_input_tokens"])
        self.assertEqual(12, result["totals"]["output_tokens"])
        self.assertEqual(5, result["totals"]["reasoning_output_tokens"])
        self.assertEqual(137, result["totals"]["total_tokens"])
        self.assertEqual(0, result["totals"]["reconciliation_delta"])
        self.assertEqual(3, result["coverage"]["token_count_events"])
        self.assertEqual(2, result["coverage"]["positive_usage_events"])
        self.assertEqual(1, result["coverage"]["duplicate_events"])
        self.assertEqual(1, result["coverage"]["sessions_with_usage"])

    def test_first_event_inside_window_is_counted_and_scope_is_explicit(self):
        total = {
            "input_tokens": 20,
            "cached_input_tokens": 15,
            "cache_write_input_tokens": 0,
            "output_tokens": 2,
            "reasoning_output_tokens": 1,
            "total_tokens": 22,
        }
        self.write_session(
            "rollout-2026-08-26T01-00-00-01a00000-0000-0000-0000-000000000002.jsonl",
            [token_event("2026-08-26T01:00:00Z", total)],
        )

        collector = load_collector()
        result = collector.collect_usage(self.codex_home, hours=24, now=self.now)

        self.assertEqual(22, result["totals"]["total_tokens"])
        self.assertIn("ChatGPT web/app conversations", result["scope"]["excluded"])
        self.assertEqual("tier_1_measured", result["data_tier"])

    def test_cli_emits_json(self):
        total = {
            "input_tokens": 10,
            "cached_input_tokens": 0,
            "cache_write_input_tokens": 0,
            "output_tokens": 1,
            "reasoning_output_tokens": 0,
            "total_tokens": 11,
        }
        self.write_session(
            "rollout-2026-08-26T02-00-00-01a00000-0000-0000-0000-000000000003.jsonl",
            [token_event("2026-08-26T02:00:00Z", total)],
        )

        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--codex-home",
                str(self.codex_home),
                "--hours",
                "24",
                "--now",
                "2026-08-26T06:00:00Z",
                "--json",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        result = json.loads(completed.stdout)
        self.assertEqual(11, result["totals"]["total_tokens"])


if __name__ == "__main__":
    unittest.main()
