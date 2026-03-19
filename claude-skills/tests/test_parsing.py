"""Tests for parse_spec_file(), parse_tracker(), _build_tracker_prefix_map()."""

import shutil
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

import task_manager


class TestParsing(unittest.TestCase):
    """Tests for parse_spec_file(), parse_tracker(), _build_tracker_prefix_map()."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_parse_spec_file(self):
        """Create a minimal spec markdown, verify title/scope/deps/files extracted."""
        spec_content = textwrap.dedent("""\
            # Agent Task — Schema Migration

            **Scope:** Add v7 migration block to init_db()

            **Depends on:** Agent A, Agent B

            **Output files:** `collector.py`, `tests/test_schema.py`

            ---

            ## Task

            Do stuff.
        """)
        spec_path = Path(self._tmpdir) / "agent-c-schema.md"
        spec_path.write_text(spec_content, encoding="utf-8")

        with mock.patch.object(task_manager, "ROOT", Path(self._tmpdir)):
            result = task_manager.parse_spec_file(spec_path)

        self.assertEqual(result["title"], "Schema Migration")
        self.assertEqual(result["scope"], "Add v7 migration block to init_db()")
        self.assertEqual(result["deps"], ["a", "b"])
        self.assertEqual(result["files"], ["collector.py", "tests/test_schema.py"])

    def test_parse_spec_file_no_deps(self):
        """Spec with 'Depends on: (none)' returns no deps."""
        spec_content = textwrap.dedent("""\
            # Agent Task — Bootstrap

            **Scope:** Initial setup

            **Depends on:** (none)

            **Output files:** `setup.py`
        """)
        spec_path = Path(self._tmpdir) / "agent-a-bootstrap.md"
        spec_path.write_text(spec_content, encoding="utf-8")

        with mock.patch.object(task_manager, "ROOT", Path(self._tmpdir)):
            result = task_manager.parse_spec_file(spec_path)

        self.assertEqual(result["title"], "Bootstrap")
        self.assertNotIn("deps", result)
        self.assertEqual(result["files"], ["setup.py"])

    def test_parse_spec_file_no_output_files(self):
        spec_content = textwrap.dedent("""\
            # Agent Task — Bootstrap

            **Scope:** Initial setup

            **Depends on:** (none)

            **Output files:** (none)
        """)
        spec_path = Path(self._tmpdir) / "agent-a-bootstrap.md"
        spec_path.write_text(spec_content, encoding="utf-8")

        with mock.patch.object(task_manager, "ROOT", Path(self._tmpdir)):
            result = task_manager.parse_spec_file(spec_path)

        self.assertEqual(result["title"], "Bootstrap")
        self.assertNotIn("deps", result)
        self.assertNotIn("files", result)

    def test_parse_tracker(self):
        """Create a tracker markdown with table rows, verify parsing."""
        tracker_content = textwrap.dedent("""\
            # Live Tracker

            | ID | Status | Owner | Scope | Issue | Update |
            |---|---|---|---|---|---|
            | SCHEMA-001 | Done | agent-a | `collector.py` | Add migration | Added v7 block |
            | SESSION-002 | In-progress | agent-b | `app.py` | Session sync | Working on it |
        """)
        tracker_path = Path(self._tmpdir) / "live-tracker.md"
        tracker_path.write_text(tracker_content, encoding="utf-8")

        with mock.patch.object(task_manager, "TRACKER_FILE", tracker_path):
            result = task_manager.parse_tracker()

        self.assertIn("SCHEMA-001", result)
        self.assertEqual(result["SCHEMA-001"]["status"], "done")
        self.assertEqual(result["SCHEMA-001"]["owner"], "agent-a")
        self.assertEqual(result["SCHEMA-001"]["update"], "Added v7 block")

        self.assertIn("SESSION-002", result)
        self.assertEqual(result["SESSION-002"]["status"], "running")

    def test_build_tracker_prefix_map(self):
        """Given state with named tasks, verify prefix -> letter mapping."""
        state = {
            "tasks": {
                "a": {"id": "a", "name": "schema"},
                "b": {"id": "b", "name": "session-analytics"},
                "c": {"id": "c", "name": "health-ui"},
            }
        }
        result = task_manager._build_tracker_prefix_map(state)
        # First segment of kebab-case name uppercased
        self.assertEqual(result["SCHEMA"], "a")
        self.assertEqual(result["SESSION"], "b")
        self.assertEqual(result["HEALTH"], "c")
        # Full name uppercased for multi-word
        self.assertEqual(result["SESSION-ANALYTICS"], "b")
        self.assertEqual(result["HEALTH-UI"], "c")


if __name__ == "__main__":
    unittest.main()
