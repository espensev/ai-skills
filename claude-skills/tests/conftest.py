"""Shared test fixtures for the claude-skills test suite."""

from __future__ import annotations

import textwrap
from contextlib import ExitStack
from pathlib import Path
from unittest import mock

import pytest
import task_manager


@pytest.fixture(autouse=True)
def _reset_analysis_cache():
    """Clear the in-memory analysis cache before every test."""
    task_manager._analysis_cache = None
    task_manager._analysis_cache_key_value = None
    yield
    task_manager._analysis_cache = None
    task_manager._analysis_cache_key_value = None


# ---------------------------------------------------------------------------
# Environment patching
# ---------------------------------------------------------------------------


def patch_env(
    proj,
    *,
    project_name: str = "Test",
    tracker: bool = False,
    commands: dict | None = None,
) -> ExitStack:
    """Patch task_manager globals to use *proj* paths.

    Returns an ExitStack that the caller must use as a context manager.
    """
    cfg = {
        "project": {"name": project_name, "conventions": "CLAUDE.md"},
        "commands": commands
        or {
            "compile": "python -m py_compile {files}",
            "test": "python -m pytest tests/ -q",
            "build": "dotnet build launcher/App.csproj -c Release",
        },
    }
    tracker_value = "custom-tracker.md" if tracker else ""
    if tracker:
        proj.tracker_file.write_text("", encoding="utf-8")

    stack = ExitStack()
    stack.enter_context(mock.patch.object(task_manager, "ROOT", proj.root))
    stack.enter_context(mock.patch.object(task_manager, "AGENTS_DIR", proj.agents_dir))
    stack.enter_context(mock.patch.object(task_manager, "STATE_FILE", proj.state_file))
    stack.enter_context(mock.patch.object(task_manager, "PLANS_DIR", proj.plans_dir))
    stack.enter_context(mock.patch.object(task_manager, "TRACKER_FILE", proj.tracker_file if tracker else None))
    stack.enter_context(mock.patch.object(task_manager, "_tracker_str", tracker_value))
    stack.enter_context(mock.patch.object(task_manager, "CONVENTIONS_FILE", "CLAUDE.md"))
    stack.enter_context(mock.patch.object(task_manager, "_CFG", cfg))
    return stack


# ---------------------------------------------------------------------------
# Spec-file helpers
# ---------------------------------------------------------------------------


def write_spec(
    agents_dir: Path,
    letter: str,
    name: str,
    *,
    scope: str | None = None,
    deps: str = "(none)",
    files: str = "`example.py`",
    include_exit_criteria: bool = True,
    placeholder: bool = False,
) -> Path:
    """Write an agent spec file and return its path.

    Supports all variants used across the test suite.
    """
    exit_block = ""
    if include_exit_criteria:
        exit_block = textwrap.dedent(
            """\

            ## Exit Criteria

            - Scope is implemented.
            - Verification passes.

            ---
            """
        )
    task_text = "TODO: finish this task." if placeholder else "Implement the scoped change."
    path = agents_dir / f"agent-{letter}-{name}.md"
    path.write_text(
        textwrap.dedent(
            f"""\
            # Agent Task - {name.replace("-", " ").title()}

            **Scope:** {scope or f"Implement {name}."}

            **Depends on:** {deps}

            **Output files:** {files}

            ---

            ## Context -- read before doing anything

            1. `CLAUDE.md`

            ---

            ## Task

            {task_text}

            ---

            {exit_block}

            ## Verification

            ```powershell
            python -m pytest tests/ -q
            ```
            """
        ),
        encoding="utf-8",
    )
    return path
