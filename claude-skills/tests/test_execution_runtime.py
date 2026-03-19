"""Direct tests for task_runtime.execution helper and command branches."""

from __future__ import annotations

import argparse
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from task_runtime.execution import (  # noqa: E402
    _AGENT_RESULT_SCHEMA,
    _SYSTEM_RULES_TEMPLATE,
    assign_groups,
    build_agent_prompt,
    cmd_add,
    cmd_complete,
    cmd_fail,
    cmd_new,
    cmd_next,
    cmd_ready,
    cmd_reset,
    cmd_run,
    cmd_status,
    cmd_template,
    compute_dependency_depths,
    recompute_ready,
    sync_state,
)


def _task(
    task_id: str,
    name: str,
    *,
    status: str = "pending",
    deps: list[str] | None = None,
    files: list[str] | None = None,
    spec_file: str | None = None,
    group: int = 0,
    started_at: str = "",
    scope: str = "",
) -> dict:
    return {
        "id": task_id,
        "name": name,
        "spec_file": spec_file or f"agents/agent-{task_id}-{name}.md",
        "scope": scope,
        "status": status,
        "deps": list(deps or []),
        "files": list(files or []),
        "group": group,
        "complexity": "low",
        "tracker_id": "",
        "started_at": started_at,
        "completed_at": "",
        "summary": "",
        "error": "",
    }


class _FakeResolvedPath:
    def __init__(self, *, exists: bool, text: str = "", raise_on_read: bool = False):
        self._exists = exists
        self._text = text
        self._raise_on_read = raise_on_read

    def exists(self) -> bool:
        return self._exists

    def read_text(self, encoding: str = "utf-8") -> str:
        del encoding
        if self._raise_on_read:
            raise OSError("boom")
        return self._text


class TestDependencyHelpers(unittest.TestCase):
    def test_compute_dependency_depths_rejects_excessive_chain(self):
        deps_map = {f"a{index}": [f"a{index + 1}"] for index in range(201)}
        deps_map["a201"] = []

        with self.assertRaises(RuntimeError) as ctx:
            compute_dependency_depths(deps_map, "deep graph")

        self.assertIn("exceeds maximum depth", str(ctx.exception))

    def test_assign_groups_and_recompute_ready_use_dependency_depths(self):
        state = {
            "tasks": {
                "a": _task("a", "alpha", status="done"),
                "b": _task("b", "beta", deps=["a"]),
                "c": _task("c", "charlie", deps=["b"]),
            }
        }

        assign_groups(state, compute_dependency_depths_fn=compute_dependency_depths)
        recompute_ready(state)

        self.assertEqual(state["tasks"]["a"]["group"], 0)
        self.assertEqual(state["tasks"]["b"]["group"], 1)
        self.assertEqual(state["tasks"]["c"]["group"], 2)
        self.assertEqual(state["groups"], {"0": ["a"], "1": ["b"], "2": ["c"]})
        self.assertEqual(state["tasks"]["b"]["status"], "ready")
        self.assertEqual(state["tasks"]["c"]["status"], "blocked")


