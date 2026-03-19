"""Focused failure-path tests for task_runtime.state."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from task_runtime.state import atomic_write  # noqa: E402


class TestAtomicWriteEdgeCases(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_atomic_write_uses_fchmod_on_non_windows(self):
        target = self.root / "state.json"

        with mock.patch("task_runtime.state.os.name", "posix"), mock.patch("task_runtime.state.os.fchmod", create=True) as chmod:
            atomic_write(target, "content")

        chmod.assert_called_once()
        self.assertEqual(target.read_text(encoding="utf-8"), "content")

    def test_atomic_write_cleans_up_temp_file_when_write_fails(self):
        target = self.root / "broken.json"

        with mock.patch("task_runtime.state.os.write", side_effect=OSError("write failed")):
            with self.assertRaises(OSError):
                atomic_write(target, "content")

        self.assertEqual(list(self.root.glob("*.tmp")), [])
        self.assertFalse(target.exists())

    def test_atomic_write_cleans_up_temp_file_when_replace_fails(self):
        target = self.root / "broken.json"

        with mock.patch("task_runtime.state.os.replace", side_effect=OSError("replace failed")):
            with self.assertRaises(OSError):
                atomic_write(target, "content")

        self.assertEqual(list(self.root.glob("*.tmp")), [])
        self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
