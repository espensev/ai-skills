"""Tests for scope_planning_context_for_agent in scripts/analysis/planning_context.py."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from analysis.planning_context import scope_planning_context_for_agent  # noqa: E402


def _make_planning_context(**overrides) -> dict:
    """Return a minimal valid planning context for testing."""
    base = {
        "analysis_health": {
            "mode": "auto",
            "requested_providers": ["basic"],
            "applied_providers": ["basic"],
            "skipped_providers": [],
            "partial_analysis": False,
            "fallback_only": False,
            "heuristic_only": True,
            "confidence": "medium",
            "warnings": [],
        },
        "detected_stacks": ["python"],
        "project_graph": {"nodes": [], "edges": []},
        "conflict_zones": [],
        "ui_surfaces": [],
        "ownership_summary": {"project_count": 0, "projects": []},
        "priority_projects": {"startup": [], "packaging": []},
        "coordination_hotspots": [],
    }
    base.update(overrides)
    return base


class TestScopePlanningContextForAgent(unittest.TestCase):
    # ------------------------------------------------------------------
    # test_zones_with_overlap_included
    # ------------------------------------------------------------------

    def test_zones_with_overlap_included(self):
        """A conflict_zone whose files overlap with agent_files is kept."""
        ctx = _make_planning_context(
            conflict_zones=[
                {"files": ["src/a.py", "src/b.py"], "reason": "shared state"},
                {"files": ["src/c.py", "src/d.py"], "reason": "other"},
            ]
        )
        result = scope_planning_context_for_agent(ctx, ["src/a.py"])
        self.assertEqual(len(result["conflict_zones"]), 1)
        self.assertEqual(result["conflict_zones"][0]["reason"], "shared state")

    # ------------------------------------------------------------------
    # test_zones_without_overlap_excluded
    # ------------------------------------------------------------------

    def test_zones_without_overlap_excluded(self):
        """A conflict_zone with no matching agent file is removed."""
        ctx = _make_planning_context(
            conflict_zones=[
                {"files": ["src/x.py", "src/y.py"], "reason": "unrelated"},
            ]
        )
        result = scope_planning_context_for_agent(ctx, ["src/a.py", "src/b.py"])
        self.assertEqual(result["conflict_zones"], [])

    # ------------------------------------------------------------------
    # test_empty_agent_files_returns_empty_lists
    # ------------------------------------------------------------------

    def test_empty_agent_files_returns_empty_lists(self):
        """If agent_files is empty, all list fields are emptied but metadata is preserved."""
        ctx = _make_planning_context(
            conflict_zones=[{"files": ["src/a.py", "src/b.py"], "reason": "r"}],
            ui_surfaces=[{"files": ["src/a.py", "src/b.py"], "kind": "startup"}],
            coordination_hotspots=[{"files": ["src/a.py", "src/b.py"], "kind": "startup"}],
            ownership_summary={
                "project_count": 1,
                "projects": [{"name": "App", "files": ["src/a.py"]}],
            },
            detected_stacks=["python"],
            priority_projects={"startup": ["App"], "packaging": []},
        )
        result = scope_planning_context_for_agent(ctx, [])

        self.assertEqual(result["conflict_zones"], [])
        self.assertEqual(result["ui_surfaces"], [])
        self.assertEqual(result["coordination_hotspots"], [])
        self.assertEqual(result["ownership_summary"]["projects"], [])

        # Metadata preserved as-is
        self.assertEqual(result["detected_stacks"], ["python"])
        self.assertEqual(result["priority_projects"], {"startup": ["App"], "packaging": []})
        self.assertIn("analysis_health", result)

    # ------------------------------------------------------------------
    # test_structure_keys_always_present
    # ------------------------------------------------------------------

    def test_structure_keys_always_present(self):
        """Output dict always contains all expected top-level keys."""
        ctx = _make_planning_context()
        expected_keys = {
            "analysis_health",
            "detected_stacks",
            "project_graph",
            "conflict_zones",
            "ui_surfaces",
            "ownership_summary",
            "priority_projects",
            "coordination_hotspots",
        }
        result_with_files = scope_planning_context_for_agent(ctx, ["src/a.py"])
        self.assertEqual(set(result_with_files.keys()), expected_keys)

        result_empty = scope_planning_context_for_agent(ctx, [])
        self.assertEqual(set(result_empty.keys()), expected_keys)

    # ------------------------------------------------------------------
    # test_path_normalization
    # ------------------------------------------------------------------

    def test_path_normalization(self):
        """Backslash paths in agent_files match forward-slash paths in zone files."""
        ctx = _make_planning_context(
            conflict_zones=[
                {"files": ["src/a.py", "src/b.py"], "reason": "shared state"},
            ]
        )
        # Provide agent_files with backslashes; should still match
        result = scope_planning_context_for_agent(ctx, ["src\\a.py"])
        self.assertEqual(len(result["conflict_zones"]), 1)

    def test_path_normalization_reverse(self):
        """Backslash paths in zone files match forward-slash agent_files."""
        ctx = _make_planning_context(
            conflict_zones=[
                {"files": ["src\\a.py", "src\\b.py"], "reason": "backslash zone"},
            ]
        )
        result = scope_planning_context_for_agent(ctx, ["src/a.py"])
        self.assertEqual(len(result["conflict_zones"]), 1)

    # ------------------------------------------------------------------
    # Additional coverage: ui_surfaces and coordination_hotspots
    # ------------------------------------------------------------------

    def test_ui_surfaces_filtered(self):
        """ui_surfaces with overlapping files are kept; others removed."""
        ctx = _make_planning_context(
            ui_surfaces=[
                {"files": ["app/main.py", "app/ui.py"], "kind": "startup"},
                {"files": ["unrelated/z.py"], "kind": "shell"},
            ]
        )
        result = scope_planning_context_for_agent(ctx, ["app/main.py"])
        self.assertEqual(len(result["ui_surfaces"]), 1)
        self.assertEqual(result["ui_surfaces"][0]["kind"], "startup")

    def test_coordination_hotspots_filtered(self):
        """coordination_hotspots with overlapping files are kept; others removed."""
        ctx = _make_planning_context(
            coordination_hotspots=[
                {"files": ["core/shared.py", "core/init.py"], "kind": "entry-point"},
                {"files": ["other/x.py", "other/y.py"], "kind": "conflict-zone"},
            ]
        )
        result = scope_planning_context_for_agent(ctx, ["core/shared.py"])
        self.assertEqual(len(result["coordination_hotspots"]), 1)
        self.assertEqual(result["coordination_hotspots"][0]["kind"], "entry-point")

    def test_ownership_projects_filtered(self):
        """ownership_summary.projects are filtered to those touching agent_files."""
        ctx = _make_planning_context(
            ownership_summary={
                "project_count": 2,
                "projects": [
                    {"name": "App", "files": ["app/main.py", "app/ui.py"]},
                    {"name": "Other", "files": ["other/z.py"]},
                ],
            }
        )
        result = scope_planning_context_for_agent(ctx, ["app/main.py"])
        self.assertEqual(len(result["ownership_summary"]["projects"]), 1)
        self.assertEqual(result["ownership_summary"]["projects"][0]["name"], "App")

    def test_preserved_fields_unchanged(self):
        """analysis_health, detected_stacks, priority_projects are preserved unchanged."""
        health = {
            "mode": "auto",
            "confidence": "high",
            "warnings": ["some warning"],
        }
        ctx = _make_planning_context(
            analysis_health=health,
            detected_stacks=["dotnet", "wpf"],
            priority_projects={"startup": ["App"], "packaging": ["Installer"]},
        )
        result = scope_planning_context_for_agent(ctx, ["src/a.py"])
        self.assertEqual(result["analysis_health"], health)
        self.assertEqual(result["detected_stacks"], ["dotnet", "wpf"])
        self.assertEqual(result["priority_projects"], {"startup": ["App"], "packaging": ["Installer"]})

    def test_does_not_mutate_input(self):
        """The function returns a new dict and does not modify the original."""
        ctx = _make_planning_context(
            conflict_zones=[{"files": ["a.py", "b.py"], "reason": "r"}],
        )
        original_zones = ctx["conflict_zones"]
        scope_planning_context_for_agent(ctx, [])
        self.assertIs(ctx["conflict_zones"], original_zones)


if __name__ == "__main__":
    unittest.main()
