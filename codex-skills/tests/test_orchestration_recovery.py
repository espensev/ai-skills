# ruff: noqa: E402
"""Tests for orchestration.py — stale task detection, worktree matching, recovery."""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from task_runtime.orchestration import _is_stale_running_task, recover_runtime


class TestIsStaleRunningTask(unittest.TestCase):
    """Boundary conditions for stale-task detection."""

    def test_exactly_at_threshold_not_stale(self):
        # 2 hours exactly should not be stale (need > 2h)
        started = "2026-01-01T00:00:00+00:00"
        now = "2026-01-01T02:00:00+00:00"
        self.assertFalse(_is_stale_running_task(started, now, max_hours=2))

    def test_one_second_over_threshold_is_stale(self):
        started = "2026-01-01T00:00:00+00:00"
        now = "2026-01-01T02:00:01+00:00"
        self.assertTrue(_is_stale_running_task(started, now, max_hours=2))

    def test_invalid_started_returns_false(self):
        self.assertFalse(_is_stale_running_task("not-a-date", "2026-01-01T00:00:00Z"))

    def test_empty_strings_return_false(self):
        self.assertFalse(_is_stale_running_task("", ""))

    def test_custom_threshold(self):
        started = "2026-01-01T00:00:00+00:00"
        now = "2026-01-01T00:31:00+00:00"
        self.assertTrue(_is_stale_running_task(started, now, max_hours=0.5))
        self.assertFalse(_is_stale_running_task(started, now, max_hours=1.0))

    def test_z_suffix_handling(self):
        started = "2026-01-01T00:00:00Z"
        now = "2026-01-01T03:00:00Z"
        self.assertTrue(_is_stale_running_task(started, now, max_hours=2))


class TestRecoverRuntimeOrphanCleanup(unittest.TestCase):
    """M3: orphan worktree cleanup errors should be captured, not silently ignored."""

    def _make_kwargs(self, state, tmp, orphan_dir=None):
        roots = set()
        if orphan_dir:
            roots.add(orphan_dir)
        return {
            "prune_orphans": True,
            "load_state_fn": lambda: state,
            "save_state_fn": lambda s: None,
            "now_iso_fn": lambda: "2026-01-01T12:00:00Z",
            "ensure_task_runtime_fields_fn": lambda t: (
                t.setdefault("launch", {}),
                t.setdefault("agent_result", {}),
                t.setdefault("merge", {}),
                False,
            )[-1],
            "empty_agent_result_fn": dict,
            "empty_launch_record_fn": dict,
            "empty_merge_record_fn": dict,
            "recompute_ready_fn": lambda s: None,
            "sync_execution_manifest_after_recover_fn": lambda s, r: None,
            "resolve_recorded_path_fn": lambda p: Path(p),
            "display_runtime_path_fn": lambda p: str(p),
            "candidate_worktree_roots_fn": lambda s: roots,
            "match_worktree_record_fn": lambda *a: None,
            "cleanup_task_worktree_fn": lambda *a: {"worktree_removed": False, "branch_removed": False},
            "git_worktree_inventory_fn": lambda: {"available": False, "worktrees": []},
            "safe_resolve_fn": lambda p: Path(p),
        }

    def test_orphan_detected(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            orphan = tmp / "orphan_worktree"
            orphan.mkdir()
            state = {"tasks": {}}
            kwargs = self._make_kwargs(state, tmp, orphan_dir=tmp)
            result = recover_runtime(**kwargs)
            self.assertEqual(len(result["orphan_worktrees"]), 1)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_no_orphans_when_empty(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            state = {"tasks": {}}
            kwargs = self._make_kwargs(state, tmp)
            result = recover_runtime(**kwargs)
            self.assertEqual(result["orphan_worktrees"], [])
            self.assertEqual(result["recovered"], [])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestRecoverRuntimeStaleRecovery(unittest.TestCase):
    """Stale running tasks should be recovered."""

    def test_stale_task_is_recovered(self):
        state = {
            "tasks": {
                "a": {
                    "id": "a",
                    "name": "alpha",
                    "status": "running",
                    "started_at": "2026-01-01T00:00:00Z",
                    "launch": {},
                    "agent_result": {},
                    "merge": {},
                },
            },
        }
        result = recover_runtime(
            prune_orphans=False,
            load_state_fn=lambda: state,
            save_state_fn=lambda s: None,
            now_iso_fn=lambda: "2026-01-01T04:00:00Z",
            ensure_task_runtime_fields_fn=lambda t: (
                t.setdefault("launch", {}),
                t.setdefault("agent_result", {}),
                t.setdefault("merge", {}),
                False,
            )[-1],
            empty_agent_result_fn=dict,
            empty_launch_record_fn=dict,
            empty_merge_record_fn=dict,
            recompute_ready_fn=lambda s: None,
            sync_execution_manifest_after_recover_fn=lambda s, r: None,
            resolve_recorded_path_fn=lambda p: Path(p),
            display_runtime_path_fn=lambda p: str(p),
            candidate_worktree_roots_fn=lambda s: set(),
            match_worktree_record_fn=lambda *a: None,
            cleanup_task_worktree_fn=lambda *a: {},
            git_worktree_inventory_fn=lambda: {"available": False, "worktrees": []},
            safe_resolve_fn=lambda p: Path(p),
        )
        self.assertTrue(len(result["recovered"]) >= 1)


if __name__ == "__main__":
    unittest.main()
