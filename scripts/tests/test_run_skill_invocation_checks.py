"""Deterministic replay-runner checks. No installed model CLI is invoked."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts import run_skill_invocation_checks as runner


def codex_command(command, output="skill instructions", exit_code=0, identifier="tool1"):
    item = {"id": identifier, "type": "command_execution", "command": command}
    return [
        {"type": "item.started", "item": dict(item)},
        {"type": "item.completed", "item": dict(item, aggregated_output=output,
                                                  exit_code=exit_code, status="completed")},
    ]


def claude_skill(skill="usage-stats", error=False, content=None):
    return [
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "skill1", "name": "Skill", "input": {"skill": skill}}]}},
        {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "skill1", "is_error": error,
             "content": content if content is not None else f"Launching skill: {skill}"}]}},
    ]


class TraceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "trace.jsonl"

    def parse(self, provider, events, positive=True, terminal=True):
        if terminal:
            events = events + [{"type": "item.completed", "item": {"id": "final", "type": "agent_message", "text": "done"}},
                               {"type": "turn.completed", "usage": {"input_tokens": 12}}] if provider == "codex" else events + [
                {"type": "result", "subtype": "success", "is_error": False, "result": "done",
                 "usage": {"input_tokens": 12}}]
        self.path.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
        case = {"expected_skill" if positive else "forbidden_skill": "usage-stats"}
        return runner.parse_trace(provider, self.path, case)

    def test_codex_read_requires_paired_success_and_nonempty_output(self):
        for command in (r"Get-Content -LiteralPath 'D:\skills\usage-stats\SKILL.md'",
                        "cat /tmp/skills/usage-stats/SKILL.md"):
            with self.subTest(command=command):
                report = self.parse("codex", codex_command(command))
                self.assertEqual(report["routing_status"], "PASS")
                self.assertEqual(report["task_result_status"], "MANUAL_REVIEW_REQUIRED")
                self.assertEqual(len(report["skill_attempts"]), 1)
        for output, code in (("", 0), ("permission denied", 1)):
            report = self.parse("codex", codex_command("cat /skills/usage-stats/SKILL.md", output, code))
            self.assertNotEqual(report["routing_status"], "PASS")

    def test_forbidden_failed_or_incomplete_reads_fail(self):
        for events in (codex_command("cat /skills/usage-stats/SKILL.md", "denied", 1),
                       codex_command("cat /skills/usage-stats/SKILL.md")[:1]):
            self.assertEqual(self.parse("codex", events, positive=False)["routing_status"], "FAIL")
        self.assertEqual(self.parse("claude", claude_skill(error=True), positive=False)["routing_status"], "FAIL")

    def test_narration_and_catalog_do_not_count_as_invocation(self):
        events = [{"type": "item.completed", "item": {"type": "agent_message", "id": "a",
                   "text": "I loaded /skills/usage-stats/SKILL.md. The total is 5250."}}]
        self.assertNotEqual(self.parse("codex", events)["routing_status"], "PASS")
        events = [{"type": "system", "subtype": "init", "skills": ["usage-stats"]},
                  {"type": "assistant", "message": {"content": [{"type": "text", "text": "Launching skill: usage-stats"}]}}]
        self.assertEqual(self.parse("claude", events, positive=False)["routing_status"], "PASS")

    def test_echo_listing_and_unrelated_reader_are_not_skill_loads(self):
        for command in ("echo /skills/usage-stats/SKILL.md", "rg --files /skills/usage-stats/SKILL.md",
                        "Get-Content README.md; Write-Output '/skills/usage-stats/SKILL.md'",
                        "echo 'Get-Content /skills/usage-stats/SKILL.md'"):
            with self.subTest(command=command):
                result = self.parse("codex", codex_command(command))
                self.assertNotEqual(result["routing_status"], "PASS")
                self.assertFalse(any(a["success"] for a in result["skill_attempts"]))

    def test_claude_requires_matched_successful_tool_result(self):
        self.assertEqual(self.parse("claude", claude_skill("plugin:usage-stats"))["routing_status"], "PASS")
        for events in (claude_skill()[:1], claude_skill(content=""), claude_skill(content="Unknown skill")):
            self.assertNotEqual(self.parse("claude", events)["routing_status"], "PASS")
        events = claude_skill()
        events[1]["message"]["content"][0]["tool_use_id"] = "different"
        self.assertNotEqual(self.parse("claude", events)["routing_status"], "PASS")

    def test_duplicate_events_do_not_inflate_attempts(self):
        events = codex_command("cat /skills/usage-stats/SKILL.md")
        result = self.parse("codex", events + events)
        self.assertEqual(len(result["skill_attempts"]), 1)
        self.assertEqual(result["routing_status"], "PASS")
        events = claude_skill()
        result = self.parse("claude", events + events)
        self.assertEqual(len(result["skill_attempts"]), 1)
        self.assertEqual(result["routing_status"], "PASS")

    def test_uppercase_failed_forbidden_reads_cannot_bypass_control(self):
        command = "Get-Content -LiteralPath '/skills/USAGE-STATS/SKILL.md'"
        result = self.parse("codex", codex_command(command, "denied", 1), positive=False)
        self.assertEqual(result["routing_status"], "FAIL")
        self.assertEqual(result["skill_attempts"][0]["skill"], "usage-stats")
        events = [
            {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "read", "name": "Read",
                                                            "input": {"file_path": "/skills/USAGE-STATS/SKILL.md"}}]}},
            {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "read", "is_error": True,
                                                       "content": "Permission denied"}]}},
        ]
        self.assertEqual(self.parse("claude", events, positive=False)["routing_status"], "FAIL")
        result = self.parse("codex", codex_command("echo /skills/USAGE-STATS/SKILL.md"), positive=False)
        self.assertEqual(result["ambiguous_skill_references"][0]["skill"], "usage-stats")
        self.assertEqual(self.parse("claude", claude_skill("plugin:USAGE-STATS"), positive=False)["routing_status"], "FAIL")

    def test_reader_option_values_cannot_become_skill_targets(self):
        for command in (
            "Get-Content -LiteralPath README -Delimiter '/trusted/usage-stats/SKILL.md'",
            "Get-Content README -Encoding '/trusted/usage-stats/SKILL.md'",
            "Get-Content -Unknown '/trusted/usage-stats/SKILL.md'",
            "cat --unknown /trusted/usage-stats/SKILL.md",
        ):
            with self.subTest(command=command):
                self.parse("codex", codex_command(command, "ordinary README content"))
                result = runner.parse_trace("codex", self.path, {"expected_skill": "usage-stats"},
                                            trusted_entries={"usage-stats": "/trusted/usage-stats/SKILL.md"})
                self.assertEqual(result["routing_status"], "INCONCLUSIVE")
                self.assertFalse(any(attempt["success"] for attempt in result["skill_attempts"]))

    def test_mixed_or_unknown_wrapper_arguments_cannot_prove_read(self):
        for command in (
            "pwsh -NoProfile -File noop.ps1 -Command \"Get-Content '/trusted/usage-stats/SKILL.md'\"",
            "pwsh -Unknown -Command \"Get-Content '/trusted/usage-stats/SKILL.md'\"",
            "pwsh -Command \"Get-Content '/trusted/usage-stats/SKILL.md'\" -File noop.ps1",
        ):
            with self.subTest(command=command):
                result = self.parse("codex", codex_command(command, "ordinary script output"))
                self.assertEqual(result["routing_status"], "INCONCLUSIVE")
                self.assertFalse(any(attempt["success"] for attempt in result["skill_attempts"]))
        valid = "pwsh -NoProfile -Command \"Get-Content -Raw -LiteralPath '/skills/usage-stats/SKILL.md'\""
        self.assertEqual(self.parse("codex", codex_command(valid))["routing_status"], "PASS")

    def test_conflicting_completed_results_never_overwrite_to_success(self):
        for provider, first, second in (
            ("codex", codex_command("cat /skills/usage-stats/SKILL.md", "Permission denied", 1),
             codex_command("cat /skills/usage-stats/SKILL.md")[1:]),
            ("claude", claude_skill(error=True, content="Permission denied"), claude_skill()[1:]),
            ("codex", codex_command("cat /skills/usage-stats/SKILL.md"),
             codex_command("cat /skills/usage-stats/SKILL.md", "different output")[1:]),
            ("claude", claude_skill(), claude_skill(content="Launching skill: usage-stats\ndifferent output")[1:]),
        ):
            with self.subTest(provider=provider, first=first):
                result = self.parse(provider, first + second)
                self.assertEqual(result["routing_status"], "INCONCLUSIVE")
                self.assertTrue(any("Conflicting completed" in error for error in result["errors"]))
                self.assertFalse(result["skill_attempts"][0]["success"])
                self.assertEqual(self.parse(provider, first + second, positive=False)["routing_status"], "FAIL")

    def test_empty_truncated_unknown_and_unterminated_traces_cannot_pass(self):
        for provider in ("codex", "claude"):
            self.assertNotEqual(self.parse(provider, [], positive=False, terminal=False)["routing_status"], "PASS")
            self.assertNotEqual(self.parse(provider, [{"type": "unknown_tool_event"}], positive=False)["routing_status"], "PASS")
            self.path.write_text('{"type":', encoding="utf-8")
            self.assertNotEqual(runner.parse_trace(provider, self.path, {"forbidden_skill": "usage-stats"})["routing_status"], "PASS")

    def test_terminal_without_final_answer_cannot_pass(self):
        for provider, terminal in (("codex", {"type": "turn.completed"}),
                                   ("claude", {"type": "result", "subtype": "success", "is_error": False, "result": ""})):
            self.assertNotEqual(self.parse(provider, [terminal], positive=False, terminal=False)["routing_status"], "PASS")
        events = [{"type": "assistant", "message": {"content": [{"type": "text", "text": "I will check."}]}},
                  {"type": "result", "subtype": "success", "is_error": False, "result": ""}]
        self.assertNotEqual(self.parse("claude", events, positive=False, terminal=False)["routing_status"], "PASS")

    def test_conflicting_tool_id_retains_forbidden_attempt(self):
        events = codex_command("cat README.md")
        events[1]["item"]["command"] = "cat /skills/usage-stats/SKILL.md"
        result = self.parse("codex", events, positive=False)
        self.assertEqual(result["routing_status"], "FAIL")
        self.assertTrue(result["errors"])
        events = claude_skill("other")[:1] + claude_skill()[:1]
        self.assertEqual(self.parse("claude", events, positive=False)["routing_status"], "FAIL")

    def test_malformed_command_completion_cannot_prove_load(self):
        events = codex_command("cat /skills/usage-stats/SKILL.md")
        events[1]["item"]["aggregated_output"] = ["not an output string"]
        self.assertNotEqual(self.parse("codex", events)["routing_status"], "PASS")

    def test_malformed_before_valid_terminal_cannot_pass(self):
        self.parse("codex", [], positive=False)
        self.path.write_text("malformed\n" + self.path.read_text(), encoding="utf-8")
        self.assertNotEqual(runner.parse_trace("codex", self.path, {"forbidden_skill": "usage-stats"})["routing_status"], "PASS")

    def test_unknown_tool_types_and_failed_provider_completions_cannot_pass(self):
        traces = [
            ("codex", [{"type": "item.completed", "item": {"id": "other", "type": "mcp_tool_call"}}]),
            ("codex", [{"type": "turn.failed", "error": {"message": "denied"}}]),
            ("claude", [{"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "other", "name": "Unknown", "input": {}}]}}]),
            ("claude", [{"type": "result", "subtype": "error_during_execution", "is_error": True, "result": "denied"}]),
        ]
        for provider, events in traces:
            with self.subTest(provider=provider, events=events):
                self.assertNotEqual(self.parse(provider, events, positive=False)["routing_status"], "PASS")

    def test_codex_unmatched_completion_cannot_prove_load(self):
        self.assertNotEqual(self.parse("codex", codex_command("cat /skills/usage-stats/SKILL.md")[1:])["routing_status"], "PASS")

    def test_claude_failed_read_of_forbidden_skill_fails(self):
        events = [
            {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "read", "name": "Read", "input": {"file_path": "/skills/usage-stats/SKILL.md"}}]}},
            {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "read", "is_error": True, "content": "Permission denied"}]}},
        ]
        self.assertEqual(self.parse("claude", events, positive=False)["routing_status"], "FAIL")

    def test_unrecognized_claude_content_cannot_hide_tool_evidence(self):
        events = [{"type": "assistant", "message": {"content": [
            {"type": "server_tool_use", "name": "read", "input": {"path": "/skills/usage-stats/SKILL.md"}}]}}]
        self.assertNotEqual(self.parse("claude", events, positive=False)["routing_status"], "PASS")

    def test_successful_reader_must_match_requested_installed_entry(self):
        case = {"expected_skill": "usage-stats"}
        self.parse("codex", codex_command("cat /other/usage-stats/SKILL.md"))
        result = runner.parse_trace("codex", self.path, case, trusted_entries={"usage-stats": "/trusted/usage-stats/SKILL.md"})
        self.assertNotEqual(result["routing_status"], "PASS")
        self.assertFalse(result["skill_attempts"][0]["success"])
        self.parse("codex", codex_command("cat /trusted/usage-stats/SKILL.md"))
        result = runner.parse_trace("codex", self.path, case, trusted_entries={"usage-stats": "/trusted/usage-stats/SKILL.md"})
        self.assertEqual(result["routing_status"], "PASS")

    def test_missing_target_in_exposed_claude_catalog_is_inconclusive(self):
        result = self.parse("claude", [{"type": "system", "subtype": "init", "skills": ["other"]}], positive=False)
        self.assertEqual(result["routing_status"], "INCONCLUSIVE")
        self.assertFalse(result["catalog"]["target_advertised"])

    def test_successful_fixture_read_recorded_without_accepting_task_result(self):
        events = claude_skill() + [
            {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "read1", "name": "Read",
                                                            "input": {"file_path": "usage-snapshot.json"}}]}},
            {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "read1", "content": "{}"}]}},
        ]
        result = self.parse("claude", events)
        self.assertEqual(result["fixture_reads"], ["usage-snapshot.json"])
        self.assertEqual(result["task_result_status"], "MANUAL_REVIEW_REQUIRED")


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.skills = self.root / "skills"
        (self.skills / "usage-stats").mkdir(parents=True)
        (self.skills / "usage-stats" / "SKILL.md").write_text("# Usage\n", encoding="utf-8")
        self.spec = {"schema_version": 1, "fixtures": {"README.md": "fixture"}, "cases": [
            {"id": "negative", "providers": ["codex"], "prompt": "Explain tokens", "forbidden_skill": "usage-stats"}]}
        self.spec_path = self.root / "spec.json"

    def args(self, *extra):
        self.spec_path.write_text(json.dumps(self.spec), encoding="utf-8")
        return runner.build_parser().parse_args(["--spec", str(self.spec_path), "--provider", "codex",
                                               "--codex-skill-root", str(self.skills), *extra])

    def test_invalid_inputs_fail_before_cli_launch(self):
        for fixture in ("../escape", "/absolute", "C:relative", "C:\\absolute", ".codex/config.toml",
                        "a/../escape", ".claude/settings.json", "AGENTS.md"):
            with self.subTest(fixture=fixture), mock.patch.object(runner, "run_process") as launch:
                self.spec["fixtures"] = {fixture: "bad"}
                with self.assertRaises(ValueError):
                    runner.run(self.args())
                launch.assert_not_called()
        self.spec = []
        with mock.patch.object(runner, "run_process") as launch, self.assertRaises(ValueError):
            runner.run(self.args())
        launch.assert_not_called()

    def test_duplicates_empty_selection_missing_entries_and_bad_limits_fail(self):
        for extra in (("--case", "missing"), ("--repeat", "0"), ("--timeout", "0")):
            with self.subTest(extra=extra), mock.patch.object(runner, "run_process") as launch:
                with self.assertRaises(ValueError):
                    runner.run(self.args(*extra))
                launch.assert_not_called()
        args = self.args()
        args.provider = ["claude"]
        args.case = ["negative"]
        with mock.patch.object(runner, "run_process") as launch, self.assertRaises(ValueError):
            runner.run(args)
        launch.assert_not_called()
        self.spec["cases"] *= 2
        with self.assertRaises(ValueError):
            runner.run(self.args())
        self.spec["cases"] = self.spec["cases"][:1]
        (self.skills / "usage-stats" / "SKILL.md").unlink()
        with mock.patch.object(runner, "run_process") as launch, self.assertRaises(ValueError):
            runner.run(self.args())
        launch.assert_not_called()

    def test_real_subprocess_fake_cli_preserves_uuid_artifacts(self):
        self.spec["fixtures"]["exec"] = self.fake_script()
        report, artifact = runner.run(self.args("--codex-cli", sys.executable))
        self.assertEqual(report["routing_status"], "PASS")
        self.assertTrue((artifact / "report.json").is_file())
        run = report["runs"][0]
        import uuid
        self.assertEqual(str(uuid.UUID(Path(run["fixture_dir"]).name)), Path(run["fixture_dir"]).name)
        self.assertTrue(Path(run["stdout_path"]).is_file())
        self.assertTrue(Path(run["prompt_path"]).is_file())
        self.assertEqual(run["task_result_status"], "MANUAL_REVIEW_REQUIRED")
        self.assertIn("skill_hashes_before", report)

    def fake_script(self, prefix="", suffix=""):
        return prefix + 'print(\'{"type":"item.completed","item":{"type":"agent_message","id":"answer","text":"Synthetic answer"}}\')\n' + 'print(\'{"type":"turn.completed","usage":{"input_tokens":1}}\')\n' + suffix

    def test_nonzero_process_with_valid_trace_fails(self):
        self.spec["fixtures"]["exec"] = self.fake_script(suffix="raise SystemExit(7)\n")
        report, _ = runner.run(self.args("--codex-cli", sys.executable))
        self.assertEqual(report["routing_status"], "FAIL")
        self.assertEqual(report["runs"][0]["process"]["returncode"], 7)

    def test_cli_version_drift_fails(self):
        self.spec["fixtures"]["exec"] = self.fake_script()
        original = runner.cli_version
        def changing_version(*args):
            value = original(*args)
            if "after" in args[2]:
                value["version"] += "-changed"
            return value
        with mock.patch.object(runner, "cli_version", side_effect=changing_version):
            report, _ = runner.run(self.args("--codex-cli", sys.executable))
        self.assertEqual(report["routing_status"], "FAIL")
        self.assertTrue(any("version/hash drift" in error for error in report["errors"]))

    def test_remember_metadata_is_separate_and_preserved(self):
        self.spec["fixtures"]["exec"] = self.fake_script(prefix="from pathlib import Path\nPath('.remember').mkdir()\nPath('.remember/now.md').write_text('hook metadata')\n")
        report, _ = runner.run(self.args("--codex-cli", sys.executable))
        self.assertEqual(report["routing_status"], "PASS")
        self.assertIn(".remember/now.md", report["runs"][0]["fixture_after"]["remember_metadata"])

    def test_network_free_help_and_actual_cli_exit_status(self):
        result = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/run_skill_invocation_checks.py"), "--help"], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0)
        self.assertIn("--codex-skill-root", result.stdout)
        self.spec["fixtures"]["exec"] = self.fake_script(suffix="raise SystemExit(7)\n")
        self.args()
        result = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/run_skill_invocation_checks.py"),
                                 "--spec", str(self.spec_path), "--provider", "codex", "--codex-cli", sys.executable,
                                 "--codex-skill-root", str(self.skills)], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Routing: FAIL", result.stdout)
        self.assertIn("Evidence:", result.stdout)

    def test_owned_process_timeout_keeps_output(self):
        out, err = self.root / "out", self.root / "err"
        prompt = self.root / "prompt"
        prompt.write_text("input", encoding="utf-8")
        result = runner.run_process([sys.executable, "-u", "-c", "import time; print('started', flush=True); time.sleep(30)"],
                                    self.root, prompt, out, err, 0.5)
        self.assertTrue(result["timed_out"])
        self.assertIn("started", out.read_text())
        self.assertIsNotNone(result["returncode"])

    def test_skill_drift_and_fixture_mutation_fail(self):
        entry = self.skills / "usage-stats" / "SKILL.md"
        for mutation in (f"from pathlib import Path\nPath({str(entry)!r}).write_text('changed')\n",
                         "from pathlib import Path\nPath('extra.txt').write_text('extra')\n"):
            self.spec["fixtures"]["exec"] = self.fake_script(prefix=mutation)
            report, _ = runner.run(self.args("--codex-cli", sys.executable))
            self.assertEqual(report["routing_status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