class TestSyncStateDirect(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)
        self.agents_dir = self.root / "agents"
        self.agents_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_sync_state_preserves_history_and_audits_removed_tasks(self):
        (self.agents_dir / "agent-a-alpha.md").write_text("alpha\n", encoding="utf-8")
        (self.agents_dir / "agent-1-ignore.md").write_text("ignored\n", encoding="utf-8")

        state = {
            "tasks": {
                "h": _task("h", "historical", deps=["x"]),
                "x": _task("x", "ancestor"),
                "z": _task("z", "stale"),
            }
        }
        ensure_calls: list[str] = []
        saved: list[dict] = []

        result = sync_state(
            load_state_fn=lambda: state,
            parse_spec_file_fn=lambda spec: {
                "spec_file": f"agents/{spec.name}",
                "scope": "Implement alpha.",
                "deps": ["h"],
                "files": ["alpha.py"],
            },
            parse_tracker_fn=lambda: {},
            build_tracker_prefix_map_fn=lambda current: {},
            save_state_fn=lambda payload: saved.append(payload),
            assign_groups_fn=lambda payload: assign_groups(payload, compute_dependency_depths_fn=compute_dependency_depths),
            recompute_ready_fn=recompute_ready,
            agents_dir=self.agents_dir,
            ensure_task_fields_fn=lambda task: ensure_calls.append(task["id"]),
        )

        self.assertIn("a", result["tasks"])
        self.assertIn("h", result["tasks"])
        self.assertIn("x", result["tasks"])
        self.assertNotIn("z", result["tasks"])
        self.assertEqual(result["sync_audit"][0]["task_id"], "z")
        self.assertEqual(result["tasks"]["a"]["status"], "blocked")
        self.assertEqual(result["tasks"]["x"]["status"], "ready")
        self.assertGreaterEqual(len(ensure_calls), 2)
        self.assertEqual(saved[-1], result)

    def test_sync_state_applies_tracker_status_updates(self):
        (self.agents_dir / "agent-a-alpha.md").write_text("alpha\n", encoding="utf-8")
        (self.agents_dir / "agent-b-beta.md").write_text("beta\n", encoding="utf-8")
        (self.agents_dir / "agent-c-charlie.md").write_text("charlie\n", encoding="utf-8")

        state = {"tasks": {}}
        tracker = {
            "run-a-1": {"status": "done", "update": "Finished"},
            "run-b-1": {"status": "running", "update": ""},
            "run-c-1": {"status": "failed", "issue": "Broken"},
        }

        result = sync_state(
            load_state_fn=lambda: state,
            parse_spec_file_fn=lambda spec: {
                "spec_file": f"agents/{spec.name}",
                "scope": spec.stem,
                "deps": [],
                "files": [],
            },
            parse_tracker_fn=lambda: tracker,
            build_tracker_prefix_map_fn=lambda current: {"run-a": "a", "run-b": "b", "run-c": "c"},
            save_state_fn=lambda payload: None,
            assign_groups_fn=lambda payload: assign_groups(payload, compute_dependency_depths_fn=compute_dependency_depths),
            recompute_ready_fn=lambda payload: None,
            agents_dir=self.agents_dir,
        )

        self.assertEqual(result["tasks"]["a"]["status"], "done")
        self.assertEqual(result["tasks"]["a"]["summary"], "Finished")
        self.assertEqual(result["tasks"]["b"]["status"], "running")
        self.assertEqual(result["tasks"]["c"]["status"], "failed")
        self.assertEqual(result["tasks"]["c"]["error"], "Broken")


