"""Tests for load_state() and save_state()."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import task_manager


class TestStatePersistence(unittest.TestCase):
    """Tests for load_state() and save_state()."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_load_state_missing(self):
        """Returns default state dict when file doesn't exist."""
        fake_path = Path(self._tmpdir) / "nonexistent.json"
        with mock.patch.object(task_manager, "STATE_FILE", fake_path):
            result = task_manager.load_state()
        self.assertEqual(result["version"], 2)
        self.assertEqual(result["tasks"], {})
        self.assertEqual(result["groups"], {})
        self.assertEqual(result["plans"], [])
        self.assertEqual(result["updated_at"], "")

    def test_save_and_load_round_trip(self):
        """Save state, load it, verify equality."""
        state_path = Path(self._tmpdir) / "tasks.json"
        state = {
            "version": 2,
            "tasks": {
                "a": {
                    "id": "a",
                    "name": "schema",
                    "status": "done",
                    "deps": [],
                    "files": ["collector.py"],
                    "group": 0,
                }
            },
            "groups": {"0": ["a"]},
            "plans": [],
            "updated_at": "",
        }
        with mock.patch.object(task_manager, "STATE_FILE", state_path):
            task_manager.save_state(state)
            loaded = task_manager.load_state()

        # Core data should match
        self.assertEqual(loaded["version"], 2)
        self.assertEqual(loaded["tasks"]["a"]["name"], "schema")
        self.assertEqual(loaded["tasks"]["a"]["status"], "done")
        self.assertEqual(loaded["groups"], {"0": ["a"]})
        self.assertEqual(loaded["plans"], [])
        # updated_at should be set by save_state
        self.assertTrue(len(loaded["updated_at"]) > 0)

    def test_save_creates_parent_dirs(self):
        """Saves to a nested path that doesn't exist yet."""
        state_path = Path(self._tmpdir) / "nested" / "deep" / "tasks.json"
        state = {
            "version": 2,
            "tasks": {},
            "groups": {},
            "plans": [],
            "updated_at": "",
        }
        with mock.patch.object(task_manager, "STATE_FILE", state_path):
            task_manager.save_state(state)
        self.assertTrue(state_path.exists())
        loaded = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(loaded["version"], 2)


if __name__ == "__main__":
    unittest.main()
