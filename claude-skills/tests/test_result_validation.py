# ruff: noqa: E402
"""Tests for result.py — payload ID validation (H1), field coercion, status transitions."""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from task_runtime.result import cmd_result


class _ResultTestBase(unittest.TestCase):
    """Shared helpers for cmd_result tests."""

    def _make_state(self, agent_id="a", status="running"):
        return {
            "tasks": {
                agent_id: {
                    "id": agent_id,
                    "name": "alpha",
                    "status": status,
                    "group": 1,
                    "launch": {},
                    "agent_result": {},
                    "merge": {},
                },
            },
        }

    def _make_kwargs(self, state, payload):
        saved = {}
        emitted = {}
        return {
            "load_state_fn": lambda: state,
            "save_state_fn": lambda s: saved.update(s),
            "ensure_task_runtime_fields_fn": lambda t: (
                t.setdefault("launch", {}),
                t.setdefault("agent_result", {}),
                t.setdefault("merge", {}),
                False,
            )[-1],
            "empty_agent_result_fn": dict,
            "empty_merge_record_fn": dict,
            "normalize_string_list_fn": lambda v: list(v) if isinstance(v, list) else [],
            "recompute_ready_fn": lambda s: None,
            "load_json_payload_fn": lambda a: payload,
            "now_iso_fn": lambda: "2026-01-01T00:00:00Z",
            "emit_json_fn": lambda d: emitted.update(d),
        }, saved, emitted

    def _run(self, agent_id, payload, state=None):
        if state is None:
            state = self._make_state(agent_id)
        args = SimpleNamespace(agent=agent_id, json=False)
        kwargs, saved, emitted = self._make_kwargs(state, payload)
        cmd_result(args, **kwargs)
        return state, saved, emitted


class TestPayloadIDValidation(_ResultTestBase):
    """H1: empty payload ID must NOT bypass mismatch validation."""

    def test_empty_id_raises(self):
        """Payload with empty string ID should be rejected (does not match agent_id)."""
        args = SimpleNamespace(agent="a", json=False)
        payload = {"id": "", "status": "done"}
        kwargs, _, _ = self._make_kwargs(self._make_state("a"), payload)
        with self.assertRaises(RuntimeError):
            cmd_result(args, **kwargs)

    def test_missing_id_raises(self):
        """Payload with no ID key should be rejected."""
        args = SimpleNamespace(agent="a", json=False)
        payload = {"status": "done"}
        kwargs, _, _ = self._make_kwargs(self._make_state("a"), payload)
        with self.assertRaises(RuntimeError):
            cmd_result(args, **kwargs)

    def test_matching_id_succeeds(self):
        """Payload with matching ID should proceed."""
        state, _, _ = self._run("a", {"id": "a", "status": "done"})
        self.assertEqual(state["tasks"]["a"]["status"], "done")

    def test_mismatched_id_raises(self):
        """Payload with wrong ID should be rejected."""
        args = SimpleNamespace(agent="a", json=False)
        payload = {"id": "b", "status": "done"}
        kwargs, _, _ = self._make_kwargs(self._make_state("a"), payload)
        with self.assertRaises(RuntimeError):
            cmd_result(args, **kwargs)

    def test_case_insensitive_match(self):
        """ID matching should be case-insensitive."""
        state, _, _ = self._run("a", {"id": "A", "status": "done"})
        self.assertEqual(state["tasks"]["a"]["status"], "done")


class TestStatusTransitions(_ResultTestBase):
    """Status field coercion and transitions."""

    def test_done_status(self):
        state, _, _ = self._run("a", {"id": "a", "status": "done", "summary": "All good"})
        self.assertEqual(state["tasks"]["a"]["status"], "done")
        self.assertEqual(state["tasks"]["a"]["summary"], "All good")

    def test_failed_status(self):
        state, _, _ = self._run("a", {"id": "a", "status": "failed", "issues": ["broke"]})
        self.assertEqual(state["tasks"]["a"]["status"], "failed")

    def test_invalid_status_raises(self):
        args = SimpleNamespace(agent="a", json=False)
        payload = {"id": "a", "status": "pending"}
        kwargs, _, _ = self._make_kwargs(self._make_state("a"), payload)
        with self.assertRaises(RuntimeError):
            cmd_result(args, **kwargs)


class TestNumericFieldCoercion(_ResultTestBase):
    """Numeric fields should be coerced safely."""

    def test_string_numbers_coerced(self):
        state, _, _ = self._run("a", {
            "id": "a",
            "status": "done",
            "tests_passed": "5",
            "tests_failed": "0",
            "input_tokens": "1000",
            "output_tokens": "500",
        })
        result = state["tasks"]["a"]["agent_result"]
        self.assertEqual(result["tests_passed"], 5)
        self.assertEqual(result["input_tokens"], 1000)

    def test_none_numbers_default_to_zero(self):
        state, _, _ = self._run("a", {"id": "a", "status": "done"})
        result = state["tasks"]["a"]["agent_result"]
        self.assertEqual(result["tests_passed"], 0)
        self.assertEqual(result["tests_failed"], 0)


class TestFilesModifiedPathNormalization(_ResultTestBase):
    """Backslash paths should be normalized to forward slashes."""

    def test_backslash_normalized(self):
        state, _, _ = self._run("a", {
            "id": "a",
            "status": "done",
            "files_modified": ["src\\main.py", "tests\\test_a.py"],
        })
        files = state["tasks"]["a"]["agent_result"]["files_modified"]
        self.assertEqual(files, ["src/main.py", "tests/test_a.py"])


if __name__ == "__main__":
    unittest.main()
