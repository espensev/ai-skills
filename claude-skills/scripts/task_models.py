"""TypedDict definitions for task manager data structures."""

from __future__ import annotations

from typing import TypedDict


class AgentResult(TypedDict, total=False):
    """Result payload reported by an agent after execution."""

    status: str
    files_modified: list[str]
    tests_passed: int
    tests_failed: int
    issues: list[str]
    summary: str
    worktree_path: str
    branch: str
    reported_at: str


class LaunchRecord(TypedDict, total=False):
    """Worktree and branch info recorded when an agent is launched."""

    worktree_path: str
    branch: str
    pid: int
    launched_at: str
    recorded_at: str


class MergeRecord(TypedDict, total=False):
    """Result of merging an agent's work back into the main branch."""

    status: str
    applied_files: list[str]
    conflicts: list[str]
    merged_at: str
    detail: str


class _TaskRecordRequired(TypedDict):
    """Keys always present on a task record."""

    id: str
    name: str
    status: str
    deps: list[str]


class TaskRecord(_TaskRecordRequired, total=False):
    """A single agent task in the campaign state.

    Always has *id*, *name*, *status*, *deps*.  Other fields are
    populated during the task lifecycle.
    """

    spec_file: str
    scope: str
    files: list[str]
    group: int
    complexity: str
    tracker_id: str
    started_at: str
    completed_at: str
    summary: str
    error: str
    agent_result: AgentResult
    launch: LaunchRecord
    merge: MergeRecord


class PlanElements(TypedDict, total=False):
    """Structured plan elements for campaign planning docs."""

    campaign_title: str
    goal_statement: str
    exit_criteria: list[str]
    impact_assessment: list[dict[str, str]]
    agent_roster: list[dict[str, object]]
    dependency_graph: list[dict[str, object]]
    file_ownership_map: list[dict[str, str]]
    conflict_zone_analysis: list[dict[str, object]]
    integration_points: list[str]
    schema_changes: list[str]
    risk_assessment: list[dict[str, str]]
    verification_strategy: list[str]
    documentation_updates: list[str]


class _PlanRecordRequired(TypedDict):
    """Keys always present on a plan record."""

    id: str
    status: str


class PlanRecord(_PlanRecordRequired, total=False):
    """A campaign plan in the system."""

    schema_version: int
    artifact_version: int
    created_at: str
    updated_at: str
    description: str
    slug: str
    planner_kind: str
    source_discovery_docs: list[str]
    source_roadmap: str
    phase: str
    behavioral_invariants: list[str]
    legacy_status: str
    backfill_reasons: list[str]
    approved_at: str
    executed_at: str
    next_letter: str
    agents: list[dict[str, object]]
    groups: dict[str, list[str]]
    conflicts: list[str]
    integration_steps: list[str]
    plan_doc: str
    plan_file: str
    plan_elements: PlanElements
    analysis_summary: dict[str, object]


class PlanSummary(TypedDict, total=False):
    """Lightweight plan summary stored in state['plans']."""

    id: str
    status: str
    description: str
    created_at: str
    updated_at: str
    next_letter: str
    agent_count: int
    plan_file: str
    plan_doc: str
    legacy_status: str


class ExecutionManifest(TypedDict, total=False):
    """Top-level execution manifest in campaign state."""

    plan_id: str
    status: str
    updated_at: str
    launch: dict[str, object]
    merge: dict[str, object]
    verify: dict[str, object]


class CampaignState(TypedDict, total=False):
    """Top-level campaign state structure (data/tasks.json)."""

    version: int
    tasks: dict[str, TaskRecord]
    groups: dict[str, list[str]]
    plans: list[PlanSummary]
    updated_at: str
    execution_manifest: ExecutionManifest
    sync_audit: list[dict[str, str]]
