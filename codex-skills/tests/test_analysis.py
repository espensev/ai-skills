"""Tests for analyze_project() — project scanning and analysis."""

import argparse
import io
import subprocess
import tempfile
import textwrap
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

import task_manager
from analysis import basic_provider, dotnet_cli_provider
from analysis.models import ANALYSIS_SCHEMA_VERSION


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

    def test_default_analysis_excludes_runtime_cache_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "app.py").write_text("print('ok')\n", encoding="utf-8")
            (root / ".mypy_cache").mkdir()
            (root / ".mypy_cache" / "cache.py").write_text("x = 1\n", encoding="utf-8")
            (root / ".pytest_cache").mkdir()
            (root / ".pytest_cache" / "cache.py").write_text("x = 2\n", encoding="utf-8")
            (root / ".ruff_cache").mkdir()
            (root / ".ruff_cache" / "cache.py").write_text("x = 3\n", encoding="utf-8")
            (root / ".venv").mkdir()
            (root / ".venv" / "cache.py").write_text("x = 4\n", encoding="utf-8")
            (root / "venv").mkdir()
            (root / "venv" / "cache.py").write_text("x = 5\n", encoding="utf-8")
            (root / ".tox").mkdir()
            (root / ".tox" / "cache.py").write_text("x = 6\n", encoding="utf-8")

            discovered = basic_provider._iter_analysis_files(root, {})
            rel_paths = {str(path.relative_to(root)).replace("\\", "/") for path in discovered}

        self.assertIn("app.py", rel_paths)
        self.assertNotIn(".mypy_cache/cache.py", rel_paths)
        self.assertNotIn(".pytest_cache/cache.py", rel_paths)
        self.assertNotIn(".ruff_cache/cache.py", rel_paths)
        self.assertNotIn(".venv/cache.py", rel_paths)
        self.assertNotIn("venv/cache.py", rel_paths)
        self.assertNotIn(".tox/cache.py", rel_paths)

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

    def test_extract_csharp_metadata_handles_record_declarations(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Models.cs"
            path.write_text(
                textwrap.dedent(
                    """\
                    namespace Demo;
                    public record User(string Name);
                    public partial record class Customer(int Id);
                    public readonly record struct Token(string Value);
                    """
                ),
                encoding="utf-8",
            )

            metadata = basic_provider._extract_csharp_metadata(path)

        self.assertEqual(metadata["namespaces"], ["Demo"])
        self.assertEqual(metadata["types"], ["Customer", "Token", "User"])

    def test_analyze_csharp_type_reference_prefers_imported_namespace_over_same_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "App" / "ViewModels").mkdir(parents=True)
            (root / "Shared").mkdir()
            (root / "App" / "App.csproj").write_text(
                textwrap.dedent(
                    """\
                    <Project Sdk="Microsoft.NET.Sdk">
                      <ItemGroup>
                        <ProjectReference Include="..\\Shared\\Shared.csproj" />
                      </ItemGroup>
                    </Project>
                    """
                ),
                encoding="utf-8",
            )
            (root / "Shared" / "Shared.csproj").write_text(
                '<Project Sdk="Microsoft.NET.Sdk"></Project>\n',
                encoding="utf-8",
            )
            (root / "App" / "Service.cs").write_text(
                "namespace App.Services; public class Service {}\n",
                encoding="utf-8",
            )
            (root / "Shared" / "Service.cs").write_text(
                "namespace Shared; public class Service {}\n",
                encoding="utf-8",
            )
            (root / "App" / "ViewModels" / "ViewModel.cs").write_text(
                textwrap.dedent(
                    """\
                    using Shared;
                    namespace App.ViewModels;
                    public class ViewModel
                    {
                        private readonly Service _service = new();
                    }
                    """
                ),
                encoding="utf-8",
            )

            cfg = {
                "analysis": {"mode": "basic"},
                "modules": {"app": ["App/"], "shared": ["Shared/"]},
            }
            with mock.patch.object(task_manager, "ROOT", root), mock.patch.object(task_manager, "_CFG", cfg):
                result = task_manager.analyze_project()

        edge_kinds = {(edge["from"], edge["to"], edge.get("kind", "")) for edge in result["dependency_edges"]}
        self.assertIn(("App/ViewModels/ViewModel.cs", "Shared/Service.cs", "csharp-type-reference"), edge_kinds)
        self.assertNotIn(("App/ViewModels/ViewModel.cs", "App/Service.cs", "csharp-type-reference"), edge_kinds)
        view_model = next(entry for entry in result["files"] if entry["path"] == "App/ViewModels/ViewModel.cs")
        self.assertEqual(view_model["type_references"], ["Service"])

    def test_analyze_csharp_type_reference_omits_ambiguous_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "App" / "ViewModels").mkdir(parents=True)
            (root / "Shared").mkdir()
            (root / "App" / "App.csproj").write_text(
                textwrap.dedent(
                    """\
                    <Project Sdk="Microsoft.NET.Sdk">
                      <ItemGroup>
                        <ProjectReference Include="..\\Shared\\Shared.csproj" />
                      </ItemGroup>
                    </Project>
                    """
                ),
                encoding="utf-8",
            )
            (root / "Shared" / "Shared.csproj").write_text(
                '<Project Sdk="Microsoft.NET.Sdk"></Project>\n',
                encoding="utf-8",
            )
            (root / "App" / "Service.cs").write_text(
                "namespace App.Services; public class Service {}\n",
                encoding="utf-8",
            )
            (root / "Shared" / "Service.cs").write_text(
                "namespace Shared; public class Service {}\n",
                encoding="utf-8",
            )
            (root / "App" / "ViewModels" / "ViewModel.cs").write_text(
                textwrap.dedent(
                    """\
                    namespace App.ViewModels;
                    public class ViewModel
                    {
                        private readonly Service _service = new();
                    }
                    """
                ),
                encoding="utf-8",
            )

            cfg = {
                "analysis": {"mode": "basic"},
                "modules": {"app": ["App/"], "shared": ["Shared/"]},
            }
            with mock.patch.object(task_manager, "ROOT", root), mock.patch.object(task_manager, "_CFG", cfg):
                result = task_manager.analyze_project()

        edge_kinds = {(edge["from"], edge["to"], edge.get("kind", "")) for edge in result["dependency_edges"]}
        self.assertNotIn(("App/ViewModels/ViewModel.cs", "App/Service.cs", "csharp-type-reference"), edge_kinds)
        self.assertNotIn(("App/ViewModels/ViewModel.cs", "Shared/Service.cs", "csharp-type-reference"), edge_kinds)
        view_model = next(entry for entry in result["files"] if entry["path"] == "App/ViewModels/ViewModel.cs")
        self.assertNotIn("type_references", view_model)

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

    def test_analyze_blazor_hybrid_maui_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "App" / "Pages").mkdir(parents=True)

            (root / "App" / "App.csproj").write_text(
                textwrap.dedent(
                    """\
                    <Project Sdk="Microsoft.NET.Sdk">
                      <PropertyGroup>
                        <TargetFramework>net8.0</TargetFramework>
                        <OutputType>Exe</OutputType>
                        <UseMaui>true</UseMaui>
                        <UseBlazorWebView>true</UseBlazorWebView>
                      </PropertyGroup>
                    </Project>
                    """
                ),
                encoding="utf-8",
            )
            (root / "App" / "MauiProgram.cs").write_text(
                "namespace Demo; public static class MauiProgram {}\n",
                encoding="utf-8",
            )
            (root / "App" / "AppShell.xaml").write_text(
                '<Shell x:Class="Demo.AppShell" xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"></Shell>\n',
                encoding="utf-8",
            )
            (root / "App" / "AppShell.xaml.cs").write_text(
                "namespace Demo; public partial class AppShell {}\n",
                encoding="utf-8",
            )
            (root / "App" / "Pages" / "Home.razor").write_text(
                '@page "/"\n@inject NavigationManager Nav\n<h1>Home</h1>\n',
                encoding="utf-8",
            )
            (root / "App" / "Pages" / "Home.razor.cs").write_text(
                "namespace Demo.Pages; public partial class Home {}\n",
                encoding="utf-8",
            )
            (root / "App" / "Pages" / "Counter.razor").write_text(
                '@page "/counter"\n@using Demo.Services\n@inject CounterService CS\n<p>Count</p>\n',
                encoding="utf-8",
            )

            with mock.patch.object(task_manager, "ROOT", root), mock.patch.object(task_manager, "_CFG", {}):
                result = task_manager.analyze_project()

        self.assertIn("blazor", result["detected_stacks"])
        self.assertIn("blazor-hybrid", result["detected_stacks"])
        self.assertIn("maui", result["detected_stacks"])
        self.assertIn("dotnet", result["detected_stacks"])
        self.assertIn("xaml-ui", result["detected_stacks"])

        csproj_entry = next(entry for entry in result["files"] if entry["path"] == "App/App.csproj")
        self.assertIn("blazor-hybrid", csproj_entry["desktop_targets"])
        self.assertIn("maui", csproj_entry["desktop_targets"])

        counter = next(entry for entry in result["files"] if entry["path"] == "App/Pages/Counter.razor")
        self.assertEqual(counter["razor_routes"], ["/counter"])
        self.assertEqual(counter["razor_injects"], ["CounterService"])
        self.assertEqual(counter["usings"], ["Demo.Services"])

        home = next(entry for entry in result["files"] if entry["path"] == "App/Pages/Home.razor")
        self.assertEqual(home["code_behind"], "App/Pages/Home.razor.cs")

        edge_kinds = {(edge["from"], edge["to"], edge.get("kind", "")) for edge in result["dependency_edges"]}
        self.assertIn(("App/Pages/Home.razor", "App/Pages/Home.razor.cs", "razor-code-behind"), edge_kinds)
        self.assertIn(("App/AppShell.xaml", "App/AppShell.xaml.cs", "xaml-code-behind"), edge_kinds)

        conflict_zones = {(tuple(zone["files"]), zone["reason"]) for zone in result["conflict_zones"]}
        self.assertIn(
            (("App/Pages/Home.razor", "App/Pages/Home.razor.cs"), "razor-code-behind pair"),
            conflict_zones,
        )

        derived = result["analysis_v2"]["derived"]
        shell_surface = next(
            (surface for surface in derived["ui_surfaces"] if surface["kind"] == "shell"),
            None,
        )
        self.assertIsNotNone(shell_surface)
        self.assertIn("App/AppShell.xaml", shell_surface["files"])

        webui_surface = next(
            (surface for surface in derived["ui_surfaces"] if surface["kind"] == "webui"),
            None,
        )
        self.assertIsNotNone(webui_surface)
        self.assertEqual(webui_surface["project"], "App/App.csproj")

    def test_analyze_razor_code_behind_uses_correct_edge_kind(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "App").mkdir()

            (root / "App" / "App.csproj").write_text(
                textwrap.dedent(
                    """\
                    <Project Sdk="Microsoft.NET.Sdk">
                      <PropertyGroup>
                        <UseBlazorWebView>true</UseBlazorWebView>
                      </PropertyGroup>
                    </Project>
                    """
                ),
                encoding="utf-8",
            )
            (root / "App" / "Component.razor").write_text(
                "<h1>Component</h1>\n",
                encoding="utf-8",
            )
            (root / "App" / "Component.razor.cs").write_text(
                "namespace App; public partial class Component {}\n",
                encoding="utf-8",
            )
            (root / "App" / "Window.xaml").write_text(
                '<Window x:Class="App.Window" xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"></Window>\n',
                encoding="utf-8",
            )
            (root / "App" / "Window.xaml.cs").write_text(
                "namespace App; public partial class Window {}\n",
                encoding="utf-8",
            )

            with mock.patch.object(task_manager, "ROOT", root), mock.patch.object(task_manager, "_CFG", {}):
                result = task_manager.analyze_project()

        edge_kinds = {(edge["from"], edge["to"], edge.get("kind", "")) for edge in result["dependency_edges"]}
        self.assertIn(("App/Component.razor", "App/Component.razor.cs", "razor-code-behind"), edge_kinds)
        self.assertIn(("App/Window.xaml", "App/Window.xaml.cs", "xaml-code-behind"), edge_kinds)
        self.assertNotIn(("App/Component.razor", "App/Component.razor.cs", "xaml-code-behind"), edge_kinds)
        self.assertNotIn(("App/Window.xaml", "App/Window.xaml.cs", "razor-code-behind"), edge_kinds)

    def test_analyze_maui_appshell_detected_as_shell_surface(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "App").mkdir()

            (root / "App" / "App.csproj").write_text(
                '<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><UseMaui>true</UseMaui></PropertyGroup></Project>\n',
                encoding="utf-8",
            )
            (root / "App" / "AppShell.xaml").write_text(
                '<Shell x:Class="Demo.AppShell" xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"></Shell>\n',
                encoding="utf-8",
            )
            (root / "App" / "AppShell.xaml.cs").write_text(
                "namespace Demo; public partial class AppShell {}\n",
                encoding="utf-8",
            )

            with mock.patch.object(task_manager, "ROOT", root), mock.patch.object(task_manager, "_CFG", {}):
                result = task_manager.analyze_project()

        conflict_zones = {(tuple(zone["files"]), zone["reason"]) for zone in result["conflict_zones"]}
        self.assertTrue(
            any("App/AppShell.xaml" in files and reason == "desktop shell surface" for files, reason in conflict_zones),
        )
        derived = result["analysis_v2"]["derived"]
        shell_surface = next(
            (surface for surface in derived["ui_surfaces"] if surface["kind"] == "shell"),
            None,
        )
        self.assertIsNotNone(shell_surface)
        self.assertIn("App/AppShell.xaml", shell_surface["files"])

    def test_analyze_xaml_extracts_root_element_type_and_merge_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "App" / "Themes").mkdir(parents=True)

            (root / "App" / "App.csproj").write_text(
                '<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><UseWPF>true</UseWPF></PropertyGroup></Project>\n',
                encoding="utf-8",
            )
            (root / "App" / "Themes" / "Dark.xaml").write_text(
                textwrap.dedent(
                    """\
                    <ResourceDictionary xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation">
                      <ResourceDictionary.MergedDictionaries>
                        <ResourceDictionary Source="Colors.xaml"/>
                      </ResourceDictionary.MergedDictionaries>
                    </ResourceDictionary>
                    """
                ),
                encoding="utf-8",
            )
            (root / "App" / "Themes" / "Colors.xaml").write_text(
                '<ResourceDictionary xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"></ResourceDictionary>\n',
                encoding="utf-8",
            )

            with mock.patch.object(task_manager, "ROOT", root), mock.patch.object(task_manager, "_CFG", {}):
                result = task_manager.analyze_project()

        dark_entry = next(entry for entry in result["files"] if entry["path"] == "App/Themes/Dark.xaml")
        self.assertEqual(dark_entry["root_element_type"], "ResourceDictionary")
        self.assertEqual(dark_entry["resource_merge_sources"], ["Colors.xaml"])

        colors_entry = next(entry for entry in result["files"] if entry["path"] == "App/Themes/Colors.xaml")
        self.assertEqual(colors_entry["root_element_type"], "ResourceDictionary")

    def test_analyze_cpp_header_source_conflict_zones(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Native" / "src").mkdir(parents=True)
            (root / "Native" / "include").mkdir(parents=True)

            (root / "Native" / "CMakeLists.txt").write_text(
                "add_library(native_a src/widget.cpp)\n",
                encoding="utf-8",
            )
            (root / "Native" / "src" / "widget.cpp").write_text(
                '#include "widget.h"\nclass WidgetImpl {};\n',
                encoding="utf-8",
            )
            (root / "Native" / "src" / "widget.h").write_text(
                "class Widget {};\n",
                encoding="utf-8",
            )
            (root / "Native" / "src" / "helper.cpp").write_text(
                "void helper() {}\n",
                encoding="utf-8",
            )

            with mock.patch.object(task_manager, "ROOT", root), mock.patch.object(task_manager, "_CFG", {}):
                result = task_manager.analyze_project()

        conflict_zones = {(tuple(zone["files"]), zone["reason"]) for zone in result["conflict_zones"]}
        has_cpp_pair = any(
            reason == "cpp header-source pair" and "Native/src/widget.cpp" in files and "Native/src/widget.h" in files
            for files, reason in conflict_zones
        )
        self.assertTrue(has_cpp_pair)
        has_helper_pair = any(reason == "cpp header-source pair" and "Native/src/helper.cpp" in files for files, reason in conflict_zones)
        self.assertFalse(has_helper_pair)

    def test_analyze_cmake_extracts_source_file_lists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Native").mkdir()

            (root / "Native" / "CMakeLists.txt").write_text(
                "add_executable(app main.cpp utils.cpp)\nadd_library(mylib STATIC lib.cpp)\n",
                encoding="utf-8",
            )
            (root / "Native" / "main.cpp").write_text("int main() {}\n", encoding="utf-8")
            (root / "Native" / "utils.cpp").write_text("void util() {}\n", encoding="utf-8")
            (root / "Native" / "lib.cpp").write_text("void lib() {}\n", encoding="utf-8")

            with mock.patch.object(task_manager, "ROOT", root), mock.patch.object(task_manager, "_CFG", {}):
                result = task_manager.analyze_project()

        cmake_entry = next(entry for entry in result["files"] if entry["path"] == "Native/CMakeLists.txt")
        self.assertEqual(sorted(cmake_entry["cmake_targets"]), ["app", "mylib"])
        self.assertEqual(cmake_entry["cmake_sources"]["app"], ["main.cpp", "utils.cpp"])
        self.assertEqual(cmake_entry["cmake_sources"]["mylib"], ["lib.cpp"])

    def test_analyze_razor_metadata_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "App").mkdir()

            (root / "App" / "App.csproj").write_text(
                '<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><UseBlazorWebView>true</UseBlazorWebView></PropertyGroup></Project>\n',
                encoding="utf-8",
            )
            (root / "App" / "Counter.razor").write_text(
                textwrap.dedent(
                    """\
                    @page "/counter"
                    @page "/counter/{id:int}"
                    @using MyApp.Services
                    @using MyApp.Models
                    @inject CounterService CS
                    @inject NavigationManager Nav
                    <h1>Counter</h1>
                    """
                ),
                encoding="utf-8",
            )

            with mock.patch.object(task_manager, "ROOT", root), mock.patch.object(task_manager, "_CFG", {}):
                result = task_manager.analyze_project()

        counter = next(entry for entry in result["files"] if entry["path"] == "App/Counter.razor")
        self.assertEqual(counter["razor_routes"], ["/counter", "/counter/{id:int}"])
        self.assertEqual(counter["razor_injects"], ["CounterService", "NavigationManager"])
        self.assertEqual(counter["usings"], ["MyApp.Models", "MyApp.Services"])

    def test_analyze_avalonia_axaml_detected_as_avalonia_stack(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "App").mkdir()
            (root / "App" / "App.csproj").write_text(
                textwrap.dedent(
                    """\
                    <Project Sdk="Microsoft.NET.Sdk">
                      <PropertyGroup>
                        <TargetFramework>net8.0</TargetFramework>
                        <OutputType>WinExe</OutputType>
                      </PropertyGroup>
                      <ItemGroup>
                        <PackageReference Include="Avalonia" Version="11.0.0" />
                        <PackageReference Include="Avalonia.Desktop" Version="11.0.0" />
                      </ItemGroup>
                    </Project>
                    """
                ),
                encoding="utf-8",
            )
            (root / "App" / "App.axaml").write_text(
                '<Application xmlns="https://github.com/avaloniaui" '
                'xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml" '
                'x:Class="Demo.App">\n'
                "  <Application.Styles>\n"
                '    <StyleInclude Source="avares://Demo/Styles.axaml" />\n'
                "  </Application.Styles>\n"
                "</Application>\n",
                encoding="utf-8",
            )
            (root / "App" / "App.axaml.cs").write_text(
                "namespace Demo; public partial class App { }\n",
                encoding="utf-8",
            )
            (root / "App" / "MainWindow.axaml").write_text(
                '<Window xmlns="https://github.com/avaloniaui" '
                'xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml" '
                'x:Class="Demo.MainWindow">\n'
                "  <TextBlock>Hello</TextBlock>\n"
                "</Window>\n",
                encoding="utf-8",
            )
            (root / "App" / "MainWindow.axaml.cs").write_text(
                "namespace Demo; public partial class MainWindow { }\n",
                encoding="utf-8",
            )

            cfg = {"analysis": {"mode": "basic"}}
            with mock.patch.object(task_manager, "ROOT", root), mock.patch.object(task_manager, "_CFG", cfg):
                result = task_manager.analyze_project()

        stacks = result["detected_stacks"]
        self.assertIn("avalonia", stacks)
        self.assertIn("xaml-ui", stacks)
        self.assertIn("dotnet", stacks)

        # .axaml code-behind resolved
        app_axaml = next(entry for entry in result["files"] if entry["path"] == "App/App.axaml")
        self.assertEqual(app_axaml["code_behind"], "App/App.axaml.cs")
        self.assertEqual(app_axaml["xaml_class"], "Demo.App")

        # MainWindow detected as shell surface
        main_window = next(entry for entry in result["files"] if entry["path"] == "App/MainWindow.axaml")
        self.assertEqual(main_window["code_behind"], "App/MainWindow.axaml.cs")

        # Avalonia StyleInclude extracted as resource merge source
        self.assertEqual(app_axaml["resource_merge_sources"], ["avares://Demo/Styles.axaml"])

        # Desktop targets include avalonia from PackageReference
        csproj = next(entry for entry in result["files"] if entry["path"] == "App/App.csproj")
        self.assertIn("avalonia", csproj.get("desktop_targets", []))

    def test_analyze_avalonia_styles_root_extracts_style_include_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Styles.axaml").write_text(
                '<Styles xmlns="https://github.com/avaloniaui">\n'
                '  <StyleInclude Source="avares://Demo/Controls.axaml" />\n'
                '  <StyleInclude Source="avares://Demo/Themes.axaml" />\n'
                "</Styles>\n",
                encoding="utf-8",
            )

            cfg = {"analysis": {"mode": "basic"}}
            with mock.patch.object(task_manager, "ROOT", root), mock.patch.object(task_manager, "_CFG", cfg):
                result = task_manager.analyze_project()

        styles = next(entry for entry in result["files"] if entry["path"] == "Styles.axaml")
        self.assertEqual(styles["root_element_type"], "Styles")
        self.assertEqual(
            styles["resource_merge_sources"],
            ["avares://Demo/Controls.axaml", "avares://Demo/Themes.axaml"],
        )

    def test_analyze_avalonia_dotnet_cli_provider_detects_avalonia_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "App").mkdir()
            (root / "App" / "App.csproj").write_text(
                '<Project Sdk="Microsoft.NET.Sdk"></Project>\n',
                encoding="utf-8",
            )

            property_payload = {
                "Properties": {
                    "TargetFramework": "net8.0",
                    "TargetFrameworks": "",
                    "OutputType": "WinExe",
                    "UseWPF": "",
                    "UseWinUI": "",
                    "UseBlazorWebView": "",
                    "UseMaui": "",
                    "AssemblyName": "AvaloniaApp",
                    "RootNamespace": "AvaloniaApp",
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
                        {"Include": "Avalonia", "Version": "11.0.0"},
                        {"Include": "Avalonia.Desktop", "Version": "11.0.0"},
                        {"Include": "Avalonia.Themes.Fluent", "Version": "11.0.0"},
                    ],
                    "Compile": [],
                    "Page": [],
                    "ApplicationDefinition": [],
                    "None": [],
                }
            }
            cfg = {"analysis": {"mode": "auto"}}

            with (
                mock.patch.object(task_manager, "ROOT", root),
                mock.patch.object(task_manager, "_CFG", cfg),
                mock.patch.object(dotnet_cli_provider.shutil, "which", return_value="dotnet"),
                mock.patch.object(dotnet_cli_provider, "_run_msbuild_query", side_effect=[property_payload, item_payload]),
                mock.patch.object(dotnet_cli_provider, "_run_solution_list", return_value=[]),
            ):
                result = task_manager.analyze_project()

        project = next(entry for entry in result["files"] if entry["path"] == "App/App.csproj")
        self.assertIn("avalonia", project.get("desktop_targets", []))

    def test_analyze_xaml_size_guard_skips_large_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Create a file and mock its size as over the limit
            (root / "Large.xaml").write_text("<ResourceDictionary />", encoding="utf-8")

            cfg = {"analysis": {"mode": "basic"}}

            original_stat = Path.stat

            def mock_stat(self, *args, **kwargs):
                result = original_stat(self, *args, **kwargs)
                if self.name == "Large.xaml":
                    # Return a mock with large size
                    import os

                    return os.stat_result(
                        (
                            result.st_mode,
                            result.st_ino,
                            result.st_dev,
                            result.st_nlink,
                            result.st_uid,
                            result.st_gid,
                            6 * 1024 * 1024,
                            result.st_atime,
                            result.st_mtime,
                            result.st_ctime,
                        )
                    )
                return result

            with (
                mock.patch.object(task_manager, "ROOT", root),
                mock.patch.object(task_manager, "_CFG", cfg),
                mock.patch.object(Path, "stat", mock_stat),
            ):
                result = task_manager.analyze_project()

        large = next(entry for entry in result["files"] if entry["path"] == "Large.xaml")
        self.assertEqual(large.get("skipped_reason"), "file_too_large")
        # Should NOT have root_element or xaml_class since it was skipped
        self.assertNotIn("root_element", large)
        self.assertNotIn("xaml_class", large)


if __name__ == "__main__":
    unittest.main()
