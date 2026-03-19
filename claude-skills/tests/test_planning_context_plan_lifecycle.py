# ruff: noqa: E402
"""Focused plan-lifecycle regressions for planning_context adoption."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import task_manager


class PlanningContextPlanLifecycleTests(unittest.TestCase):
    def _base_plan(self) -> dict:
        plan = {
            "id": "plan-200",
            "created_at": "2026-03-12T10:00:00+00:00",
            "status": "draft",
            "description": "Planning context lifecycle test",
            "agents": [],
            "groups": {},
            "conflicts": [],
            "integration_steps": [],
            "analysis_summary": {
                "total_files": 4,
                "total_lines": 120,
                "conflict_zones": [],
                "modules": {},
                "planning_context": {
                    "analysis_health": {
                        "mode": "auto",
                        "requested_providers": ["basic", "dotnet-cli"],
                        "applied_providers": ["basic"],
                        "skipped_providers": [{"name": "dotnet-cli", "reason": "not-available"}],
                        "partial_analysis": True,
                        "fallback_only": True,
                        "heuristic_only": True,
                        "confidence": "low",
                        "warnings": ["Optional analysis providers did not contribute; planning data is heuristic-only."],
                    },
                    "priority_projects": {
                        "startup": ["App/App.csproj"],
                        "packaging": ["App/App.Package.wapproj"],
                    },
                    "ownership_summary": {
                        "project_count": 1,
                        "assigned_file_count": 2,
                        "assigned_line_count": 80,
                        "unassigned_file_count": 1,
                        "unassigned_paths": ["App/LooseFile.cs"],
                        "projects": [],
                    },
                    "coordination_hotspots": [
                        {
                            "kind": "startup",
                            "project": "App/App.csproj",
                            "entry": "App/App.xaml",
                            "files": ["App/App.csproj", "App/App.xaml", "App/App.xaml.cs"],
                            "reason": "desktop startup surface",
                            "startup": True,
                        }
                    ],
                },
            },
            "plan_elements": task_manager._empty_plan_elements("Planning context lifecycle test"),
        }
        return task_manager._default_plan_fields(plan)

    def test_refresh_plan_elements_backfills_from_planning_context(self):
        plan = self._base_plan()

        task_manager._refresh_plan_elements(plan)

        conflicts = plan["plan_elements"]["conflict_zone_analysis"]
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["conflict_zone"], "App/App.xaml")
        self.assertIn("desktop startup surface", conflicts[0]["mitigation"])

        integration_points = plan["plan_elements"]["integration_points"]
        self.assertTrue(any("App/App.csproj" in item for item in integration_points))
        self.assertTrue(any("App/App.Package.wapproj" in item for item in integration_points))

    def test_plan_validation_warnings_surface_analysis_health(self):
        plan = self._base_plan()

        warnings = task_manager._plan_validation_warnings(plan)

        self.assertIn(
            "Analysis health: Optional analysis providers did not contribute; planning data is heuristic-only.",
            warnings,
        )
        self.assertIn(
            "Analysis shows 1 unassigned files; verify ownership before approval",
            warnings,
        )


if __name__ == "__main__":
    unittest.main()
