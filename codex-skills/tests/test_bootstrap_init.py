"""Tests for task_runtime.bootstrap — project init, config generation, and messages."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from task_runtime.bootstrap import (  # noqa: E402
    InitResult,
    build_init_config,
    detect_project_type,
    format_init_messages,
    init_project,
)
from task_runtime.state import TaskRuntimeError  # noqa: E402


def _detected_project(
    name: str = "test",
    *,
    language: str = "python",
    test: str = "",
    compile_cmd: str = "",
    build: str = "",
    has_tests_dir: bool = False,
) -> dict[str, str | bool]:
    return {
        "name": name,
        "language": language,
        "test": test,
        "compile": compile_cmd,
        "build": build,
        "has_tests_dir": has_tests_dir,
    }


# ---------------------------------------------------------------------------
# build_init_config — fallback (no template)
# ---------------------------------------------------------------------------


class TestBuildInitConfigFallback(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_fallback_includes_project_name(self):
        detected = {"name": "my-project", "test": "pytest", "compile": "", "build": ""}
        content, used_template = build_init_config(self.root, detected)
        self.assertFalse(used_template)
        self.assertIn('"my-project"', content)

    def test_fallback_includes_test_command(self):
        detected = {"name": "proj", "test": "python -m pytest", "compile": "", "build": ""}
        content, _ = build_init_config(self.root, detected)
        self.assertIn('test = "python -m pytest"', content)

    def test_fallback_comments_out_empty_commands(self):
        detected = {"name": "proj", "test": "", "compile": "", "build": ""}
        content, _ = build_init_config(self.root, detected)
        self.assertIn("# build", content)

    def test_fallback_includes_models_section(self):
        detected = {"name": "proj", "test": "", "compile": "", "build": ""}
        content, _ = build_init_config(self.root, detected)
        self.assertIn("[models]", content)
        self.assertIn('low = "mini"', content)
        self.assertIn('medium = "standard"', content)
        self.assertIn('high = "max"', content)

    def test_fallback_includes_analysis_section(self):
        detected = {"name": "proj", "test": "", "compile": "", "build": ""}
        content, _ = build_init_config(self.root, detected)
        self.assertIn("[analysis]", content)
        self.assertIn("exclude-globs", content)

    def test_custom_conventions_path(self):
        detected = {"name": "proj", "test": "", "compile": "", "build": ""}
        content, _ = build_init_config(self.root, detected, conventions_path="docs/CONVENTIONS.md")
        self.assertIn("docs/CONVENTIONS.md", content)

    def test_ends_with_newline(self):
        detected = {"name": "proj", "test": "", "compile": "", "build": ""}
        content, _ = build_init_config(self.root, detected)
        self.assertTrue(content.endswith("\n"))


# ---------------------------------------------------------------------------
# build_init_config — template rendering
# ---------------------------------------------------------------------------


class TestBuildInitConfigTemplate(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_template_substitution(self):
        template_path = self.root / "project.toml.template"
        template_path.write_text(
            "[project]\nname = {{PROJECT_NAME}}\nconventions = {{CONVENTIONS_PATH}}\n\n"
            "[commands]\n{{TEST_LINE}}\n{{TEST_FAST_LINE}}\n{{TEST_FULL_LINE}}\n{{COMPILE_LINE}}\n{{BUILD_LINE}}\n",
            encoding="utf-8",
        )
        detected = {"name": "my-app", "test": "pytest", "compile": "pycompile", "build": "make"}
        content, used_template = build_init_config(self.root, detected, template_path=template_path)
        self.assertTrue(used_template)
        self.assertIn('"my-app"', content)
        self.assertIn('test = "pytest"', content)
        self.assertIn('test_fast = "pytest"', content)
        self.assertIn('test_full = "pytest"', content)

    def test_template_not_found_uses_fallback(self):
        detected = {"name": "proj", "test": "", "compile": "", "build": ""}
        # No template file exists at default path
        content, used_template = build_init_config(self.root, detected)
        self.assertFalse(used_template)

    def test_unreadable_template_raises(self):
        template_path = self.root / "bad-template"
        template_path.mkdir()  # Directory, not a file - will fail to read
        detected = {"name": "proj", "test": "", "compile": "", "build": ""}
        with self.assertRaises(TaskRuntimeError):
            build_init_config(self.root, detected, template_path=template_path)

    def test_repo_template_includes_models_section(self):
        detected = {"name": "my-app", "test": "pytest", "compile": "", "build": ""}
        content, used_template = build_init_config(ROOT, detected, template_path=ROOT / "project.toml.template")
        self.assertTrue(used_template)
        self.assertIn("[models]", content)
        self.assertIn('low = "mini"', content)
        self.assertIn('medium = "standard"', content)
        self.assertIn('high = "max"', content)
        self.assertIn("GPT-5.3-Codex-Spark", content)


# ---------------------------------------------------------------------------
# init_project — using DI to avoid real filesystem
# ---------------------------------------------------------------------------


class TestInitProject(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_fresh_init_creates_files(self):
        result = init_project(
            self.root,
            detect_project_type_fn=lambda root: _detected_project(test="pytest"),
            load_toml_file_fn=lambda path: {"paths": {"state": "data/tasks.json", "plans": "data/plans", "specs": "agents"}},
        )
        self.assertTrue(result.config_written)
        self.assertFalse(result.already_initialized)
        self.assertIsNotNone(result.detected)
        self.assertTrue(len(result.created) >= 1)
        self.assertTrue((self.root / "AGENTS.md").exists())

    def test_already_initialized(self):
        # First init
        init_project(
            self.root,
            detect_project_type_fn=lambda root: _detected_project(),
            load_toml_file_fn=lambda path: {},
        )
        # Second init without force
        result = init_project(
            self.root,
            detect_project_type_fn=lambda root: _detected_project(),
            load_toml_file_fn=lambda path: {},
        )
        self.assertFalse(result.config_written)
        self.assertTrue(result.already_initialized)

    def test_force_overwrites(self):
        # First init
        init_project(
            self.root,
            detect_project_type_fn=lambda root: _detected_project(),
            load_toml_file_fn=lambda path: {},
        )
        # Force re-init
        result = init_project(
            self.root,
            force=True,
            detect_project_type_fn=lambda root: _detected_project(name="test-v2"),
            load_toml_file_fn=lambda path: {},
        )
        self.assertTrue(result.config_written)
        self.assertFalse(result.already_initialized)

    def test_creates_required_directories(self):
        result = init_project(
            self.root,
            detect_project_type_fn=lambda root: _detected_project(),
            load_toml_file_fn=lambda path: {"paths": {"specs": "agents", "plans": "data/plans", "state": "data/tasks.json"}},
        )
        self.assertTrue(result.agents_dir.is_dir())
        self.assertTrue(result.plans_dir.is_dir())
        self.assertTrue(result.state_path.parent.is_dir())

    def test_custom_config_path(self):
        custom_path = self.root / "custom" / "config.toml"
        result = init_project(
            self.root,
            config_path=custom_path,
            detect_project_type_fn=lambda root: _detected_project(),
            load_toml_file_fn=lambda path: {},
        )
        self.assertEqual(result.config_path, custom_path)
        self.assertTrue(custom_path.exists())

    def test_custom_conventions_path_creates_stub(self):
        init_project(
            self.root,
            conventions_path="docs/CONVENTIONS.md",
            detect_project_type_fn=lambda root: _detected_project(),
            load_toml_file_fn=lambda path: {
                "project": {"conventions": "docs/CONVENTIONS.md"},
                "paths": {"state": "data/tasks.json", "plans": "data/plans", "specs": "agents"},
            },
        )
        conventions = self.root / "docs" / "CONVENTIONS.md"
        self.assertTrue(conventions.exists())
        self.assertIn("Project Conventions", conventions.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# format_init_messages
# ---------------------------------------------------------------------------


class TestFormatInitMessages(unittest.TestCase):
    def test_new_project_messages(self):
        result = InitResult(
            root=Path("/fake"),
            config_path=Path("/fake/.codex/skills/project.toml"),
            state_path=Path("/fake/data/tasks.json"),
            agents_dir=Path("/fake/agents"),
            plans_dir=Path("/fake/data/plans"),
            created=[".codex/skills/project.toml", "data/tasks.json"],
            detected={"name": "my-proj", "language": "python", "test": "pytest", "compile": "", "build": ""},
            config_written=True,
        )
        lines = format_init_messages(result)
        text = "\n".join(lines)
        self.assertIn("Python", text)
        self.assertIn("pytest", text)
        self.assertIn("Created", text)

    def test_already_initialized_message(self):
        result = InitResult(
            root=Path("/fake"),
            config_path=Path("/fake/.codex/skills/project.toml"),
            state_path=Path("/fake/data/tasks.json"),
            agents_dir=Path("/fake/agents"),
            plans_dir=Path("/fake/data/plans"),
            created=[],
            detected=None,
            config_written=False,
        )
        # config_path must exist for the "already exists" branch
        lines = format_init_messages(result)
        text = "\n".join(lines)
        self.assertIn("already initialized", text)

    def test_unknown_language_shows_next_step(self):
        result = InitResult(
            root=Path("/fake"),
            config_path=Path("/fake/.codex/skills/project.toml"),
            state_path=Path("/fake/data/tasks.json"),
            agents_dir=Path("/fake/agents"),
            plans_dir=Path("/fake/data/plans"),
            created=[".codex/skills/project.toml"],
            detected={"name": "proj", "language": "unknown", "test": "", "compile": "", "build": ""},
            config_written=True,
        )
        lines = format_init_messages(result)
        text = "\n".join(lines)
        self.assertIn("edit", text.lower())
        self.assertIn("test", text.lower())

    def test_config_exists_no_write_shows_use_force(self):
        result = InitResult(
            root=Path("/fake"),
            config_path=Path("/fake/.codex/skills/project.toml"),
            state_path=Path("/fake/data/tasks.json"),
            agents_dir=Path("/fake/agents"),
            plans_dir=Path("/fake/data/plans"),
            created=[],
            detected=None,
            config_written=False,
        )
        # Simulate config file existing
        with unittest.mock.patch.object(Path, "exists", return_value=True):
            lines = format_init_messages(result)
        text = "\n".join(lines)
        self.assertIn("--force", text)

    def test_detected_prefilled_fields(self):
        result = InitResult(
            root=Path("/fake"),
            config_path=Path("/fake/.codex/skills/project.toml"),
            state_path=Path("/fake/data/tasks.json"),
            agents_dir=Path("/fake/agents"),
            plans_dir=Path("/fake/data/plans"),
            created=[".codex/skills/project.toml"],
            detected={"name": "app", "language": "node", "test": "npm test", "compile": "", "build": "npm run build"},
            config_written=True,
        )
        lines = format_init_messages(result)
        text = "\n".join(lines)
        self.assertIn("npm test", text)
        self.assertIn("npm run build", text)
        self.assertIn("Pre-filled", text)


# ---------------------------------------------------------------------------
# detect_project_type (direct tests for untested edge cases)
# ---------------------------------------------------------------------------


class TestDetectProjectTypeEdgeCases(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_unknown_project(self):
        result = detect_project_type(self.root)
        self.assertEqual(result["language"], "unknown")
        self.assertEqual(result["test"], "")

    def test_go_project(self):
        (self.root / "go.mod").write_text("module example.com/foo\n", encoding="utf-8")
        result = detect_project_type(self.root)
        self.assertEqual(result["language"], "go")
        self.assertIn("go test", result["test"])

    def test_rust_project(self):
        (self.root / "Cargo.toml").write_text("[package]\nname = 'test'\n", encoding="utf-8")
        result = detect_project_type(self.root)
        self.assertEqual(result["language"], "rust")
        self.assertIn("cargo test", result["test"])

    def test_has_tests_dir_detection(self):
        (self.root / "tests").mkdir()
        (self.root / "pyproject.toml").write_text("[project]\nname = 'test'\n", encoding="utf-8")
        result = detect_project_type(self.root)
        self.assertTrue(result["has_tests_dir"])
        self.assertIn("tests/", result["test"])

    def test_space_in_project_name(self):
        root = Path(self._tmpdir.name) / "My Project"
        root.mkdir()
        result = detect_project_type(root)
        self.assertEqual(result["name"], "my-project")


# ---------------------------------------------------------------------------
# InitResult dataclass
# ---------------------------------------------------------------------------


class TestInitResult(unittest.TestCase):
    def test_fields(self):
        r = InitResult(
            root=Path("/a"),
            config_path=Path("/a/config.toml"),
            state_path=Path("/a/state.json"),
            agents_dir=Path("/a/agents"),
            plans_dir=Path("/a/plans"),
        )
        self.assertEqual(r.created, [])
        self.assertIsNone(r.detected)
        self.assertFalse(r.config_written)
        self.assertFalse(r.already_initialized)
        self.assertFalse(r.used_template)


if __name__ == "__main__":
    unittest.main()
