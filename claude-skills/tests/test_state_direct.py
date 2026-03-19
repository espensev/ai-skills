"""Direct tests for task_runtime.state — atomic writes, path safety, state lifecycle."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from task_runtime.state import (  # noqa: E402
    TaskRuntimeError,
    atomic_write,
    default_state,
    empty_execution_manifest,
    load_state,
    now_iso,
    relative_path,
    safe_resolve,
    save_state,
    write_state_file,
)

# ---------------------------------------------------------------------------
# empty_execution_manifest
# ---------------------------------------------------------------------------


class TestEmptyExecutionManifest(unittest.TestCase):
    def test_structure(self):
        m = empty_execution_manifest()
        self.assertIn("plan_id", m)
        self.assertIn("launch", m)
        self.assertIn("merge", m)
        self.assertIn("verify", m)
        self.assertEqual(m["launch"]["launched"], [])
        self.assertIsNone(m["verify"]["passed"])


# ---------------------------------------------------------------------------
# default_state
# ---------------------------------------------------------------------------


class TestDefaultState(unittest.TestCase):
    def test_structure(self):
        s = default_state()
        self.assertEqual(s["version"], 2)
        self.assertIsInstance(s["tasks"], dict)
        self.assertIsInstance(s["plans"], list)
        self.assertIn("execution_manifest", s)

    def test_returns_fresh_copy(self):
        s1 = default_state()
        s2 = default_state()
        s1["tasks"]["x"] = "modified"
        self.assertNotIn("x", s2["tasks"])


# ---------------------------------------------------------------------------
# relative_path
# ---------------------------------------------------------------------------


class TestRelativePath(unittest.TestCase):
    def test_normal(self):
        root = Path("/project")
        path = Path("/project/src/main.py")
        self.assertEqual(relative_path(path, root), "src/main.py")

    def test_outside_root_returns_full_path(self):
        root = Path("/project")
        path = Path("/other/file.py")
        result = relative_path(path, root)
        self.assertIn("other", result)

    def test_backslash_normalized(self):
        # On Windows, paths may use backslashes
        root = Path("C:/project")
        path = Path("C:/project/src/file.py")
        result = relative_path(path, root)
        self.assertNotIn("\\", result)


# ---------------------------------------------------------------------------
# safe_resolve
# ---------------------------------------------------------------------------


class TestSafeResolve(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_normal_path(self):
        result = safe_resolve("src/main.py", self.root)
        self.assertTrue(str(result).startswith(str(self.root.resolve())))

    def test_traversal_blocked(self):
        with self.assertRaises(TaskRuntimeError) as ctx:
            safe_resolve("../../etc/passwd", self.root)
        self.assertIn("escapes", str(ctx.exception))

    def test_nested_path(self):
        result = safe_resolve("a/b/c/d.txt", self.root)
        self.assertTrue(str(result).endswith("d.txt"))

    def test_path_object_accepted(self):
        result = safe_resolve(Path("data/state.json"), self.root)
        self.assertTrue(str(result).endswith("state.json"))


# ---------------------------------------------------------------------------
# atomic_write
# ---------------------------------------------------------------------------


class TestAtomicWrite(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_writes_content(self):
        target = self.root / "test.txt"
        atomic_write(target, "hello world")
        self.assertEqual(target.read_text(encoding="utf-8"), "hello world")

    def test_creates_parent_directories(self):
        target = self.root / "a" / "b" / "c" / "file.txt"
        atomic_write(target, "nested")
        self.assertEqual(target.read_text(encoding="utf-8"), "nested")

    def test_overwrites_existing(self):
        target = self.root / "overwrite.txt"
        atomic_write(target, "first")
        atomic_write(target, "second")
        self.assertEqual(target.read_text(encoding="utf-8"), "second")

    def test_unicode_content(self):
        target = self.root / "unicode.txt"
        atomic_write(target, "emoji: \u2713 check")
        self.assertIn("\u2713", target.read_text(encoding="utf-8"))

    def test_no_temp_file_left_on_success(self):
        target = self.root / "clean.txt"
        atomic_write(target, "data")
        tmp_files = list(self.root.glob("*.tmp"))
        self.assertEqual(len(tmp_files), 0)


# ---------------------------------------------------------------------------
# now_iso
# ---------------------------------------------------------------------------


class TestNowIso(unittest.TestCase):
    def test_returns_string(self):
        result = now_iso()
        self.assertIsInstance(result, str)

    def test_parseable_iso_format(self):
        result = now_iso()
        parsed = datetime.fromisoformat(result)
        self.assertEqual(parsed.tzinfo, timezone.utc)

    def test_seconds_precision(self):
        result = now_iso()
        # Should not contain microseconds
        self.assertNotIn(".", result.split("+")[0])


# ---------------------------------------------------------------------------
# write_state_file
# ---------------------------------------------------------------------------


class TestWriteStateFile(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_writes_json(self):
        state_file = self.root / "state.json"
        state = {"version": 2, "tasks": {}}
        write_state_file(state_file, state)
        loaded = json.loads(state_file.read_text(encoding="utf-8"))
        self.assertEqual(loaded["version"], 2)

    def test_updates_timestamp_by_default(self):
        state_file = self.root / "state.json"
        state = {"version": 2, "tasks": {}}
        write_state_file(state_file, state)
        self.assertIn("updated_at", state)
        self.assertTrue(len(state["updated_at"]) > 0)

    def test_skip_timestamp_update(self):
        state_file = self.root / "state.json"
        state = {"version": 2, "tasks": {}, "updated_at": "original"}
        write_state_file(state_file, state, update_timestamp=False)
        self.assertEqual(state["updated_at"], "original")


# ---------------------------------------------------------------------------
# load_state
# ---------------------------------------------------------------------------


class TestLoadState(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_missing_file_returns_default(self):
        state_file = self.root / "nonexistent.json"
        state = load_state(state_file)
        self.assertEqual(state["version"], 2)
        self.assertIsInstance(state["tasks"], dict)

    def test_reads_existing_file(self):
        state_file = self.root / "state.json"
        state_file.write_text(
            json.dumps({"version": 2, "tasks": {"a": {"id": "a"}}, "plans": []}),
            encoding="utf-8",
        )
        state = load_state(state_file)
        self.assertIn("a", state["tasks"])

    def test_corrupt_file_raises(self):
        state_file = self.root / "bad.json"
        state_file.write_text("not json at all", encoding="utf-8")
        with self.assertRaises(TaskRuntimeError):
            load_state(state_file)

    def test_normalize_called(self):
        state_file = self.root / "state.json"
        state_file.write_text(json.dumps({"version": 2, "tasks": {}, "plans": []}), encoding="utf-8")
        normalized = [False]

        def fake_normalize(state):
            state["normalized"] = True
            normalized[0] = True
            return True  # signal migration happened

        state = load_state(state_file, normalize_state=fake_normalize)
        self.assertTrue(state.get("normalized"))

    def test_migration_triggers_write_back(self):
        state_file = self.root / "state.json"
        state_file.write_text(json.dumps({"version": 1, "tasks": {}, "plans": []}), encoding="utf-8")
        write_back_calls = []

        def fake_normalize(state):
            state["version"] = 2
            return True

        def fake_write_back(state, update_timestamp=False):
            write_back_calls.append(state["version"])

        load_state(state_file, normalize_state=fake_normalize, write_back=fake_write_back)
        self.assertEqual(write_back_calls, [2])

    def test_no_migration_skips_write_back(self):
        state_file = self.root / "state.json"
        state_file.write_text(json.dumps({"version": 2, "tasks": {}, "plans": []}), encoding="utf-8")
        write_back_calls = []

        def no_migration(state):
            return False

        def track_write(state, update_timestamp=False):
            write_back_calls.append(True)

        load_state(state_file, normalize_state=no_migration, write_back=track_write)
        self.assertEqual(len(write_back_calls), 0)


# ---------------------------------------------------------------------------
# save_state
# ---------------------------------------------------------------------------


class TestSaveState(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_round_trip(self):
        state_file = self.root / "state.json"
        original = default_state()
        original["tasks"]["x"] = {"id": "x", "name": "test"}
        save_state(state_file, original)
        loaded = load_state(state_file)
        self.assertIn("x", loaded["tasks"])

    def test_normalize_called_on_save(self):
        state_file = self.root / "state.json"
        state = default_state()
        normalized = [False]

        def fake_normalize(s):
            normalized[0] = True

        save_state(state_file, state, normalize_state=fake_normalize)
        self.assertTrue(normalized[0])

    def test_custom_write_back(self):
        state_file = self.root / "state.json"
        state = default_state()
        calls = []

        def custom_writer(s, update_timestamp=True):
            calls.append(update_timestamp)

        save_state(state_file, state, write_back=custom_writer)
        self.assertEqual(calls, [True])


# ---------------------------------------------------------------------------
# TaskRuntimeError
# ---------------------------------------------------------------------------


class TestTaskRuntimeError(unittest.TestCase):
    def test_is_runtime_error(self):
        self.assertTrue(issubclass(TaskRuntimeError, RuntimeError))

    def test_message(self):
        err = TaskRuntimeError("test error")
        self.assertEqual(str(err), "test error")


if __name__ == "__main__":
    unittest.main()
