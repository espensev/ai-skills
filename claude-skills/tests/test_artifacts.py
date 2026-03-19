"""Tests for task_runtime.artifacts — markdown rendering and plan persistence."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from task_runtime.artifacts import (  # noqa: E402
    markdown_escape,
    markdown_table,
    persist_plan_artifacts,
    render_dependency_graph,
    render_markdown_list,
    render_plan_doc,
    write_plan_doc,
)

# ---------------------------------------------------------------------------
# markdown_escape
# ---------------------------------------------------------------------------


class TestMarkdownEscape(unittest.TestCase):
    def test_pipe_escaped(self):
        self.assertEqual(markdown_escape("a|b"), "a\\|b")

    def test_newline_replaced(self):
        self.assertEqual(markdown_escape("line1\nline2"), "line1<br>line2")

    def test_both(self):
        self.assertEqual(markdown_escape("a|b\nc"), "a\\|b<br>c")

    def test_non_string_coerced(self):
        self.assertEqual(markdown_escape(42), "42")

    def test_empty_string(self):
        self.assertEqual(markdown_escape(""), "")


# ---------------------------------------------------------------------------
# markdown_table
# ---------------------------------------------------------------------------


class TestMarkdownTable(unittest.TestCase):
    def test_basic_table(self):
        result = markdown_table(["A", "B"], [["1", "2"]])
        lines = result.split("\n")
        self.assertEqual(len(lines), 3)
        self.assertIn("A", lines[0])
        self.assertIn("---", lines[1])
        self.assertIn("1", lines[2])

    def test_empty_rows(self):
        result = markdown_table(["X"], [])
        lines = result.split("\n")
        self.assertEqual(len(lines), 2)  # header + separator only

    def test_row_padding(self):
        """Rows shorter than headers get padded with empty strings."""
        result = markdown_table(["A", "B", "C"], [["only-one"]])
        self.assertIn("only-one", result)
        # Should have 4 pipes per row (3 columns)
        data_line = result.split("\n")[2]
        self.assertEqual(data_line.count("|"), 4)

    def test_row_truncation(self):
        """Rows longer than headers get truncated."""
        result = markdown_table(["A"], [["keep", "discard"]])
        self.assertIn("keep", result)
        self.assertNotIn("discard", result)

    def test_pipe_in_cell_escaped(self):
        result = markdown_table(["Col"], [["a|b"]])
        self.assertIn("a\\|b", result)

    def test_multi_row(self):
        result = markdown_table(["H"], [["r1"], ["r2"], ["r3"]])
        lines = result.split("\n")
        self.assertEqual(len(lines), 5)  # header + sep + 3 rows


# ---------------------------------------------------------------------------
# render_markdown_list
# ---------------------------------------------------------------------------


def _identity_normalize(items):
    """Trivial normalizer for testing."""
    if isinstance(items, list):
        return items
    return [str(items)]


class TestRenderMarkdownList(unittest.TestCase):
    def test_empty_list_shows_empty_text(self):
        result = render_markdown_list([], empty_text="Nothing here.", normalize_string_list=_identity_normalize)
        self.assertEqual(result, "- Nothing here.")

    def test_string_items(self):
        result = render_markdown_list(
            ["alpha", "beta"],
            empty_text="N/A",
            normalize_string_list=_identity_normalize,
        )
        self.assertIn("- alpha", result)
        self.assertIn("- beta", result)

    def test_dict_items_use_file_key(self):
        items = [{"file": "foo.py", "change": "add"}]
        result = render_markdown_list(items, empty_text="N/A", normalize_string_list=_identity_normalize)
        self.assertIn("`foo.py`", result)
        self.assertIn(json.dumps(items[0], ensure_ascii=False), result)

    def test_dict_items_fallback_to_letter(self):
        items = [{"letter": "a", "name": "agent-a"}]
        result = render_markdown_list(items, empty_text="N/A", normalize_string_list=_identity_normalize)
        self.assertIn("`a`", result)

    def test_non_list_passed_to_normalizer(self):
        result = render_markdown_list(
            "raw-string",
            empty_text="N/A",
            normalize_string_list=_identity_normalize,
        )
        self.assertIn("- raw-string", result)


# ---------------------------------------------------------------------------
# render_dependency_graph
# ---------------------------------------------------------------------------


class TestRenderDependencyGraph(unittest.TestCase):
    def test_no_groups(self):
        self.assertEqual(render_dependency_graph({}), "Group 0: (none)")

    def test_single_group(self):
        plan = {"groups": {"0": ["a", "b"]}}
        result = render_dependency_graph(plan)
        self.assertEqual(result, "Group 0: a, b")

    def test_multi_group_sorted(self):
        plan = {"groups": {"1": ["c"], "0": ["a", "b"]}}
        lines = render_dependency_graph(plan).split("\n")
        self.assertTrue(lines[0].startswith("Group 0"))
        self.assertTrue(lines[1].startswith("Group 1"))

    def test_empty_group(self):
        plan = {"groups": {"0": []}}
        self.assertIn("(none)", render_dependency_graph(plan))


# ---------------------------------------------------------------------------
# render_plan_doc
# ---------------------------------------------------------------------------


def _noop_refresh(plan):
    pass


def _passthrough_defaults(plan):
    plan.setdefault(
        "plan_elements",
        {
            "campaign_title": plan.get("description", ""),
            "goal_statement": "Test goal",
            "exit_criteria": ["Tests pass"],
            "impact_assessment": [],
            "agent_roster": [],
            "dependency_graph": [],
            "file_ownership_map": [],
            "conflict_zone_analysis": [],
            "integration_points": [],
            "schema_changes": [],
            "risk_assessment": [],
            "verification_strategy": ["Run tests"],
            "documentation_updates": ["None needed"],
        },
    )
    return plan


class TestRenderPlanDoc(unittest.TestCase):
    def _render(self, plan):
        return render_plan_doc(
            plan,
            default_plan_fields=_passthrough_defaults,
            refresh_plan_elements=_noop_refresh,
            normalize_string_list=_identity_normalize,
        )

    def test_minimal_plan(self):
        plan = {"id": "plan-001", "description": "Test", "status": "draft", "created_at": "2026-01-01T00:00:00"}
        doc = self._render(plan)
        self.assertIn("# Campaign", doc)
        self.assertIn("plan-001", doc)
        self.assertIn("Test goal", doc)

    def test_contains_all_13_sections(self):
        plan = {"id": "plan-001", "description": "Test", "status": "draft", "created_at": "2026-01-01T00:00:00"}
        doc = self._render(plan)
        for section_num in range(1, 13):
            self.assertIn(f"## {section_num}.", doc)

    def test_optional_roadmap_section(self):
        plan = {
            "id": "plan-001",
            "description": "Test",
            "status": "draft",
            "created_at": "2026-01-01T00:00:00",
            "phase": "Phase 2",
            "source_roadmap": "docs/roadmap.md",
        }
        doc = self._render(plan)
        self.assertIn("## R1. Roadmap Phase", doc)
        self.assertIn("Phase 2", doc)

    def test_optional_behavioral_invariants(self):
        plan = {
            "id": "plan-001",
            "description": "Test",
            "status": "draft",
            "created_at": "2026-01-01T00:00:00",
            "behavioral_invariants": ["No breaking changes"],
        }
        doc = self._render(plan)
        self.assertIn("## R2. Behavioral Invariants", doc)
        self.assertIn("No breaking changes", doc)

    def test_agent_roster_rendered_as_table(self):
        plan = {"id": "plan-001", "description": "Test", "status": "draft", "created_at": "2026-01-01T00:00:00"}
        plan = _passthrough_defaults(plan)
        plan["plan_elements"]["agent_roster"] = [
            {"letter": "a", "name": "alpha", "scope": "Do stuff", "deps": [], "files": ["a.py"], "group": 0, "complexity": "low"},
        ]
        doc = render_plan_doc(
            plan,
            default_plan_fields=lambda p: p,
            refresh_plan_elements=_noop_refresh,
            normalize_string_list=_identity_normalize,
        )
        self.assertIn("alpha", doc)
        self.assertIn("a.py", doc)

    def test_discovery_docs_rendered(self):
        plan = {
            "id": "plan-001",
            "description": "Test",
            "status": "draft",
            "created_at": "2026-01-01T00:00:00",
            "source_discovery_docs": ["docs/discovery-auth.md"],
        }
        doc = self._render(plan)
        self.assertIn("discovery-auth.md", doc)


# ---------------------------------------------------------------------------
# write_plan_doc (DI-based, no real filesystem)
# ---------------------------------------------------------------------------


class TestWritePlanDoc(unittest.TestCase):
    def test_calls_render_and_writes(self):
        def fake_safe_resolve(path):
            return Path("/fake") / path

        def fake_plan_doc_path(plan):
            return f"docs/campaign-{plan['id']}.md"

        def fake_render(plan):
            return "# rendered doc"

        def fake_relative_path(path):
            return str(path)

        # Patch atomic_write at module level
        with mock.patch("task_runtime.artifacts.atomic_write") as mock_aw:
            write_plan_doc(
                {"id": "plan-001", "plan_doc": ""},
                safe_resolve=fake_safe_resolve,
                plan_doc_path=fake_plan_doc_path,
                render_plan_doc_fn=fake_render,
                relative_path=fake_relative_path,
            )

        mock_aw.assert_called_once()
        call_args = mock_aw.call_args
        self.assertEqual(call_args[0][1], "# rendered doc")


# ---------------------------------------------------------------------------
# persist_plan_artifacts (DI-based, no real filesystem)
# ---------------------------------------------------------------------------


class TestPersistPlanArtifacts(unittest.TestCase):
    def test_updates_timestamp_and_writes(self):
        calls = {"atomic_write": [], "write_doc": []}

        def fake_defaults(plan):
            return dict(plan)

        def fake_refresh(plan):
            pass

        def fake_now():
            return "2026-03-12T00:00:00+00:00"

        def fake_write_doc(plan):
            calls["write_doc"].append(plan["id"])
            return "docs/campaign-plan-001.md"

        def fake_plan_file_path(plan_id):
            return Path("/fake/plans") / f"{plan_id}.json"

        def fake_atomic_write(path, content):
            calls["atomic_write"].append((str(path), content))

        result = persist_plan_artifacts(
            {"id": "plan-001", "status": "draft"},
            default_plan_fields=fake_defaults,
            refresh_plan_elements=fake_refresh,
            now_iso=fake_now,
            write_plan_doc_fn=fake_write_doc,
            plan_file_path=fake_plan_file_path,
            atomic_write=fake_atomic_write,
        )

        self.assertEqual(result["updated_at"], "2026-03-12T00:00:00+00:00")
        self.assertEqual(result["plan_doc"], "docs/campaign-plan-001.md")
        self.assertEqual(len(calls["atomic_write"]), 1)
        # Written content should be valid JSON
        written_json = json.loads(calls["atomic_write"][0][1])
        self.assertEqual(written_json["id"], "plan-001")

    def test_preserves_existing_fields(self):
        result = persist_plan_artifacts(
            {"id": "plan-002", "status": "approved", "custom_field": "keep-me"},
            default_plan_fields=lambda p: dict(p),
            refresh_plan_elements=lambda p: None,
            now_iso=lambda: "2026-01-01T00:00:00+00:00",
            write_plan_doc_fn=lambda p: "doc.md",
            plan_file_path=lambda pid: Path(f"/fake/{pid}.json"),
            atomic_write=lambda path, content: None,
        )
        self.assertEqual(result["custom_field"], "keep-me")


if __name__ == "__main__":
    unittest.main()
