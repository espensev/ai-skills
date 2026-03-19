"""Tests for _load_config(), auto-discovery, and project detection heuristics."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import task_manager
from task_runtime.config import get_conflict_zones, get_first_party, get_module_map


class TestConfigLoading(unittest.TestCase):
    """Tests for _load_config() and related auto-discovery functions."""

    def test_load_config_missing_file(self):
        """With _CONFIG_PATH pointing to nonexistent path, returns {}."""
        fake_path = Path(tempfile.gettempdir()) / "nonexistent_project.toml"
        with mock.patch.object(task_manager, "_CONFIG_PATH", fake_path):
            result = task_manager._load_config()
        self.assertEqual(result, {})

    def test_load_config_valid_file(self):
        """With a temp project.toml, loads correctly."""
        content = '[project]\nname = "TestProject"\n'
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False, encoding="utf-8") as f:
            f.write(content)
            f.flush()
            tmp_path = Path(f.name)
        try:
            with mock.patch.object(task_manager, "_CONFIG_PATH", tmp_path):
                result = task_manager._load_config()
            self.assertIn("project", result)
            self.assertEqual(result["project"]["name"], "TestProject")
        finally:
            os.unlink(tmp_path)

    def test_get_module_map_from_config(self):
        """With config containing [modules], returns configured map."""
        cfg = {"modules": {"core": ["app.py", "collector.py"], "tests": ["tests/"]}}
        result = get_module_map(task_manager.ROOT, cfg)
        self.assertEqual(result, cfg["modules"])

    def test_get_module_map_auto_discovery(self):
        """With empty config, auto-discovers from filesystem."""
        result = get_module_map(task_manager.ROOT, {})
        self.assertIsInstance(result, dict)
        if list(task_manager.ROOT.glob("*.py")):
            self.assertIn("core", result)

    def test_get_first_party_from_config(self):
        """Returns stems from modules.core list."""
        cfg = {"modules": {"core": ["app.py", "collector.py", "pricing.py"]}}
        result = get_first_party(task_manager.ROOT, cfg)
        self.assertEqual(result, {"app", "collector", "pricing"})

    def test_get_first_party_auto_discovery(self):
        """With empty config, scans .py files in root."""
        result = get_first_party(task_manager.ROOT, {})
        self.assertIsInstance(result, set)
        if list(task_manager.ROOT.glob("*.py")):
            self.assertTrue(len(result) > 0)

    def test_get_conflict_zones_from_config(self):
        """Parses 'a.py, b.py | reason' format."""
        cfg = {"conflict-zones": {"zones": ["a.py, b.py | mutual imports"]}}
        result = get_conflict_zones(cfg)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["files"], ["a.py", "b.py"])
        self.assertEqual(result[0]["reason"], "mutual imports")

    def test_get_conflict_zones_empty(self):
        """Returns [] when no config."""
        result = get_conflict_zones({})
        self.assertEqual(result, [])


class TestProjectDetection(unittest.TestCase):
    """Tests for init-time project detection heuristics."""

    def test_detect_project_type_cpp_from_cmake(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "CMakeLists.txt").write_text("cmake_minimum_required(VERSION 3.28)\n", encoding="utf-8")
            detected = task_manager._detect_project_type(root)

        self.assertEqual(detected["language"], "cpp")
        self.assertEqual(detected["build"], "cmake --build build")
        self.assertEqual(detected["test"], "ctest --test-dir build --output-on-failure")

    def test_detect_project_type_dotnet_from_nested_slnx(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "Demo.slnx").write_text("<Solution></Solution>\n", encoding="utf-8")
            detected = task_manager._detect_project_type(root)

        self.assertEqual(detected["language"], "dotnet")
        self.assertEqual(detected["build"], "dotnet build")
        self.assertEqual(detected["test"], "dotnet test")

    def test_detect_project_type_cpp_from_vcxproj_solution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "Native.sln").write_text(
                "Microsoft Visual Studio Solution File, Format Version 12.00\n",
                encoding="utf-8",
            )
            (root / "src" / "App.vcxproj").write_text("<Project></Project>\n", encoding="utf-8")
            detected = task_manager._detect_project_type(root)

        self.assertEqual(detected["language"], "cpp")
        self.assertEqual(detected["build"], "")
        self.assertEqual(detected["test"], "")


if __name__ == "__main__":
    unittest.main()
