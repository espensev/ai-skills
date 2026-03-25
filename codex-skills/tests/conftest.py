"""Shared test fixtures for the codex-skills test suite."""

from __future__ import annotations

import os
import shutil
import tempfile
import textwrap
from contextlib import ExitStack
from pathlib import Path
from unittest import mock
from uuid import uuid4

import pytest
import task_manager

_TEST_TMP_ROOT = Path(__file__).resolve().parent.parent / ".tmp" / "pytest"
_TEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)
os.environ["TMPDIR"] = str(_TEST_TMP_ROOT)
os.environ["TEMP"] = str(_TEST_TMP_ROOT)
os.environ["TMP"] = str(_TEST_TMP_ROOT)
tempfile.tempdir = str(_TEST_TMP_ROOT)


def _workspace_temp_path(*, suffix: str = "", prefix: str = "tmp", dir: str | os.PathLike[str] | None = None) -> Path:
    base = Path(dir) if dir else _TEST_TMP_ROOT
    base.mkdir(parents=True, exist_ok=True)
    while True:
        candidate = base / f"{prefix}{uuid4().hex}{suffix}"
        if not candidate.exists():
            candidate.mkdir(parents=True, exist_ok=False)
            return candidate


class WorkspaceTemporaryDirectory:
    def __init__(
        self,
        suffix: str | None = None,
        prefix: str | None = None,
        dir: str | os.PathLike[str] | None = None,
        ignore_cleanup_errors: bool = False,
    ) -> None:
        self.name = str(
            _workspace_temp_path(
                suffix=suffix or "",
                prefix=prefix or "tmp",
                dir=dir,
            )
        )
        self._ignore_cleanup_errors = ignore_cleanup_errors
        self._closed = False

    def __enter__(self) -> str:
        return self.name

    def __exit__(self, exc_type, exc, tb) -> None:
        self.cleanup()

    def cleanup(self) -> None:
        if self._closed:
            return
        self._closed = True
        shutil.rmtree(self.name, ignore_errors=self._ignore_cleanup_errors)


def _workspace_mkdtemp(suffix: str | None = None, prefix: str | None = None, dir: str | os.PathLike[str] | None = None) -> str:
    return str(_workspace_temp_path(suffix=suffix or "", prefix=prefix or "tmp", dir=dir))


def _workspace_gettempdir() -> str:
    return str(_TEST_TMP_ROOT)


tempfile.TemporaryDirectory = WorkspaceTemporaryDirectory
tempfile.mkdtemp = _workspace_mkdtemp
tempfile.gettempdir = _workspace_gettempdir


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
        "project": {"name": project_name, "conventions": "AGENTS.md"},
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
    stack.enter_context(mock.patch.object(task_manager, "CONVENTIONS_FILE", "AGENTS.md"))
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

            1. `AGENTS.md`

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
