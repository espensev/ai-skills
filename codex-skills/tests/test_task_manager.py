# ruff: noqa: E402
"""Tests for scripts/task_manager.py — campaign orchestration backend."""

import argparse
import io
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

# Add project root to path so we can import task_manager
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import task_manager
from analysis import dotnet_cli_provider
from analysis.models import ANALYSIS_SCHEMA_VERSION
from task_runtime.config import get_conflict_zones, get_first_party, get_module_map

# ---------------------------------------------------------------------------
# Part 2 — TOML parsing tests
# ---------------------------------------------------------------------------


class TestTomlParser(unittest.TestCase):
    """Tests for _parse_toml_simple() — the fallback TOML parser."""

    def _parse(self, content: str) -> dict:
        """Helper: write content to a temp file and parse it."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False, encoding="utf-8") as f:
            f.write(content)
            f.flush()
            tmp_path = Path(f.name)
        try:
            return task_manager._parse_toml_simple(tmp_path)
        finally:
            os.unlink(tmp_path)

    def test_simple_string(self):
        result = self._parse('[project]\nname = "My App"\n')
        self.assertEqual(result["project"]["name"], "My App")

    def test_string_array_single_line(self):
        result = self._parse('[modules]\ncore = ["a.py", "b.py"]\n')
        self.assertEqual(result["modules"]["core"], ["a.py", "b.py"])

    def test_string_array_multi_line(self):
        content = textwrap.dedent("""\
            [modules]
            core = [
                "alpha.py",
                "beta.py",
                "gamma.py",
            ]
        """)
        result = self._parse(content)
        self.assertEqual(result["modules"]["core"], ["alpha.py", "beta.py", "gamma.py"])

    def test_boolean_values(self):
        content = "[flags]\nenabled = true\ndisabled = false\n"
        result = self._parse(content)
        self.assertIs(result["flags"]["enabled"], True)
        self.assertIs(result["flags"]["disabled"], False)

    def test_comments_ignored(self):
        content = '# This is a comment\n[project]\n# Another comment\nname = "Test"\n'
        result = self._parse(content)
        self.assertEqual(result["project"]["name"], "Test")
        # Comments should not appear as keys anywhere
        for section in result.values():
            if isinstance(section, dict):
                for key in section:
                    self.assertFalse(key.startswith("#"))

    def test_empty_file(self):
        result = self._parse("")
        self.assertEqual(result, {})

    def test_multiple_sections(self):
        content = textwrap.dedent("""\
            [project]
            name = "Dashboard"

            [paths]
            state = "data/tasks.json"
            specs = "agents/"
        """)
        result = self._parse(content)
        self.assertIn("project", result)
        self.assertIn("paths", result)
        self.assertEqual(result["project"]["name"], "Dashboard")
        self.assertEqual(result["paths"]["state"], "data/tasks.json")
        self.assertEqual(result["paths"]["specs"], "agents/")

    def test_conflict_zones_format(self):
        """Parse the 'file1, file2 | reason' format via get_conflict_zones()."""
        cfg = {
            "conflict-zones": {
                "zones": [
                    "app.py, collector.py | shared DB schema",
                    "static/index.html, app.py | API contract",
                ]
            }
        }
        zones = get_conflict_zones(cfg)
        self.assertEqual(len(zones), 2)
        self.assertEqual(zones[0]["files"], ["app.py", "collector.py"])
        self.assertEqual(zones[0]["reason"], "shared DB schema")
        self.assertEqual(zones[1]["files"], ["static/index.html", "app.py"])
        self.assertEqual(zones[1]["reason"], "API contract")


# ---------------------------------------------------------------------------
# Part 3 — Config loading tests
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Part 4 — State persistence tests
# ---------------------------------------------------------------------------


class TestStatePersistence(unittest.TestCase):
    """Tests for load_state() and save_state()."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil

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


# ---------------------------------------------------------------------------
# Part 5 — Parsing tests
# ---------------------------------------------------------------------------


