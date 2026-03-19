"""Tests verifying TypedDict structures, factory consistency, and type annotation coverage.

These tests ensure that:
- Each TypedDict has the expected keys and annotations.
- Factory functions return dicts matching their corresponding TypedDict shapes.
- All TypedDict classes are importable from task_models.
"""

from __future__ import annotations

from pathlib import Path

from task_models import (
    AgentResult,
    CampaignState,
    ExecutionManifest,
    LaunchRecord,
    MergeRecord,
    PlanElements,
    PlanRecord,
    PlanSummary,
    TaskRecord,
)
from task_runtime.config import RuntimePaths, derive_runtime_paths
from task_runtime.plans import empty_plan_elements, plan_summary
from task_runtime.state import default_state, empty_execution_manifest

# ---------------------------------------------------------------------------
# 1. TypedDict structure tests
# ---------------------------------------------------------------------------


class TestTaskRecordStructure:
    """Verify TaskRecord TypedDict required and optional keys."""

    def test_task_record_required_keys(self):
        """TaskRecord must have id, name, status, deps as required."""
        record: TaskRecord = {"id": "a", "name": "test", "status": "pending", "deps": []}
        assert record["id"] == "a"
        assert record["name"] == "test"
        assert record["status"] == "pending"
        assert record["deps"] == []

    def test_task_record_optional_keys(self):
        """TaskRecord accepts optional keys beyond the required four."""
        record: TaskRecord = {
            "id": "b",
            "name": "optional-check",
            "status": "ready",
            "deps": ["a"],
            "spec_file": "agents/agent-b-optional-check.md",
            "scope": "Test optional fields",
            "files": ["src/example.py"],
            "group": 1,
        }
        assert record["spec_file"] == "agents/agent-b-optional-check.md"
        assert record["group"] == 1

    def test_task_record_annotations_cover_expected_fields(self):
        """TaskRecord annotations include all expected field names."""
        annotations = TaskRecord.__annotations__
        expected_optional = {
            "spec_file",
            "scope",
            "files",
            "group",
            "tracker_id",
            "started_at",
            "completed_at",
            "summary",
            "error",
            "agent_result",
            "launch",
            "merge",
        }
        for key in expected_optional:
            assert key in annotations, f"Missing annotation for optional key: {key}"


class TestPlanElementsStructure:
    """Verify PlanElements TypedDict and its factory."""

    def test_plan_elements_keys_from_factory(self):
        """empty_plan_elements() returns all PlanElements keys."""
        elements = empty_plan_elements("test")
        expected_keys = {
            "campaign_title",
            "goal_statement",
            "exit_criteria",
            "impact_assessment",
            "agent_roster",
            "dependency_graph",
            "file_ownership_map",
            "conflict_zone_analysis",
            "integration_points",
            "schema_changes",
            "risk_assessment",
            "verification_strategy",
            "documentation_updates",
        }
        assert expected_keys.issubset(set(elements.keys()))

    def test_plan_elements_annotations(self):
        """PlanElements has annotations for all expected keys."""
        annotations = PlanElements.__annotations__
        expected_keys = {
            "campaign_title",
            "goal_statement",
            "exit_criteria",
            "impact_assessment",
            "agent_roster",
            "dependency_graph",
            "file_ownership_map",
            "conflict_zone_analysis",
            "integration_points",
            "schema_changes",
            "risk_assessment",
            "verification_strategy",
            "documentation_updates",
        }
        assert expected_keys == set(annotations.keys())

    def test_plan_elements_factory_default_values(self):
        """empty_plan_elements populates defaults correctly."""
        elements = empty_plan_elements("Campaign Title")
        assert elements["campaign_title"] == "Campaign Title"
        assert elements["goal_statement"] == ""
        assert elements["exit_criteria"] == []
        assert elements["documentation_updates"] == ["No documentation updates required."]


