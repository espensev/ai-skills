# ruff: noqa: E402
"""Portability and contract tests for scripts/task_manager.py."""

import argparse
import io
import json
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from contextlib import ExitStack, redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
INSTALL_MANIFEST = json.loads((ROOT / "package" / "install-manifest.json").read_text(encoding="utf-8"))
sys.path.insert(0, str(ROOT / "scripts"))

import task_manager
from analysis.models import ANALYSIS_SCHEMA_VERSION


class TaskManagerPortabilityTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)
        self.agents_dir = self.root / "agents"
        self.agents_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir = self.root / "data"
        self.plans_dir = self.data_dir / "plans"
        self.plans_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.data_dir / "tasks.json"
        self.tracker_file = self.root / "custom-tracker.md"
        self.conventions_file = self.root / "AGENTS.md"
        self.conventions_file.write_text("Portable test conventions.\n", encoding="utf-8")

    def tearDown(self):
        self._tmpdir.cleanup()

    def _patch_env(self, *, tracker: bool = True, commands: dict | None = None):
        cfg = {
            "project": {"name": "Portable Test", "conventions": "AGENTS.md"},
            "commands": commands
            or {
                "compile": "python -m py_compile {files}",
                "test": "python -m pytest tests/ -q",
            },
        }
        tracker_value = "custom-tracker.md" if tracker else ""
        if tracker:
            self.tracker_file.write_text("", encoding="utf-8")

        stack = ExitStack()
        stack.enter_context(mock.patch.object(task_manager, "ROOT", self.root))
        stack.enter_context(mock.patch.object(task_manager, "AGENTS_DIR", self.agents_dir))
        stack.enter_context(mock.patch.object(task_manager, "STATE_FILE", self.state_file))
        stack.enter_context(mock.patch.object(task_manager, "PLANS_DIR", self.plans_dir))
        stack.enter_context(mock.patch.object(task_manager, "TRACKER_FILE", self.tracker_file if tracker else None))
        stack.enter_context(mock.patch.object(task_manager, "_tracker_str", tracker_value))
        stack.enter_context(mock.patch.object(task_manager, "CONVENTIONS_FILE", "AGENTS.md"))
        stack.enter_context(mock.patch.object(task_manager, "_CFG", cfg))
        return stack

    def _git_result(self, *, returncode: int = 0, stdout: str = "", stderr: str = ""):
        return subprocess.CompletedProcess(["git"], returncode, stdout=stdout, stderr=stderr)

    def _write_spec(
        self,
        letter: str,
        name: str,
        *,
        scope: str | None = None,
        deps: str = "(none)",
        files: str = "`example.py`",
        include_exit_criteria: bool = True,
    ) -> Path:
        path = self.agents_dir / f"agent-{letter}-{name}.md"
        exit_criteria = ""
        if include_exit_criteria:
            exit_criteria = textwrap.dedent(
                """\

                ## Exit Criteria

                - Scope is implemented.
                - Verification passes.
                """
            )
        path.write_text(
            textwrap.dedent(
                f"""\
                # Agent Task - {name.replace("-", " ").title()}

                **Scope:** {scope or f"Implement {name}."}

                **Depends on:** {deps}

                **Output files:** {files}
                {exit_criteria}
                """
            ),
            encoding="utf-8",
        )
        return path

    def _legacy_task(self, task_id: str, *, deps: list[str] | None = None, status: str = "done") -> dict:
        return {
            "id": task_id,
            "name": f"legacy-{task_id}",
            "spec_file": "",
            "scope": "",
            "status": status,
            "deps": list(deps or []),
            "files": [],
            "group": 0,
            "tracker_id": "",
            "started_at": "",
            "completed_at": "",
            "summary": "",
            "error": "",
        }

    def _analysis_payload(self) -> dict:
        return {
            "totals": {"files": 3, "lines": 120},
            "conflict_zones": [],
            "modules": {"core": {"total_lines": 120}},
            "detected_stacks": ["python"],
            "project_graph": {"nodes": [], "edges": []},
            "analysis_v2": {
                "schema_version": ANALYSIS_SCHEMA_VERSION,
                "providers": [{"name": "basic"}],
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
                    "detected_stacks": ["python"],
                    "project_graph": {"nodes": [], "edges": []},
                    "conflict_zones": [],
                    "ui_surfaces": [],
                    "ownership_summary": {
                        "project_count": 0,
                        "assigned_file_count": 0,
                        "assigned_line_count": 0,
                        "unassigned_file_count": 3,
                        "unassigned_paths": ["alpha.py"],
                        "projects": [],
                    },
                    "priority_projects": {"startup": [], "packaging": []},
                    "coordination_hotspots": [],
                },
            },
        }

    def _install_runtime(self, install_root: Path, *, extra_skills: tuple[str, ...] = ()) -> None:
        skills = []
        for skill_name in list(INSTALL_MANIFEST["default_skills"]) + list(extra_skills):
            if skill_name not in skills:
                skills.append(skill_name)

        for skill_name in skills:
            shutil.copytree(
                ROOT / "skills" / skill_name,
                install_root / ".codex" / "skills" / skill_name,
            )

        for rel_path in INSTALL_MANIFEST["contract_files"]:
            source = ROOT / rel_path
            shutil.copy2(source, install_root / ".codex" / "skills" / source.name)

        for rel_path in INSTALL_MANIFEST["runtime_files"]:
            source = ROOT / rel_path
            target = install_root / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

        for rel_path in INSTALL_MANIFEST["runtime_directories"]:
            source = ROOT / rel_path
            target = install_root / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source, target)

    def _register_plan(self, plan: dict) -> dict:
        persisted = task_manager._persist_plan_artifacts(plan)
        state = task_manager.load_state()
        task_manager._upsert_plan_summary(state, persisted)
        task_manager.save_state(state)
        return persisted

    def test_next_agent_letter_supports_multi_letter_ids(self):
        self.assertEqual(task_manager._next_agent_letter({"tasks": {}}), "a")
        self.assertEqual(task_manager._next_agent_letter({"tasks": {"z": {}}}), "aa")
        self.assertEqual(task_manager._next_agent_letter({"tasks": {"az": {}}}), "ba")

    def test_parse_spec_file_supports_singular_and_plural_agent_dependencies(self):
        singular = self.root / "agent-singular.md"
        singular.write_text(
            textwrap.dedent(
                """\
                # Agent Task - Singular

                **Scope:** singular
                **Depends on:** Agent D (baseprovider), Agent AD (session-event-storage)
                **Output files:** `collector.py`
                """
            ),
            encoding="utf-8",
        )
        plural = self.root / "agent-plural.md"
        plural.write_text(
            textwrap.dedent(
                """\
                # Agent Task - Plural

                **Scope:** plural
                **Depends on:** agents aa, ae and af
                **Output files:** `collector.py`
                """
            ),
            encoding="utf-8",
        )

        singular_info = task_manager.parse_spec_file(singular)
        plural_info = task_manager.parse_spec_file(plural)

        self.assertEqual(singular_info["deps"], ["d", "ad"])
        self.assertEqual(plural_info["deps"], ["aa", "ae", "af"])

    def test_sync_state_prunes_orphans_but_preserves_referenced_historical_chain(self):
        with self._patch_env(tracker=False):
            self._write_spec("d", "baseprovider")
            self._write_spec("h", "live-sessions")
            self._write_spec("i", "reprocess")
            self._write_spec(
                "aj",
                "collector-service-split",
                deps="Agent D (baseprovider), Agent H (live-sessions), Agent I (reprocess), Agent AD (legacy-ad)",
            )

            task_manager.save_state(
                {
                    "version": 2,
                    "tasks": {
                        "ad": self._legacy_task("ad", deps=["aa"]),
                        "aa": self._legacy_task("aa"),
                        "xx": self._legacy_task("xx"),
                    },
                    "groups": {},
                    "plans": [],
                    "updated_at": "",
                }
            )

            state = task_manager.sync_state()

        self.assertIn("ad", state["tasks"])
        self.assertIn("aa", state["tasks"])
        self.assertNotIn("xx", state["tasks"])
        self.assertEqual(state["tasks"]["aj"]["deps"], ["d", "h", "i", "ad"])
        self.assertEqual(state["tasks"]["aj"]["group"], 2)

    def test_sync_state_rejects_duplicate_spec_ids(self):
        with self._patch_env(tracker=False):
            self._write_spec("a", "one")
            self._write_spec("a", "two")

            with self.assertRaises(task_manager.TaskManagerError) as exc:
                task_manager.sync_state()

        self.assertIn("Duplicate agent IDs", str(exc.exception))

    def test_sync_state_clears_removed_deps_and_files(self):
        with self._patch_env(tracker=False):
            spec = self._write_spec("a", "alpha", deps="Agent B (beta)", files="`alpha.py`, `beta.py`")
            self._write_spec("b", "beta", deps="(none)", files="`beta.py`")

            initial = task_manager.sync_state()
            self.assertEqual(initial["tasks"]["a"]["deps"], ["b"])
            self.assertEqual(initial["tasks"]["a"]["files"], ["alpha.py", "beta.py"])

            spec.write_text(
                textwrap.dedent(
                    """\
                    # Agent Task - Alpha

                    **Scope:** Implement alpha.

                    **Depends on:** (none)
                    """
                ),
                encoding="utf-8",
            )

            updated = task_manager.sync_state()

        self.assertEqual(updated["tasks"]["a"]["deps"], [])
        self.assertEqual(updated["tasks"]["a"]["files"], [])

    def test_sync_state_preserves_failed_tracker_status(self):
        with self._patch_env(tracker=True):
            self._write_spec("a", "alpha", deps="(none)")
            self.tracker_file.write_text(
                textwrap.dedent(
                    """\
                    # Live Tracker

                    | ID | Status | Owner | Scope | Issue | Update |
                    |---|---|---|---|---|---|
                    | ALPHA-001 | Failed | agent-a | `alpha.py` | Verification broke | Needs retry |
                    """
                ),
                encoding="utf-8",
            )

            state = task_manager.sync_state()

        self.assertEqual(state["tasks"]["a"]["tracker_id"], "ALPHA-001")
        self.assertEqual(state["tasks"]["a"]["status"], "failed")
        self.assertEqual(state["tasks"]["a"]["error"], "Verification broke")

    def test_cmd_ready_json_is_pure_json(self):
        with self._patch_env(tracker=False):
            self._write_spec("a", "alpha", deps="(none)")
            self._write_spec("b", "beta", deps="Agent A (alpha)")

            buf = io.StringIO()
            with redirect_stdout(buf):
                task_manager.cmd_ready(argparse.Namespace(json=True))

        payload = json.loads(buf.getvalue())
        self.assertEqual([item["id"] for item in payload["ready"]], ["a"])
        self.assertEqual(payload["blocked"], [{"id": "b", "name": "beta", "pending_deps": ["a"]}])
        self.assertEqual(payload["summary"]["total"], 2)

    def test_cmd_run_json_is_pure_json(self):
        with self._patch_env(tracker=False):
            self._write_spec("a", "alpha", deps="(none)")
            self._write_spec("b", "beta", deps="Agent A (alpha)")

            buf = io.StringIO()
            with redirect_stdout(buf):
                task_manager.cmd_run(argparse.Namespace(agents="a,b,missing", json=True))

            state = task_manager.load_state()

        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["launched"], ["a"])
        skipped = {entry["id"]: entry for entry in payload["skipped"]}
        self.assertEqual(skipped["b"]["reason"], "blocked")
        self.assertEqual(skipped["b"]["pending_deps"], ["a"])
        self.assertEqual(skipped["missing"]["reason"], "not_found")
        self.assertEqual(state["tasks"]["a"]["status"], "running")
        self.assertEqual(payload["agents"][0]["id"], "a")
        self.assertIn("AGENT_RESULT_JSON", payload["agents"][0]["prompt"])

    def test_cmd_result_records_payload_and_unblocks_dependents(self):
        with self._patch_env(tracker=False):
            self._write_spec("a", "alpha", deps="(none)", files="`app.py`")
            self._write_spec("b", "beta", deps="Agent A (alpha)", files="`tests/test_app.py`")

            with redirect_stdout(io.StringIO()):
                task_manager.cmd_run(argparse.Namespace(agents="a", json=True))

            buf = io.StringIO()
            with redirect_stdout(buf):
                task_manager.cmd_result(
                    argparse.Namespace(
                        agent="a",
                        payload=json.dumps(
                            {
                                "id": "A",
                                "status": "done",
                                "files_modified": ["app.py"],
                                "tests_passed": 1,
                                "tests_failed": 0,
                                "issues": [],
                                "summary": "Updated app.py",
                                "worktree_path": ".worktrees/agent-a",
                                "branch": "agent/a",
                            }
                        ),
                        payload_file="",
                        json=True,
                    )
                )

            payload = json.loads(buf.getvalue())
            state = task_manager.load_state()

        self.assertEqual(state["tasks"]["a"]["status"], "done")
        self.assertEqual(state["tasks"]["b"]["status"], "ready")
        self.assertEqual(state["tasks"]["a"]["agent_result"]["files_modified"], ["app.py"])
        self.assertEqual(state["tasks"]["a"]["agent_result"]["branch"], "agent/a")
        self.assertEqual(payload["next_ready"], [{"id": "b", "name": "beta"}])

    def test_cmd_recover_resets_running_task_without_worktree_record(self):
        with self._patch_env(tracker=False):
            self._write_spec("a", "alpha", deps="(none)")
            state = task_manager.sync_state()
            state["tasks"]["a"]["status"] = "running"
            task_manager._ensure_task_runtime_fields(state["tasks"]["a"])
            task_manager.save_state(state)

            buf = io.StringIO()
            with redirect_stdout(buf):
                task_manager.cmd_recover(argparse.Namespace(prune_orphans=False, json=True))

            payload = json.loads(buf.getvalue())
            recovered_state = task_manager.load_state()

        self.assertEqual(payload["recovered"][0]["id"], "a")
        self.assertEqual(payload["recovered"][0]["reason"], "missing_worktree_record")
        self.assertEqual(recovered_state["tasks"]["a"]["status"], "ready")

    def test_cmd_recover_updates_running_task_from_git_worktree_inventory(self):
        with self._patch_env(tracker=False):
            self._write_spec("a", "alpha", deps="(none)")
            live_worktree = self.root / ".worktrees" / "live-a"
            live_worktree.mkdir(parents=True, exist_ok=True)

            state = task_manager.sync_state()
            state["tasks"]["a"]["status"] = "running"
            task_manager._ensure_task_runtime_fields(state["tasks"]["a"])
            state["tasks"]["a"]["launch"].update(
                {
                    "worktree_path": ".worktrees/stale-a",
                    "branch": "agent/a",
                    "recorded_at": "2026-03-12T10:00:00+00:00",
                }
            )
            task_manager.save_state(state)

            buf = io.StringIO()
            with (
                mock.patch.object(
                    task_manager,
                    "_git_worktree_inventory",
                    return_value={
                        "available": True,
                        "error": "",
                        "worktrees": [
                            {
                                "path": str(live_worktree.resolve()),
                                "branch": "agent/a",
                            }
                        ],
                    },
                ),
                redirect_stdout(buf),
            ):
                task_manager.cmd_recover(argparse.Namespace(prune_orphans=False, json=True))

            payload = json.loads(buf.getvalue())
            recovered_state = task_manager.load_state()

        self.assertEqual(payload["recovered"], [])
        self.assertEqual(payload["active"][0]["id"], "a")
        self.assertEqual(payload["active"][0]["source"], "git-worktree")
        self.assertEqual(recovered_state["tasks"]["a"]["status"], "running")
        self.assertEqual(recovered_state["tasks"]["a"]["launch"]["worktree_path"], ".worktrees/live-a")

    def test_cmd_recover_reconciles_execution_manifest_after_reset(self):
        with self._patch_env(tracker=False):
            self._write_spec("a", "alpha", deps="(none)")
            state = task_manager.sync_state()
            state["tasks"]["a"]["status"] = "running"
            task_manager._ensure_task_runtime_fields(state["tasks"]["a"])
            state["execution_manifest"] = task_manager._empty_execution_manifest()
            state["execution_manifest"]["plan_id"] = "plan-001"
            state["execution_manifest"]["status"] = "awaiting_results"
            state["execution_manifest"]["launch"].update(
                {
                    "status": "awaiting_results",
                    "launched": ["a"],
                    "running": ["a"],
                    "failed": [],
                }
            )
            task_manager.save_state(state)

            buf = io.StringIO()
            with redirect_stdout(buf):
                task_manager.cmd_recover(argparse.Namespace(prune_orphans=False, json=True))

            payload = json.loads(buf.getvalue())
            recovered_state = task_manager.load_state()

        self.assertEqual(payload["recovered"][0]["reason"], "missing_worktree_record")
        self.assertEqual(recovered_state["tasks"]["a"]["status"], "ready")
        self.assertEqual(recovered_state["execution_manifest"]["status"], "recovered")
        self.assertEqual(recovered_state["execution_manifest"]["launch"]["status"], "recovered")
        self.assertEqual(recovered_state["execution_manifest"]["launch"]["running"], [])

    def test_go_merges_done_agents_and_verifies(self):
        commands = {
            "compile": "python -m py_compile {files}",
            "build": "",
            "test": "python -c \"print('verified')\"",
        }
        with self._patch_env(tracker=False, commands=commands):
            self._write_spec("a", "alpha", deps="(none)", files="`app.py`")
            (self.root / "app.py").write_text("VALUE = 'old'\n", encoding="utf-8")
            worktree = self.root / ".worktrees" / "agent-a"
            worktree.mkdir(parents=True, exist_ok=True)
            (worktree / "app.py").write_text("VALUE = 'new'\n", encoding="utf-8")

            plan = {
                "id": "plan-001",
                "created_at": "2026-03-12T10:00:00+00:00",
                "status": "executed",
                "description": "Portable lifecycle smoke",
                "agents": [
                    {
                        "letter": "a",
                        "name": "alpha",
                        "scope": "Update app.py",
                        "deps": [],
                        "files": ["app.py"],
                        "group": 0,
                        "complexity": "low",
                    }
                ],
                "groups": {"0": ["a"]},
                "conflicts": [],
                "integration_steps": [],
                "analysis_summary": {"total_files": 1, "total_lines": 1, "conflict_zones": [], "modules": {}},
                "plan_elements": task_manager._empty_plan_elements("Portable lifecycle smoke"),
            }
            plan = task_manager._default_plan_fields(plan)
            plan["plan_elements"]["goal_statement"] = "Update app.py and verify the repo."
            plan["plan_elements"]["exit_criteria"] = ["Updated app.py is merged and verification passes."]
            plan["plan_elements"]["verification_strategy"] = ["python -c \"print('verified')\""]
            plan["plan_elements"]["documentation_updates"] = ["No documentation updates required."]
            task_manager._refresh_plan_elements(plan)
            self._register_plan(plan)

            state = task_manager.load_state()
            state["tasks"]["a"] = task_manager._new_task_record(
                "a",
                "alpha",
                spec_file="agents/agent-a-alpha.md",
                scope="Update app.py",
                status="done",
                deps=[],
                files=["app.py"],
                group=0,
            )
            state["tasks"]["a"]["agent_result"].update(
                {
                    "status": "done",
                    "files_modified": ["app.py"],
                    "tests_passed": 1,
                    "tests_failed": 0,
                    "issues": [],
                    "summary": "Updated app.py in worktree",
                    "worktree_path": ".worktrees/agent-a",
                    "branch": "agent/a",
                    "reported_at": "2026-03-12T10:01:00+00:00",
                }
            )
            state["tasks"]["a"]["launch"].update(
                {
                    "worktree_path": ".worktrees/agent-a",
                    "branch": "agent/a",
                    "recorded_at": "2026-03-12T10:00:30+00:00",
                }
            )
            task_manager.save_state(state)

            buf = io.StringIO()
            with redirect_stdout(buf):
                task_manager.cmd_go(
                    argparse.Namespace(
                        plan_id="plan-001",
                        goal="",
                        exit_criterion=[],
                        verification_step=[],
                        documentation_update=[],
                        json=True,
                    )
                )

            payload = json.loads(buf.getvalue())
            merged_state = task_manager.load_state()

        self.assertEqual(payload["status"], "verified")
        self.assertTrue(payload["verify"]["passed"])
        self.assertEqual(payload["merge"]["merged"][0]["id"], "a")
        self.assertEqual(merged_state["tasks"]["a"]["merge"]["status"], "merged")
        self.assertEqual((self.root / "app.py").read_text(encoding="utf-8"), "VALUE = 'new'\n")

    def test_go_persists_execution_manifest_and_resumes_verify_only(self):
        commands = {
            "compile": "",
            "build": "",
            "test": 'python -c "import sys; sys.exit(1)"',
        }
        with self._patch_env(tracker=False, commands=commands):
            self._write_spec("a", "alpha", deps="(none)", files="`app.py`")
            (self.root / "app.py").write_text("VALUE = 'old'\n", encoding="utf-8")
            worktree = self.root / ".worktrees" / "agent-a"
            worktree.mkdir(parents=True, exist_ok=True)
            (worktree / "app.py").write_text("VALUE = 'new'\n", encoding="utf-8")

            plan = {
                "id": "plan-002",
                "created_at": "2026-03-12T10:00:00+00:00",
                "status": "executed",
                "description": "Resume verify smoke",
                "agents": [
                    {
                        "letter": "a",
                        "name": "alpha",
                        "scope": "Update app.py",
                        "deps": [],
                        "files": ["app.py"],
                        "group": 0,
                        "complexity": "low",
                    }
                ],
                "groups": {"0": ["a"]},
                "conflicts": [],
                "integration_steps": [],
                "analysis_summary": {"total_files": 1, "total_lines": 1, "conflict_zones": [], "modules": {}},
                "plan_elements": task_manager._empty_plan_elements("Resume verify smoke"),
            }
            plan = task_manager._default_plan_fields(plan)
            plan["plan_elements"]["goal_statement"] = "Resume verify after a failed post-merge check."
            plan["plan_elements"]["exit_criteria"] = ["Merged work is verified without re-running merge."]
            plan["plan_elements"]["verification_strategy"] = ["python -c \"print('ok')\""]
            plan["plan_elements"]["documentation_updates"] = ["No documentation updates required."]
            task_manager._refresh_plan_elements(plan)
            self._register_plan(plan)

            state = task_manager.load_state()
            state["tasks"]["a"] = task_manager._new_task_record(
                "a",
                "alpha",
                spec_file="agents/agent-a-alpha.md",
                scope="Update app.py",
                status="done",
                deps=[],
                files=["app.py"],
                group=0,
            )
            state["tasks"]["a"]["agent_result"].update(
                {
                    "status": "done",
                    "files_modified": ["app.py"],
                    "tests_passed": 1,
                    "tests_failed": 0,
                    "issues": [],
                    "summary": "Updated app.py in worktree",
                    "worktree_path": ".worktrees/agent-a",
                    "branch": "agent/a",
                    "reported_at": "2026-03-12T10:01:00+00:00",
                }
            )
            state["tasks"]["a"]["launch"].update(
                {
                    "worktree_path": ".worktrees/agent-a",
                    "branch": "agent/a",
                    "recorded_at": "2026-03-12T10:00:30+00:00",
                }
            )
            task_manager.save_state(state)

            first_buf = io.StringIO()
            with redirect_stdout(first_buf):
                task_manager.cmd_go(
                    argparse.Namespace(
                        plan_id="plan-002",
                        goal="",
                        exit_criterion=[],
                        verification_step=[],
                        documentation_update=[],
                        json=True,
                    )
                )

            first_payload = json.loads(first_buf.getvalue())
            first_state = task_manager.load_state()

            task_manager._CFG["commands"]["test"] = "python -c \"print('verified')\""

            second_buf = io.StringIO()
            with redirect_stdout(second_buf):
                task_manager.cmd_go(
                    argparse.Namespace(
                        plan_id="plan-002",
                        goal="",
                        exit_criterion=[],
                        verification_step=[],
                        documentation_update=[],
                        json=True,
                    )
                )

            second_payload = json.loads(second_buf.getvalue())
            second_state = task_manager.load_state()

        self.assertEqual(first_payload["status"], "verification_failed")
        self.assertEqual(first_state["execution_manifest"]["status"], "verification_failed")
        self.assertEqual(first_state["execution_manifest"]["merge"]["status"], "merged")
        self.assertEqual(first_state["execution_manifest"]["verify"]["status"], "failed")
        self.assertEqual(second_payload["resume"]["mode"], "verify_only")
        self.assertEqual(second_payload["merge"]["status"], "reused_previous_merge")
        self.assertEqual(second_payload["status"], "verified")
        self.assertEqual(second_state["execution_manifest"]["status"], "verified")
        self.assertEqual(second_state["execution_manifest"]["verify"]["status"], "passed")

    def test_merge_runtime_cleans_up_finished_worktree_directory_and_branch(self):
        commands = {
            "compile": "",
            "build": "",
            "test": "python -c \"print('verified')\"",
        }
        with self._patch_env(tracker=False, commands=commands):
            subprocess.run(["git", "init"], cwd=self.root, capture_output=True, text=True, check=True)
            subprocess.run(["git", "config", "user.name", "Portable Test"], cwd=self.root, capture_output=True, text=True, check=True)
            subprocess.run(
                ["git", "config", "user.email", "portable@example.com"], cwd=self.root, capture_output=True, text=True, check=True
            )
            (self.root / "app.py").write_text("VALUE = 'old'\n", encoding="utf-8")
            subprocess.run(["git", "add", "app.py"], cwd=self.root, capture_output=True, text=True, check=True)
            subprocess.run(["git", "commit", "-m", "bootstrap"], cwd=self.root, capture_output=True, text=True, check=True)
            subprocess.run(["git", "branch", "agent/a"], cwd=self.root, capture_output=True, text=True, check=True)

            self._write_spec("a", "alpha", deps="(none)", files="`app.py`")
            worktree = self.root / ".worktrees" / "agent-a"
            worktree.mkdir(parents=True, exist_ok=True)
            (worktree / "app.py").write_text("VALUE = 'new'\n", encoding="utf-8")

            state = task_manager.sync_state()
            state["tasks"]["a"]["status"] = "done"
            task_manager._ensure_task_runtime_fields(state["tasks"]["a"])
            state["tasks"]["a"]["agent_result"].update(
                {
                    "status": "done",
                    "files_modified": ["app.py"],
                    "tests_passed": 1,
                    "tests_failed": 0,
                    "issues": [],
                    "summary": "Updated app.py",
                    "worktree_path": ".worktrees/agent-a",
                    "branch": "agent/a",
                    "reported_at": "2026-03-12T10:01:00+00:00",
                }
            )
            state["tasks"]["a"]["launch"].update(
                {
                    "worktree_path": ".worktrees/agent-a",
                    "branch": "agent/a",
                    "recorded_at": "2026-03-12T10:00:30+00:00",
                }
            )
            task_manager.save_state(state)

            buf = io.StringIO()
            with redirect_stdout(buf):
                task_manager.cmd_merge(argparse.Namespace(agents="all", json=True))

            payload = json.loads(buf.getvalue())
            branch_list = subprocess.run(
                ["git", "branch", "--list", "agent/a"],
                cwd=self.root,
                capture_output=True,
                text=True,
                check=True,
            )

        self.assertEqual(payload["merged"][0]["id"], "a")
        self.assertTrue(payload["cleanup"][0]["worktree_removed"])
        self.assertTrue(payload["cleanup"][0]["branch_removed"])
        self.assertFalse(worktree.exists())
        self.assertEqual(branch_list.stdout.strip(), "")

    def test_plan_preflight_requires_test_command_for_autonomous_verify(self):
        config_dir = self.root / ".codex" / "skills"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "project.toml").write_text('[project]\nname = "Portable Test"\n', encoding="utf-8")
        (config_dir / "planning-contract.md").write_text("contract\n", encoding="utf-8")

        git_side_effect = [
            self._git_result(stdout=str(self.root) + "\n"),
            self._git_result(stdout=str(self.root) + "\n"),
            self._git_result(stdout=""),
        ]

        with (
            self._patch_env(tracker=False, commands={"compile": "", "test": "", "build": ""}),
            mock.patch.object(
                task_manager.subprocess,
                "run",
                side_effect=git_side_effect,
            ),
        ):
            buf = io.StringIO()
            with redirect_stdout(buf):
                task_manager.cmd_plan_preflight(argparse.Namespace(json=True))

        payload = json.loads(buf.getvalue())
        self.assertFalse(payload["ready"])
        self.assertIn("Config is missing [commands].test; autonomous verify cannot run.", payload["errors"])
        self.assertTrue(payload["git"]["available"])

    def test_plan_preflight_rejects_placeholder_test_command(self):
        config_dir = self.root / ".codex" / "skills"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "project.toml").write_text('[project]\nname = "Portable Test"\n', encoding="utf-8")
        (config_dir / "planning-contract.md").write_text("contract\n", encoding="utf-8")

        git_side_effect = [
            self._git_result(stdout=str(self.root) + "\n"),
            self._git_result(stdout=str(self.root) + "\n"),
            self._git_result(stdout=""),
        ]

        with (
            self._patch_env(tracker=False, commands={"compile": "", "test": "TODO", "build": ""}),
            mock.patch.object(
                task_manager.subprocess,
                "run",
                side_effect=git_side_effect,
            ),
        ):
            buf = io.StringIO()
            with redirect_stdout(buf):
                task_manager.cmd_plan_preflight(argparse.Namespace(json=True))

        payload = json.loads(buf.getvalue())
        self.assertFalse(payload["ready"])
        self.assertIn("Configured [commands].test looks like a placeholder (contains TODO).", payload["errors"])

    def test_plan_preflight_reports_missing_git_repo(self):
        config_dir = self.root / ".codex" / "skills"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "project.toml").write_text('[project]\nname = "Portable Test"\n', encoding="utf-8")
        (config_dir / "planning-contract.md").write_text("contract\n", encoding="utf-8")

        with (
            self._patch_env(tracker=False),
            mock.patch.object(
                task_manager.subprocess,
                "run",
                return_value=self._git_result(returncode=1, stderr="fatal: not a git repository"),
            ),
        ):
            buf = io.StringIO()
            with redirect_stdout(buf):
                task_manager.cmd_plan_preflight(argparse.Namespace(json=True))

        payload = json.loads(buf.getvalue())
        self.assertFalse(payload["ready"])
        self.assertIn(
            "Git repository not available for autonomous worktree execution (fatal: not a git repository).",
            payload["errors"],
        )
        self.assertFalse(payload["git"]["available"])

    def test_plan_preflight_warns_on_dirty_worktree(self):
        config_dir = self.root / ".codex" / "skills"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "project.toml").write_text('[project]\nname = "Portable Test"\n', encoding="utf-8")
        (config_dir / "planning-contract.md").write_text("contract\n", encoding="utf-8")

        git_side_effect = [
            self._git_result(stdout=str(self.root) + "\n"),
            self._git_result(stdout=str(self.root) + "\n"),
            self._git_result(stdout=" M README.md\n"),
        ]

        with (
            self._patch_env(tracker=False),
            mock.patch.object(
                task_manager.subprocess,
                "run",
                side_effect=git_side_effect,
            ),
        ):
            buf = io.StringIO()
            with redirect_stdout(buf):
                task_manager.cmd_plan_preflight(argparse.Namespace(json=True))

        payload = json.loads(buf.getvalue())
        self.assertTrue(payload["ready"])
        self.assertIn("Git working tree is dirty; autonomous merge may need extra review.", payload["warnings"])
        self.assertTrue(payload["git"]["dirty"])

    def test_plan_preflight_requires_build_command_for_dotnet_projects(self):
        config_dir = self.root / ".codex" / "skills"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "project.toml").write_text('[project]\nname = "Portable Test"\n', encoding="utf-8")
        (config_dir / "planning-contract.md").write_text("contract\n", encoding="utf-8")

        git_side_effect = [
            self._git_result(stdout=str(self.root) + "\n"),
            self._git_result(stdout=str(self.root) + "\n"),
            self._git_result(stdout=""),
        ]

        with (
            self._patch_env(tracker=False, commands={"compile": "", "test": "dotnet test", "build": ""}),
            mock.patch.object(
                task_manager,
                "_detect_project_type",
                return_value={"name": "portable-test", "language": "dotnet", "build": "dotnet build", "has_tests_dir": True},
            ),
            mock.patch.object(
                task_manager.subprocess,
                "run",
                side_effect=git_side_effect,
            ),
        ):
            buf = io.StringIO()
            with redirect_stdout(buf):
                task_manager.cmd_plan_preflight(argparse.Namespace(json=True))

        payload = json.loads(buf.getvalue())
        self.assertFalse(payload["ready"])
        self.assertEqual(payload["detected_project"]["language"], "dotnet")
        self.assertIn(
            "Detected .NET project but [commands].build is missing; autonomous verification should include a build step.",
            payload["errors"],
        )

    def test_plan_preflight_python_missing_build_is_only_a_warning(self):
        config_dir = self.root / ".codex" / "skills"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "project.toml").write_text('[project]\nname = "Portable Test"\n', encoding="utf-8")
        (config_dir / "planning-contract.md").write_text("contract\n", encoding="utf-8")

        git_side_effect = [
            self._git_result(stdout=str(self.root) + "\n"),
            self._git_result(stdout=str(self.root) + "\n"),
            self._git_result(stdout=""),
        ]

        with (
            self._patch_env(
                tracker=False,
                commands={"compile": "", "test": "python -m pytest tests/ -q", "build": ""},
            ),
            mock.patch.object(
                task_manager,
                "_detect_project_type",
                return_value={
                    "name": "portable-test",
                    "language": "python",
                    "compile": "python -m py_compile {files}",
                    "has_tests_dir": True,
                },
            ),
            mock.patch.object(
                task_manager.subprocess,
                "run",
                side_effect=git_side_effect,
            ),
        ):
            buf = io.StringIO()
            with redirect_stdout(buf):
                task_manager.cmd_plan_preflight(argparse.Namespace(json=True))

        payload = json.loads(buf.getvalue())
        self.assertTrue(payload["ready"])
        self.assertEqual(payload["detected_project"]["language"], "python")
        self.assertIn("Detected Python project but [commands].compile is missing.", payload["warnings"])
        self.assertNotIn(
            "Detected Python project but [commands].build is missing; autonomous verification should include a build step.",
            payload["errors"],
        )

    def test_verify_fast_profile_uses_test_fast_and_expands_compile_files(self):
        commands = {
            "compile": "python -m py_compile {files}",
            "build": "python -c \"print('build')\"",
            "test": "python -c \"print('default')\"",
            "test_fast": "python -c \"print('fast')\"",
        }
        with self._patch_env(tracker=False, commands=commands):
            plan = {
                "id": "plan-fast",
                "created_at": "2026-03-12T10:00:00+00:00",
                "status": "executed",
                "description": "Verify profile smoke",
                "agents": [
                    {
                        "letter": "a",
                        "name": "alpha",
                        "scope": "Update app.py",
                        "deps": [],
                        "files": ["app.py", "tests/test_smoke.py"],
                        "group": 0,
                        "complexity": "low",
                    }
                ],
                "groups": {"0": ["a"]},
                "conflicts": [],
                "integration_steps": [],
                "analysis_summary": {"total_files": 2, "total_lines": 2, "conflict_zones": [], "modules": {}},
                "plan_elements": task_manager._empty_plan_elements("Verify profile smoke"),
            }
            plan = task_manager._default_plan_fields(plan)
            plan["plan_elements"]["goal_statement"] = "Verify the fast profile uses the fast test command."
            plan["plan_elements"]["exit_criteria"] = ["Fast verification passes."]
            plan["plan_elements"]["verification_strategy"] = ["python -m pytest tests/ -q -k fast"]
            plan["plan_elements"]["documentation_updates"] = ["No documentation updates required."]
            task_manager._refresh_plan_elements(plan)
            self._register_plan(plan)

            captured: list[tuple[str, str]] = []

            def _capture_command(label: str, command: str) -> dict:
                captured.append((label, command))
                return {
                    "label": label,
                    "command": command,
                    "returncode": 0,
                    "passed": True,
                    "stdout": "",
                    "stderr": "",
                }

            with (
                mock.patch.object(task_manager, "_recover_runtime", return_value={"recovered": [], "active": [], "orphans": []}),
                mock.patch.object(task_manager, "_run_runtime_command", side_effect=_capture_command),
            ):
                payload = task_manager._verify_runtime("plan-fast", profile="fast")

        self.assertEqual(payload["profile"], "fast")
        self.assertTrue(payload["passed"])
        self.assertEqual([label for label, _command in captured], ["compile", "build", "test_fast"])
        self.assertIn("app.py tests/test_smoke.py", captured[0][1])

    def test_verify_full_profile_falls_back_to_default_test_command(self):
        commands = {
            "compile": "",
            "build": "",
            "test": "python -c \"print('default')\"",
        }
        with self._patch_env(tracker=False, commands=commands):
            plan = {
                "id": "plan-full",
                "created_at": "2026-03-12T10:00:00+00:00",
                "status": "executed",
                "description": "Verify full profile fallback",
                "agents": [],
                "groups": {},
                "conflicts": [],
                "integration_steps": [],
                "analysis_summary": {"total_files": 0, "total_lines": 0, "conflict_zones": [], "modules": {}},
                "plan_elements": task_manager._empty_plan_elements("Verify full profile fallback"),
            }
            plan = task_manager._default_plan_fields(plan)
            plan["plan_elements"]["goal_statement"] = "Verify full profile falls back to the default test command."
            plan["plan_elements"]["exit_criteria"] = ["Full verification passes."]
            plan["plan_elements"]["verification_strategy"] = ["python -m pytest tests/ -q"]
            plan["plan_elements"]["documentation_updates"] = ["No documentation updates required."]
            task_manager._refresh_plan_elements(plan)
            self._register_plan(plan)

            captured: list[tuple[str, str]] = []

            def _capture_command(label: str, command: str) -> dict:
                captured.append((label, command))
                return {
                    "label": label,
                    "command": command,
                    "returncode": 0,
                    "passed": True,
                    "stdout": "",
                    "stderr": "",
                }

            with (
                mock.patch.object(task_manager, "_recover_runtime", return_value={"recovered": [], "active": [], "orphans": []}),
                mock.patch.object(task_manager, "_run_runtime_command", side_effect=_capture_command),
            ):
                payload = task_manager._verify_runtime("plan-full", profile="full")

        self.assertEqual(payload["profile"], "full")
        self.assertEqual(captured, [("test", 'python -c "print(\'default\')"')])
        self.assertIn("Verify profile 'full' requested", payload["warnings"][0])

    def test_init_creates_default_conventions_stub_for_installed_runtime(self):
        install_root = self.root / "consumer-init-conventions"
        (install_root / ".codex" / "skills").mkdir(parents=True, exist_ok=True)
        (install_root / "scripts").mkdir(parents=True, exist_ok=True)
        (install_root / "tests").mkdir(parents=True, exist_ok=True)
        (install_root / "README.md").write_text("consumer repo\n", encoding="utf-8")
        (install_root / "pyproject.toml").write_text(
            '[project]\nname = "consumer-init-conventions"\nversion = "0.1.0"\n',
            encoding="utf-8",
        )
        (install_root / "app.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        (install_root / "tests" / "test_smoke.py").write_text(
            "from app import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n",
            encoding="utf-8",
        )

        self._install_runtime(install_root)

        subprocess.run(["git", "init"], cwd=install_root, capture_output=True, text=True, check=True)
        subprocess.run(["git", "config", "user.name", "Portable Test"], cwd=install_root, capture_output=True, text=True, check=True)
        subprocess.run(
            ["git", "config", "user.email", "portable@example.com"], cwd=install_root, capture_output=True, text=True, check=True
        )
        subprocess.run(["git", "add", "."], cwd=install_root, capture_output=True, text=True, check=True)
        subprocess.run(["git", "commit", "-m", "bootstrap"], cwd=install_root, capture_output=True, text=True, check=True)

        subprocess.run(
            [sys.executable, "scripts/task_manager.py", "init", "--force"],
            cwd=install_root,
            capture_output=True,
            text=True,
            check=True,
        )

        self.assertTrue((install_root / "AGENTS.md").exists())
        self.assertIn("Project Conventions", (install_root / "AGENTS.md").read_text(encoding="utf-8"))

    def test_plan_finalize_populates_required_elements_and_allows_approval(self):
        analysis = self._analysis_payload()

        with self._patch_env(tracker=False), mock.patch.object(task_manager, "analyze_project", return_value=analysis):
            create_buf = io.StringIO()
            with redirect_stdout(create_buf):
                task_manager._plan_create(argparse.Namespace(description="Autonomous smoke", json=True))

            plan_id = json.loads(create_buf.getvalue())["plan"]["id"]
            task_manager.cmd_plan_add_agent(
                argparse.Namespace(
                    plan_id=plan_id,
                    letter="a",
                    name="alpha",
                    scope="Touch alpha",
                    deps="",
                    files="alpha.py",
                    group="",
                    complexity="low",
                )
            )

            with self.assertRaises(task_manager.TaskManagerError) as exc:
                task_manager._plan_approve(argparse.Namespace(plan_id=plan_id))
            self.assertIn("Missing required plan element: goal_statement", str(exc.exception))

            finalize_buf = io.StringIO()
            with redirect_stdout(finalize_buf):
                task_manager.cmd_plan_finalize(
                    argparse.Namespace(
                        plan_id=plan_id,
                        goal="Complete the autonomous smoke campaign.",
                        exit_criterion=["Agent scope is registered and executable."],
                        verification_step=["python -m pytest tests/ -q"],
                        documentation_update=["No documentation updates required."],
                        json=True,
                    )
                )

            payload = json.loads(finalize_buf.getvalue())
            self.assertTrue(payload["valid"])
            self.assertIn("goal_statement", payload["updated_fields"])
            self.assertIn("exit_criteria", payload["updated_fields"])

            task_manager._plan_approve(argparse.Namespace(plan_id=plan_id))
            approved_plan = task_manager._load_plan_from_summary(task_manager.load_state()["plans"][0])

        self.assertEqual(approved_plan["status"], "approved")
        self.assertEqual(
            approved_plan["plan_elements"]["goal_statement"],
            "Complete the autonomous smoke campaign.",
        )
        self.assertEqual(
            approved_plan["plan_elements"]["exit_criteria"],
            ["Agent scope is registered and executable."],
        )
        self.assertTrue(approved_plan["plan_elements"]["impact_assessment"])
        self.assertTrue(approved_plan["plan_elements"]["risk_assessment"])

    def test_plan_create_writes_machine_readable_plan_file_and_summary(self):
        analysis = {
            **self._analysis_payload(),
            "detected_stacks": ["dotnet", "wpf"],
            "project_graph": {
                "nodes": [{"id": "App/App.csproj", "kind": "project", "name": "App", "path": "App/App.csproj"}],
                "edges": [],
            },
        }
        analysis["analysis_v2"]["planning_context"]["detected_stacks"] = ["dotnet", "wpf"]
        analysis["analysis_v2"]["planning_context"]["project_graph"] = {
            "nodes": [{"id": "App/App.csproj", "kind": "project", "name": "App", "path": "App/App.csproj"}],
            "edges": [],
        }
        analysis["analysis_v2"]["planning_context"]["ownership_summary"] = {
            "project_count": 1,
            "assigned_file_count": 1,
            "assigned_line_count": 120,
            "unassigned_file_count": 0,
            "unassigned_paths": [],
            "projects": [],
        }
        analysis["analysis_v2"]["planning_context"]["priority_projects"] = {"startup": ["App/App.csproj"], "packaging": []}

        with self._patch_env(tracker=False), mock.patch.object(task_manager, "analyze_project", return_value=analysis):
            buf = io.StringIO()
            with redirect_stdout(buf):
                task_manager._plan_create(argparse.Namespace(description="Skill contract hardening", json=True))

            state = task_manager.load_state()

        payload = json.loads(buf.getvalue())
        plan = payload["plan"]
        plan_file = self.root / plan["plan_file"]
        stored = json.loads(plan_file.read_text(encoding="utf-8"))

        self.assertTrue(plan_file.exists())
        self.assertEqual(stored["description"], "Skill contract hardening")
        self.assertIn("plan_elements", stored)
        self.assertEqual(stored["analysis_summary"]["detected_stacks"], ["dotnet", "wpf"])
        self.assertEqual(stored["analysis_summary"]["project_graph"]["nodes"][0]["id"], "App/App.csproj")
        self.assertEqual(stored["analysis_summary"]["analysis_schema_version"], ANALYSIS_SCHEMA_VERSION)
        self.assertEqual(stored["analysis_summary"]["analysis_providers"], ["basic"])
        self.assertTrue(stored["analysis_summary"]["analysis_health"]["fallback_only"])
        self.assertEqual(
            stored["analysis_summary"]["planning_context"]["priority_projects"]["startup"],
            ["App/App.csproj"],
        )
        self.assertEqual(state["plans"][0]["id"], plan["id"])
        self.assertIn("plan_file", state["plans"][0])
        self.assertNotIn("agents", state["plans"][0])

    def test_render_spec_template_uses_configured_commands_and_tracker_path(self):
        commands = {
            "compile": "python -m py_compile {files}",
            "test": "python -m pytest tests/test_runtime.py -q",
            "build": "dotnet build launcher/App.csproj -c Release",
        }
        with self._patch_env(tracker=True, commands=commands):
            rendered = task_manager._render_spec_template(
                "aq",
                "contract-hardening",
                "Implement contract hardening.",
                deps=["a", "ad"],
                files=["scripts/task_manager.py", "docs/contract.md"],
            )

        self.assertIn("python -m py_compile scripts/task_manager.py docs/contract.md", rendered)
        self.assertIn("python -m pytest tests/test_runtime.py -q", rendered)
        self.assertIn("dotnet build launcher/App.csproj -c Release", rendered)
        self.assertIn("Update `custom-tracker.md`", rendered)

    def test_parse_tracker_is_optional(self):
        with self._patch_env(tracker=False):
            self.assertEqual(task_manager.parse_tracker(), {})

    def test_init_prefers_project_template_when_present(self):
        template_dir = self.root / ".codex" / "skills"
        template_dir.mkdir(parents=True, exist_ok=True)
        (template_dir / "project.toml.template").write_text(
            textwrap.dedent(
                """\
                [project]
                name = {{PROJECT_NAME}}
                conventions = {{CONVENTIONS_PATH}}

                [paths]
                state = "state/tasks.json"
                plans = "plans/store"
                specs = "work/agents"
                tracker = "portable-tracker.md"

                [commands]
                {{TEST_LINE}}
                {{COMPILE_LINE}}
                {{BUILD_LINE}}
                """
            ),
            encoding="utf-8",
        )

        detected = {
            "name": "Portable Init",
            "language": "python",
            "test": "python -m pytest tests/ -q",
            "compile": "python -m py_compile {files}",
            "build": "",
            "has_tests_dir": True,
        }

        with (
            mock.patch.object(task_manager, "ROOT", self.root),
            mock.patch.object(task_manager, "_detect_project_type", return_value=detected),
        ):
            buf = io.StringIO()
            with redirect_stdout(buf):
                task_manager.cmd_init(argparse.Namespace(force=True))

        rendered = (template_dir / "project.toml").read_text(encoding="utf-8")
        self.assertIn('name = "Portable Init"', rendered)
        self.assertIn('state = "state/tasks.json"', rendered)
        self.assertIn('plans = "plans/store"', rendered)
        self.assertIn('tracker = "portable-tracker.md"', rendered)
        self.assertIn('test = "python -m pytest tests/ -q"', rendered)
        self.assertIn('compile = "python -m py_compile {files}"', rendered)

    def test_init_creates_configured_runtime_paths_from_template(self):
        init_root = self.root / "init-root"
        template_dir = init_root / ".codex" / "skills"
        template_dir.mkdir(parents=True, exist_ok=True)
        (template_dir / "project.toml.template").write_text(
            textwrap.dedent(
                """\
                [project]
                name = {{PROJECT_NAME}}
                conventions = {{CONVENTIONS_PATH}}

                [paths]
                state = "state/tasks.json"
                plans = "plans/store"
                specs = "work/agents"
                tracker = "portable-tracker.md"

                [commands]
                {{TEST_LINE}}
                {{COMPILE_LINE}}
                {{BUILD_LINE}}
                """
            ),
            encoding="utf-8",
        )

        detected = {
            "name": "Portable Init",
            "language": "python",
            "test": "python -m pytest tests/ -q",
            "compile": "python -m py_compile {files}",
            "build": "",
            "has_tests_dir": True,
        }

        with (
            mock.patch.object(task_manager, "ROOT", init_root),
            mock.patch.object(task_manager, "_detect_project_type", return_value=detected),
        ):
            task_manager.cmd_init(argparse.Namespace(force=True))

        self.assertTrue((init_root / "state" / "tasks.json").exists())
        self.assertTrue((init_root / "plans" / "store").is_dir())
        self.assertTrue((init_root / "work" / "agents").is_dir())
        self.assertFalse((init_root / "data").exists())
        self.assertFalse((init_root / "agents").exists())

    def test_readme_install_flow_smoke_generates_project_config(self):
        install_root = self.root / "consumer"
        (install_root / ".codex" / "skills").mkdir(parents=True, exist_ok=True)
        (install_root / "scripts").mkdir(parents=True, exist_ok=True)
        (install_root / "README.md").write_text("consumer repo\n", encoding="utf-8")
        self._install_runtime(install_root)

        init_result = subprocess.run(
            [sys.executable, "scripts/task_manager.py", "init", "--force"],
            cwd=install_root,
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("Created:", init_result.stdout)

        rendered_config = (install_root / ".codex" / "skills" / "project.toml").read_text(encoding="utf-8")
        self.assertIn('name = "consumer"', rendered_config)
        self.assertNotIn("{{PROJECT_NAME}}", rendered_config)
        self.assertTrue((install_root / "data" / "tasks.json").exists())
        init_state = json.loads((install_root / "data" / "tasks.json").read_text(encoding="utf-8"))
        self.assertIn("execution_manifest", init_state)

        analyze_result = subprocess.run(
            [sys.executable, "scripts/task_manager.py", "analyze", "--json"],
            cwd=install_root,
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(analyze_result.stdout)
        self.assertEqual(payload["root"], str(install_root))
        self.assertGreaterEqual(payload["totals"]["files"], 4)
        self.assertEqual(payload["analysis_v2"]["schema_version"], ANALYSIS_SCHEMA_VERSION)
        self.assertEqual(payload["analysis_v2"]["providers"][0]["name"], "basic")
        self.assertIn("planning_context", payload["analysis_v2"])

    def test_installed_runtime_go_smoke_can_launch_record_merge_and_verify(self):
        install_root = self.root / "consumer-runtime-go"
        (install_root / ".codex" / "skills").mkdir(parents=True, exist_ok=True)
        (install_root / "scripts").mkdir(parents=True, exist_ok=True)
        (install_root / "tests").mkdir(parents=True, exist_ok=True)
        (install_root / "README.md").write_text("consumer repo\n", encoding="utf-8")
        (install_root / "AGENTS.md").write_text("consumer conventions\n", encoding="utf-8")
        (install_root / "pyproject.toml").write_text('[project]\nname = "consumer-runtime-go"\nversion = "0.1.0"\n', encoding="utf-8")
        (install_root / "app.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        (install_root / "tests" / "test_smoke.py").write_text(
            "from app import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n",
            encoding="utf-8",
        )

        self._install_runtime(install_root)

        subprocess.run(["git", "init"], cwd=install_root, capture_output=True, text=True, check=True)
        subprocess.run(["git", "config", "user.name", "Portable Test"], cwd=install_root, capture_output=True, text=True, check=True)
        subprocess.run(
            ["git", "config", "user.email", "portable@example.com"], cwd=install_root, capture_output=True, text=True, check=True
        )
        subprocess.run(["git", "add", "."], cwd=install_root, capture_output=True, text=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "bootstrap"],
            cwd=install_root,
            capture_output=True,
            text=True,
            check=True,
        )

        subprocess.run(
            [sys.executable, "scripts/task_manager.py", "init", "--force"],
            cwd=install_root,
            capture_output=True,
            text=True,
            check=True,
        )

        create_result = subprocess.run(
            [sys.executable, "scripts/task_manager.py", "plan", "create", "Runtime go smoke", "--json"],
            cwd=install_root,
            capture_output=True,
            text=True,
            check=True,
        )
        plan_id = json.loads(create_result.stdout)["plan"]["id"]

        subprocess.run(
            [
                sys.executable,
                "scripts/task_manager.py",
                "plan-add-agent",
                plan_id,
                "a",
                "smoke-agent",
                "--scope",
                "Update app.py to subtract instead of add.",
                "--deps",
                "",
                "--files",
                "app.py,tests/test_smoke.py",
                "--complexity",
                "low",
            ],
            cwd=install_root,
            capture_output=True,
            text=True,
            check=True,
        )

        subprocess.run(
            [
                sys.executable,
                "scripts/task_manager.py",
                "plan",
                "go",
                plan_id,
                "--goal",
                "Validate the installed runtime go lifecycle.",
                "--exit-criterion",
                "The smoke agent is merged and verification passes.",
                "--verification-step",
                "python -m pytest tests/ -q",
                "--documentation-update",
                "No documentation updates required.",
                "--json",
            ],
            cwd=install_root,
            capture_output=True,
            text=True,
            check=True,
        )

        launch_result = subprocess.run(
            [sys.executable, "scripts/task_manager.py", "go", plan_id, "--json"],
            cwd=install_root,
            capture_output=True,
            text=True,
            check=True,
        )
        launch_payload = json.loads(launch_result.stdout)
        self.assertEqual(launch_payload["status"], "awaiting_results")
        self.assertEqual(launch_payload["launch"]["launched"], ["a"])

        worktree = install_root / ".worktrees" / "agent-a"
        worktree.mkdir(parents=True, exist_ok=True)
        (worktree / "app.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
        (worktree / "tests").mkdir(parents=True, exist_ok=True)
        (worktree / "tests" / "test_smoke.py").write_text(
            "from app import add\n\n\ndef test_add():\n    assert add(3, 1) == 2\n",
            encoding="utf-8",
        )

        subprocess.run(
            [
                sys.executable,
                "scripts/task_manager.py",
                "attach",
                "a",
                "--worktree-path",
                ".worktrees/agent-a",
                "--branch",
                "agent/a",
            ],
            cwd=install_root,
            capture_output=True,
            text=True,
            check=True,
        )

        subprocess.run(
            [
                sys.executable,
                "scripts/task_manager.py",
                "result",
                "a",
                "--payload",
                json.dumps(
                    {
                        "id": "A",
                        "status": "done",
                        "files_modified": ["app.py", "tests/test_smoke.py"],
                        "tests_passed": 1,
                        "tests_failed": 0,
                        "issues": [],
                        "summary": "Updated add() semantics and adjusted tests.",
                        "worktree_path": ".worktrees/agent-a",
                        "branch": "agent/a",
                    }
                ),
                "--json",
            ],
            cwd=install_root,
            capture_output=True,
            text=True,
            check=True,
        )

        finish_result = subprocess.run(
            [sys.executable, "scripts/task_manager.py", "go", plan_id, "--json"],
            cwd=install_root,
            capture_output=True,
            text=True,
            check=True,
        )
        finish_payload = json.loads(finish_result.stdout)

        self.assertEqual(finish_payload["status"], "verified")
        self.assertTrue(finish_payload["verify"]["passed"])
        self.assertEqual((install_root / "app.py").read_text(encoding="utf-8"), "def add(a, b):\n    return a - b\n")
        self.assertEqual(
            (install_root / "tests" / "test_smoke.py").read_text(encoding="utf-8"),
            "from app import add\n\n\ndef test_add():\n    assert add(3, 1) == 2\n",
        )

    def test_installed_runtime_go_resume_smoke_reuses_merge_after_verify_failure(self):
        install_root = self.root / "consumer-runtime-go-resume"
        (install_root / ".codex" / "skills").mkdir(parents=True, exist_ok=True)
        (install_root / "scripts").mkdir(parents=True, exist_ok=True)
        (install_root / "tests").mkdir(parents=True, exist_ok=True)
        (install_root / "README.md").write_text("consumer repo\n", encoding="utf-8")
        (install_root / "AGENTS.md").write_text("consumer conventions\n", encoding="utf-8")
        (install_root / "pyproject.toml").write_text(
            '[project]\nname = "consumer-runtime-go-resume"\nversion = "0.1.0"\n', encoding="utf-8"
        )
        (install_root / "app.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        (install_root / "tests" / "test_smoke.py").write_text(
            "from app import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n",
            encoding="utf-8",
        )

        self._install_runtime(install_root)

        subprocess.run(["git", "init"], cwd=install_root, capture_output=True, text=True, check=True)
        subprocess.run(["git", "config", "user.name", "Portable Test"], cwd=install_root, capture_output=True, text=True, check=True)
        subprocess.run(
            ["git", "config", "user.email", "portable@example.com"], cwd=install_root, capture_output=True, text=True, check=True
        )
        subprocess.run(["git", "add", "."], cwd=install_root, capture_output=True, text=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "bootstrap"],
            cwd=install_root,
            capture_output=True,
            text=True,
            check=True,
        )

        subprocess.run(
            [sys.executable, "scripts/task_manager.py", "init", "--force"],
            cwd=install_root,
            capture_output=True,
            text=True,
            check=True,
        )

        project_config = install_root / ".codex" / "skills" / "project.toml"
        config_text = project_config.read_text(encoding="utf-8")
        project_config.write_text(
            config_text.replace(
                'test = "python -m pytest tests/ -q"',
                'test = "python -c \\"import sys; sys.exit(1)\\""',
            ),
            encoding="utf-8",
        )

        create_result = subprocess.run(
            [sys.executable, "scripts/task_manager.py", "plan", "create", "Runtime go resume smoke", "--json"],
            cwd=install_root,
            capture_output=True,
            text=True,
            check=True,
        )
        plan_id = json.loads(create_result.stdout)["plan"]["id"]

        subprocess.run(
            [
                sys.executable,
                "scripts/task_manager.py",
                "plan-add-agent",
                plan_id,
                "a",
                "smoke-agent",
                "--scope",
                "Update app.py to subtract instead of add.",
                "--deps",
                "",
                "--files",
                "app.py,tests/test_smoke.py",
                "--complexity",
                "low",
            ],
            cwd=install_root,
            capture_output=True,
            text=True,
            check=True,
        )

        subprocess.run(
            [
                sys.executable,
                "scripts/task_manager.py",
                "plan",
                "go",
                plan_id,
                "--goal",
                "Validate verify-only resume in the installed runtime lifecycle.",
                "--exit-criterion",
                "Merged work is verified without repeating merge.",
                "--verification-step",
                'python -c "import sys; sys.exit(1)"',
                "--documentation-update",
                "No documentation updates required.",
                "--json",
            ],
            cwd=install_root,
            capture_output=True,
            text=True,
            check=True,
        )

        launch_result = subprocess.run(
            [sys.executable, "scripts/task_manager.py", "go", plan_id, "--json"],
            cwd=install_root,
            capture_output=True,
            text=True,
            check=True,
        )
        launch_payload = json.loads(launch_result.stdout)
        self.assertEqual(launch_payload["status"], "awaiting_results")
        self.assertEqual(launch_payload["launch"]["launched"], ["a"])

        worktree = install_root / ".worktrees" / "agent-a"
        worktree.mkdir(parents=True, exist_ok=True)
        (worktree / "app.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
        (worktree / "tests").mkdir(parents=True, exist_ok=True)
        (worktree / "tests" / "test_smoke.py").write_text(
            "from app import add\n\n\ndef test_add():\n    assert add(3, 1) == 2\n",
            encoding="utf-8",
        )

        subprocess.run(
            [
                sys.executable,
                "scripts/task_manager.py",
                "attach",
                "a",
                "--worktree-path",
                ".worktrees/agent-a",
                "--branch",
                "agent/a",
            ],
            cwd=install_root,
            capture_output=True,
            text=True,
            check=True,
        )

        subprocess.run(
            [
                sys.executable,
                "scripts/task_manager.py",
                "result",
                "a",
                "--payload",
                json.dumps(
                    {
                        "id": "A",
                        "status": "done",
                        "files_modified": ["app.py", "tests/test_smoke.py"],
                        "tests_passed": 1,
                        "tests_failed": 0,
                        "issues": [],
                        "summary": "Updated add() semantics and adjusted tests.",
                        "worktree_path": ".worktrees/agent-a",
                        "branch": "agent/a",
                    }
                ),
                "--json",
            ],
            cwd=install_root,
            capture_output=True,
            text=True,
            check=True,
        )

        first_finish_result = subprocess.run(
            [sys.executable, "scripts/task_manager.py", "go", plan_id, "--json"],
            cwd=install_root,
            capture_output=True,
            text=True,
            check=True,
        )
        first_finish_payload = json.loads(first_finish_result.stdout)
        first_state = json.loads((install_root / "data" / "tasks.json").read_text(encoding="utf-8"))

        self.assertEqual(first_finish_payload["status"], "verification_failed")
        self.assertEqual(first_state["execution_manifest"]["status"], "verification_failed")
        self.assertEqual(first_state["execution_manifest"]["merge"]["status"], "merged")
        self.assertEqual(first_state["execution_manifest"]["verify"]["status"], "failed")

        project_config.write_text(
            project_config.read_text(encoding="utf-8").replace(
                'test = "python -c \\"import sys; sys.exit(1)\\""',
                'test = "python -m pytest tests/ -q"',
            ),
            encoding="utf-8",
        )

        second_finish_result = subprocess.run(
            [sys.executable, "scripts/task_manager.py", "go", plan_id, "--json"],
            cwd=install_root,
            capture_output=True,
            text=True,
            check=True,
        )
        second_finish_payload = json.loads(second_finish_result.stdout)
        second_state = json.loads((install_root / "data" / "tasks.json").read_text(encoding="utf-8"))

        self.assertEqual(second_finish_payload["resume"]["mode"], "verify_only")
        self.assertEqual(second_finish_payload["merge"]["status"], "reused_previous_merge")
        self.assertEqual(second_finish_payload["status"], "verified")
        self.assertTrue(second_finish_payload["verify"]["passed"])
        self.assertEqual(second_state["execution_manifest"]["status"], "verified")
        self.assertEqual(second_state["execution_manifest"]["verify"]["status"], "passed")

    def test_installed_runtime_recover_smoke_resets_stale_run_and_relaunches(self):
        install_root = self.root / "consumer-runtime-recover"
        (install_root / ".codex" / "skills").mkdir(parents=True, exist_ok=True)
        (install_root / "scripts").mkdir(parents=True, exist_ok=True)
        (install_root / "tests").mkdir(parents=True, exist_ok=True)
        (install_root / "README.md").write_text("consumer repo\n", encoding="utf-8")
        (install_root / "AGENTS.md").write_text("consumer conventions\n", encoding="utf-8")
        (install_root / "pyproject.toml").write_text('[project]\nname = "consumer-runtime-recover"\nversion = "0.1.0"\n', encoding="utf-8")
        (install_root / "app.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        (install_root / "tests" / "test_smoke.py").write_text(
            "from app import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n",
            encoding="utf-8",
        )

        self._install_runtime(install_root)

        subprocess.run(["git", "init"], cwd=install_root, capture_output=True, text=True, check=True)
        subprocess.run(["git", "config", "user.name", "Portable Test"], cwd=install_root, capture_output=True, text=True, check=True)
        subprocess.run(
            ["git", "config", "user.email", "portable@example.com"], cwd=install_root, capture_output=True, text=True, check=True
        )
        subprocess.run(["git", "add", "."], cwd=install_root, capture_output=True, text=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "bootstrap"],
            cwd=install_root,
            capture_output=True,
            text=True,
            check=True,
        )

        subprocess.run(
            [sys.executable, "scripts/task_manager.py", "init", "--force"],
            cwd=install_root,
            capture_output=True,
            text=True,
            check=True,
        )

        create_result = subprocess.run(
            [sys.executable, "scripts/task_manager.py", "plan", "create", "Runtime recover smoke", "--json"],
            cwd=install_root,
            capture_output=True,
            text=True,
            check=True,
        )
        plan_id = json.loads(create_result.stdout)["plan"]["id"]

        subprocess.run(
            [
                sys.executable,
                "scripts/task_manager.py",
                "plan-add-agent",
                plan_id,
                "a",
                "smoke-agent",
                "--scope",
                "Update app.py to subtract instead of add.",
                "--deps",
                "",
                "--files",
                "app.py",
                "--complexity",
                "low",
            ],
            cwd=install_root,
            capture_output=True,
            text=True,
            check=True,
        )

        subprocess.run(
            [
                sys.executable,
                "scripts/task_manager.py",
                "plan",
                "go",
                plan_id,
                "--goal",
                "Validate stale-run recovery in the installed runtime lifecycle.",
                "--exit-criterion",
                "A stale running task can be recovered and relaunched.",
                "--verification-step",
                "python -m pytest tests/ -q",
                "--documentation-update",
                "No documentation updates required.",
                "--json",
            ],
            cwd=install_root,
            capture_output=True,
            text=True,
            check=True,
        )

        first_go_result = subprocess.run(
            [sys.executable, "scripts/task_manager.py", "go", plan_id, "--json"],
            cwd=install_root,
            capture_output=True,
            text=True,
            check=True,
        )
        first_go_payload = json.loads(first_go_result.stdout)
        self.assertEqual(first_go_payload["status"], "awaiting_results")
        self.assertEqual(first_go_payload["launch"]["launched"], ["a"])

        recover_result = subprocess.run(
            [sys.executable, "scripts/task_manager.py", "recover", "--json"],
            cwd=install_root,
            capture_output=True,
            text=True,
            check=True,
        )
        recover_payload = json.loads(recover_result.stdout)
        recovered_state = json.loads((install_root / "data" / "tasks.json").read_text(encoding="utf-8"))

        self.assertEqual(recover_payload["recovered"][0]["id"], "a")
        self.assertEqual(recover_payload["recovered"][0]["reason"], "missing_worktree_record")
        self.assertEqual(recovered_state["tasks"]["a"]["status"], "ready")
        self.assertEqual(recovered_state["execution_manifest"]["status"], "recovered")
        self.assertEqual(recovered_state["execution_manifest"]["launch"]["status"], "recovered")
        self.assertEqual(recovered_state["execution_manifest"]["launch"]["running"], [])

        second_go_result = subprocess.run(
            [sys.executable, "scripts/task_manager.py", "go", plan_id, "--json"],
            cwd=install_root,
            capture_output=True,
            text=True,
            check=True,
        )
        second_go_payload = json.loads(second_go_result.stdout)

        self.assertEqual(second_go_payload["status"], "awaiting_results")
        self.assertEqual(second_go_payload["launch"]["launched"], ["a"])

    def test_installed_runtime_recover_smoke_reconciles_git_worktree_by_branch(self):
        install_root = self.root / "consumer-runtime-recover-branch"
        (install_root / ".codex" / "skills").mkdir(parents=True, exist_ok=True)
        (install_root / "scripts").mkdir(parents=True, exist_ok=True)
        (install_root / "tests").mkdir(parents=True, exist_ok=True)
        (install_root / "README.md").write_text("consumer repo\n", encoding="utf-8")
        (install_root / "AGENTS.md").write_text("consumer conventions\n", encoding="utf-8")
        (install_root / "pyproject.toml").write_text(
            '[project]\nname = "consumer-runtime-recover-branch"\nversion = "0.1.0"\n', encoding="utf-8"
        )
        (install_root / "app.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        (install_root / "tests" / "test_smoke.py").write_text(
            "from app import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n",
            encoding="utf-8",
        )

        self._install_runtime(install_root)

        subprocess.run(["git", "init"], cwd=install_root, capture_output=True, text=True, check=True)
        subprocess.run(["git", "config", "user.name", "Portable Test"], cwd=install_root, capture_output=True, text=True, check=True)
        subprocess.run(
            ["git", "config", "user.email", "portable@example.com"], cwd=install_root, capture_output=True, text=True, check=True
        )
        subprocess.run(["git", "add", "."], cwd=install_root, capture_output=True, text=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "bootstrap"],
            cwd=install_root,
            capture_output=True,
            text=True,
            check=True,
        )

        subprocess.run(
            [sys.executable, "scripts/task_manager.py", "init", "--force"],
            cwd=install_root,
            capture_output=True,
            text=True,
            check=True,
        )

        create_result = subprocess.run(
            [sys.executable, "scripts/task_manager.py", "plan", "create", "Runtime recover branch smoke", "--json"],
            cwd=install_root,
            capture_output=True,
            text=True,
            check=True,
        )
        plan_id = json.loads(create_result.stdout)["plan"]["id"]

        subprocess.run(
            [
                sys.executable,
                "scripts/task_manager.py",
                "plan-add-agent",
                plan_id,
                "a",
                "smoke-agent",
                "--scope",
                "Update app.py to subtract instead of add.",
                "--deps",
                "",
                "--files",
                "app.py",
                "--complexity",
                "low",
            ],
            cwd=install_root,
            capture_output=True,
            text=True,
            check=True,
        )

        subprocess.run(
            [
                sys.executable,
                "scripts/task_manager.py",
                "plan",
                "go",
                plan_id,
                "--goal",
                "Validate git-worktree branch reconciliation in the installed runtime lifecycle.",
                "--exit-criterion",
                "A stale recorded path is reconciled against a live worktree branch.",
                "--verification-step",
                "python -m pytest tests/ -q",
                "--documentation-update",
                "No documentation updates required.",
                "--json",
            ],
            cwd=install_root,
            capture_output=True,
            text=True,
            check=True,
        )

        first_go_result = subprocess.run(
            [sys.executable, "scripts/task_manager.py", "go", plan_id, "--json"],
            cwd=install_root,
            capture_output=True,
            text=True,
            check=True,
        )
        first_go_payload = json.loads(first_go_result.stdout)
        self.assertEqual(first_go_payload["status"], "awaiting_results")
        self.assertEqual(first_go_payload["launch"]["launched"], ["a"])

        live_worktree = install_root / ".worktrees" / "live-a"
        subprocess.run(
            ["git", "worktree", "add", str(live_worktree), "-b", "agent/a"],
            cwd=install_root,
            capture_output=True,
            text=True,
            check=True,
        )

        subprocess.run(
            [
                sys.executable,
                "scripts/task_manager.py",
                "attach",
                "a",
                "--worktree-path",
                ".worktrees/stale-a",
                "--branch",
                "agent/a",
                "--json",
            ],
            cwd=install_root,
            capture_output=True,
            text=True,
            check=True,
        )

        recover_result = subprocess.run(
            [sys.executable, "scripts/task_manager.py", "recover", "--json"],
            cwd=install_root,
            capture_output=True,
            text=True,
            check=True,
        )
        recover_payload = json.loads(recover_result.stdout)
        recovered_state = json.loads((install_root / "data" / "tasks.json").read_text(encoding="utf-8"))

        self.assertEqual(recover_payload["recovered"], [])
        self.assertEqual(recover_payload["active"][0]["id"], "a")
        self.assertEqual(recover_payload["active"][0]["source"], "git-worktree")
        self.assertEqual(recovered_state["tasks"]["a"]["status"], "running")
        self.assertEqual(recovered_state["tasks"]["a"]["launch"]["worktree_path"], ".worktrees/live-a")
        self.assertEqual(recovered_state["execution_manifest"]["status"], "awaiting_results")
        self.assertEqual(recovered_state["execution_manifest"]["launch"]["running"], ["a"])


if __name__ == "__main__":
    unittest.main()
