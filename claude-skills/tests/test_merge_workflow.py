# ruff: noqa: E402
"""Tests for merge.py — full merge workflow, ownership, ordering, status logic."""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from task_runtime.merge import merge_runtime

# ---------------------------------------------------------------------------
# Helpers (shared with test_merge_safety.py patterns)
# ---------------------------------------------------------------------------


def _stub_state(tasks: dict) -> dict:
    return {"tasks": tasks}


def _noop(*args, **kwargs):
    pass


def _make_merge_kwargs(tmp: Path, state: dict, **overrides):
    """Build full kwargs for merge_runtime with sensible defaults."""
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


def _make_worktree(tmp: Path, name: str, files: dict[str, str]) -> Path:
    """Create a fake worktree directory with given files."""
    wt = tmp / name
    wt.mkdir(parents=True, exist_ok=True)
    for rel_path, content in files.items():
        f = wt / rel_path
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content, encoding="utf-8")
    return wt


def _task(task_id: str, worktree: Path, files: list[str], *, group: int = 1, merge: dict | None = None) -> dict:
    """Build a done task with agent result pointing to a worktree."""
    return {
        "id": task_id,
        "name": f"agent-{task_id}",
        "status": "done",
        "group": group,
        "launch": {"worktree_path": str(worktree)},
        "agent_result": {"status": "done", "files_modified": files, "worktree_path": str(worktree)},
        "merge": merge or {},
    }


# ---------------------------------------------------------------------------
# Single-agent merge tests
# ---------------------------------------------------------------------------