class TestPlanSummaryStructure:
    """Verify PlanSummary TypedDict shape and the plan_summary() factory."""

    def test_plan_summary_from_plan_summary_fn(self):
        """plan_summary() returns a dict matching PlanSummary shape."""
        plan = {
            "id": "plan-001",
            "status": "draft",
            "description": "test plan",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
            "next_letter": "a",
            "agents": [],
            "plan_file": "data/plans/plan-001.json",
            "plan_doc": "data/plans/plan-001.md",
        }
        result = plan_summary(
            plan,
            relative_path=lambda p: str(p),
            plan_file_path=lambda pid: f"plans/{pid}.json",
            plan_doc_path=lambda p: p.get("plan_doc", ""),
        )
        expected_keys = {
            "id",
            "status",
            "description",
            "created_at",
            "updated_at",
            "next_letter",
            "agent_count",
            "plan_file",
            "plan_doc",
            "legacy_status",
        }
        assert expected_keys.issubset(set(result.keys()))

    def test_plan_summary_annotations(self):
        """PlanSummary annotations match the expected set of keys."""
        annotations = PlanSummary.__annotations__
        expected_keys = {
            "id",
            "status",
            "description",
            "created_at",
            "updated_at",
            "next_letter",
            "agent_count",
            "plan_file",
            "plan_doc",
            "legacy_status",
        }
        assert expected_keys == set(annotations.keys())


class TestExecutionManifestStructure:
    """Verify ExecutionManifest TypedDict and factory."""

    def test_execution_manifest_structure(self):
        """ExecutionManifest matches empty_execution_manifest() shape."""
        manifest = empty_execution_manifest()
        assert "plan_id" in manifest
        assert "status" in manifest
        assert "launch" in manifest
        assert "merge" in manifest
        assert "verify" in manifest

    def test_execution_manifest_nested_launch(self):
        """Launch section of manifest has expected sub-keys."""
        manifest = empty_execution_manifest()
        launch = manifest["launch"]
        assert "status" in launch
        assert "launched" in launch
        assert "running" in launch
        assert "failed" in launch

    def test_execution_manifest_nested_merge(self):
        """Merge section of manifest has expected sub-keys."""
        manifest = empty_execution_manifest()
        merge = manifest["merge"]
        assert "status" in merge
        assert "merged_agents" in merge
        assert "conflict_agents" in merge

    def test_execution_manifest_nested_verify(self):
        """Verify section of manifest has expected sub-keys."""
        manifest = empty_execution_manifest()
        verify = manifest["verify"]
        assert "status" in verify
        assert "passed" in verify
        assert "failed_commands" in verify

    def test_execution_manifest_annotations(self):
        """ExecutionManifest annotations cover expected top-level keys."""
        annotations = ExecutionManifest.__annotations__
        expected_keys = {"plan_id", "status", "updated_at", "launch", "merge", "verify"}
        assert expected_keys == set(annotations.keys())


class TestCampaignStateStructure:
    """Verify CampaignState TypedDict and default_state() factory."""

    def test_campaign_state_structure(self):
        """CampaignState matches default_state() shape."""
        state = default_state()
        expected_keys = {"version", "tasks", "groups", "plans", "updated_at", "execution_manifest"}
        assert expected_keys.issubset(set(state.keys()))

    def test_campaign_state_default_values(self):
        """default_state() initializes with sensible defaults."""
        state = default_state()
        assert state["version"] == 2
        assert state["tasks"] == {}
        assert state["groups"] == {}
        assert state["plans"] == []
        assert state["updated_at"] == ""

    def test_campaign_state_annotations(self):
        """CampaignState annotations include all expected top-level keys."""
        annotations = CampaignState.__annotations__
        expected_keys = {"version", "tasks", "groups", "plans", "updated_at", "execution_manifest"}
        assert expected_keys.issubset(set(annotations.keys()))


class TestRuntimePathsStructure:
    """Verify RuntimePaths TypedDict from config module."""

    def test_runtime_paths_from_config(self):
        """derive_runtime_paths() returns expected keys."""
        paths = derive_runtime_paths(Path("/fake/root"), {})
        expected_keys = {"agents_dir", "state_file", "analysis_cache_file", "plans_dir", "tracker_path", "tracker_file"}
        assert expected_keys == set(paths.keys())

    def test_runtime_paths_defaults(self):
        """derive_runtime_paths() uses default subdirectory names."""
        paths = derive_runtime_paths(Path("/fake/root"), {})
        assert paths["agents_dir"] == Path("/fake/root/agents")
        assert paths["state_file"] == Path("/fake/root/data/tasks.json")
        assert paths["analysis_cache_file"] == Path("/fake/root/data/analysis-cache.json")
        assert paths["plans_dir"] == Path("/fake/root/data/plans")
        assert paths["tracker_path"] == "live-tracker.md"
        assert paths["tracker_file"] == Path("/fake/root/live-tracker.md")

    def test_runtime_paths_annotations(self):
        """RuntimePaths annotations cover all expected keys."""
        annotations = RuntimePaths.__annotations__
        expected_keys = {"agents_dir", "state_file", "analysis_cache_file", "plans_dir", "tracker_path", "tracker_file"}
        assert expected_keys == set(annotations.keys())


