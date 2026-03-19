# ruff: noqa: E402
"""Tests for merge.py — conflict detection, backup behavior, path containment."""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from task_runtime.merge import merge_runtime


def _stub_state(tasks: dict) -> dict:
    return {"tasks": tasks}


def _noop(*args, **kwargs):
    pass


def _noop_return(val):
    def inner(*args, **kwargs):
        return val
    return inner


def _make_merge_kwargs(tmp: Path, state: dict, **overrides):
    """Build the full kwargs for merge_runtime with sensible defaults."""
    return {
        "load_state_fn": lambda: state,
        "save_state_fn": _noop,
        "now_iso_fn": lambda: "2026-01-01T00:00:00Z",
        "ensure_task_runtime_fields_fn": lambda t: (
            t.setdefault("launch", {}),
            t.setdefault("agent_result", {}),
            t.setdefault("merge", {}),
            False,
        )[-1],
        "normalize_string_list_fn": lambda v: list(v) if isinstance(v, list) else [],
        "safe_resolve_fn": lambda p: (tmp / p).resolve(),
        "persist_execution_manifest_fn": _noop,
        "resolve_recorded_path_fn": lambda p: Path(p),
        "display_runtime_path_fn": lambda p: str(p),
        "match_worktree_record_fn": lambda *a: None,
        "cleanup_task_worktree_fn": lambda *a: {"worktree_removed": False, "branch_removed": False},
        "git_worktree_inventory_fn": lambda: {"available": False, "worktrees": []},
        "run_git_runtime_fn": lambda cmd: MagicMock(returncode=1, stdout="", stderr=""),
        **overrides,
    }


class TestMergeBackupFailureLogged(unittest.TestCase):
    """H4: backup failure should be recorded in merge notes, not silently swallowed."""

    def test_backup_failure_appears_in_notes(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            # Set up worktree with a source file
            worktree = tmp / "worktree"
            worktree.mkdir()
            (worktree / "file.py").write_text("new content")

            # Set up dest file that needs backup
            dest_dir = tmp / "dest"
            dest_dir.mkdir()
            dest_file = dest_dir / "file.py"
            dest_file.write_text("old content")

            state = _stub_state({
                "a": {
                    "id": "a",
                    "name": "alpha",
                    "status": "done",
                    "group": 1,
                    "launch": {"worktree_path": str(worktree)},
                    "agent_result": {"status": "done", "files_modified": ["file.py"]},
                    "merge": {},
                },
            })

            kwargs = _make_merge_kwargs(
                dest_dir,
                state,
                safe_resolve_fn=lambda p: (dest_dir / p).resolve(),
                resolve_recorded_path_fn=lambda p: Path(p),
                match_worktree_record_fn=lambda path, branch, inv: {"path": str(worktree), "branch": ""},
            )

            # Mock shutil.copy2 to fail on .bak copies but succeed on actual merges
            original_copy2 = shutil.copy2

            def copy2_that_fails_bak(src, dst, **kw):
                if str(dst).endswith(".bak"):
                    raise OSError("Permission denied (simulated)")
                return original_copy2(src, dst, **kw)

            with patch("task_runtime.merge.shutil.copy2", side_effect=copy2_that_fails_bak):
                merge_runtime(["a"], plan_id=None, **kwargs)

            # The merge should proceed but the detail should mention backup failure
            task = state["tasks"]["a"]
            merge_detail = task.get("merge", {}).get("detail", "")
            self.assertIn("backup failed", merge_detail, f"Expected backup failure in detail: {merge_detail!r}")
        finally:
            shutil.rmtree(tmp)


class TestMergePathContainment(unittest.TestCase):
    """Path traversal attempts should be caught as conflicts."""

    def test_path_escape_is_conflict(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            worktree = tmp / "worktree"
            worktree.mkdir()

            state = _stub_state({
                "a": {
                    "id": "a",
                    "name": "alpha",
                    "status": "done",
                    "group": 1,
                    "launch": {"worktree_path": str(worktree)},
                    "agent_result": {"status": "done", "files_modified": ["../../../etc/passwd"]},
                    "merge": {},
                },
            })

            kwargs = _make_merge_kwargs(
                tmp,
                state,
                resolve_recorded_path_fn=lambda p: Path(p),
                match_worktree_record_fn=lambda path, branch, inv: {"path": str(worktree), "branch": ""},
            )
            merge_runtime(["a"], plan_id=None, **kwargs)

            # The traversal path should show up as a conflict
            task_merge = state["tasks"]["a"].get("merge", {})
            self.assertIn("../../../etc/passwd", task_merge.get("conflicts", []))
        finally:
            shutil.rmtree(tmp)


class TestMergeMissingWorktree(unittest.TestCase):
    """Missing worktree path should produce a conflict, not crash."""

    def test_missing_worktree_is_conflict(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            state = _stub_state({
                "a": {
                    "id": "a",
                    "name": "alpha",
                    "status": "done",
                    "group": 1,
                    "launch": {"worktree_path": ""},
                    "agent_result": {"status": "done", "files_modified": ["file.py"]},
                    "merge": {},
                },
            })
            kwargs = _make_merge_kwargs(tmp, state)
            merge_runtime(["a"], plan_id=None, **kwargs)

            task_merge = state["tasks"]["a"].get("merge", {})
            self.assertEqual(task_merge.get("status"), "conflict")
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
