"""Direct tests for task_runtime.config and Node detection branches."""

from __future__ import annotations

import builtins
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from task_runtime.bootstrap import detect_project_type  # noqa: E402
from task_runtime.config import (  # noqa: E402
    config_path,
    derive_runtime_paths,
    load_config,
    load_toml_file,
)


class TestConfigDirect(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _write_toml(self, name: str = "project.toml", content: str = '[project]\nname = "demo"\n') -> Path:
        path = self.root / name
        path.write_text(content, encoding="utf-8")
        return path

    def test_load_toml_file_uses_tomli_when_tomllib_missing(self):
        path = self._write_toml()
        real_import = builtins.__import__
        fake_tomli = types.SimpleNamespace(load=lambda handle: {"project": {"name": "tomli"}})

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "tomllib":
                raise ModuleNotFoundError("no tomllib")
            return real_import(name, globals, locals, fromlist, level)

        with mock.patch("builtins.__import__", side_effect=fake_import):
            with mock.patch.dict(sys.modules, {"tomli": fake_tomli}):
                result = load_toml_file(path)

        self.assertEqual(result["project"]["name"], "tomli")

    def test_load_toml_file_falls_back_to_simple_parser(self):
        path = self._write_toml(content='[project]\nname = "fallback"\n')
        real_import = builtins.__import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name in {"tomllib", "tomli"}:
                raise ModuleNotFoundError(name)
            return real_import(name, globals, locals, fromlist, level)

        with mock.patch("builtins.__import__", side_effect=fake_import):
            with mock.patch("task_runtime.config.parse_toml_simple", return_value={"project": {"name": "fallback"}}) as fallback:
                result = load_toml_file(path)

        fallback.assert_called_once_with(path)
        self.assertEqual(result["project"]["name"], "fallback")

    def test_config_path_and_load_config_delegate_for_existing_files(self):
        path = config_path(self.root, "config/project.toml")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('[project]\nname = "demo"\n', encoding="utf-8")

        with mock.patch("task_runtime.config.load_toml_file", return_value={"project": {"name": "demo"}}) as loader:
            result = load_config(path)

        loader.assert_called_once_with(path)
        self.assertEqual(result["project"]["name"], "demo")

    def test_derive_runtime_paths_handles_disabled_tracker(self):
        result = derive_runtime_paths(
            self.root,
            {"paths": {"specs": "crew", "plans": "plans", "state": "state.json", "tracker": ""}},
        )

        self.assertEqual(result["agents_dir"], self.root / "crew")
        self.assertEqual(result["plans_dir"], self.root / "plans")
        self.assertEqual(result["state_file"], self.root / "state.json")
        self.assertEqual(result["analysis_cache_file"], self.root / "data" / "analysis-cache.json")
        self.assertEqual(result["tracker_path"], "")
        self.assertIsNone(result["tracker_file"])


class TestNodeProjectDetection(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _write_package_json(self, payload: dict | str) -> None:
        text = payload if isinstance(payload, str) else json.dumps(payload)
        (self.root / "package.json").write_text(text, encoding="utf-8")

    def test_detect_project_type_uses_package_scripts(self):
        self._write_package_json({"scripts": {"test": "vitest run", "build": "vite build"}})

        result = detect_project_type(self.root)

        self.assertEqual(result["language"], "node")
        self.assertEqual(result["test"], "npm test")
        self.assertEqual(result["build"], "npm run build")

    def test_detect_project_type_falls_back_to_vitest_dependency(self):
        self._write_package_json({"devDependencies": {"vitest": "^2.0.0"}})

        result = detect_project_type(self.root)

        self.assertEqual(result["test"], "npx vitest")
        self.assertEqual(result["build"], "")

    def test_detect_project_type_falls_back_to_jest_dependency(self):
        self._write_package_json({"dependencies": {"jest": "^29.0.0"}})

        result = detect_project_type(self.root)

        self.assertEqual(result["test"], "npx jest")
        self.assertEqual(result["build"], "")

    def test_detect_project_type_tolerates_malformed_package_json(self):
        self._write_package_json("{not-json")

        result = detect_project_type(self.root)

        self.assertEqual(result["language"], "node")
        self.assertEqual(result["test"], "")
        self.assertEqual(result["build"], "")


if __name__ == "__main__":
    unittest.main()