class TestParsing(unittest.TestCase):
    """Tests for parse_spec_file(), parse_tracker(), _build_tracker_prefix_map()."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil

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


# ---------------------------------------------------------------------------
# Part 6 — Plan lifecycle tests
# ---------------------------------------------------------------------------


class TestPlanLifecycle(unittest.TestCase):
    """Tests for _plan_assign_groups() — plan agent group assignment."""

    def test_plan_assign_groups_no_deps(self):
        """All agents with no deps get group 0."""
        plan = {
            "agents": [
                {"letter": "a", "name": "alpha", "deps": []},
                {"letter": "b", "name": "beta", "deps": []},
                {"letter": "c", "name": "gamma", "deps": []},
            ],
            "groups": {},
        }
        task_manager._plan_assign_groups(plan)

        for a in plan["agents"]:
            self.assertEqual(a["group"], 0, f"Agent {a['letter']} should be group 0")
        self.assertEqual(plan["groups"], {"0": ["a", "b", "c"]})

    def test_plan_assign_groups_chain(self):
        """A -> B -> C gets groups 0, 1, 2."""
        plan = {
            "agents": [
                {"letter": "a", "name": "first", "deps": []},
                {"letter": "b", "name": "second", "deps": ["a"]},
                {"letter": "c", "name": "third", "deps": ["b"]},
            ],
            "groups": {},
        }
        task_manager._plan_assign_groups(plan)

        agents_by_letter = {a["letter"]: a for a in plan["agents"]}
        self.assertEqual(agents_by_letter["a"]["group"], 0)
        self.assertEqual(agents_by_letter["b"]["group"], 1)
        self.assertEqual(agents_by_letter["c"]["group"], 2)
        self.assertEqual(plan["groups"]["0"], ["a"])
        self.assertEqual(plan["groups"]["1"], ["b"])
        self.assertEqual(plan["groups"]["2"], ["c"])

    def test_plan_assign_groups_diamond(self):
        """A -> C, B -> C — C gets group 1 (max dep depth + 1)."""
        plan = {
            "agents": [
                {"letter": "a", "name": "left", "deps": []},
                {"letter": "b", "name": "right", "deps": []},
                {"letter": "c", "name": "merge", "deps": ["a", "b"]},
            ],
            "groups": {},
        }
        task_manager._plan_assign_groups(plan)

        agents_by_letter = {a["letter"]: a for a in plan["agents"]}
        self.assertEqual(agents_by_letter["a"]["group"], 0)
        self.assertEqual(agents_by_letter["b"]["group"], 0)
        self.assertEqual(agents_by_letter["c"]["group"], 1)
        self.assertIn("a", plan["groups"]["0"])
        self.assertIn("b", plan["groups"]["0"])
        self.assertEqual(plan["groups"]["1"], ["c"])


# ---------------------------------------------------------------------------
# Part 7 — Analyze tests
# ---------------------------------------------------------------------------


class TestAnalyze(unittest.TestCase):
    """Tests for analyze_project() — project scanning and analysis."""

    def test_analyze_returns_structure(self):
        """Verify analyze_project() returns dict with expected keys."""
        result = task_manager.analyze_project()

        self.assertIsInstance(result, dict)
        # Required top-level keys
        for key in ("root", "files", "totals", "modules", "conflict_zones", "dependency_edges", "project_graph", "analysis_v2"):
            self.assertIn(key, result, f"Missing key: {key}")

        # totals should have files and lines
        self.assertIn("files", result["totals"])
        self.assertIn("lines", result["totals"])
        self.assertIsInstance(result["totals"]["files"], int)
        self.assertIsInstance(result["totals"]["lines"], int)
        self.assertGreater(result["totals"]["files"], 0)
        self.assertGreater(result["totals"]["lines"], 0)

        # files should be a list of dicts
        self.assertIsInstance(result["files"], list)
        self.assertTrue(len(result["files"]) > 0)
        first_file = result["files"][0]
        self.assertIn("path", first_file)
        self.assertIn("lines", first_file)
        self.assertIn("category", first_file)

        # modules should be a dict of dicts
        self.assertIsInstance(result["modules"], dict)
        for cat, info in result["modules"].items():
            self.assertIn("file_count", info)
            self.assertIn("total_lines", info)
            self.assertIn("files", info)

        # conflict_zones should be a list
        self.assertIsInstance(result["conflict_zones"], list)

        # dependency_edges should be a list
        self.assertIsInstance(result["dependency_edges"], list)

        # root should be a string path
        self.assertIsInstance(result["root"], str)
        self.assertEqual(result["analysis_v2"]["schema_version"], ANALYSIS_SCHEMA_VERSION)
        self.assertIn("inventory", result["analysis_v2"])
        self.assertIn("graphs", result["analysis_v2"])
        self.assertIn("signals", result["analysis_v2"])
        self.assertIn("derived", result["analysis_v2"])
        self.assertIn("planning_context", result["analysis_v2"])

    def test_analyze_detects_dotnet_xaml_and_cpp_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "App").mkdir()
            (root / "Lib").mkdir()
            (root / "Package").mkdir()
            (root / "Native" / "src").mkdir(parents=True)
            (root / "Native" / "include").mkdir(parents=True)

            (root / "Demo.sln").write_text(
                textwrap.dedent(
                    """\
                    Microsoft Visual Studio Solution File, Format Version 12.00
                    Project("{FAKE-TYPE}") = "App", "App\\App.csproj", "{APP-GUID}"
                    EndProject
                    Project("{FAKE-TYPE}") = "Lib", "Lib\\Lib.csproj", "{LIB-GUID}"
                    EndProject
                    Project("{FAKE-TYPE}") = "Package", "Package\\App.Package.wapproj", "{PACKAGE-GUID}"
                    EndProject
                    """
                ),
                encoding="utf-8",
            )

            (root / "App" / "App.csproj").write_text(
                textwrap.dedent(
                    """\
                    <Project Sdk="Microsoft.NET.Sdk">
                      <PropertyGroup>
                        <TargetFramework>net8.0-windows</TargetFramework>
                        <OutputType>WinExe</OutputType>
                        <UseWPF>true</UseWPF>
                      </PropertyGroup>
                      <ItemGroup>
                        <ProjectReference Include="..\\Lib\\Lib.csproj" />
                      </ItemGroup>
                    </Project>
                    """
                ),
                encoding="utf-8",
            )
            (root / "Lib" / "Lib.csproj").write_text(
                '<Project Sdk="Microsoft.NET.Sdk"></Project>\n',
                encoding="utf-8",
            )
            (root / "Lib" / "TelemetryService.cs").write_text(
                "namespace DemoApp.Lib; public class TelemetryService {}\n",
                encoding="utf-8",
            )
            (root / "App" / "MainWindow.xaml").write_text(
                '<Window x:Class="DemoApp.MainWindow" xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"></Window>\n',
                encoding="utf-8",
            )
            (root / "App" / "App.xaml").write_text(
                '<Application x:Class="DemoApp.App" xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"></Application>\n',
                encoding="utf-8",
            )
            (root / "App" / "App.xaml.cs").write_text(
                "namespace DemoApp; public partial class App {}\n",
                encoding="utf-8",
            )
            (root / "App" / "MainWindow.xaml.cs").write_text(
                textwrap.dedent(
                    """\
                    using DemoApp.Lib;
                    using DemoApp.Views;
                    namespace DemoApp;
                    public partial class MainWindow
                    {
                        private readonly TelemetryService _service = new();
                    }
                    """
                ),
                encoding="utf-8",
            )
            (root / "App" / "Styles.xaml").write_text(
                '<ResourceDictionary xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"></ResourceDictionary>\n',
                encoding="utf-8",
            )
            (root / "Package" / "App.Package.wapproj").write_text(
                textwrap.dedent(
                    """\
                    <Project Sdk="Microsoft.NET.Sdk">
                      <PropertyGroup>
                        <EnableMsixTooling>true</EnableMsixTooling>
                      </PropertyGroup>
                      <ItemGroup>
                        <ProjectReference Include="..\\App\\App.csproj" />
                      </ItemGroup>
                    </Project>
                    """
                ),
                encoding="utf-8",
            )
            (root / "Package" / "Package.appxmanifest").write_text(
                textwrap.dedent(
                    """\
                    <Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10"
                             xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10">
                      <Identity Name="DemoApp" Publisher="CN=Demo" Version="1.0.0.0" />
                      <Properties>
                        <DisplayName>Demo App</DisplayName>
                      </Properties>
                      <Applications>
                        <Application Id="App" Executable="$targetnametoken$.exe" EntryPoint="DemoApp.App">
                          <uap:VisualElements DisplayName="Demo App" />
                        </Application>
                      </Applications>
                    </Package>
                    """
                ),
                encoding="utf-8",
            )
            (root / "Native" / "CMakeLists.txt").write_text(
                "add_library(native_core src/widget.cpp)\n",
                encoding="utf-8",
            )
            (root / "Native" / "include" / "widget.h").write_text(
                "class Widget {};\n",
                encoding="utf-8",
            )
            (root / "Native" / "src" / "widget.cpp").write_text(
                '#include "widget.h"\nnamespace Native {}\n',
                encoding="utf-8",
            )

            cfg = {
                "modules": {
                    "app": ["App/"],
                    "lib": ["Lib/"],
                    "native": ["Native/"],
                }
            }

            with mock.patch.object(task_manager, "ROOT", root), mock.patch.object(task_manager, "_CFG", cfg):
                result = task_manager.analyze_project()

        paths = {entry["path"] for entry in result["files"]}
        self.assertIn("Demo.sln", paths)
        self.assertIn("App/App.csproj", paths)
        self.assertIn("App/App.xaml", paths)
        self.assertIn("App/App.xaml.cs", paths)
        self.assertIn("App/MainWindow.xaml", paths)
        self.assertIn("App/MainWindow.xaml.cs", paths)
        self.assertIn("Lib/TelemetryService.cs", paths)
        self.assertIn("Package/App.Package.wapproj", paths)
        self.assertIn("Package/Package.appxmanifest", paths)
        self.assertIn("Native/CMakeLists.txt", paths)
        self.assertIn("Native/include/widget.h", paths)
        self.assertIn("Native/src/widget.cpp", paths)

        xaml_entry = next(entry for entry in result["files"] if entry["path"] == "App/MainWindow.xaml")
        self.assertEqual(xaml_entry["xaml_class"], "DemoApp.MainWindow")
        self.assertEqual(xaml_entry["code_behind"], "App/MainWindow.xaml.cs")
        self.assertEqual(xaml_entry["project"], "App/App.csproj")

        app_xaml_entry = next(entry for entry in result["files"] if entry["path"] == "App/App.xaml")
        self.assertEqual(app_xaml_entry["code_behind"], "App/App.xaml.cs")
        self.assertEqual(app_xaml_entry["project"], "App/App.csproj")

        manifest_entry = next(entry for entry in result["files"] if entry["path"] == "Package/Package.appxmanifest")
        self.assertEqual(manifest_entry["project"], "Package/App.Package.wapproj")
        self.assertEqual(manifest_entry["package_identity"], "DemoApp")
        self.assertEqual(manifest_entry["package_entry_point"], "DemoApp.App")

        main_window_code = next(entry for entry in result["files"] if entry["path"] == "App/MainWindow.xaml.cs")
        self.assertIn("TelemetryService", main_window_code["type_references"])

        edge_kinds = {(edge["from"], edge["to"], edge.get("kind", "")) for edge in result["dependency_edges"]}
        self.assertIn(("App/MainWindow.xaml", "App/MainWindow.xaml.cs", "xaml-code-behind"), edge_kinds)
        self.assertIn(("App/App.xaml", "App/App.xaml.cs", "xaml-code-behind"), edge_kinds)
        self.assertIn(("App/App.csproj", "Lib/Lib.csproj", "project-reference"), edge_kinds)
        self.assertIn(("Package/App.Package.wapproj", "App/App.csproj", "project-reference"), edge_kinds)
        self.assertIn(("App/MainWindow.xaml.cs", "Lib/TelemetryService.cs", "csharp-type-reference"), edge_kinds)
        self.assertIn(("Package/Package.appxmanifest", "App/App.xaml.cs", "manifest-entry-point"), edge_kinds)
        self.assertIn(("Native/src/widget.cpp", "Native/include/widget.h", "cpp-include"), edge_kinds)

        graph_nodes = {node["id"]: node for node in result["project_graph"]["nodes"]}
        graph_edges = {(edge["from"], edge["to"], edge.get("kind", "")) for edge in result["project_graph"]["edges"]}
        self.assertIn("Demo.sln", graph_nodes)
        self.assertIn("App/App.csproj", graph_nodes)
        self.assertIn("Package/App.Package.wapproj", graph_nodes)
        self.assertEqual(graph_nodes["App/App.csproj"]["desktop_targets"], ["wpf"])
        self.assertEqual(graph_nodes["App/App.csproj"]["output_type"], "WinExe")
        self.assertEqual(graph_nodes["Package/App.Package.wapproj"]["project_role"], "packaging")
        self.assertEqual(graph_nodes["Package/App.Package.wapproj"]["packaging_model"], "msix")
        self.assertEqual(graph_nodes["Package/App.Package.wapproj"]["package_manifest"], "Package/Package.appxmanifest")
        self.assertTrue(graph_nodes["App/App.csproj"]["startup"])
        self.assertEqual(graph_nodes["Demo.sln"]["startup_project"], "App/App.csproj")
        self.assertIn(("Demo.sln", "App/App.csproj", "solution-project"), graph_edges)
        self.assertIn(("Demo.sln", "Lib/Lib.csproj", "solution-project"), graph_edges)
        self.assertIn(("Demo.sln", "Package/App.Package.wapproj", "solution-project"), graph_edges)
        self.assertIn(("App/App.csproj", "Lib/Lib.csproj", "project-reference"), graph_edges)
        self.assertIn(("Package/App.Package.wapproj", "App/App.csproj", "project-reference"), graph_edges)

        conflict_zones = {(tuple(zone["files"]), zone["reason"]) for zone in result["conflict_zones"]}
        self.assertIn((("App/App.xaml", "App/App.xaml.cs"), "xaml-code-behind pair"), conflict_zones)
        self.assertIn((("App/App.csproj", "App/App.xaml", "App/App.xaml.cs"), "desktop app startup surface"), conflict_zones)
        self.assertIn((("App/App.csproj", "App/MainWindow.xaml", "App/MainWindow.xaml.cs"), "desktop shell surface"), conflict_zones)
        self.assertIn((("App/App.csproj", "App/Styles.xaml"), "shared desktop resource dictionary"), conflict_zones)
        self.assertIn((("Package/App.Package.wapproj", "Package/Package.appxmanifest"), "desktop packaging surface"), conflict_zones)

        self.assertIn("dotnet", result["detected_stacks"])
        self.assertIn("wpf", result["detected_stacks"])
        self.assertIn("msix", result["detected_stacks"])
        self.assertIn("cpp", result["detected_stacks"])
        self.assertEqual(result["analysis_v2"]["providers"][0]["name"], "basic")
        self.assertEqual(result["analysis_v2"]["inventory"]["totals"], result["totals"])
        self.assertEqual(result["analysis_v2"]["graphs"]["project_graph"], result["project_graph"])
        self.assertEqual(result["analysis_v2"]["signals"]["conflict_zones"], result["conflict_zones"])
        derived = result["analysis_v2"]["derived"]
        planning_context = result["analysis_v2"]["planning_context"]
        app_startup_surface = next(
            surface for surface in derived["ui_surfaces"] if surface["kind"] == "startup" and surface["project"] == "App/App.csproj"
        )
        self.assertEqual(app_startup_surface["entry"], "App/App.xaml")
        self.assertTrue(app_startup_surface["startup"])
        ownership = next(item for item in derived["ownership_summary"]["projects"] if item["project"] == "App/App.csproj")
        self.assertTrue(ownership["startup"])
        self.assertGreaterEqual(ownership["ui_surface_count"], 3)
        self.assertGreaterEqual(ownership["xaml_file_count"], 3)
        self.assertEqual(planning_context["project_graph"], result["project_graph"])
        self.assertEqual(planning_context["conflict_zones"], result["conflict_zones"])
        self.assertEqual(planning_context["ui_surfaces"], derived["ui_surfaces"])
        self.assertEqual(planning_context["ownership_summary"], derived["ownership_summary"])
        self.assertEqual(planning_context["priority_projects"]["startup"], ["App/App.csproj"])
        self.assertEqual(
            planning_context["analysis_health"]["applied_providers"],
            result["analysis_v2"]["selection"]["applied"],
        )
        self.assertEqual(
            planning_context["analysis_health"]["partial_analysis"],
            bool(result["analysis_v2"]["selection"]["skipped"]),
        )

    def test_analyze_basic_mode_uses_only_basic_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "App").mkdir()
            (root / "App" / "App.csproj").write_text(
                '<Project Sdk="Microsoft.NET.Sdk"></Project>\n',
                encoding="utf-8",
            )
            cfg = {"analysis": {"mode": "basic"}}

            with mock.patch.object(task_manager, "ROOT", root), mock.patch.object(task_manager, "_CFG", cfg):
                result = task_manager.analyze_project()

        self.assertEqual([provider["name"] for provider in result["analysis_v2"]["providers"]], ["basic"])
        self.assertEqual(result["analysis_v2"]["selection"]["requested"], ["basic"])
        self.assertEqual(result["analysis_v2"]["selection"]["applied"], ["basic"])
        self.assertEqual(result["analysis_v2"]["selection"]["skipped"], [])
        self.assertTrue(result["analysis_v2"]["planning_context"]["analysis_health"]["heuristic_only"])
        self.assertFalse(result["analysis_v2"]["planning_context"]["analysis_health"]["fallback_only"])

    def test_analyze_parses_slnx_and_rebases_solution_project_edges(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src" / "App").mkdir(parents=True)
            (root / "src" / "Demo.slnx").write_text(
                textwrap.dedent(
                    """\
                    <Solution>
                      <Folder Name="/App/">
                        <Project Path="App/App.csproj" />
                      </Folder>
                    </Solution>
                    """
                ),
                encoding="utf-8",
            )
            (root / "src" / "App" / "App.csproj").write_text(
                '<Project Sdk="Microsoft.NET.Sdk"></Project>\n',
                encoding="utf-8",
            )

            cfg = {"analysis": {"mode": "basic"}, "modules": {"app": ["src/App/"]}}
            with mock.patch.object(task_manager, "ROOT", root), mock.patch.object(task_manager, "_CFG", cfg):
                result = task_manager.analyze_project()

        paths = {entry["path"] for entry in result["files"]}
        self.assertIn("src/Demo.slnx", paths)
        self.assertIn("src/App/App.csproj", paths)
        graph_edges = {(edge["from"], edge["to"], edge.get("kind", "")) for edge in result["project_graph"]["edges"]}
        self.assertIn(("src/Demo.slnx", "src/App/App.csproj", "solution-project"), graph_edges)
        self.assertIn("dotnet", result["detected_stacks"])

    def test_run_solution_list_rebases_nested_solution_output(self):
        root = Path("D:/repo")
        completed = mock.Mock()
        completed.stdout = "Project(s)\n----------\nApp\\App.csproj\nLib\\Lib.csproj\n"

        with mock.patch.object(dotnet_cli_provider.subprocess, "run", return_value=completed):
            projects = dotnet_cli_provider._run_solution_list(root, "src/Demo.sln")

        self.assertEqual(projects, ["src/App/App.csproj", "src/Lib/Lib.csproj"])

    def test_analyze_auto_mode_runs_dotnet_cli_for_vcxproj_projects(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Native").mkdir()
            (root / "Native" / "App.vcxproj").write_text("<Project></Project>\n", encoding="utf-8")
            (root / "Native" / "main.cpp").write_text("int main() { return 0; }\n", encoding="utf-8")
            (root / "Native" / "main.h").write_text("#pragma once\n", encoding="utf-8")
            (root / "Native.sln").write_text(
                "Microsoft Visual Studio Solution File, Format Version 12.00\n",
                encoding="utf-8",
            )

            property_payload = {
                "Properties": {
                    "TargetFramework": "",
                    "TargetFrameworks": "",
                    "OutputType": "",
                    "UseWPF": "",
                    "UseWinUI": "",
                    "AssemblyName": "NativeApp",
                    "RootNamespace": "",
                    "ApplicationManifest": "",
                    "AppxManifest": "",
                    "WindowsPackageType": "",
                    "EnableMsixTooling": "",
                }
            }
            item_payload = {
                "Items": {
                    "ProjectReference": [],
                    "PackageReference": [],
                    "Compile": [],
                    "ClCompile": [
                        {
                            "Identity": "main.cpp",
                            "FullPath": str((root / "Native" / "main.cpp").resolve()),
                            "DefiningProjectExtension": ".vcxproj",
                        }
                    ],
                    "ClInclude": [
                        {
                            "Identity": "main.h",
                            "FullPath": str((root / "Native" / "main.h").resolve()),
                            "DefiningProjectExtension": ".vcxproj",
                        }
                    ],
                    "Page": [],
                    "ApplicationDefinition": [],
                    "None": [],
                }
            }
            cfg = {
                "analysis": {"mode": "auto"},
                "modules": {"native": ["Native/"]},
            }

            with (
                mock.patch.object(task_manager, "ROOT", root),
                mock.patch.object(task_manager, "_CFG", cfg),
                mock.patch.object(dotnet_cli_provider.shutil, "which", return_value="dotnet"),
                mock.patch.object(dotnet_cli_provider, "_run_solution_list", return_value=["Native/App.vcxproj"]),
                mock.patch.object(
                    dotnet_cli_provider,
                    "_run_msbuild_query",
                    side_effect=[property_payload, item_payload],
                ) as msbuild_query,
            ):
                result = task_manager.analyze_project()

        self.assertEqual([provider["name"] for provider in result["analysis_v2"]["providers"]], ["basic", "dotnet-cli"])
        self.assertEqual([call.args[1] for call in msbuild_query.call_args_list], ["Native/App.vcxproj", "Native/App.vcxproj"])
        graph_nodes = {node["id"]: node for node in result["project_graph"]["nodes"]}
        self.assertIn("Native/App.vcxproj", graph_nodes)

    def test_analyze_prefers_desktop_project_when_multiple_projects_share_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "App").mkdir()
            (root / "App" / "A.Tests.csproj").write_text(
                '<Project Sdk="Microsoft.NET.Sdk"></Project>\n',
                encoding="utf-8",
            )
            (root / "App" / "ZApp.csproj").write_text(
                textwrap.dedent(
                    """\
                    <Project Sdk="Microsoft.NET.Sdk">
                      <PropertyGroup>
                        <UseWPF>true</UseWPF>
                        <OutputType>WinExe</OutputType>
                      </PropertyGroup>
                    </Project>
                    """
                ),
                encoding="utf-8",
            )
            (root / "App" / "MainWindow.xaml").write_text(
                '<Window x:Class="Demo.MainWindow" xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"></Window>\n',
                encoding="utf-8",
            )
            (root / "App" / "MainWindow.xaml.cs").write_text(
                "namespace Demo; public partial class MainWindow {}\n",
                encoding="utf-8",
            )

            cfg = {"analysis": {"mode": "basic"}}
            with mock.patch.object(task_manager, "ROOT", root), mock.patch.object(task_manager, "_CFG", cfg):
                result = task_manager.analyze_project()

        xaml_entry = next(entry for entry in result["files"] if entry["path"] == "App/MainWindow.xaml")
        code_entry = next(entry for entry in result["files"] if entry["path"] == "App/MainWindow.xaml.cs")
        self.assertEqual(xaml_entry["project"], "App/ZApp.csproj")
        self.assertEqual(code_entry["project"], "App/ZApp.csproj")

    def test_cmd_analyze_handles_provider_only_files_without_lines(self):
        analysis = {
            "root": "D:/repo",
            "analyzed_at": "2026-03-11T00:00:00Z",
            "files": [
                {"path": "App/Generated.g.cs", "category": "app"},
                {"path": "App/App.xaml", "category": "app", "lines": 12, "xaml_class": "Demo.App"},
            ],
            "dependency_edges": [],
            "modules": {"app": {"file_count": 2, "total_lines": 12, "files": ["App/Generated.g.cs", "App/App.xaml"]}},
            "detected_stacks": ["dotnet", "wpf"],
            "project_graph": {"nodes": [], "edges": []},
            "conflict_zones": [],
            "totals": {"files": 2, "lines": 12},
        }

        buf = io.StringIO()
        with (
            mock.patch.object(task_manager, "analyze_project", return_value=analysis),
            mock.patch.object(task_manager, "_CFG", {}),
            redirect_stdout(buf),
        ):
            task_manager.cmd_analyze(argparse.Namespace(json=False))

        output = buf.getvalue()
        self.assertIn("App/Generated.g.cs", output)
        self.assertIn("App/App.xaml", output)

    def test_analyze_avalonia_surfaces_match_wpf_conflict_zones(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "App").mkdir()
            (root / "App" / "App.csproj").write_text(
                '<Project Sdk="Microsoft.NET.Sdk"></Project>\n',
                encoding="utf-8",
            )
            (root / "App" / "App.axaml").write_text(
                '<Application x:Class="Demo.App" xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"></Application>\n',
                encoding="utf-8",
            )
            (root / "App" / "App.axaml.cs").write_text(
                "namespace Demo; public partial class App {}\n",
                encoding="utf-8",
            )
            (root / "App" / "MainWindow.axaml").write_text(
                '<Window x:Class="Demo.MainWindow" xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"></Window>\n',
                encoding="utf-8",
            )
            (root / "App" / "MainWindow.axaml.cs").write_text(
                "namespace Demo; public partial class MainWindow {}\n",
                encoding="utf-8",
            )
            (root / "App" / "Styles.axaml").write_text(
                '<Styles xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"></Styles>\n',
                encoding="utf-8",
            )

            cfg = {"analysis": {"mode": "basic"}, "modules": {"app": ["App/"]}}
            with mock.patch.object(task_manager, "ROOT", root), mock.patch.object(task_manager, "_CFG", cfg):
                result = task_manager.analyze_project()

        conflict_zones = {(tuple(zone["files"]), zone["reason"]) for zone in result["conflict_zones"]}
        self.assertIn((("App/App.axaml", "App/App.axaml.cs"), "xaml-code-behind pair"), conflict_zones)
        self.assertIn((("App/App.axaml", "App/App.axaml.cs", "App/App.csproj"), "desktop app startup surface"), conflict_zones)
        self.assertIn((("App/App.csproj", "App/MainWindow.axaml", "App/MainWindow.axaml.cs"), "desktop shell surface"), conflict_zones)
        self.assertIn((("App/App.csproj", "App/Styles.axaml"), "shared desktop resource dictionary"), conflict_zones)
        surfaces = {(surface["kind"], surface["entry"]) for surface in result["analysis_v2"]["derived"]["ui_surfaces"]}
        self.assertIn(("startup", "App/App.axaml"), surfaces)
        self.assertIn(("shell", "App/MainWindow.axaml"), surfaces)
        self.assertIn(("resources", "App/Styles.axaml"), surfaces)

    def test_analyze_cpp_angle_include_resolves_same_project_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "NativeA" / "src").mkdir(parents=True)
            (root / "NativeA" / "include").mkdir(parents=True)
            (root / "NativeB" / "include").mkdir(parents=True)
            (root / "NativeA" / "CMakeLists.txt").write_text("add_library(native_a src/widget.cpp)\n", encoding="utf-8")
            (root / "NativeB" / "CMakeLists.txt").write_text("add_library(native_b include/widget.h)\n", encoding="utf-8")
            (root / "NativeA" / "src" / "widget.cpp").write_text("#include <widget.h>\nnamespace NativeA {}\n", encoding="utf-8")
            (root / "NativeA" / "include" / "widget.h").write_text("class WidgetA {};\n", encoding="utf-8")
            (root / "NativeB" / "include" / "widget.h").write_text("class WidgetB {};\n", encoding="utf-8")

            cfg = {
                "analysis": {"mode": "basic"},
                "modules": {"native-a": ["NativeA/"], "native-b": ["NativeB/"]},
            }
            with mock.patch.object(task_manager, "ROOT", root), mock.patch.object(task_manager, "_CFG", cfg):
                result = task_manager.analyze_project()

        edge_kinds = {(edge["from"], edge["to"], edge.get("kind", "")) for edge in result["dependency_edges"]}
        self.assertIn(("NativeA/src/widget.cpp", "NativeA/include/widget.h", "cpp-include"), edge_kinds)
        self.assertNotIn(("NativeA/src/widget.cpp", "NativeB/include/widget.h", "cpp-include"), edge_kinds)

    def test_analyze_cpp_include_does_not_fallback_to_other_project_by_basename(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "NativeA" / "src").mkdir(parents=True)
            (root / "NativeB" / "include").mkdir(parents=True)
            (root / "NativeA" / "CMakeLists.txt").write_text("add_library(native_a src/widget.cpp)\n", encoding="utf-8")
            (root / "NativeB" / "CMakeLists.txt").write_text("add_library(native_b include/widget.h)\n", encoding="utf-8")
            (root / "NativeA" / "src" / "widget.cpp").write_text('#include "widget.h"\nnamespace NativeA {}\n', encoding="utf-8")
            (root / "NativeB" / "include" / "widget.h").write_text("class WidgetB {};\n", encoding="utf-8")

            cfg = {
                "analysis": {"mode": "basic"},
                "modules": {"native-a": ["NativeA/"], "native-b": ["NativeB/"]},
            }
            with mock.patch.object(task_manager, "ROOT", root), mock.patch.object(task_manager, "_CFG", cfg):
                result = task_manager.analyze_project()

        edge_kinds = {(edge["from"], edge["to"], edge.get("kind", "")) for edge in result["dependency_edges"]}
        self.assertNotIn(("NativeA/src/widget.cpp", "NativeB/include/widget.h", "cpp-include"), edge_kinds)

    def test_analyze_dotnet_cli_provider_assigns_linked_compile_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "App").mkdir()
            (root / "Shared").mkdir()
            (root / "App" / "App.csproj").write_text(
                textwrap.dedent(
                    """\
                    <Project Sdk="Microsoft.NET.Sdk">
                      <PropertyGroup>
                        <TargetFramework>net8.0</TargetFramework>
                      </PropertyGroup>
                      <ItemGroup>
                        <Compile Include="..\\Shared\\LinkedFile.cs" Link="LinkedFile.cs" />
                      </ItemGroup>
                    </Project>
                    """
                ),
                encoding="utf-8",
            )
            (root / "Shared" / "LinkedFile.cs").write_text(
                "namespace DemoApp; public class LinkedFile {}\n",
                encoding="utf-8",
            )

            property_payload = {
                "Properties": {
                    "TargetFramework": "net8.0",
                    "TargetFrameworks": "",
                    "OutputType": "Exe",
                    "UseWPF": "",
                    "UseWinUI": "",
                    "AssemblyName": "DemoApp",
                    "RootNamespace": "DemoApp",
                    "ApplicationManifest": "",
                    "AppxManifest": "",
                    "WindowsPackageType": "",
                    "EnableMsixTooling": "",
                }
            }
            item_payload = {
                "Items": {
                    "ProjectReference": [],
                    "PackageReference": [
                        {
                            "Identity": "Newtonsoft.Json",
                            "Version": "13.0.3",
                        }
                    ],
                    "Compile": [
                        {
                            "FullPath": str((root / "Shared" / "LinkedFile.cs").resolve()),
                        }
                    ],
                    "Page": [],
                    "ApplicationDefinition": [],
                    "None": [],
                }
            }
            cfg = {
                "analysis": {"mode": "auto"},
                "modules": {"app": ["App/"], "shared": ["Shared/"]},
            }

            with (
                mock.patch.object(task_manager, "ROOT", root),
                mock.patch.object(task_manager, "_CFG", cfg),
                mock.patch.object(dotnet_cli_provider.shutil, "which", return_value="dotnet"),
                mock.patch.object(dotnet_cli_provider, "_run_msbuild_query", side_effect=[property_payload, item_payload]),
                mock.patch.object(dotnet_cli_provider, "_run_solution_list", return_value=[]),
            ):
                result = task_manager.analyze_project()

        linked_entry = next(entry for entry in result["files"] if entry["path"] == "Shared/LinkedFile.cs")
        project_entry = next(entry for entry in result["files"] if entry["path"] == "App/App.csproj")
        self.assertEqual(linked_entry["project"], "App/App.csproj")
        self.assertEqual(project_entry["package_references"], [{"name": "Newtonsoft.Json", "version": "13.0.3"}])
        project_node = next(node for node in result["project_graph"]["nodes"] if node["id"] == "App/App.csproj")
        self.assertEqual(project_node["package_references"], [{"name": "Newtonsoft.Json", "version": "13.0.3"}])
        package_node = next(node for node in result["project_graph"]["nodes"] if node["id"] == "nuget:Newtonsoft.Json")
        self.assertEqual(package_node["kind"], "package")
        self.assertEqual(package_node["version"], "13.0.3")
        self.assertIn(
            ("App/App.csproj", "nuget:Newtonsoft.Json", "package-reference"),
            {(edge["from"], edge["to"], edge.get("kind", "")) for edge in result["project_graph"]["edges"]},
        )
        self.assertEqual([provider["name"] for provider in result["analysis_v2"]["providers"]], ["basic", "dotnet-cli"])
        self.assertEqual(result["analysis_v2"]["selection"]["applied"], ["basic", "dotnet-cli"])

    def test_analyze_refreshes_startup_project_from_linked_app_xaml(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "App").mkdir()
            (root / "Tool").mkdir()
            (root / "Shared").mkdir()
            (root / "Demo.slnx").write_text(
                textwrap.dedent(
                    """\
                    <Solution>
                      <Folder Name="/Apps/">
                        <Project Path="App/App.csproj" />
                        <Project Path="Tool/Tool.csproj" />
                      </Folder>
                    </Solution>
                    """
                ),
                encoding="utf-8",
            )
            project_xml = textwrap.dedent(
                """\
                <Project Sdk="Microsoft.NET.Sdk">
                  <PropertyGroup>
                    <TargetFramework>net8.0-windows</TargetFramework>
                    <UseWPF>true</UseWPF>
                    <OutputType>WinExe</OutputType>
                  </PropertyGroup>
                </Project>
                """
            )
            (root / "App" / "App.csproj").write_text(project_xml, encoding="utf-8")
            (root / "Tool" / "Tool.csproj").write_text(project_xml, encoding="utf-8")
            (root / "Shared" / "App.xaml").write_text(
                '<Application x:Class="Demo.App" xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"></Application>\n',
                encoding="utf-8",
            )
            (root / "Shared" / "App.xaml.cs").write_text(
                "namespace Demo; public partial class App {}\n",
                encoding="utf-8",
            )

            app_properties = {
                "Properties": {
                    "TargetFramework": "net8.0-windows",
                    "TargetFrameworks": "",
                    "OutputType": "WinExe",
                    "UseWPF": "true",
                    "UseWinUI": "",
                    "AssemblyName": "DemoApp",
                    "RootNamespace": "DemoApp",
                    "ApplicationManifest": "",
                    "AppxManifest": "",
                    "WindowsPackageType": "",
                    "EnableMsixTooling": "",
                }
            }
            app_items = {
                "Items": {
                    "ProjectReference": [],
                    "PackageReference": [],
                    "Compile": [],
                    "Page": [],
                    "ApplicationDefinition": [
                        {
                            "Identity": "..\\Shared\\App.xaml",
                            "Generator": "MSBuild:Compile",
                            "XamlRuntime": "Wpf",
                            "SubType": "Designer",
                            "DependentUpon": "App.xaml.cs",
                            "FullPath": str((root / "Shared" / "App.xaml").resolve()),
                            "DefiningProjectExtension": ".csproj",
                        },
                    ],
                    "None": [],
                }
            }
            tool_properties = {
                "Properties": {
                    "TargetFramework": "net8.0-windows",
                    "TargetFrameworks": "",
                    "OutputType": "WinExe",
                    "UseWPF": "true",
                    "UseWinUI": "",
                    "AssemblyName": "ToolApp",
                    "RootNamespace": "ToolApp",
                    "ApplicationManifest": "",
                    "AppxManifest": "",
                    "WindowsPackageType": "",
                    "EnableMsixTooling": "",
                }
            }
            tool_items = {
                "Items": {
                    "ProjectReference": [],
                    "PackageReference": [],
                    "Compile": [],
                    "Page": [],
                    "ApplicationDefinition": [],
                    "None": [],
                }
            }
            cfg = {
                "analysis": {"mode": "auto"},
                "modules": {"app": ["App/"], "tool": ["Tool/"], "shared": ["Shared/"]},
            }

            with (
                mock.patch.object(task_manager, "ROOT", root),
                mock.patch.object(task_manager, "_CFG", cfg),
                mock.patch.object(dotnet_cli_provider.shutil, "which", return_value="dotnet"),
                mock.patch.object(
                    dotnet_cli_provider,
                    "_run_msbuild_query",
                    side_effect=[app_properties, app_items, tool_properties, tool_items],
                ),
                mock.patch.object(
                    dotnet_cli_provider,
                    "_run_solution_list",
                    return_value=["App/App.csproj", "Tool/Tool.csproj"],
                ),
            ):
                result = task_manager.analyze_project()

        project_entry = next(entry for entry in result["files"] if entry["path"] == "App/App.csproj")
        self.assertEqual(project_entry["app_xaml"], "Shared/App.xaml")
        self.assertEqual(project_entry["app_code_behind"], "Shared/App.xaml.cs")
        graph_nodes = {node["id"]: node for node in result["project_graph"]["nodes"]}
        self.assertEqual(graph_nodes["App/App.csproj"]["app_xaml"], "Shared/App.xaml")
        self.assertTrue(graph_nodes["App/App.csproj"]["startup"])
        self.assertEqual(graph_nodes["Demo.slnx"]["startup_project"], "App/App.csproj")

    def test_analyze_refreshes_linked_package_manifest_onto_project_node(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Package").mkdir()
            (root / "Shared").mkdir()
            (root / "Package" / "App.Package.wapproj").write_text(
                '<Project Sdk="Microsoft.NET.Sdk"></Project>\n',
                encoding="utf-8",
            )
            (root / "Shared" / "Package.appxmanifest").write_text(
                textwrap.dedent(
                    """\
                    <Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10">
                      <Identity Name="DemoApp" Publisher="CN=Demo" Version="1.0.0.0" />
                      <Properties>
                        <DisplayName>Demo</DisplayName>
                      </Properties>
                      <Applications>
                        <Application Id="App" Executable="$targetnametoken$.exe" EntryPoint="DemoApp.App" />
                      </Applications>
                    </Package>
                    """
                ),
                encoding="utf-8",
            )

            property_payload = {
                "Properties": {
                    "TargetFramework": "",
                    "TargetFrameworks": "",
                    "OutputType": "",
                    "UseWPF": "",
                    "UseWinUI": "",
                    "AssemblyName": "App.Package",
                    "RootNamespace": "DemoApp.Package",
                    "ApplicationManifest": "",
                    "AppxManifest": "..\\Shared\\Package.appxmanifest",
                    "WindowsPackageType": "MSIX",
                    "EnableMsixTooling": "true",
                }
            }
            item_payload = {
                "Items": {
                    "ProjectReference": [],
                    "PackageReference": [],
                    "Compile": [],
                    "Page": [],
                    "ApplicationDefinition": [],
                    "None": [
                        {
                            "Identity": "..\\Shared\\Package.appxmanifest",
                            "FullPath": str((root / "Shared" / "Package.appxmanifest").resolve()),
                            "DefiningProjectExtension": ".wapproj",
                        }
                    ],
                }
            }
            cfg = {
                "analysis": {"mode": "auto"},
                "modules": {"package": ["Package/"], "shared": ["Shared/"]},
            }

            with (
                mock.patch.object(task_manager, "ROOT", root),
                mock.patch.object(task_manager, "_CFG", cfg),
                mock.patch.object(dotnet_cli_provider.shutil, "which", return_value="dotnet"),
                mock.patch.object(dotnet_cli_provider, "_run_msbuild_query", side_effect=[property_payload, item_payload]),
                mock.patch.object(dotnet_cli_provider, "_run_solution_list", return_value=[]),
            ):
                result = task_manager.analyze_project()

        project_entry = next(entry for entry in result["files"] if entry["path"] == "Package/App.Package.wapproj")
        self.assertEqual(project_entry["package_manifest"], "Shared/Package.appxmanifest")
        self.assertEqual(project_entry["package_entry_point"], "DemoApp.App")
        project_node = next(node for node in result["project_graph"]["nodes"] if node["id"] == "Package/App.Package.wapproj")
        self.assertEqual(project_node["package_manifest"], "Shared/Package.appxmanifest")
        self.assertEqual(project_node["package_entry_point"], "DemoApp.App")

    def test_analyze_rebases_project_relative_manifest_without_manifest_file_inventory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Package").mkdir()
            (root / "Shared").mkdir()
            (root / "Package" / "App.Package.wapproj").write_text(
                '<Project Sdk="Microsoft.NET.Sdk"></Project>\n',
                encoding="utf-8",
            )
            (root / "Shared" / "Package.appxmanifest").write_text(
                "<Package></Package>\n",
                encoding="utf-8",
            )

            property_payload = {
                "Properties": {
                    "TargetFramework": "",
                    "TargetFrameworks": "",
                    "OutputType": "",
                    "UseWPF": "",
                    "UseWinUI": "",
                    "AssemblyName": "App.Package",
                    "RootNamespace": "DemoApp.Package",
                    "ApplicationManifest": "..\\Shared\\app.manifest",
                    "AppxManifest": "..\\Shared\\Package.appxmanifest",
                    "WindowsPackageType": "MSIX",
                    "EnableMsixTooling": "true",
                }
            }
            item_payload = {
                "Items": {
                    "ProjectReference": [],
                    "PackageReference": [],
                    "Compile": [],
                    "Page": [],
                    "ApplicationDefinition": [],
                    "None": [],
                }
            }
            cfg = {
                "analysis": {"mode": "auto", "exclude-globs": ["Shared/**"]},
                "modules": {"package": ["Package/"], "shared": ["Shared/"]},
            }

            with (
                mock.patch.object(task_manager, "ROOT", root),
                mock.patch.object(task_manager, "_CFG", cfg),
                mock.patch.object(dotnet_cli_provider.shutil, "which", return_value="dotnet"),
                mock.patch.object(dotnet_cli_provider, "_run_msbuild_query", side_effect=[property_payload, item_payload]),
                mock.patch.object(dotnet_cli_provider, "_run_solution_list", return_value=[]),
            ):
                result = task_manager.analyze_project()

        project_entry = next(entry for entry in result["files"] if entry["path"] == "Package/App.Package.wapproj")
        self.assertEqual(project_entry["package_manifest"], "Shared/Package.appxmanifest")
        self.assertEqual(project_entry["application_manifest_path"], "Shared/app.manifest")
        project_node = next(node for node in result["project_graph"]["nodes"] if node["id"] == "Package/App.Package.wapproj")
        self.assertEqual(project_node["package_manifest"], "Shared/Package.appxmanifest")
        self.assertEqual(project_node["application_manifest_path"], "Shared/app.manifest")

    def test_analyze_dotnet_cli_provider_prefers_explicit_xaml_item_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "App").mkdir(parents=True)
            (root / "App" / "App.csproj").write_text(
                textwrap.dedent(
                    """\
                    <Project Sdk="Microsoft.NET.Sdk">
                      <PropertyGroup>
                        <TargetFramework>net8.0-windows</TargetFramework>
                        <UseWPF>true</UseWPF>
                      </PropertyGroup>
                    </Project>
                    """
                ),
                encoding="utf-8",
            )
            (root / "App" / "App.xaml").write_text(
                '<Application x:Class="Demo.App" xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"></Application>\n',
                encoding="utf-8",
            )
            (root / "App" / "App.xaml.cs").write_text(
                "namespace Demo; public partial class App {}\n",
                encoding="utf-8",
            )

            property_payload = {
                "Properties": {
                    "TargetFramework": "net8.0-windows",
                    "TargetFrameworks": "",
                    "OutputType": "WinExe",
                    "UseWPF": "true",
                    "UseWinUI": "",
                    "AssemblyName": "DemoApp",
                    "RootNamespace": "DemoApp",
                    "ApplicationManifest": "",
                    "AppxManifest": "",
                    "WindowsPackageType": "",
                    "EnableMsixTooling": "",
                }
            }
            item_payload = {
                "Items": {
                    "ProjectReference": [],
                    "PackageReference": [],
                    "Compile": [],
                    "Page": [],
                    "ApplicationDefinition": [
                        {
                            "Identity": "App.xaml",
                            "Generator": "MSBuild:Compile",
                            "XamlRuntime": "Wpf",
                            "SubType": "Designer",
                            "FullPath": str((root / "App" / "App.xaml").resolve()),
                            "DefiningProjectExtension": ".props",
                        },
                        {
                            "Identity": "App.xaml",
                            "Generator": "MSBuild:Compile",
                            "XamlRuntime": "Wpf",
                            "SubType": "Designer",
                            "DependentUpon": "App.xaml.cs",
                            "Link": "Ui\\App.xaml",
                            "FullPath": str((root / "App" / "App.xaml").resolve()),
                            "DefiningProjectExtension": ".csproj",
                        },
                    ],
                    "None": [],
                }
            }
            cfg = {
                "analysis": {"mode": "auto"},
                "modules": {"app": ["App/"]},
            }

            with (
                mock.patch.object(task_manager, "ROOT", root),
                mock.patch.object(task_manager, "_CFG", cfg),
                mock.patch.object(dotnet_cli_provider.shutil, "which", return_value="dotnet"),
                mock.patch.object(dotnet_cli_provider, "_run_msbuild_query", side_effect=[property_payload, item_payload]),
                mock.patch.object(dotnet_cli_provider, "_run_solution_list", return_value=[]),
            ):
                result = task_manager.analyze_project()

        app_xaml = next(entry for entry in result["files"] if entry["path"] == "App/App.xaml")
        self.assertEqual(app_xaml["project_item_kind"], "application-definition")
        self.assertEqual(app_xaml["project_item_link"], "Ui/App.xaml")
        self.assertEqual(app_xaml["dependent_upon"], "App.xaml.cs")
        self.assertEqual(app_xaml["code_behind"], "App/App.xaml.cs")
        self.assertEqual(app_xaml["xaml_runtime"], "Wpf")

    def test_analyze_skips_timed_out_dotnet_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "App").mkdir()
            (root / "App" / "App.csproj").write_text(
                '<Project Sdk="Microsoft.NET.Sdk"></Project>\n',
                encoding="utf-8",
            )
            cfg = {"analysis": {"mode": "auto"}}

            with (
                mock.patch.object(task_manager, "ROOT", root),
                mock.patch.object(task_manager, "_CFG", cfg),
                mock.patch.object(dotnet_cli_provider.shutil, "which", return_value="dotnet"),
                mock.patch.object(
                    dotnet_cli_provider,
                    "_run_msbuild_query",
                    side_effect=subprocess.TimeoutExpired(cmd=["dotnet", "msbuild"], timeout=20),
                ),
                mock.patch.object(dotnet_cli_provider, "_run_solution_list", return_value=[]),
            ):
                result = task_manager.analyze_project()

        self.assertEqual([provider["name"] for provider in result["analysis_v2"]["providers"]], ["basic"])
        skipped = next(item for item in result["analysis_v2"]["selection"]["skipped"] if item["name"] == "dotnet-cli")
        self.assertIn("timed out", skipped["reason"])
        self.assertTrue(result["analysis_v2"]["planning_context"]["analysis_health"]["fallback_only"])
        self.assertTrue(result["analysis_v2"]["planning_context"]["analysis_health"]["partial_analysis"])
        self.assertEqual(result["analysis_v2"]["planning_context"]["analysis_health"]["confidence"], "low")

    def test_analyze_detects_mutual_imports_for_python_packages(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pkg").mkdir()
            (root / "consumer.py").write_text(
                "import pkg\nimport pkg.module\n",
                encoding="utf-8",
            )
            (root / "pkg" / "__init__.py").write_text(
                "import consumer\n",
                encoding="utf-8",
            )
            (root / "pkg" / "module.py").write_text(
                "import consumer\n",
                encoding="utf-8",
            )

            cfg = {"analysis": {"mode": "basic"}}
            with mock.patch.object(task_manager, "ROOT", root), mock.patch.object(task_manager, "_CFG", cfg):
                result = task_manager.analyze_project()

        edge_kinds = {(edge["from"], edge["to"], edge.get("kind", "")) for edge in result["dependency_edges"]}
        self.assertIn(("consumer.py", "pkg/__init__.py", "python-import"), edge_kinds)
        self.assertIn(("consumer.py", "pkg/module.py", "python-import"), edge_kinds)
        conflict_zones = {(tuple(zone["files"]), zone["reason"]) for zone in result["conflict_zones"]}
        self.assertIn((("consumer.py", "pkg/__init__.py"), "mutual imports"), conflict_zones)
        self.assertIn((("consumer.py", "pkg/module.py"), "mutual imports"), conflict_zones)

    def test_analyze_ignores_non_package_directory_imports(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tests").mkdir()
            (root / "consumer.py").write_text(
                "import tests.helper\n",
                encoding="utf-8",
            )
            (root / "tests" / "helper.py").write_text(
                "import consumer\n",
                encoding="utf-8",
            )

            cfg = {"analysis": {"mode": "basic"}}
            with mock.patch.object(task_manager, "ROOT", root), mock.patch.object(task_manager, "_CFG", cfg):
                result = task_manager.analyze_project()

        edge_kinds = {(edge["from"], edge["to"], edge.get("kind", "")) for edge in result["dependency_edges"]}
        self.assertNotIn(("consumer.py", "tests/helper.py", "python-import"), edge_kinds)
        conflict_zones = {(tuple(zone["files"]), zone["reason"]) for zone in result["conflict_zones"]}
        self.assertNotIn((("consumer.py", "tests/helper.py"), "mutual imports"), conflict_zones)

    def test_analyze_does_not_resolve_missing_python_package_by_basename(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "shared").mkdir()
            (root / "consumer.py").write_text(
                "import pkg.module\n",
                encoding="utf-8",
            )
            (root / "shared" / "module.py").write_text(
                "import consumer\n",
                encoding="utf-8",
            )

            cfg = {
                "analysis": {"mode": "basic"},
                "modules": {"core": ["consumer.py", "pkg.py", "shared/module.py"]},
            }
            with mock.patch.object(task_manager, "ROOT", root), mock.patch.object(task_manager, "_CFG", cfg):
                result = task_manager.analyze_project()

        edge_kinds = {(edge["from"], edge["to"], edge.get("kind", "")) for edge in result["dependency_edges"]}
        self.assertNotIn(("consumer.py", "shared/module.py", "python-import"), edge_kinds)

    def test_analyze_recomputes_conflict_zones_from_merged_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "App").mkdir(parents=True)
            (root / "Shared").mkdir()
            (root / "App" / "App.csproj").write_text(
                textwrap.dedent(
                    """\
                    <Project Sdk="Microsoft.NET.Sdk">
                      <PropertyGroup>
                        <TargetFramework>net8.0-windows</TargetFramework>
                        <UseWPF>true</UseWPF>
                        <OutputType>WinExe</OutputType>
                      </PropertyGroup>
                    </Project>
                    """
                ),
                encoding="utf-8",
            )
            (root / "Shared" / "App.xaml").write_text(
                '<Application x:Class="Demo.App" xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"></Application>\n',
                encoding="utf-8",
            )
            (root / "Shared" / "App.xaml.cs").write_text(
                "namespace Demo; public partial class App {}\n",
                encoding="utf-8",
            )

            property_payload = {
                "Properties": {
                    "TargetFramework": "net8.0-windows",
                    "TargetFrameworks": "",
                    "OutputType": "WinExe",
                    "UseWPF": "true",
                    "UseWinUI": "",
                    "AssemblyName": "DemoApp",
                    "RootNamespace": "DemoApp",
                    "ApplicationManifest": "",
                    "AppxManifest": "",
                    "WindowsPackageType": "",
                    "EnableMsixTooling": "",
                }
            }
            item_payload = {
                "Items": {
                    "ProjectReference": [],
                    "PackageReference": [],
                    "Compile": [],
                    "Page": [],
                    "ApplicationDefinition": [
                        {
                            "Identity": "..\\Shared\\App.xaml",
                            "Generator": "MSBuild:Compile",
                            "XamlRuntime": "Wpf",
                            "SubType": "Designer",
                            "DependentUpon": "App.xaml.cs",
                            "Link": "Ui\\App.xaml",
                            "FullPath": str((root / "Shared" / "App.xaml").resolve()),
                            "DefiningProjectExtension": ".csproj",
                        },
                    ],
                    "None": [],
                }
            }
            cfg = {
                "analysis": {"mode": "auto"},
                "modules": {"app": ["App/"], "shared": ["Shared/"]},
            }

            with (
                mock.patch.object(task_manager, "ROOT", root),
                mock.patch.object(task_manager, "_CFG", cfg),
                mock.patch.object(dotnet_cli_provider.shutil, "which", return_value="dotnet"),
                mock.patch.object(dotnet_cli_provider, "_run_msbuild_query", side_effect=[property_payload, item_payload]),
                mock.patch.object(dotnet_cli_provider, "_run_solution_list", return_value=[]),
            ):
                result = task_manager.analyze_project()

        conflict_zones = {(tuple(zone["files"]), zone["reason"]) for zone in result["conflict_zones"]}
        self.assertIn(
            (("App/App.csproj", "Shared/App.xaml", "Shared/App.xaml.cs"), "desktop app startup surface"),
            conflict_zones,
        )
        edge_kinds = {(edge["from"], edge["to"], edge.get("kind", "")) for edge in result["dependency_edges"]}
        self.assertIn(
            ("Shared/App.xaml", "Shared/App.xaml.cs", "xaml-code-behind"),
            edge_kinds,
        )
        self.assertEqual(result["analysis_v2"]["signals"]["conflict_zones"], result["conflict_zones"])
        startup_surface = next(
            surface
            for surface in result["analysis_v2"]["derived"]["ui_surfaces"]
            if surface["kind"] == "startup" and surface["project"] == "App/App.csproj"
        )
        self.assertEqual(startup_surface["entry"], "Shared/App.xaml")
        ownership = next(
            item for item in result["analysis_v2"]["derived"]["ownership_summary"]["projects"] if item["project"] == "App/App.csproj"
        )
        self.assertEqual(ownership["ui_surface_count"], 1)

    def test_analyze_preserves_shared_xaml_membership_across_projects(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "App").mkdir()
            (root / "Tool").mkdir()
            (root / "Shared").mkdir()
            project_xml = textwrap.dedent(
                """\
                <Project Sdk="Microsoft.NET.Sdk">
                  <PropertyGroup>
                    <TargetFramework>net8.0-windows</TargetFramework>
                    <UseWPF>true</UseWPF>
                    <OutputType>WinExe</OutputType>
                  </PropertyGroup>
                </Project>
                """
            )
            (root / "App" / "App.csproj").write_text(project_xml, encoding="utf-8")
            (root / "Tool" / "Tool.csproj").write_text(project_xml, encoding="utf-8")
            (root / "Shared" / "Styles.xaml").write_text(
                '<ResourceDictionary xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"></ResourceDictionary>\n',
                encoding="utf-8",
            )

            property_payload = {
                "Properties": {
                    "TargetFramework": "net8.0-windows",
                    "TargetFrameworks": "",
                    "OutputType": "WinExe",
                    "UseWPF": "true",
                    "UseWinUI": "",
                    "AssemblyName": "DemoApp",
                    "RootNamespace": "DemoApp",
                    "ApplicationManifest": "",
                    "AppxManifest": "",
                    "WindowsPackageType": "",
                    "EnableMsixTooling": "",
                }
            }
            shared_item = {
                "Identity": "..\\Shared\\Styles.xaml",
                "Link": "Ui\\Styles.xaml",
                "FullPath": str((root / "Shared" / "Styles.xaml").resolve()),
                "DefiningProjectExtension": ".csproj",
            }
            item_payload = {
                "Items": {
                    "ProjectReference": [],
                    "PackageReference": [],
                    "Compile": [],
                    "Page": [],
                    "ApplicationDefinition": [],
                    "None": [shared_item],
                }
            }
            cfg = {
                "analysis": {"mode": "auto"},
                "modules": {"app": ["App/"], "tool": ["Tool/"], "shared": ["Shared/"]},
            }

            with (
                mock.patch.object(task_manager, "ROOT", root),
                mock.patch.object(task_manager, "_CFG", cfg),
                mock.patch.object(dotnet_cli_provider.shutil, "which", return_value="dotnet"),
                mock.patch.object(
                    dotnet_cli_provider,
                    "_run_msbuild_query",
                    side_effect=[property_payload, item_payload, property_payload, item_payload],
                ),
                mock.patch.object(dotnet_cli_provider, "_run_solution_list", return_value=[]),
            ):
                result = task_manager.analyze_project()

        shared_entry = next(entry for entry in result["files"] if entry["path"] == "Shared/Styles.xaml")
        self.assertEqual(
            set(shared_entry["project_memberships"]),
            {"App/App.csproj", "Tool/Tool.csproj"},
        )
        conflict_zones = {(tuple(zone["files"]), zone["reason"]) for zone in result["conflict_zones"]}
        self.assertIn(
            (tuple(sorted(("App/App.csproj", "Shared/Styles.xaml"))), "shared desktop resource dictionary"),
            conflict_zones,
        )
        self.assertIn(
            (tuple(sorted(("Tool/Tool.csproj", "Shared/Styles.xaml"))), "shared desktop resource dictionary"),
            conflict_zones,
        )
        surfaces = {(surface["project"], surface["kind"], surface["entry"]) for surface in result["analysis_v2"]["derived"]["ui_surfaces"]}
        self.assertIn(("App/App.csproj", "resources", "Shared/Styles.xaml"), surfaces)
        self.assertIn(("Tool/Tool.csproj", "resources", "Shared/Styles.xaml"), surfaces)

    def test_analyze_does_not_guess_plain_cs_file_as_xaml_code_behind(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "App").mkdir()
            (root / "App" / "App.csproj").write_text(
                '<Project Sdk="Microsoft.NET.Sdk"></Project>\n',
                encoding="utf-8",
            )
            (root / "App" / "MainWindow.xaml").write_text(
                '<Window x:Class="Demo.MainWindow" xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"></Window>\n',
                encoding="utf-8",
            )
            (root / "App" / "MainWindow.cs").write_text(
                "namespace Demo; public class MainWindow {}\n",
                encoding="utf-8",
            )

            cfg = {"analysis": {"mode": "basic"}, "modules": {"app": ["App/"]}}
            with mock.patch.object(task_manager, "ROOT", root), mock.patch.object(task_manager, "_CFG", cfg):
                result = task_manager.analyze_project()

        xaml_entry = next(entry for entry in result["files"] if entry["path"] == "App/MainWindow.xaml")
        self.assertNotIn("code_behind", xaml_entry)
        edge_kinds = {(edge["from"], edge["to"], edge.get("kind", "")) for edge in result["dependency_edges"]}
        self.assertNotIn(("App/MainWindow.xaml", "App/MainWindow.cs", "xaml-code-behind"), edge_kinds)

    def test_analyze_treats_avalonia_styles_root_as_resource_surface(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "App").mkdir()
            (root / "App" / "App.csproj").write_text(
                '<Project Sdk="Microsoft.NET.Sdk"></Project>\n',
                encoding="utf-8",
            )
            (root / "App" / "Theme.axaml").write_text(
                '<Styles xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"></Styles>\n',
                encoding="utf-8",
            )

            cfg = {"analysis": {"mode": "basic"}, "modules": {"app": ["App/"]}}
            with mock.patch.object(task_manager, "ROOT", root), mock.patch.object(task_manager, "_CFG", cfg):
                result = task_manager.analyze_project()

        conflict_zones = {(tuple(zone["files"]), zone["reason"]) for zone in result["conflict_zones"]}
        self.assertIn(
            (tuple(sorted(("App/App.csproj", "App/Theme.axaml"))), "shared desktop resource dictionary"),
            conflict_zones,
        )
        surfaces = {(surface["kind"], surface["entry"]) for surface in result["analysis_v2"]["derived"]["ui_surfaces"]}
        self.assertIn(("resources", "App/Theme.axaml"), surfaces)

    def test_analyze_resource_conflict_zone_includes_all_project_resources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "App").mkdir()
            (root / "App" / "App.csproj").write_text(
                '<Project Sdk="Microsoft.NET.Sdk"></Project>\n',
                encoding="utf-8",
            )
            (root / "App" / "Styles.xaml").write_text("<ResourceDictionary></ResourceDictionary>\n", encoding="utf-8")
            (root / "App" / "Colors.xaml").write_text("<ResourceDictionary></ResourceDictionary>\n", encoding="utf-8")
            (root / "App" / "Generic.xaml").write_text("<ResourceDictionary></ResourceDictionary>\n", encoding="utf-8")

            cfg = {"analysis": {"mode": "basic"}, "modules": {"app": ["App/"]}}
            with mock.patch.object(task_manager, "ROOT", root), mock.patch.object(task_manager, "_CFG", cfg):
                result = task_manager.analyze_project()

        conflict_zones = {(tuple(zone["files"]), zone["reason"]) for zone in result["conflict_zones"]}
        self.assertIn(
            (
                tuple(sorted(("App/App.csproj", "App/Styles.xaml", "App/Colors.xaml", "App/Generic.xaml"))),
                "shared desktop resource dictionary",
            ),
            conflict_zones,
        )

    def test_analyze_detects_database_projects_and_sql_conflict_zones(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Db" / "Migrations").mkdir(parents=True)
            (root / "Db" / "Database.sqlproj").write_text(
                '<Project Sdk="Microsoft.Build.Sql"></Project>\n',
                encoding="utf-8",
            )
            (root / "Db" / "001_init.sql").write_text(
                "create table Demo(Id int);\n",
                encoding="utf-8",
            )
            (root / "Db" / "Migrations" / "002_add_name.sql").write_text(
                "alter table Demo add Name nvarchar(50);\n",
                encoding="utf-8",
            )

            cfg = {"analysis": {"mode": "basic"}, "modules": {"db": ["Db/"]}}
            with mock.patch.object(task_manager, "ROOT", root), mock.patch.object(task_manager, "_CFG", cfg):
                result = task_manager.analyze_project()

        project_node = next(node for node in result["project_graph"]["nodes"] if node["id"] == "Db/Database.sqlproj")
        self.assertEqual(project_node["project_kind"], "database")
        self.assertEqual(project_node["project_role"], "database")
        sql_entry = next(entry for entry in result["files"] if entry["path"] == "Db/001_init.sql")
        self.assertEqual(sql_entry["project"], "Db/Database.sqlproj")
        self.assertIn("database", result["detected_stacks"])
        conflict_zones = {(tuple(zone["files"]), zone["reason"]) for zone in result["conflict_zones"]}
        self.assertIn(
            (
                tuple(sorted(("Db/Database.sqlproj", "Db/001_init.sql", "Db/Migrations/002_add_name.sql"))),
                "database schema surface",
            ),
            conflict_zones,
        )
        self.assertIn(
            (
                tuple(sorted(("Db/Database.sqlproj", "Db/Migrations/002_add_name.sql"))),
                "database migration surface",
            ),
            conflict_zones,
        )

    def test_run_solution_list_includes_sqlproj_membership(self):
        root = Path("D:/repo")
        completed = mock.Mock()
        completed.stdout = "Project(s)\n----------\nDb\\Database.sqlproj\n"

        with mock.patch.object(dotnet_cli_provider.subprocess, "run", return_value=completed):
            projects = dotnet_cli_provider._run_solution_list(root, "Demo.sln")

        self.assertEqual(projects, ["Db/Database.sqlproj"])


if __name__ == "__main__":
    unittest.main()