# ---------------------------------------------------------------------------
# 2. Factory consistency tests
# ---------------------------------------------------------------------------


class TestAgentResultContract:
    """Verify AgentResult TypedDict shape."""

    def test_agent_result_keys(self):
        """AgentResult can be constructed with expected keys."""
        result: AgentResult = {
            "status": "success",
            "files_modified": ["src/main.py"],
            "tests_passed": 5,
            "tests_failed": 0,
            "issues": [],
            "summary": "All checks passed",
            "worktree_path": "/tmp/wt",
            "branch": "agent-a",
            "reported_at": "2026-01-01T00:00:00+00:00",
        }
        assert result["status"] == "success"
        assert result["tests_passed"] == 5

    def test_agent_result_empty(self):
        """AgentResult allows empty/default values since total=False."""
        result: AgentResult = {}
        assert isinstance(result, dict)

    def test_agent_result_annotations(self):
        """AgentResult annotations cover all expected fields."""
        annotations = AgentResult.__annotations__
        expected = {
            "status",
            "files_modified",
            "tests_passed",
            "tests_failed",
            "issues",
            "summary",
            "worktree_path",
            "branch",
            "reported_at",
        }
        assert expected == set(annotations.keys())


class TestLaunchRecordContract:
    """Verify LaunchRecord TypedDict shape."""

    def test_launch_record_keys(self):
        """LaunchRecord accepts all expected keys."""
        record: LaunchRecord = {
            "worktree_path": "/tmp/wt",
            "branch": "agent-a",
            "pid": 12345,
            "launched_at": "2026-01-01T00:00:00+00:00",
            "recorded_at": "2026-01-01T00:00:00+00:00",
        }
        assert record["pid"] == 12345

    def test_launch_record_annotations(self):
        """LaunchRecord annotations cover all expected fields."""
        annotations = LaunchRecord.__annotations__
        expected = {"worktree_path", "branch", "pid", "launched_at", "recorded_at"}
        assert expected == set(annotations.keys())


class TestMergeRecordContract:
    """Verify MergeRecord TypedDict shape."""

    def test_merge_record_keys(self):
        """MergeRecord can be constructed with expected keys."""
        record: MergeRecord = {
            "status": "clean",
            "applied_files": ["src/main.py"],
            "conflicts": [],
            "merged_at": "2026-01-01T00:00:00+00:00",
            "detail": "No conflicts",
        }
        assert isinstance(record["applied_files"], list)
        assert record["conflicts"] == []

    def test_merge_record_annotations(self):
        """MergeRecord annotations cover all expected fields."""
        annotations = MergeRecord.__annotations__
        expected = {"status", "applied_files", "conflicts", "merged_at", "detail"}
        assert expected == set(annotations.keys())


class TestPlanRecordContract:
    """Verify PlanRecord TypedDict shape."""

    def test_plan_record_required_keys(self):
        """PlanRecord requires id and status."""
        record: PlanRecord = {"id": "plan-001", "status": "draft"}
        assert record["id"] == "plan-001"
        assert record["status"] == "draft"

    def test_plan_record_optional_keys(self):
        """PlanRecord accepts many optional fields beyond id and status."""
        record: PlanRecord = {
            "id": "plan-002",
            "status": "approved",
            "schema_version": 1,
            "description": "test plan",
            "agents": [],
            "plan_elements": {},
        }
        assert record["schema_version"] == 1

    def test_plan_record_annotations(self):
        """PlanRecord annotations include both required and optional keys."""
        annotations = PlanRecord.__annotations__
        expected_subset = {
            "schema_version",
            "artifact_version",
            "created_at",
            "updated_at",
            "description",
            "slug",
            "planner_kind",
            "agents",
            "plan_doc",
            "plan_file",
            "plan_elements",
        }
        assert expected_subset.issubset(set(annotations.keys()))


# ---------------------------------------------------------------------------
# 3. Import verification tests
# ---------------------------------------------------------------------------


