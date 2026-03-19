"""Direct tests for analysis.dotnet_cli_provider helper functions."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from analysis import dotnet_cli_provider  # noqa: E402
from analysis.models import AnalysisRequest  # noqa: E402


def _request(root: Path, cfg: dict | None = None) -> AnalysisRequest:
    return AnalysisRequest(root=root, cfg=cfg or {}, generated_at="2026-03-12T00:00:00+00:00")


class TestDotnetCliAvailable(unittest.TestCase):
    def test_returns_not_found_when_dotnet_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            request = _request(Path(tmp))
            with mock.patch.object(dotnet_cli_provider.shutil, "which", return_value=None):
                self.assertEqual(
                    dotnet_cli_provider.dotnet_cli_available(request),
                    (False, "dotnet-not-found"),
                )

    def test_returns_no_projects_when_no_candidates_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            request = _request(Path(tmp))
            with mock.patch.object(dotnet_cli_provider.shutil, "which", return_value="dotnet"):
                self.assertEqual(
                    dotnet_cli_provider.dotnet_cli_available(request),
                    (False, "no-dotnet-projects"),
                )

    def test_returns_available_when_inventory_contains_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            request = _request(Path(tmp))
            current = {"inventory": {"files": [{"path": "src/App.csproj"}]}}
            with mock.patch.object(dotnet_cli_provider.shutil, "which", return_value="dotnet"):
                self.assertEqual(dotnet_cli_provider.dotnet_cli_available(request, current), (True, ""))


class TestCandidateProjectPaths(unittest.TestCase):
    def test_prefers_inventory_and_filters_irrelevant_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            request = _request(Path(tmp))
            current = {
                "inventory": {
                    "files": [
                        {"path": "src/App.csproj"},
                        {"path": "src/App.csproj"},
                        {"path": "pkg/Installer.wapproj"},
                        {"path": "native/App.vcxproj"},
                        {"path": "db/Schema.sqlproj"},
                        {"path": "Demo.slnx"},
                        {"path": "notes.txt"},
                    ]
                }
            }

            result = dotnet_cli_provider._candidate_project_paths(request, current)

        self.assertEqual(
            result["projects"],
            ["db/Schema.sqlproj", "native/App.vcxproj", "pkg/Installer.wapproj", "src/App.csproj"],
        )
        self.assertEqual(result["solutions"], ["Demo.slnx"])

    def test_scans_filesystem_when_inventory_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "pkg").mkdir()
            (root / "src" / "App.csproj").write_text("<Project />", encoding="utf-8")
            (root / "pkg" / "Installer.wapproj").write_text("<Project />", encoding="utf-8")
            (root / "Demo.sln").write_text("Microsoft Visual Studio Solution File\n", encoding="utf-8")

            result = dotnet_cli_provider._candidate_project_paths(_request(root))

        self.assertEqual(result["projects"], ["pkg/Installer.wapproj", "src/App.csproj"])
        self.assertEqual(result["solutions"], ["Demo.sln"])


class TestRelativeFromMsbuildItem(unittest.TestCase):
    def test_uses_full_path_inside_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            file_path = root / "src" / "Views" / "MainWindow.xaml"
            file_path.parent.mkdir(parents=True)
            file_path.write_text("<Window />", encoding="utf-8")

            result = dotnet_cli_provider._relative_from_msbuild_item(
                root,
                "src/App.csproj",
                {"FullPath": str(file_path)},
            )

        self.assertEqual(result, "src/Views/MainWindow.xaml")

    def test_rejects_full_path_outside_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outside = Path(tmp).parent / "outside.cs"

            result = dotnet_cli_provider._relative_from_msbuild_item(
                root,
                "src/App.csproj",
                {"FullPath": str(outside)},
            )

        self.assertEqual(result, "")

    def test_resolves_identity_relative_to_project_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = dotnet_cli_provider._relative_from_msbuild_item(
                root,
                "src/App.csproj",
                {"Identity": r"Views\MainWindow.xaml"},
            )

        self.assertEqual(result, "src/Views/MainWindow.xaml")

    def test_returns_empty_when_item_has_no_path_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(
                dotnet_cli_provider._relative_from_msbuild_item(root, "src/App.csproj", {}),
                "",
            )


class TestProjectEntryHelpers(unittest.TestCase):
    def test_project_entry_collects_frameworks_desktop_targets_and_packaging(self):
        entry = dotnet_cli_provider._project_entry_from_properties(
            "pkg/App.wapproj",
            {
                "TargetFramework": "net8.0-windows",
                "TargetFrameworks": "net8.0-windows; net9.0-windows; net8.0-windows",
                "UseWPF": "true",
                "UseWinUI": "true",
                "UseBlazorWebView": "true",
                "UseMaui": "true",
                "OutputType": "WinExe",
                "AssemblyName": "DemoApp",
                "RootNamespace": "Demo.App",
                "ApplicationManifest": "app.manifest",
                "AppxManifest": "Package.appxmanifest",
                "WindowsPackageType": "MSIX",
                "EnableMsixTooling": "true",
            },
        )

        self.assertEqual(entry["target_frameworks"], ["net8.0-windows", "net9.0-windows"])
        self.assertEqual(entry["desktop_targets"], ["blazor-hybrid", "maui", "winui", "wpf"])
        self.assertEqual(entry["output_type"], "WinExe")
        self.assertEqual(entry["assembly_name"], "DemoApp")
        self.assertEqual(entry["root_namespace"], "Demo.App")
        self.assertEqual(entry["application_manifest"], "app.manifest")
        self.assertEqual(entry["appx_manifest"], "Package.appxmanifest")
        self.assertEqual(entry["windows_package_type"], "MSIX")
        self.assertEqual(entry["project_role"], "packaging")
        self.assertEqual(entry["packaging_model"], "msix")

    def test_project_entry_marks_sqlproj_as_database(self):
        entry = dotnet_cli_provider._project_entry_from_properties("db/Schema.sqlproj", {})
        self.assertEqual(entry["project_role"], "database")
        self.assertEqual(entry["project_kind"], "database")

    def test_project_node_copies_optional_fields(self):
        node = dotnet_cli_provider._project_node_from_entry(
            "App/App.csproj",
            {
                "assembly_name": "DemoApp",
                "desktop_targets": ["wpf"],
                "target_frameworks": ["net8.0-windows"],
                "output_type": "WinExe",
                "project_role": "application",
                "packaging_model": "msix",
                "package_manifest": "App/Package.appxmanifest",
                "package_identity": "DemoApp",
                "package_entry_point": "DemoApp.App",
                "package_references": [{"name": "Newtonsoft.Json"}],
            },
        )

        self.assertEqual(node["name"], "DemoApp")
        self.assertEqual(node["project_kind"], "msbuild")
        self.assertEqual(node["desktop_targets"], ["wpf"])
        self.assertEqual(node["package_manifest"], "App/Package.appxmanifest")
        self.assertEqual(node["package_identity"], "DemoApp")
        self.assertEqual(node["package_entry_point"], "DemoApp.App")
        self.assertEqual(node["package_references"], [{"name": "Newtonsoft.Json"}])


class TestPackageHelpers(unittest.TestCase):
    def test_package_reference_from_item_handles_empty_identity(self):
        self.assertEqual(dotnet_cli_provider._package_reference_from_item({}), {})

    def test_package_reference_from_item_includes_optional_fields(self):
        package = dotnet_cli_provider._package_reference_from_item(
            {
                "Identity": "Newtonsoft.Json",
                "Version": "13.0.3",
                "PrivateAssets": "all",
                "IncludeAssets": "runtime; build",
                "ExcludeAssets": "analyzers",
            }
        )
        self.assertEqual(
            package,
            {
                "name": "Newtonsoft.Json",
                "version": "13.0.3",
                "private_assets": "all",
                "include_assets": "runtime; build",
                "exclude_assets": "analyzers",
            },
        )

    def test_merge_package_references_preserves_order_and_merges_existing(self):
        merged = dotnet_cli_provider._merge_package_references(
            [
                {"name": "A", "version": "1.0"},
                {"name": "B", "version": "2.0"},
            ],
            [
                {"name": "A", "private_assets": "all"},
                {"name": "C", "version": "3.0"},
            ],
        )

        self.assertEqual(
            merged,
            [
                {"name": "A", "version": "1.0", "private_assets": "all"},
                {"name": "B", "version": "2.0"},
                {"name": "C", "version": "3.0"},
            ],
        )

    def test_dedupe_msbuild_items_prefers_project_file_over_props(self):
        deduped = dotnet_cli_provider._dedupe_msbuild_items(
            [
                {"Identity": "Views/MainWindow.xaml", "DefiningProjectExtension": ".props", "SubType": "Designer"},
                {"Identity": "Views/MainWindow.xaml", "DefiningProjectExtension": ".csproj", "SubType": "Code"},
                {"Identity": "Views/About.xaml", "DefiningProjectExtension": ".targets"},
            ]
        )

        self.assertEqual(len(deduped), 2)
        self.assertEqual(deduped[0]["SubType"], "Code")
        self.assertEqual(deduped[1]["Identity"], "Views/About.xaml")

    def test_item_priority_defaults_to_low_for_unknown_extensions(self):
        self.assertEqual(dotnet_cli_provider._item_priority({"DefiningProjectExtension": ".csproj"}), 3)
        self.assertEqual(dotnet_cli_provider._item_priority({"DefiningProjectExtension": ".targets"}), 2)
        self.assertEqual(dotnet_cli_provider._item_priority({"DefiningProjectExtension": ".txt"}), 1)

    def test_resolve_dependent_upon_normalizes_backslashes(self):
        self.assertEqual(
            dotnet_cli_provider._resolve_dependent_upon("Views/MainWindow.xaml", r"MainWindow.xaml.cs"),
            "Views/MainWindow.xaml.cs",
        )


class TestMergeHelpers(unittest.TestCase):
    def test_merge_records_merges_lists_dicts_and_project_memberships(self):
        merged = dotnet_cli_provider._merge_records(
            {
                "path": "App/App.csproj",
                "project": "App/App.csproj",
                "desktop_targets": ["wpf"],
                "metadata": {"version": "1.0"},
                "output_type": "WinExe",
            },
            {
                "path": "App/App.csproj",
                "project_memberships": ["Shared/Shared.csproj"],
                "desktop_targets": ["avalonia"],
                "metadata": {"commit": "abc123"},
                "output_type": "",
                "root_namespace": "Demo.App",
            },
        )

        self.assertEqual(merged["project"], "App/App.csproj")
        self.assertEqual(
            merged["project_memberships"],
            ["App/App.csproj", "Shared/Shared.csproj"],
        )
        self.assertEqual(merged["desktop_targets"], ["wpf", "avalonia"])
        self.assertEqual(merged["metadata"], {"version": "1.0", "commit": "abc123"})
        self.assertEqual(merged["output_type"], "WinExe")
        self.assertEqual(merged["root_namespace"], "Demo.App")

    def test_merge_lists_appends_only_new_values(self):
        self.assertEqual(dotnet_cli_provider._merge_lists(["a", "b"], ["b", "c"]), ["a", "b", "c"])


class TestRunDotnetCliAnalysisFailures(unittest.TestCase):
    def test_raises_last_solution_failure_when_nothing_contributes(self):
        with tempfile.TemporaryDirectory() as tmp:
            request = _request(Path(tmp))
            current = {"inventory": {"files": [{"path": "Demo.sln"}]}}

            with mock.patch.object(
                dotnet_cli_provider,
                "_run_solution_list",
                side_effect=subprocess.TimeoutExpired(cmd="dotnet", timeout=20),
            ):
                with self.assertRaisesRegex(RuntimeError, "timed out while listing solution Demo.sln"):
                    dotnet_cli_provider.run_dotnet_cli_analysis(request, current)

    def test_raises_last_project_failure_when_project_queries_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            request = _request(Path(tmp))
            current = {"inventory": {"files": [{"path": "App/App.csproj"}]}}

            with mock.patch.object(
                dotnet_cli_provider,
                "_run_msbuild_query",
                side_effect=subprocess.CalledProcessError(1, "dotnet"),
            ):
                with self.assertRaisesRegex(RuntimeError, "failed while analyzing project App/App.csproj"):
                    dotnet_cli_provider.run_dotnet_cli_analysis(request, current)


if __name__ == "__main__":
    unittest.main()