class TestExecutionCommands(unittest.TestCase):
    def test_build_agent_prompt_embeds_conventions_and_spec(self):
        prompt = build_agent_prompt(
            {"id": "a", "name": "alpha"},
            "## Task\nDo work",
            conventions_file="CLAUDE.md",
        )

        self.assertIn("Read CLAUDE.md first", prompt)
        self.assertIn('"id": "A"', prompt)
        self.assertIn("## Task", prompt)

    def test_system_rules_template_contains_expected_markers(self):
        self.assertIn("RULES:", _SYSTEM_RULES_TEMPLATE)
        self.assertIn("Read {conventions_file}", _SYSTEM_RULES_TEMPLATE)

    def test_agent_result_schema_contains_expected_markers(self):
        self.assertIn("AGENT_RESULT_JSON:", _AGENT_RESULT_SCHEMA)
        self.assertIn('"status"', _AGENT_RESULT_SCHEMA)

    def test_cmd_status_without_tasks_emits_json_payload(self):
        payloads: list[dict] = []

        cmd_status(
            argparse.Namespace(json=True),
            sync_state_fn=lambda: {"tasks": {}, "execution_manifest": {}, "updated_at": ""},
            cfg={},
            sym_map={},
            emit_json_fn=lambda payload: payloads.append(payload),
        )

        self.assertEqual(payloads[0]["status"], "idle")
        self.assertEqual(payloads[0]["next_action"], "idle")

    def test_cmd_status_json_requires_emitter_when_tasks_exist(self):
        with self.assertRaises(RuntimeError):
            cmd_status(
                argparse.Namespace(json=True),
                sync_state_fn=lambda: {"tasks": {"a": _task("a", "alpha", status="ready")}},
                cfg={},
                sym_map={},
                emit_json_fn=None,
            )

    def test_cmd_ready_text_reports_blocked_agents_when_none_ready(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            cmd_ready(
                argparse.Namespace(json=False),
                sync_state_fn=lambda: {
                    "tasks": {
                        "a": _task("a", "alpha", status="done"),
                        "b": _task("b", "beta", status="blocked", deps=["a", "c"]),
                    }
                },
                emit_json_fn=lambda payload: None,
            )

        output = buf.getvalue()
        self.assertIn("No agents ready to launch", output)
        self.assertIn("waiting on: C", output)

    def test_cmd_run_handles_explicit_ids_and_launch_payload(self):
        state = {
            "tasks": {
                "a": _task("a", "alpha", status="done"),
                "b": _task("b", "beta", status="running"),
                "c": _task("c", "charlie", status="blocked", deps=["d"]),
                "d": _task("d", "delta", status="ready"),
                "e": _task("e", "echo", status="ready"),
                "f": _task("f", "foxtrot", status="ready"),
            }
        }
        resolved = {
            state["tasks"]["d"]["spec_file"]: _FakeResolvedPath(exists=True, text="ignored"),
            state["tasks"]["e"]["spec_file"]: _FakeResolvedPath(exists=True, raise_on_read=True),
            state["tasks"]["f"]["spec_file"]: _FakeResolvedPath(exists=False),
        }
        saved: list[dict] = []
        payloads: list[dict] = []
        ensure_calls: list[str] = []

        cmd_run(
            argparse.Namespace(agents="missing,a,b,c,d,e,f"),
            sync_state_fn=lambda: state,
            now_iso_fn=lambda: "2026-03-12T10:00:00+00:00",
            safe_resolve_fn=lambda spec_file: resolved[spec_file],
            validate_spec_file_fn=lambda spec_path, agent_id, strict: ["missing criteria"] if agent_id == "d" else [],
            save_state_fn=lambda payload: saved.append(payload),
            build_agent_prompt_fn=lambda task, spec_text: f"{task['id']}::{spec_text}",
            emit_json_fn=lambda payload: payloads.append(payload),
            ensure_task_fields_fn=lambda task: ensure_calls.append(task["id"]),
            cfg=None,
        )

        payload = payloads[0]
        self.assertEqual(payload["requested"], ["missing", "a", "b", "c", "d", "e", "f"])
        self.assertEqual(payload["launched"], ["e", "f"])
        skipped_reasons = {item["id"]: item["reason"] for item in payload["skipped"]}
        self.assertEqual(skipped_reasons["missing"], "not_found")
        self.assertEqual(skipped_reasons["a"], "already_done")
        self.assertEqual(skipped_reasons["b"], "already_running")
        self.assertEqual(skipped_reasons["c"], "blocked")
        self.assertEqual(skipped_reasons["d"], "invalid_spec")
        self.assertEqual(payload["agents"][0]["prompt"], "e::")
        self.assertEqual(payload["agents"][1]["prompt"], "f::")
        self.assertEqual(payload["agents"][0]["model"], "haiku")
        self.assertEqual(sorted(ensure_calls), ["e", "f"])
        self.assertEqual(saved[-1]["tasks"]["e"]["status"], "running")
        self.assertEqual(saved[-1]["tasks"]["f"]["started_at"], "2026-03-12T10:00:00+00:00")

    def test_cmd_run_all_targets_ready_and_pending(self):
        state = {
            "tasks": {
                "a": _task("a", "alpha", status="ready"),
                "b": _task("b", "beta", status="pending"),
                "c": _task("c", "charlie", status="blocked"),
            }
        }
        payloads: list[dict] = []

        cmd_run(
            argparse.Namespace(agents="all"),
            sync_state_fn=lambda: state,
            now_iso_fn=lambda: "2026-03-12T10:00:00+00:00",
            safe_resolve_fn=lambda spec_file: _FakeResolvedPath(exists=False),
            validate_spec_file_fn=lambda spec_path, agent_id, strict: [],
            save_state_fn=lambda payload: None,
            build_agent_prompt_fn=lambda task, spec_text: task["id"],
            emit_json_fn=lambda payload: payloads.append(payload),
            cfg={},
        )

        self.assertEqual(payloads[0]["requested"], ["a", "b"])
        self.assertEqual(payloads[0]["launched"], ["a", "b"])

    def test_cmd_complete_updates_agent_result_and_announces_newly_ready(self):
        state = {
            "tasks": {
                "a": {
                    **_task("a", "alpha", status="running"),
                    "agent_result": {"status": "running", "summary": "", "reported_at": ""},
                },
                "b": _task("b", "beta", deps=["a"]),
            }
        }
        buf = io.StringIO()

        with redirect_stdout(buf):
            cmd_complete(
                argparse.Namespace(agent="A", summary="All checks pass."),
                load_state_fn=lambda: state,
                now_iso_fn=lambda: "2026-03-12T11:00:00+00:00",
                recompute_ready_fn=recompute_ready,
                save_state_fn=lambda payload: None,
                empty_merge_record_factory=lambda: {"status": "pending"},
            )

        self.assertEqual(state["tasks"]["a"]["status"], "done")
        self.assertEqual(state["tasks"]["a"]["agent_result"]["summary"], "All checks pass.")
        self.assertEqual(state["tasks"]["a"]["merge"], {"status": "pending"})
        self.assertEqual(state["tasks"]["b"]["status"], "ready")
        self.assertIn("Newly ready", buf.getvalue())

    def test_cmd_complete_missing_agent_exits(self):
        with self.assertRaises(SystemExit):
            cmd_complete(
                argparse.Namespace(agent="z", summary=""),
                load_state_fn=lambda: {"tasks": {}},
                now_iso_fn=lambda: "",
                recompute_ready_fn=lambda payload: None,
                save_state_fn=lambda payload: None,
            )

    def test_cmd_fail_updates_agent_result_and_merge_record(self):
        state = {
            "tasks": {
                "a": {
                    **_task("a", "alpha", status="running"),
                    "agent_result": {"status": "running", "issues": [], "reported_at": ""},
                }
            }
        }

        cmd_fail(
            argparse.Namespace(agent="a", reason="Build broke"),
            load_state_fn=lambda: state,
            now_iso_fn=lambda: "2026-03-12T12:00:00+00:00",
            save_state_fn=lambda payload: None,
            normalize_string_list_fn=lambda value: [str(value)],
            empty_merge_record_factory=lambda: {"status": "pending"},
        )

        self.assertEqual(state["tasks"]["a"]["status"], "failed")
        self.assertEqual(state["tasks"]["a"]["agent_result"]["issues"], ["Build broke"])
        self.assertEqual(state["tasks"]["a"]["merge"], {"status": "pending"})

    def test_cmd_fail_missing_agent_exits(self):
        with self.assertRaises(SystemExit):
            cmd_fail(
                argparse.Namespace(agent="z", reason=""),
                load_state_fn=lambda: {"tasks": {}},
                now_iso_fn=lambda: "",
                save_state_fn=lambda payload: None,
            )

    def test_cmd_reset_resets_result_and_merge_state(self):
        state = {
            "tasks": {
                "a": {
                    **_task("a", "alpha", status="failed", deps=[]),
                    "agent_result": {"status": "failed"},
                    "merge": {"status": "conflict"},
                    "started_at": "2026-03-12T09:00:00+00:00",
                    "completed_at": "2026-03-12T09:30:00+00:00",
                    "summary": "bad",
                    "error": "boom",
                }
            }
        }

        cmd_reset(
            argparse.Namespace(agent="a"),
            load_state_fn=lambda: state,
            recompute_ready_fn=recompute_ready,
            save_state_fn=lambda payload: None,
            empty_agent_result_factory=lambda: {"status": ""},
            empty_merge_record_factory=lambda: {"status": ""},
        )

        self.assertEqual(state["tasks"]["a"]["status"], "ready")
        self.assertEqual(state["tasks"]["a"]["agent_result"], {"status": ""})
        self.assertEqual(state["tasks"]["a"]["merge"], {"status": ""})
        self.assertEqual(state["tasks"]["a"]["error"], "")

    def test_cmd_reset_missing_agent_exits(self):
        with self.assertRaises(SystemExit):
            cmd_reset(
                argparse.Namespace(agent="z"),
                load_state_fn=lambda: {"tasks": {}},
                recompute_ready_fn=lambda payload: None,
                save_state_fn=lambda payload: None,
            )

    def test_cmd_next_reports_running_and_blocked_or_done_states(self):
        running_state = {
            "tasks": {
                "a": _task("a", "alpha", status="running", started_at="2026-03-12T09:00:00+00:00"),
            }
        }
        blocked_state = {
            "tasks": {
                "a": _task("a", "alpha", status="blocked"),
            }
        }
        done_state = {
            "tasks": {
                "a": _task("a", "alpha", status="done"),
            }
        }

        running_buf = io.StringIO()
        with redirect_stdout(running_buf):
            cmd_next(argparse.Namespace(), sync_state_fn=lambda: running_state)
        self.assertIn("Running (1)", running_buf.getvalue())

        blocked_buf = io.StringIO()
        with redirect_stdout(blocked_buf):
            cmd_next(argparse.Namespace(), sync_state_fn=lambda: blocked_state)
        self.assertIn("All remaining agents are blocked", blocked_buf.getvalue())

        done_buf = io.StringIO()
        with redirect_stdout(done_buf):
            cmd_next(argparse.Namespace(), sync_state_fn=lambda: done_state)
        self.assertIn("All done!", done_buf.getvalue())

    def test_cmd_add_without_factory_creates_task_and_warns_about_missing_spec(self):
        state = {"tasks": {}}
        saved: list[dict] = []
        buf = io.StringIO()

        with redirect_stdout(buf):
            cmd_add(
                argparse.Namespace(letter="A", name="Alpha", scope="Ship it", deps="", files="one.py,two.py", complexity="high"),
                sync_state_fn=lambda: {
                    "tasks": state["tasks"],
                    "groups": {},
                },
                validate_agent_id_fn=lambda letter: None,
                assign_groups_fn=lambda payload: assign_groups(payload, compute_dependency_depths_fn=compute_dependency_depths),
                recompute_ready_fn=recompute_ready,
                save_state_fn=lambda payload: saved.append(payload),
                safe_resolve_fn=lambda spec_file: _FakeResolvedPath(exists=False),
            )

        self.assertEqual(state["tasks"]["a"]["complexity"], "high")
        self.assertEqual(state["tasks"]["a"]["deps"], [])
        self.assertIn("Spec file missing", buf.getvalue())
        self.assertEqual(saved[-1]["tasks"], state["tasks"])
        self.assertEqual(saved[-1]["groups"], {"0": ["a"]})

    def test_cmd_new_passes_through_generated_letter(self):
        add_calls: list[argparse.Namespace] = []
        template_calls: list[argparse.Namespace] = []

        cmd_new(
            argparse.Namespace(name="alpha", scope="Do alpha", deps="b", files="alpha.py", no_template=False),
            sync_state_fn=lambda: {"tasks": {}},
            next_agent_letter_fn=lambda state: "q",
            cmd_add_fn=lambda ns: add_calls.append(ns),
            cmd_template_fn=lambda ns: template_calls.append(ns),
        )

        self.assertEqual(add_calls[0].letter, "q")
        self.assertEqual(template_calls[0].letter, "q")

    def test_cmd_new_skips_template_when_requested(self):
        template_calls: list[argparse.Namespace] = []

        cmd_new(
            argparse.Namespace(name="alpha", scope="", deps="", files="", no_template=True),
            sync_state_fn=lambda: {"tasks": {}},
            next_agent_letter_fn=lambda state: "r",
            cmd_add_fn=lambda ns: None,
            cmd_template_fn=lambda ns: template_calls.append(ns),
        )

        self.assertEqual(template_calls, [])

    def test_cmd_template_creates_file_with_default_scope_and_rejects_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            agents_dir = Path(tmp) / "agents"
            buf = io.StringIO()

            with redirect_stdout(buf):
                cmd_template(
                    argparse.Namespace(letter="A", name="Alpha", scope=""),
                    validate_agent_id_fn=lambda letter: None,
                    agents_dir=agents_dir,
                    render_spec_template_fn=lambda letter, name, scope: f"{letter}|{name}|{scope}",
                )

            spec_path = agents_dir / "agent-a-alpha.md"
            self.assertTrue(spec_path.exists())
            self.assertIn("Implement the assigned scope for Agent A.", spec_path.read_text(encoding="utf-8"))
            self.assertIn("Created:", buf.getvalue())

            with self.assertRaises(SystemExit):
                cmd_template(
                    argparse.Namespace(letter="A", name="Alpha", scope=""),
                    validate_agent_id_fn=lambda letter: None,
                    agents_dir=agents_dir,
                    render_spec_template_fn=lambda letter, name, scope: "",
                )


if __name__ == "__main__":
    unittest.main()