class TestTypeImports:
    """Verify all TypedDict classes are importable and well-formed."""

    def test_all_typeddict_imports(self):
        """All TypedDict classes are importable from task_models."""
        from task_models import (
            AgentResult,
            CampaignState,
            ExecutionManifest,
            LaunchRecord,
            MergeRecord,
            PlanElements,
            PlanRecord,
            PlanSummary,
            TaskRecord,
        )

        for cls in (
            AgentResult,
            LaunchRecord,
            MergeRecord,
            TaskRecord,
            PlanElements,
            PlanRecord,
            PlanSummary,
            ExecutionManifest,
            CampaignState,
        ):
            assert hasattr(cls, "__annotations__") or hasattr(cls, "__required_keys__"), f"{cls.__name__} is not a proper TypedDict"

    def test_runtime_paths_import(self):
        """RuntimePaths TypedDict is importable from task_runtime.config."""
        from task_runtime.config import RuntimePaths

        assert hasattr(RuntimePaths, "__annotations__")

    def test_typeddict_classes_have_docstrings(self):
        """All TypedDict classes should have a docstring."""
        classes = (
            AgentResult,
            LaunchRecord,
            MergeRecord,
            TaskRecord,
            PlanElements,
            PlanRecord,
            PlanSummary,
            ExecutionManifest,
            CampaignState,
        )
        for cls in classes:
            assert cls.__doc__ is not None and cls.__doc__.strip(), f"{cls.__name__} is missing a docstring"

    def test_typeddict_classes_are_dict_subclasses(self):
        """TypedDict instances should be regular dicts at runtime."""
        # TypedDict instances are just dicts; verify with a quick instantiation
        result: AgentResult = {"status": "ok"}
        assert isinstance(result, dict)

        record: TaskRecord = {"id": "x", "name": "n", "status": "s", "deps": []}
        assert isinstance(record, dict)


# ---------------------------------------------------------------------------
# 4. Cross-validation: factory output vs TypedDict annotations
# ---------------------------------------------------------------------------


class TestFactoryAnnotationAlignment:
    """Verify factory function outputs align with TypedDict annotations."""

    def test_empty_plan_elements_covers_all_annotations(self):
        """empty_plan_elements() output keys match PlanElements annotations."""
        elements = empty_plan_elements("test")
        annotation_keys = set(PlanElements.__annotations__.keys())
        factory_keys = set(elements.keys())
        assert annotation_keys == factory_keys, (
            f"Mismatch: annotations={annotation_keys - factory_keys}, factory={factory_keys - annotation_keys}"
        )

    def test_empty_execution_manifest_covers_annotations(self):
        """empty_execution_manifest() output keys match ExecutionManifest annotations."""
        manifest = empty_execution_manifest()
        annotation_keys = set(ExecutionManifest.__annotations__.keys())
        factory_keys = set(manifest.keys())
        assert annotation_keys == factory_keys, (
            f"Mismatch: annotations={annotation_keys - factory_keys}, factory={factory_keys - annotation_keys}"
        )

    def test_default_state_covers_campaign_state_annotations(self):
        """default_state() output keys match CampaignState annotations."""
        state = default_state()
        annotation_keys = set(CampaignState.__annotations__.keys())
        factory_keys = set(state.keys())
        # default_state should at least cover the core keys
        core_keys = {"version", "tasks", "groups", "plans", "updated_at", "execution_manifest"}
        assert core_keys.issubset(factory_keys), f"default_state() missing core keys: {core_keys - factory_keys}"
        # Any extra annotations (like sync_audit) are acceptable optional fields
        # that aren't populated by default
        assert factory_keys.issubset(annotation_keys | core_keys)

    def test_plan_summary_fn_covers_annotations(self):
        """plan_summary() output keys match PlanSummary annotations."""
        plan = {
            "id": "plan-001",
            "status": "draft",
            "description": "test",
            "created_at": "",
            "updated_at": "",
            "next_letter": "a",
            "agents": [],
            "plan_file": "f",
            "plan_doc": "d",
        }
        result = plan_summary(
            plan,
            relative_path=lambda p: str(p),
            plan_file_path=lambda pid: f"plans/{pid}.json",
            plan_doc_path=lambda p: p.get("plan_doc", ""),
        )
        annotation_keys = set(PlanSummary.__annotations__.keys())
        factory_keys = set(result.keys())
        assert annotation_keys == factory_keys, (
            f"Mismatch: annotations={annotation_keys - factory_keys}, factory={factory_keys - annotation_keys}"
        )

    def test_derive_runtime_paths_covers_annotations(self):
        """derive_runtime_paths() output keys match RuntimePaths annotations."""
        paths = derive_runtime_paths(Path("/fake/root"), {})
        annotation_keys = set(RuntimePaths.__annotations__.keys())
        factory_keys = set(paths.keys())
        assert annotation_keys == factory_keys, (
            f"Mismatch: annotations={annotation_keys - factory_keys}, factory={factory_keys - annotation_keys}"
        )