class TestMergeSingleAgent(unittest.TestCase):
    """Basic single-agent merge: file is copied from worktree to dest."""

    def test_single_file_merge(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            wt = _make_worktree(tmp, "wt-a", {"src/app.py": "new content"})
            dest = tmp / "dest"
            dest.mkdir()

            state = _stub_state({"a": _task("a", wt, ["src/app.py"])})
            kwargs = _make_merge_kwargs(
                dest, state,
                safe_resolve_fn=lambda p: (dest / p).resolve(),
                match_worktree_record_fn=lambda path, branch, inv: {"path": str(wt), "branch": ""},
            )
            result = merge_runtime(["a"], plan_id="plan-001", **kwargs)

            self.assertEqual(result["status"], "merged")
            self.assertEqual(len(result["merged"]), 1)
            self.assertIn("src/app.py", result["merged"][0]["applied_files"])
            self.assertTrue((dest / "src" / "app.py").exists())
            self.assertEqual((dest / "src" / "app.py").read_text(), "new content")
        finally:
            shutil.rmtree(tmp)

    def test_multiple_files_merge(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            wt = _make_worktree(tmp, "wt-a", {"a.py": "a", "b.py": "b", "c.py": "c"})
            dest = tmp / "dest"
            dest.mkdir()

            state = _stub_state({"a": _task("a", wt, ["a.py", "b.py", "c.py"])})
            kwargs = _make_merge_kwargs(
                dest, state,
                safe_resolve_fn=lambda p: (dest / p).resolve(),
                match_worktree_record_fn=lambda path, branch, inv: {"path": str(wt), "branch": ""},
            )
            result = merge_runtime(["a"], plan_id="plan-001", **kwargs)

            self.assertEqual(len(result["merged"][0]["applied_files"]), 3)
        finally:
            shutil.rmtree(tmp)


# ---------------------------------------------------------------------------
# No-files / no-result edge cases
# ---------------------------------------------------------------------------


class TestMergeNoopCases(unittest.TestCase):
    """Tasks with no files or no done result produce noop/skip."""

    def test_no_files_is_noop(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            wt = _make_worktree(tmp, "wt-a", {})
            state = _stub_state({"a": _task("a", wt, [])})
            kwargs = _make_merge_kwargs(tmp, state)
            result = merge_runtime(["a"], plan_id=None, **kwargs)

            self.assertEqual(len(result["merged"]), 1)
            self.assertEqual(result["merged"][0]["status"], "noop")
        finally:
            shutil.rmtree(tmp)

    def test_no_done_result_is_skipped(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            task = {
                "id": "a", "name": "agent-a", "status": "done", "group": 1,
                "launch": {}, "agent_result": {"status": "failed"}, "merge": {},
            }
            state = _stub_state({"a": task})
            kwargs = _make_merge_kwargs(tmp, state)
            result = merge_runtime(["a"], plan_id=None, **kwargs)

            self.assertEqual(len(result["skipped"]), 1)
            self.assertEqual(result["skipped"][0]["reason"], "no_done_result")
        finally:
            shutil.rmtree(tmp)

    def test_already_merged_is_skipped(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            wt = _make_worktree(tmp, "wt-a", {"f.py": "x"})
            task = _task("a", wt, ["f.py"], merge={"status": "merged", "merged_at": "2026-01-01T00:00:00Z"})
            state = _stub_state({"a": task})
            kwargs = _make_merge_kwargs(tmp, state)
            result = merge_runtime(["a"], plan_id=None, **kwargs)

            self.assertEqual(len(result["skipped"]), 1)
            self.assertEqual(result["skipped"][0]["reason"], "already_merged")
        finally:
            shutil.rmtree(tmp)


# ---------------------------------------------------------------------------
# Multi-agent ownership and group ordering
# ---------------------------------------------------------------------------


class TestMergeOwnership(unittest.TestCase):
    """File ownership: later groups supersede earlier groups on same file."""

    def test_later_group_supersedes(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            wt_a = _make_worktree(tmp, "wt-a", {"shared.py": "from agent a"})
            wt_b = _make_worktree(tmp, "wt-b", {"shared.py": "from agent b"})
            dest = tmp / "dest"
            dest.mkdir()

            state = _stub_state({
                "a": _task("a", wt_a, ["shared.py"], group=1),
                "b": _task("b", wt_b, ["shared.py"], group=2),
            })
            kwargs = _make_merge_kwargs(
                dest, state,
                safe_resolve_fn=lambda p: (dest / p).resolve(),
                match_worktree_record_fn=lambda path, branch, inv: (
                    {"path": str(wt_a), "branch": ""} if str(wt_a) in path else {"path": str(wt_b), "branch": ""}
                ),
            )
            result = merge_runtime(None, plan_id="plan-001", **kwargs)

            # Agent b (group 2) should win
            self.assertEqual((dest / "shared.py").read_text(), "from agent b")
            # Both should be in merged (a first, then b supersedes)
            merged_ids = [m["id"] for m in result["merged"]]
            self.assertIn("a", merged_ids)
            self.assertIn("b", merged_ids)
        finally:
            shutil.rmtree(tmp)

    def test_same_group_conflict(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            wt_a = _make_worktree(tmp, "wt-a", {"shared.py": "from a"})
            wt_b = _make_worktree(tmp, "wt-b", {"shared.py": "from b"})
            dest = tmp / "dest"
            dest.mkdir()

            state = _stub_state({
                "a": _task("a", wt_a, ["shared.py"], group=1),
                "b": _task("b", wt_b, ["shared.py"], group=1),
            })
            kwargs = _make_merge_kwargs(
                dest, state,
                safe_resolve_fn=lambda p: (dest / p).resolve(),
                match_worktree_record_fn=lambda path, branch, inv: (
                    {"path": str(wt_a), "branch": ""} if str(wt_a) in path else {"path": str(wt_b), "branch": ""}
                ),
            )
            result = merge_runtime(None, plan_id=None, **kwargs)

            # Second agent in same group should get a conflict
            self.assertTrue(len(result["conflicts"]) > 0)
        finally:
            shutil.rmtree(tmp)


# ---------------------------------------------------------------------------
# Agent selection
# ---------------------------------------------------------------------------


class TestMergeAgentSelection(unittest.TestCase):
    """Agent filtering: specific IDs vs all."""

    def test_select_specific_agent(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            wt_a = _make_worktree(tmp, "wt-a", {"a.py": "a"})
            wt_b = _make_worktree(tmp, "wt-b", {"b.py": "b"})
            dest = tmp / "dest"
            dest.mkdir()

            state = _stub_state({
                "a": _task("a", wt_a, ["a.py"]),
                "b": _task("b", wt_b, ["b.py"]),
            })
            kwargs = _make_merge_kwargs(
                dest, state,
                safe_resolve_fn=lambda p: (dest / p).resolve(),
                match_worktree_record_fn=lambda path, branch, inv: (
                    {"path": str(wt_a), "branch": ""} if str(wt_a) in path else {"path": str(wt_b), "branch": ""}
                ),
            )
            result = merge_runtime(["a"], plan_id=None, **kwargs)

            merged_ids = [m["id"] for m in result["merged"]]
            self.assertIn("a", merged_ids)
            self.assertNotIn("b", merged_ids)
        finally:
            shutil.rmtree(tmp)

    def test_select_all_when_none(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            wt_a = _make_worktree(tmp, "wt-a", {"a.py": "a"})
            wt_b = _make_worktree(tmp, "wt-b", {"b.py": "b"})
            dest = tmp / "dest"
            dest.mkdir()

            state = _stub_state({
                "a": _task("a", wt_a, ["a.py"]),
                "b": _task("b", wt_b, ["b.py"]),
            })
            kwargs = _make_merge_kwargs(
                dest, state,
                safe_resolve_fn=lambda p: (dest / p).resolve(),
                match_worktree_record_fn=lambda path, branch, inv: (
                    {"path": str(wt_a), "branch": ""} if str(wt_a) in path else {"path": str(wt_b), "branch": ""}
                ),
            )
            result = merge_runtime(None, plan_id=None, **kwargs)

            merged_ids = [m["id"] for m in result["merged"]]
            self.assertIn("a", merged_ids)
            self.assertIn("b", merged_ids)
        finally:
            shutil.rmtree(tmp)


# ---------------------------------------------------------------------------
# Missing file in worktree
# ---------------------------------------------------------------------------


class TestMergeMissingSourceFile(unittest.TestCase):
    """File declared in result but missing from worktree = conflict."""

    def test_missing_file_is_conflict(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            wt = _make_worktree(tmp, "wt-a", {})  # no actual files
            dest = tmp / "dest"
            dest.mkdir()

            state = _stub_state({"a": _task("a", wt, ["missing.py"])})
            kwargs = _make_merge_kwargs(
                dest, state,
                safe_resolve_fn=lambda p: (dest / p).resolve(),
                match_worktree_record_fn=lambda path, branch, inv: {"path": str(wt), "branch": ""},
            )
            result = merge_runtime(["a"], plan_id=None, **kwargs)

            self.assertEqual(len(result["conflicts"]), 1)
            self.assertIn("missing.py", result["conflicts"][0]["files"])
        finally:
            shutil.rmtree(tmp)


# ---------------------------------------------------------------------------
# Overall status logic
# ---------------------------------------------------------------------------


class TestMergeOverallStatus(unittest.TestCase):
    """Overall status: merged, conflicts, noop, nothing_to_merge, already_merged."""

    def test_nothing_to_merge_when_no_candidates(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            # pending task, not done
            task = {"id": "a", "name": "agent-a", "status": "pending", "group": 1, "launch": {}, "agent_result": {}, "merge": {}}
            state = _stub_state({"a": task})
            kwargs = _make_merge_kwargs(tmp, state)
            result = merge_runtime(None, plan_id=None, **kwargs)

            self.assertEqual(result["status"], "nothing_to_merge")
        finally:
            shutil.rmtree(tmp)

    def test_already_merged_status(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            wt = _make_worktree(tmp, "wt-a", {"f.py": "x"})
            task = _task("a", wt, ["f.py"], merge={"status": "merged", "merged_at": "2026-01-01T00:00:00Z"})
            state = _stub_state({"a": task})
            kwargs = _make_merge_kwargs(tmp, state)
            result = merge_runtime(None, plan_id=None, **kwargs)

            self.assertEqual(result["status"], "already_merged")
        finally:
            shutil.rmtree(tmp)

    def test_conflicts_status_when_any_conflict(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            state = _stub_state({
                "a": {
                    "id": "a", "name": "agent-a", "status": "done", "group": 1,
                    "launch": {"worktree_path": ""},
                    "agent_result": {"status": "done", "files_modified": ["file.py"]},
                    "merge": {},
                },
            })
            kwargs = _make_merge_kwargs(tmp, state)
            result = merge_runtime(["a"], plan_id=None, **kwargs)

            self.assertEqual(result["status"], "conflicts")
        finally:
            shutil.rmtree(tmp)


# ---------------------------------------------------------------------------
# Manifest persistence
# ---------------------------------------------------------------------------


class TestMergeManifest(unittest.TestCase):
    """Execution manifest is persisted with merge details."""

    def test_manifest_persisted_on_success(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            wt = _make_worktree(tmp, "wt-a", {"f.py": "content"})
            dest = tmp / "dest"
            dest.mkdir()
            persisted = {}

            def persist_fn(s, *, plan_id, status, merge):
                persisted.update({"plan_id": plan_id, "status": status, "merge": merge})

            state = _stub_state({"a": _task("a", wt, ["f.py"])})
            kwargs = _make_merge_kwargs(
                dest, state,
                safe_resolve_fn=lambda p: (dest / p).resolve(),
                match_worktree_record_fn=lambda path, branch, inv: {"path": str(wt), "branch": ""},
                persist_execution_manifest_fn=persist_fn,
            )
            merge_runtime(["a"], plan_id="plan-001", **kwargs)

            self.assertEqual(persisted["plan_id"], "plan-001")
            self.assertEqual(persisted["status"], "merged")
            self.assertIn("a", persisted["merge"]["merged_agents"])
        finally:
            shutil.rmtree(tmp)

    def test_no_manifest_when_no_plan_id(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            wt = _make_worktree(tmp, "wt-a", {"f.py": "content"})
            dest = tmp / "dest"
            dest.mkdir()
            persisted = {"called": False}

            def persist_fn(s, **kw):
                persisted["called"] = True

            state = _stub_state({"a": _task("a", wt, ["f.py"])})
            kwargs = _make_merge_kwargs(
                dest, state,
                safe_resolve_fn=lambda p: (dest / p).resolve(),
                match_worktree_record_fn=lambda path, branch, inv: {"path": str(wt), "branch": ""},
                persist_execution_manifest_fn=persist_fn,
            )
            merge_runtime(["a"], plan_id=None, **kwargs)

            self.assertFalse(persisted["called"])
        finally:
            shutil.rmtree(tmp)


# ---------------------------------------------------------------------------
# Backup method
# ---------------------------------------------------------------------------


class TestMergeBackupMethod(unittest.TestCase):
    """Backup method selection: git_stash when available, file_copy otherwise."""

    def test_git_stash_when_git_available(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            state = _stub_state({})
            kwargs = _make_merge_kwargs(
                tmp, state,
                git_worktree_inventory_fn=lambda: {"available": True, "worktrees": []},
                run_git_runtime_fn=lambda cmd: MagicMock(returncode=0, stdout="", stderr=""),
            )
            result = merge_runtime(None, plan_id=None, **kwargs)

            self.assertEqual(result["backup_method"], "git_stash")
        finally:
            shutil.rmtree(tmp)

    def test_file_copy_when_git_unavailable(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            state = _stub_state({})
            kwargs = _make_merge_kwargs(
                tmp, state,
                git_worktree_inventory_fn=lambda: {"available": False, "worktrees": []},
            )
            result = merge_runtime(None, plan_id=None, **kwargs)

            self.assertEqual(result["backup_method"], "file_copy")
        finally:
            shutil.rmtree(tmp)


# ---------------------------------------------------------------------------
# cmd_merge CLI wrapper
# ---------------------------------------------------------------------------

from task_runtime.merge import cmd_merge


class TestCmdMerge(unittest.TestCase):
    """cmd_merge: agent ID parsing, JSON output."""

    def test_json_output(self):
        payload = {"merged": [{"id": "a"}], "conflicts": [], "skipped": [], "cleanup": [], "status": "merged", "backup_method": "none"}
        emitted = {}

        def emit(data):
            emitted.update(data)

        args = MagicMock(agents="a", json=True)
        cmd_merge(args, merge_runtime_fn=lambda ids, **kw: payload, emit_json_fn=emit)

        self.assertEqual(emitted["status"], "merged")

    def test_all_agents_passes_none(self):
        received = {}

        def merge_fn(ids, **kw):
            received["ids"] = ids
            return {"merged": [], "conflicts": [], "skipped": [], "cleanup": [], "status": "nothing_to_merge", "backup_method": "none"}

        args = MagicMock(agents="all", json=False)
        cmd_merge(args, merge_runtime_fn=merge_fn, emit_json_fn=lambda d: None)

        self.assertIsNone(received["ids"])

    def test_comma_separated_agents(self):
        received = {}

        def merge_fn(ids, **kw):
            received["ids"] = ids
            return {"merged": [], "conflicts": [], "skipped": [], "cleanup": [], "status": "nothing_to_merge", "backup_method": "none"}

        args = MagicMock(agents="a,b,c", json=False)
        cmd_merge(args, merge_runtime_fn=merge_fn, emit_json_fn=lambda d: None)

        self.assertEqual(received["ids"], ["a", "b", "c"])


if __name__ == "__main__":
    unittest.main()
