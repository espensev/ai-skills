"""Tests for _parse_toml_simple() — the fallback TOML parser."""

import os
import tempfile
import unittest
from pathlib import Path

from task_runtime import parse_toml_simple


class TestTomlParser(unittest.TestCase):
    """Tests for parse_toml_simple() — the fallback TOML parser."""

    def _parse(self, content: str) -> dict:
        """Helper: write content to a temp file and parse it."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False, encoding="utf-8") as f:
            f.write(content)
            f.flush()
            tmp_path = Path(f.name)
        try:
            return parse_toml_simple(tmp_path)
        finally:
            os.unlink(tmp_path)

    def test_simple_string(self):
        result = self._parse('[project]\nname = "My App"\n')
        self.assertEqual(result["project"]["name"], "My App")

    def test_string_array_single_line(self):
        result = self._parse('[modules]\ncore = ["a.py", "b.py"]\n')
        self.assertEqual(result["modules"]["core"], ["a.py", "b.py"])

    def test_string_array_multiline(self):
        result = self._parse('[modules]\ncore = [\n  "a.py",\n  "b.py",\n]\n')
        self.assertEqual(result["modules"]["core"], ["a.py", "b.py"])

    def test_string_array_multiline_trailing_comma(self):
        result = self._parse('[modules]\ncore = [\n  "a.py",\n  "b.py",\n]\n')
        self.assertEqual(result["modules"]["core"], ["a.py", "b.py"])

    def test_boolean_true(self):
        result = self._parse("[flags]\nverbose = true\n")
        self.assertTrue(result["flags"]["verbose"])

    def test_boolean_false(self):
        result = self._parse("[flags]\nverbose = false\n")
        self.assertFalse(result["flags"]["verbose"])

    def test_integer_value(self):
        result = self._parse("[project]\nversion = 3\n")
        self.assertEqual(result["project"]["version"], "3")

    def test_empty_string(self):
        result = self._parse('[project]\nname = ""\n')
        self.assertEqual(result["project"]["name"], "")

    def test_multiple_sections(self):
        result = self._parse('[project]\nname = "A"\n[commands]\ntest = "pytest"\n')
        self.assertEqual(result["project"]["name"], "A")
        self.assertEqual(result["commands"]["test"], "pytest")

    def test_comments_ignored(self):
        result = self._parse('# Comment line\n[project]\n# Another comment\nname = "Test"\n')
        self.assertEqual(result["project"]["name"], "Test")

    def test_empty_file(self):
        result = self._parse("")
        self.assertEqual(result, {})

    def test_section_with_no_values(self):
        result = self._parse('[empty_section]\n[project]\nname = "Test"\n')
        self.assertEqual(result["empty_section"], {})
        self.assertEqual(result["project"]["name"], "Test")

    def test_pipe_delimited_string_preserved(self):
        result = self._parse('[conflict-zones]\nzones = ["a.py, b.py | mutual imports"]\n')
        self.assertEqual(result["conflict-zones"]["zones"], ["a.py, b.py | mutual imports"])

    def test_quoted_string_with_spaces(self):
        result = self._parse('[project]\nname = "My Complex App Name"\n')
        self.assertEqual(result["project"]["name"], "My Complex App Name")

    def test_multiline_array_with_pipes(self):
        result = self._parse('[conflict-zones]\nzones = [\n  "a.py, b.py | reason one",\n  "c.py, d.py | reason two",\n]\n')
        self.assertEqual(len(result["conflict-zones"]["zones"]), 2)
        self.assertEqual(result["conflict-zones"]["zones"][0], "a.py, b.py | reason one")


if __name__ == "__main__":
    unittest.main()
