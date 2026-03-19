"""Direct tests for low-level analysis.basic_provider helpers."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from analysis import basic_provider  # noqa: E402


class TestNormalizeStringList(unittest.TestCase):
    def test_handles_multiple_input_shapes(self):
        self.assertEqual(basic_provider._normalize_string_list(None), [])
        self.assertEqual(basic_provider._normalize_string_list("  item  "), ["item"])
        self.assertEqual(
            basic_provider._normalize_string_list(["  alpha  ", "", "beta", 3]),
            ["alpha", "beta", "3"],
        )
        self.assertEqual(basic_provider._normalize_string_list(42), ["42"])


class TestGlobHelpers(unittest.TestCase):
    def test_analysis_matches_glob_expands_trailing_slash(self):
        self.assertTrue(basic_provider._analysis_matches_glob("src/app.py", "src/"))

    def test_analysis_matches_glob_returns_false_on_invalid_pattern(self):
        with mock.patch("fnmatch.fnmatchcase", side_effect=ValueError("bad pattern")):
            self.assertFalse(basic_provider._analysis_matches_glob("src/app.py", "src/**"))

    def test_should_skip_analysis_path_normalizes_backslashes(self):
        cfg = {"analysis": {"exclude-globs": ["build/**", "obj/**"]}}
        self.assertTrue(basic_provider._should_skip_analysis_path(r"build\generated.cs", cfg))
        self.assertFalse(basic_provider._should_skip_analysis_path("src/main.cs", cfg))


class TestModuleAndOwnershipDiscovery(unittest.TestCase):
    def test_get_module_map_auto_discovers_core_and_ignores_standard_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "main.py").write_text("print('ok')\n", encoding="utf-8")
            (root / "setup.py").write_text("from setuptools import setup\n", encoding="utf-8")
            (root / "src").mkdir()
            (root / "data").mkdir()
            (root / "__pycache__").mkdir()
            (root / "node_modules").mkdir()
            (root / ".hidden").mkdir()

            result = basic_provider._get_module_map(root, {})

        self.assertEqual(result["core"], ["main.py"])
        self.assertEqual(result["src"], ["src/"])
        self.assertNotIn("data", result)
        self.assertNotIn("__pycache__", result)
        self.assertNotIn("node_modules", result)
        self.assertNotIn(".hidden", result)

    def test_get_first_party_from_config_includes_package_dirs_and_modules(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pkg").mkdir()
            (root / "pkg" / "__init__.py").write_text("", encoding="utf-8")
            cfg = {"modules": {"core": ["single.py", "pkg/", "pkg/__init__.py", "docs/"]}}

            result = basic_provider._get_first_party(root, cfg)

        self.assertEqual(result, {"pkg", "single"})


class TestFileAndImportHelpers(unittest.TestCase):
    def test_count_lines_returns_zero_on_oserror(self):
        with mock.patch.object(Path, "open", side_effect=OSError("boom")):
            self.assertEqual(basic_provider._count_lines(Path("missing.py")), 0)

    def test_extract_python_imports_filters_to_first_party(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "module.py"
            path.write_text(
                "\n".join(
                    [
                        "# comment only",
                        "from app.services import Service",
                        "import app, app.utils as utils, thirdparty",
                        "import app.models as models",
                        "from thirdparty.helpers import value",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            imports = basic_provider._extract_python_imports(path, {"app"})

        self.assertEqual(imports, ["app", "app.models", "app.services", "app.utils"])

    def test_extract_python_definitions_only_returns_top_level_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "module.py"
            path.write_text(
                "\n".join(
                    [
                        "class TopLevel:",
                        "    def method(self):",
                        "        pass",
                        "",
                        "def utility():",
                        "    def inner():",
                        "        return None",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            definitions = basic_provider._extract_python_definitions(path)

        self.assertEqual(definitions["classes"], ["TopLevel"])
        self.assertEqual(definitions["functions"], ["utility"])

    def test_extract_cpp_metadata_collects_unique_symbols(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "widget.cpp"
            path.write_text(
                "\n".join(
                    [
                        '#include "widget.h"',
                        "#include <vector>",
                        "class Widget {};",
                        "struct State {};",
                        "namespace Demo {}",
                        "enum class Mode { A, B };",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            metadata = basic_provider._extract_cpp_metadata(path)

        self.assertEqual(metadata["includes"], ["vector", "widget.h"])
        self.assertEqual(metadata["symbols"], ["Demo", "Mode", "State", "Widget"])

    def test_extract_razor_metadata_dedupes_routes_injects_and_usings(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Counter.razor"
            path.write_text(
                "\n".join(
                    [
                        '@page "/counter"',
                        '@page "/counter"',
                        "@using Demo.Services",
                        "@using Demo.Services",
                        "@inject NavigationManager Nav",
                        "@inject NavigationManager Nav",
                        "<h1>Counter</h1>",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            metadata = basic_provider._extract_razor_metadata(path)

        self.assertEqual(metadata["razor_routes"], ["/counter"])
        self.assertEqual(metadata["razor_injects"], ["NavigationManager"])
        self.assertEqual(metadata["usings"], ["Demo.Services"])


class TestReferenceHelpers(unittest.TestCase):
    def test_resolve_analysis_reference_prefers_relative_path(self):
        known_paths = {"App/Lib/Shared.csproj", "Shared.csproj"}
        name_index = {"Shared.csproj": ["Shared.csproj"]}
        self.assertEqual(
            basic_provider._resolve_analysis_reference("App/App.csproj", "Lib/Shared.csproj", known_paths, name_index),
            "App/Lib/Shared.csproj",
        )

    def test_resolve_analysis_reference_uses_unique_basename_and_rejects_ambiguous_names(self):
        known_paths = {"src/Unique.csproj", "src/One/App.csproj", "src/Two/App.csproj"}
        name_index = {
            "Unique.csproj": ["src/Unique.csproj"],
            "App.csproj": ["src/One/App.csproj", "src/Two/App.csproj"],
        }
        self.assertEqual(
            basic_provider._resolve_analysis_reference("Demo.sln", "Unique.csproj", known_paths, name_index),
            "src/Unique.csproj",
        )
        self.assertEqual(
            basic_provider._resolve_analysis_reference("Demo.sln", "App.csproj", known_paths, name_index),
            "",
        )

    def test_resolve_python_import_reference_prefers_module_before_package(self):
        known_paths = {"pkg.py", "pkg/__init__.py", "other/__init__.py"}
        self.assertEqual(basic_provider._resolve_python_import_reference("pkg", known_paths), "pkg.py")
        self.assertEqual(
            basic_provider._resolve_python_import_reference("other", known_paths),
            "other/__init__.py",
        )
        self.assertEqual(basic_provider._resolve_python_import_reference("", known_paths), "")

    def test_add_dependency_edge_skips_self_empty_and_duplicates(self):
        edges: list[dict] = []
        seen: set[tuple[str, str, str]] = set()

        basic_provider._add_dependency_edge(edges, seen, "", "b", "kind")
        basic_provider._add_dependency_edge(edges, seen, "a", "a", "kind")
        basic_provider._add_dependency_edge(edges, seen, "a", "b", "kind")
        basic_provider._add_dependency_edge(edges, seen, "a", "b", "kind")

        self.assertEqual(edges, [{"from": "a", "to": "b", "kind": "kind"}])


class TestProjectSelectionHelpers(unittest.TestCase):
    def test_looks_like_test_project_checks_multiple_fields(self):
        self.assertTrue(
            basic_provider._looks_like_test_project({"path": "tests/App.Tests.csproj", "name": "AppTests", "root_namespace": "Demo.Tests"})
        )
        self.assertFalse(basic_provider._looks_like_test_project({"path": "src/App.csproj", "name": "App", "root_namespace": "Demo.App"}))

    def test_select_project_candidate_prefers_packaging_for_manifests(self):
        entry = {"path": "Package/Package.appxmanifest"}
        candidates = [
            {"path": "App/App.csproj", "project_role": "application"},
            {"path": "Package/App.Package.wapproj", "project_role": "packaging"},
        ]
        selected = basic_provider._select_project_candidate(entry, candidates)
        self.assertEqual(selected["path"], "Package/App.Package.wapproj")

    def test_select_project_candidate_prefers_database_for_sql_files(self):
        entry = {"path": "Db/V001__init.sql"}
        candidates = [
            {"path": "App/App.csproj", "project_role": "application"},
            {"path": "Db/Database.sqlproj", "project_role": "database"},
        ]
        selected = basic_provider._select_project_candidate(entry, candidates)
        self.assertEqual(selected["path"], "Db/Database.sqlproj")

    def test_select_project_candidate_prefers_executable_non_test_ui_project(self):
        entry = {"path": "App/MainWindow.xaml"}
        candidates = [
            {
                "path": "App.Tests/App.Tests.csproj",
                "name": "App.Tests",
                "root_namespace": "Demo.App.Tests",
                "desktop_targets": ["wpf"],
                "output_type": "WinExe",
            },
            {
                "path": "App/App.csproj",
                "name": "App",
                "root_namespace": "Demo.App",
                "desktop_targets": ["wpf"],
                "output_type": "WinExe",
            },
        ]

        selected = basic_provider._select_project_candidate(entry, candidates)

        self.assertEqual(selected["path"], "App/App.csproj")

    def test_resolve_cpp_include_reference_prefers_relative_path_then_unique_category_match(self):
        direct = basic_provider._resolve_cpp_include_reference(
            {"path": "src/main.cpp", "category": "native"},
            "../include/widget.h",
            {"include/widget.h"},
            {},
            {("native", "widget.h"): ["headers/widget.h"]},
        )
        category = basic_provider._resolve_cpp_include_reference(
            {"path": "src/main.cpp", "category": "native"},
            "widget.h",
            {"other/file.h"},
            {},
            {("native", "widget.h"): ["headers/widget.h"]},
        )

        self.assertEqual(direct, "include/widget.h")
        self.assertEqual(category, "headers/widget.h")

    def test_resolve_cpp_include_reference_rejects_ambiguous_project_match(self):
        result = basic_provider._resolve_cpp_include_reference(
            {"path": "src/main.cpp", "project": "App/App.csproj", "category": "native"},
            "widget.h",
            set(),
            {("App/App.csproj", "widget.h"): ["include/widget.h", "alt/widget.h"]},
            {("native", "widget.h"): ["headers/widget.h"]},
        )

        self.assertEqual(result, "")


if __name__ == "__main__":
    unittest.main()
