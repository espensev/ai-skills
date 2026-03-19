"""Shared constants for the task manager system."""

from __future__ import annotations


class TaskStatus:
    """Task lifecycle states."""

    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    BLOCKED = "blocked"


class PlanStatus:
    """Plan lifecycle states."""

    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    PARTIAL = "partial"


class LaunchStatus:
    """Execution launch states."""

    AWAITING_RESULTS = "awaiting_results"
    BLOCKED = "blocked"


class MergeStatus:
    """Merge operation states."""

    NOOP = "noop"
    MERGED = "merged"
    CONFLICT = "conflict"


class VerifyStatus:
    """Verification states."""

    VERIFIED = "verified"
    VERIFICATION_FAILED = "verification_failed"
    MERGE_CONFLICTS = "merge_conflicts"
    PASSED = "passed"
    FAILED = "failed"
