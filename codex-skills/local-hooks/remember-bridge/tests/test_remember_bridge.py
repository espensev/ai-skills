"""Unit and end-to-end tests for the Grok/Kimi Remember bridge.

Run from the repository root:

    python -B -m unittest .\\codex-skills\\local-hooks\\remember-bridge\\tests\\test_remember_bridge.py

The end-to-end tests need Git Bash and the pinned Remember checkout
(`REMEMBER_BRIDGE_PLUGIN_ROOT`, default `D:/DevHome/state/remember/artifacts/remember-current`);
they are skipped elsewhere and say so.
"""

import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PACKAGE_ROOT / "Invoke-RememberBridge.py"


def _load_bridge():
    spec = importlib.util.spec_from_file_location("remember_bridge", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to construct bridge import spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


bridge = _load_bridge()

GIT_BASH = Path(r"C:\Program Files\Git\bin\bash.exe")
PLUGIN_ROOT = Path(os.environ.get("REMEMBER_BRIDGE_PLUGIN_ROOT", "D:/DevHome/state/remember/artifacts/remember-current"))
HAVE_BASH = GIT_BASH.exists() or shutil.which("bash") is not None
HAVE_PLUGIN = (PLUGIN_ROOT / "scripts" / "session-end-hook.sh").exists() and (PLUGIN_ROOT / "pipeline" / "slug.py").exists()

GROK_SID = "01a0718b-9a49-7332-b136-e054f1490e57"
KIMI_UUID = "d2ba7fb0-edfa-4dc9-938f-3cfd693d5c91"
KIMI_SID = "session_" + KIMI_UUID


# ── fixtures (sanitised shapes of real captures, 2026-09-05) ─────────────────

def grok_lines():
    return [
        {"type": "system", "content": "You are Grok 4.6 released by xAI."},
        {"type": "user", "content": [{"type": "text", "text": "<user_info>\nOS Version: windows\nShell: pwsh\nWorkspace Path: D:\\DevHome\n</user_info>"}]},
        {"type": "user", "content": [{"type": "text", "text": "<system-reminder>\nThe following skills are available\n</system-reminder>"}], "synthetic_reason": "skills"},
        {"type": "user", "content": [{"type": "text", "text": "<user_query>\nwhat do these settings do\n</user_query>"}], "prompt_index": 0},
        {"type": "reasoning", "id": "rs_1", "summary": [{"type": "summary_text", "text": "thinking"}], "encrypted_content": "xxx", "status": "completed"},
        {"type": "backend_tool_call", "kind": {"tool_type": "web_search"}},
        {"type": "assistant", "content": "I'll look those up.", "tool_calls": [{"id": "call-1", "name": "read_file", "arguments": "{\"target_file\":\"C:\\\\Users\\\\x\\\\SKILL.md\",\"limit\":80}"}], "model_id": "grok-4.6-build"},
        {"type": "tool_result", "tool_call_id": "call-1", "content": "1: ---\nname: documentation-lookup"},
        {"type": "user", "content": [{"type": "text", "text": "The user sent a message while you were working:\n<user_query>\nmy terminals\n</user_query>\nMake sure to complete the current task."}], "prompt_index": 1},
        {"type": "assistant", "content": "Both settings control paste trimming.", "tool_calls": [], "model_id": "grok-4.6-build"},
    ]


def kimi_loop(event, **fields):
    return {"type": "context.append_loop_event", "agentId": "main", "event": {"type": event, **fields}, "time": 1788606162326}


def kimi_lines():
    step = {"turnId": "0", "step": 1, "stepUuid": "s1"}
    return [
        {"type": "metadata", "protocol_version": "1.5", "created_at": 1788606147142},
        {"type": "profile.bind", "agentId": "main", "modelAlias": "kimi-code/k3", "systemPrompt": "You are Kimi Code CLI."},
        {"type": "context.append_message", "agentId": "main", "message": {"role": "user", "content": [{"type": "text", "text": "<system-reminder>\n## Swarm Mode\n</system-reminder>"}]}},
        {"type": "prompt.accepted", "agentId": "main", "promptId": "msg_1", "content": [{"type": "text", "text": "Review the earlier work"}]},
        {"type": "turn.prompt", "agentId": "main", "input": [{"type": "text", "text": "Review the earlier work"}], "origin": {"kind": "user"}, "promptId": "msg_1"},
        kimi_loop("step.begin", uuid="s1", turnId="0", step=1),
        kimi_loop("content.part", uuid="p1", **step, part={"type": "think", "think": "Let me think about it."}),
        kimi_loop("content.part", uuid="p2", **step, part={"type": "text", "text": "Using the review skill."}),
        kimi_loop("tool.call", uuid="t1", **step, toolCallId="tool_1", name="Skill", args={"skill": "review"}),
        kimi_loop("tool.result", parentUuid="t1", toolCallId="tool_1", result={"output": "Skill loaded."}),
        kimi_loop("step.end", uuid="s1", turnId="0", step=1, finishReason="tool_use"),
        {"type": "turn.steer", "agentId": "main", "input": [{"type": "text", "text": "Skill tool loaded instructions."}], "origin": {"kind": "system"}},
        kimi_loop("step.begin", uuid="s2", turnId="0", step=2),
        kimi_loop("content.part", uuid="p3", turnId="0", step=2, stepUuid="s2", part={"type": "text", "text": "The review is written."}),
        kimi_loop("step.end", uuid="s2", turnId="0", step=2, finishReason="stop"),
        {"type": "turn.ended", "agentId": "main", "turnId": 0, "reason": "completed"},
    ]


def write_jsonl(path, records, trailing_newline=True):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(json.dumps(r, ensure_ascii=False) for r in records)
    if trailing_newline:
        text += "\n"
    path.write_text(text, encoding="utf-8")
    return path


def append_jsonl(path, records, trailing_newline=True):
    text = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records)
    if not trailing_newline:
        text = text[:-1]
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(text)


def read_jsonl(path):
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


class FakeRunner:
    """Stands in for run_upstream: records calls, returns canned stdout."""

    def __init__(self, stdout="", rc=0):
        self.calls = []
        self.stdout = stdout
        self.rc = rc

    def __call__(self, cfg, script, payload_text, env, cwd):
        self.calls.append({"script": script, "payload": json.loads(payload_text), "env": env, "cwd": cwd})
        return bridge.UpstreamResult(rc=self.rc, stdout=self.stdout, stderr="", elapsed_ms=1)


def base_env(tmp, host_dirs=True):
    env = {
        "USERPROFILE": str(Path(tmp) / "home"),
        "REMEMBER_BRIDGE_PLUGIN_ROOT": str(Path(tmp) / "plugin"),
        "REMEMBER_BRIDGE_ROOT": str(Path(tmp) / "bridge"),
        "REMEMBER_BRIDGE_BASH": str(Path(tmp) / "fake-bash.exe"),
        "GROK_HOME": str(Path(tmp) / "grok"),
        "KIMI_CODE_HOME": str(Path(tmp) / "kimi"),
    }
    (Path(tmp) / "home").mkdir(exist_ok=True)
    (Path(tmp) / "plugin" / "scripts").mkdir(parents=True, exist_ok=True)
    for name in bridge.HOOK_SCRIPTS.values():
        if name:
            (Path(tmp) / "plugin" / "scripts" / name).write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
    (Path(tmp) / "fake-bash.exe").write_text("", encoding="utf-8")
    return env


def run_main(argv, stdin_obj, env, runner):
    out = io.StringIO()
    err = io.StringIO()
    stdin = io.StringIO(json.dumps(stdin_obj) if isinstance(stdin_obj, dict) else stdin_obj)
    rc = bridge.main(argv, stdin=stdin, stdout=out, stderr=err, env=env, runner=runner)
    return rc, out.getvalue(), err.getvalue()


# ── payload normalisation ────────────────────────────────────────────────────

class PayloadTests(unittest.TestCase):
    def test_camel_case_keys_become_snake_case(self):
        payload = bridge.normalize_payload({"hookEventName": "pre_tool_use", "sessionId": GROK_SID, "workspaceRoot": "D:\\x", "toolUseId": "t"})
        self.assertEqual(payload["hook_event_name"], "pre_tool_use")
        self.assertEqual(payload["session_id"], GROK_SID)
        self.assertEqual(payload["workspace_root"], "D:\\x")
        self.assertEqual(payload["tool_use_id"], "t")

    def test_snake_case_keys_are_kept(self):
        payload = bridge.normalize_payload({"hook_event_name": "SessionStart", "session_id": KIMI_SID, "cwd": "/p"})
        self.assertEqual(payload["hook_event_name"], "SessionStart")
        self.assertEqual(payload["cwd"], "/p")

    def test_kimi_session_prefix_is_stripped_and_kept_raw(self):
        payload = bridge.normalize_payload({"session_id": KIMI_SID})
        self.assertEqual(payload["session_id"], KIMI_UUID)
        self.assertEqual(payload["raw_session_id"], KIMI_SID)

    def test_session_id_is_lower_cased(self):
        payload = bridge.normalize_payload({"sessionId": GROK_SID.upper()})
        self.assertEqual(payload["session_id"], GROK_SID)

    def test_session_id_gate_matches_remember(self):
        self.assertTrue(bridge.valid_session_id(GROK_SID))
        self.assertTrue(bridge.valid_session_id(KIMI_UUID))
        self.assertFalse(bridge.valid_session_id("session_abc"))
        self.assertFalse(bridge.valid_session_id("../etc"))
        self.assertFalse(bridge.valid_session_id(""))
        self.assertFalse(bridge.valid_session_id("-abc"))
        self.assertFalse(bridge.valid_session_id("ABCDEF"))

    def test_non_dict_payload_is_empty(self):
        self.assertEqual(bridge.normalize_payload(["x"]), {})
        self.assertEqual(bridge.parse_payload(""), {})
        self.assertEqual(bridge.parse_payload("not json"), {})

    def test_project_dir_prefers_cwd_then_workspace_then_env(self):
        self.assertEqual(bridge.project_dir_from({"cwd": "D:\\a\\b\\"}, {}), "D:/a/b")
        self.assertEqual(bridge.project_dir_from({"workspace_root": "D:\\w"}, {}), "D:/w")
        self.assertEqual(bridge.project_dir_from({}, {"CLAUDE_PROJECT_DIR": "D:\\e"}), "D:/e")
        self.assertIsNone(bridge.project_dir_from({}, {}))
        self.assertEqual(bridge.project_dir_from({"cwd": "D:/"}, {}), "D:/")


# ── slug parity ──────────────────────────────────────────────────────────────

class SlugTests(unittest.TestCase):
    def test_known_slugs(self):
        self.assertEqual(bridge.session_dir_slug("D:/Development/AI-related"), "d--Development-AI-related")
        self.assertEqual(bridge.session_dir_slug("D:\\Development\\AI-related\\.research\\remember-acceptance"), "d--Development-AI-related--research-remember-acceptance")
        self.assertEqual(bridge.session_dir_slug("/Users/x/proj"), "-Users-x-proj")

    def test_astral_characters_cost_two_dashes(self):
        self.assertEqual(bridge.session_dir_slug("D:/a\U0001F600b"), "d--a--b")

    def test_long_paths_are_truncated_with_hash(self):
        path = "D:/" + "x" * 250
        slug = bridge.session_dir_slug(path)
        self.assertEqual(len(slug.split("-")[-1]) > 0, True)
        self.assertTrue(slug.startswith("d--" + "x" * 197))
        self.assertLess(len(slug), 220)

    @unittest.skipUnless(HAVE_PLUGIN, "pinned Remember checkout not present")
    def test_parity_with_pinned_pipeline_slug(self):
        spec = importlib.util.spec_from_file_location("remember_slug", PLUGIN_ROOT / "pipeline" / "slug.py")
        upstream = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(upstream)
        for path in ("D:/Development/AI-related", "D:\\DevHome", "/tmp/x y", "D:/" + "y" * 300, "D:/proj-\u00e9-\U0001F600", "c:/lower"):
            self.assertEqual(bridge.session_dir_slug(path), upstream.session_dir_slug(path), path)


# ── translators ──────────────────────────────────────────────────────────────

class GrokTranslatorTests(unittest.TestCase):
    def translate_all(self, lines):
        translator = bridge.GrokTranslator()
        out = []
        for obj in lines:
            out.extend(translator.translate(obj))
        out.extend(translator.flush())
        return out, translator

    def test_scaffolding_is_dropped_and_prompts_are_unwrapped(self):
        records, _ = self.translate_all(grok_lines())
        humans = [r for r in records if r["type"] == "user"]
        self.assertEqual([r["message"]["content"][0]["text"] for r in humans], ["what do these settings do", "my terminals"])
        for record in records:
            self.assertIsInstance(record["message"], dict)
            self.assertIn(record["type"], ("user", "assistant"))
            self.assertEqual(record["message"]["role"], record["type"])

    def test_assistant_text_and_tool_calls_become_claude_blocks(self):
        records, _ = self.translate_all(grok_lines())
        agents = [r for r in records if r["type"] == "assistant"]
        self.assertEqual(len(agents), 2)
        blocks = agents[0]["message"]["content"]
        self.assertEqual(blocks[0], {"type": "text", "text": "I'll look those up."})
        self.assertEqual(blocks[1]["type"], "tool_use")
        self.assertEqual(blocks[1]["name"], "read_file")
        self.assertEqual(blocks[1]["input"], {"target_file": "C:\\Users\\x\\SKILL.md", "limit": 80})
        self.assertEqual(agents[1]["message"]["content"], [{"type": "text", "text": "Both settings control paste trimming."}])

    def test_unknown_record_types_are_counted_not_fatal(self):
        records, translator = self.translate_all([{"type": "mystery", "content": "x"}, {"no": "type"}])
        self.assertEqual(records, [])
        self.assertEqual(translator.unknown, {"mystery": 1, "<none>": 1})

    def test_grok_translator_is_always_idle(self):
        translator = bridge.GrokTranslator()
        translator.translate(grok_lines()[6])
        self.assertTrue(translator.idle())


class KimiTranslatorTests(unittest.TestCase):
    def translate_all(self, lines):
        translator = bridge.KimiTranslator()
        out = []
        for obj in lines:
            out.extend(translator.translate(obj))
        return out, translator

    def test_user_prompts_come_from_turn_prompt_only(self):
        records, _ = self.translate_all(kimi_lines())
        humans = [r for r in records if r["type"] == "user"]
        self.assertEqual([r["message"]["content"][0]["text"] for r in humans], ["Review the earlier work"])

    def test_assistant_steps_are_flushed_at_step_end_without_think_parts(self):
        records, _ = self.translate_all(kimi_lines())
        agents = [r for r in records if r["type"] == "assistant"]
        self.assertEqual(len(agents), 2)
        first = agents[0]["message"]["content"]
        self.assertEqual(first[0], {"type": "text", "text": "Using the review skill."})
        self.assertEqual(first[1]["type"], "tool_use")
        self.assertEqual(first[1]["name"], "Skill")
        self.assertEqual(first[1]["input"], {"skill": "review"})
        self.assertNotIn("think", json.dumps(first))
        self.assertEqual(agents[1]["message"]["content"], [{"type": "text", "text": "The review is written."}])

    def test_translator_reports_open_step(self):
        translator = bridge.KimiTranslator()
        lines = kimi_lines()
        for obj in lines[:7]:
            translator.translate(obj)
        self.assertFalse(translator.idle())
        for obj in lines[7:11]:
            translator.translate(obj)
        self.assertTrue(translator.idle())

    def test_turn_ended_flushes_an_interrupted_step(self):
        translator = bridge.KimiTranslator()
        out = []
        for obj in [kimi_loop("step.begin", uuid="s9", turnId="1", step=1), kimi_loop("content.part", uuid="p9", turnId="1", step=1, stepUuid="s9", part={"type": "text", "text": "partial answer"}), {"type": "turn.ended", "agentId": "main", "turnId": 1, "reason": "aborted"}]:
            out.extend(translator.translate(obj))
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["message"]["content"], [{"type": "text", "text": "partial answer"}])
        self.assertTrue(translator.idle())

    def test_sub_agent_events_are_ignored(self):
        translator = bridge.KimiTranslator()
        out = translator.translate({"type": "turn.prompt", "agentId": "agent-0", "input": [{"type": "text", "text": "sub task"}], "origin": {"kind": "user"}})
        self.assertEqual(out, [])


# ── incremental mirroring ────────────────────────────────────────────────────

class MirrorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_grok_mirror_is_incremental_and_defers_partial_lines(self):
        native = write_jsonl(self.root / "chat_history.jsonl", grok_lines()[:7])
        mirror = self.root / "mirror" / f"{GROK_SID}.jsonl"
        state = self.root / "state" / f"{GROK_SID}.json"
        first = bridge.mirror_transcript("grok", str(native), str(mirror), str(state), GROK_SID)
        self.assertEqual(first.new_records, 2)
        self.assertEqual(len(read_jsonl(mirror)), 2)
        append_jsonl(native, grok_lines()[7:9])
        append_jsonl(native, [grok_lines()[9]], trailing_newline=False)
        second = bridge.mirror_transcript("grok", str(native), str(mirror), str(state), GROK_SID)
        self.assertEqual(second.new_records, 1)
        self.assertEqual(len(read_jsonl(mirror)), 3)
        with open(native, "a", encoding="utf-8") as handle:
            handle.write("\n")
        third = bridge.mirror_transcript("grok", str(native), str(mirror), str(state), GROK_SID)
        self.assertEqual(third.new_records, 1)
        records = read_jsonl(mirror)
        self.assertEqual(len(records), 4)
        self.assertEqual(records[-1]["message"]["content"][0]["text"], "Both settings control paste trimming.")
        saved = json.loads(state.read_text(encoding="utf-8"))
        self.assertEqual(saved["offset"], native.stat().st_size)

    def test_kimi_mirror_reprocesses_an_open_step_next_time(self):
        lines = kimi_lines()
        native = write_jsonl(self.root / "wire.jsonl", lines[:8])
        mirror = self.root / "mirror" / f"{KIMI_UUID}.jsonl"
        state = self.root / "state" / f"{KIMI_UUID}.json"
        first = bridge.mirror_transcript("kimi", str(native), str(mirror), str(state), KIMI_UUID)
        self.assertEqual(first.new_records, 1)
        saved = json.loads(state.read_text(encoding="utf-8"))
        self.assertLess(saved["offset"], native.stat().st_size, "offset must stop before the open step")
        append_jsonl(native, lines[8:])
        second = bridge.mirror_transcript("kimi", str(native), str(mirror), str(state), KIMI_UUID)
        self.assertEqual(second.new_records, 2)
        records = read_jsonl(mirror)
        self.assertEqual([r["type"] for r in records], ["user", "assistant", "assistant"])

    def test_mirror_records_carry_session_id_and_sniff_as_claude_code(self):
        native = write_jsonl(self.root / "chat_history.jsonl", grok_lines())
        mirror = self.root / "mirror" / f"{GROK_SID}.jsonl"
        bridge.mirror_transcript("grok", str(native), str(mirror), str(state := self.root / "s.json"), GROK_SID)
        for record in read_jsonl(mirror):
            self.assertEqual(record["sessionId"], GROK_SID)
            self.assertTrue(isinstance(record.get("message"), dict) or record.get("type") in ("user", "assistant"))

    def test_mirror_without_trailing_newline_is_repaired_before_append(self):
        native = write_jsonl(self.root / "chat_history.jsonl", grok_lines()[:4])
        mirror = self.root / "mirror" / f"{GROK_SID}.jsonl"
        state = self.root / "state.json"
        bridge.mirror_transcript("grok", str(native), str(mirror), str(state), GROK_SID)
        with open(mirror, "a", encoding="utf-8") as handle:
            handle.write('{"type": "user", "message": {"role": "user", "content": "torn')
        append_jsonl(native, grok_lines()[4:7])
        bridge.mirror_transcript("grok", str(native), str(mirror), str(state), GROK_SID)
        text = mirror.read_text(encoding="utf-8")
        good = [line for line in text.splitlines() if line.strip()]
        parsed = 0
        for line in good:
            try:
                json.loads(line)
                parsed += 1
            except json.JSONDecodeError:
                pass
        self.assertEqual(parsed, 2, "the torn line stays torn on its own line; the new record parses")

    def test_missing_native_transcript_is_reported_not_raised(self):
        result = bridge.mirror_transcript("grok", str(self.root / "nope.jsonl"), str(self.root / "m.jsonl"), str(self.root / "s.json"), GROK_SID)
        self.assertEqual(result.new_records, 0)
        self.assertIn("missing", result.note)


# ── transcript location ──────────────────────────────────────────────────────

class TranscriptLocationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_grok_transcript_is_found_by_session_id_regardless_of_cwd_encoding(self):
        home = self.root / "grok"
        path = write_jsonl(home / "sessions" / "D%3A%5CDevHome" / GROK_SID / "chat_history.jsonl", [])
        self.assertEqual(Path(bridge.grok_transcript(str(home), GROK_SID, "D:/DevHome")), path)
        self.assertIsNone(bridge.grok_transcript(str(home), "ffffffff-0000-0000-0000-000000000000", "D:/DevHome"))

    def test_grok_transcript_prefers_the_directory_matching_cwd(self):
        home = self.root / "grok"
        other = write_jsonl(home / "sessions" / "D%3A%5COther" / GROK_SID / "chat_history.jsonl", [])
        wanted = write_jsonl(home / "sessions" / "D%3A%5CDevHome" / GROK_SID / "chat_history.jsonl", [])
        self.assertEqual(Path(bridge.grok_transcript(str(home), GROK_SID, "D:\\DevHome")), wanted)
        self.assertIn(Path(bridge.grok_transcript(str(home), GROK_SID, "D:/Elsewhere")), (other, wanted))

    def test_kimi_transcript_via_session_index_then_glob(self):
        home = self.root / "kimi"
        session_dir = home / "sessions" / "wd_work_aa1e3f8c9c18" / KIMI_SID
        wire = write_jsonl(session_dir / "agents" / "main" / "wire.jsonl", [])
        write_jsonl(session_dir / "agents" / "agent-0" / "wire.jsonl", [])
        index = home / "session_index.jsonl"
        index.parent.mkdir(parents=True, exist_ok=True)
        index.write_text(
            json.dumps({"sessionId": "session_other", "sessionDir": "D:/nowhere", "workDir": "D:/x"}) + "\n"
            + json.dumps({"sessionId": KIMI_SID, "sessionDir": str(session_dir).replace("\\", "/"), "workDir": "D:/Development/Thermals/SQ-control/work"}) + "\n",
            encoding="utf-8",
        )
        self.assertEqual(Path(bridge.kimi_transcript(str(home), KIMI_SID)), wire)
        index.unlink()
        self.assertEqual(Path(bridge.kimi_transcript(str(home), KIMI_SID)), wire)
        self.assertIsNone(bridge.kimi_transcript(str(home), "session_missing"))


# ── configuration ────────────────────────────────────────────────────────────

class ConfigTests(unittest.TestCase):
    def test_bash_resolution_order(self):
        exists = lambda p: p in {"E:/custom/bash.exe", bridge.GIT_BASH}
        cfg = bridge.BridgeConfig.from_env({"REMEMBER_BRIDGE_BASH": "E:/custom/bash.exe", "USERPROFILE": "C:/Users/u"}, exists=exists, which=lambda n: "P:/bash.exe")
        self.assertEqual(cfg.bash, "E:/custom/bash.exe")
        cfg = bridge.BridgeConfig.from_env({"USERPROFILE": "C:/Users/u"}, exists=exists, which=lambda n: "P:/bash.exe")
        self.assertEqual(cfg.bash, bridge.GIT_BASH)
        cfg = bridge.BridgeConfig.from_env({"USERPROFILE": "C:/Users/u"}, exists=lambda p: False, which=lambda n: "P:/bash.exe")
        self.assertEqual(cfg.bash, "P:/bash.exe")
        cfg = bridge.BridgeConfig.from_env({"USERPROFILE": "C:/Users/u"}, exists=lambda p: False, which=lambda n: None)
        self.assertIsNone(cfg.bash)

    def test_env_overrides_and_defaults(self):
        cfg = bridge.BridgeConfig.from_env({"USERPROFILE": "C:\\Users\\u"}, exists=lambda p: False, which=lambda n: None)
        self.assertEqual(cfg.plugin_root, bridge.DEFAULT_PLUGIN_ROOT)
        self.assertEqual(cfg.bridge_root, bridge.DEFAULT_BRIDGE_ROOT)
        self.assertEqual(cfg.home, "C:/Users/u")
        self.assertEqual(cfg.grok_home, "C:/Users/u/.grok")
        self.assertEqual(cfg.kimi_home, "C:/Users/u/.kimi-code")
        cfg = bridge.BridgeConfig.from_env({"HOME": "/h", "GROK_HOME": "D:\\g", "KIMI_CODE_HOME": "D:/k", "REMEMBER_BRIDGE_ROOT": "D:/b", "REMEMBER_BRIDGE_PLUGIN_ROOT": "D:/p"}, exists=lambda p: False, which=lambda n: None)
        self.assertEqual((cfg.home, cfg.grok_home, cfg.kimi_home, cfg.bridge_root, cfg.plugin_root), ("/h", "D:/g", "D:/k", "D:/b", "D:/p"))

    def test_upstream_env_sets_the_claude_shaped_variables(self):
        cfg = bridge.BridgeConfig.from_env({"USERPROFILE": "C:/Users/u", "PATH": "x"}, exists=lambda p: False, which=lambda n: None)
        env = bridge.upstream_env(cfg, "grok", "D:/proj", {"PATH": "x", "USERPROFILE": "C:/Users/u", "REMEMBER_TRANSCRIPT_PATH": "ambient"})
        self.assertEqual(env["CLAUDE_PLUGIN_ROOT"], cfg.plugin_root)
        self.assertEqual(env["PLUGIN_ROOT"], cfg.plugin_root)
        self.assertEqual(env["CLAUDE_PROJECT_DIR"], "D:/proj")
        self.assertEqual(env["CLAUDE_CONFIG_DIR"], cfg.bridge_root + "/grok")
        self.assertEqual(env["HOME"], "C:/Users/u")
        self.assertNotIn("REMEMBER_TRANSCRIPT_PATH", env)
        self.assertNotIn("REMEMBER_SUMMARIZER", env)
        env = bridge.upstream_env(cfg, "kimi", "D:/proj", {"HOME": "/keep"})
        self.assertEqual(env["HOME"], "/keep")

    def test_bare_invocation_prints_configuration(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = base_env(tmp)
            out = io.StringIO()
            rc = bridge.main([], stdin=io.StringIO(""), stdout=out, stderr=io.StringIO(), env=env, runner=FakeRunner())
            self.assertEqual(rc, 0)
            text = out.getvalue()
            for key in ("plugin_root", "bridge_root", "bash", "grok_home", "kimi_home", "remember_config"):
                self.assertIn(key, text)
            self.assertIn(env["REMEMBER_BRIDGE_PLUGIN_ROOT"].replace("\\", "/"), text)


# ── event flow through main() ────────────────────────────────────────────────

class EventFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.env = base_env(self.tmp.name)
        self.project = self.root / "proj"
        self.project.mkdir()
        self.grok_native = write_jsonl(self.root / "grok" / "sessions" / "D%3A%5Cproj" / GROK_SID / "chat_history.jsonl", grok_lines())
        self.kimi_native = write_jsonl(self.root / "kimi" / "sessions" / "wd_proj_1" / KIMI_SID / "agents" / "main" / "wire.jsonl", kimi_lines())

    def tearDown(self):
        self.tmp.cleanup()

    def grok_payload(self, event, **extra):
        payload = {"hookEventName": event, "sessionId": GROK_SID, "cwd": str(self.project), "workspaceRoot": str(self.project), "timestamp": "2026-09-05T12:00:00Z", "permissionMode": "default"}
        payload.update(extra)
        return payload

    def kimi_payload(self, event, **extra):
        payload = {"hook_event_name": event, "session_id": KIMI_SID, "cwd": str(self.project), "client_type": "kimi_code_cli"}
        payload.update(extra)
        return payload

    def mirror_path(self, host, sid):
        slug = bridge.session_dir_slug(str(self.project).replace("\\", "/"))
        return Path(self.env["REMEMBER_BRIDGE_ROOT"]) / host / "projects" / slug / f"{sid}.jsonl"

    def test_session_start_caches_upstream_stdout_and_prints_nothing(self):
        runner = FakeRunner(stdout="=== MEMORY ===\nremembered things\n")
        rc, out, _ = run_main(["--host", "grok", "--event", "SessionStart"], self.grok_payload("session_start"), self.env, runner)
        self.assertEqual(rc, 0)
        self.assertEqual(out, "")
        self.assertEqual(len(runner.calls), 1)
        call = runner.calls[0]
        self.assertTrue(call["script"].endswith("session-start-hook.sh"))
        self.assertEqual(call["payload"]["session_id"], GROK_SID)
        self.assertEqual(call["payload"]["cwd"], str(self.project).replace("\\", "/"))
        self.assertEqual(call["payload"]["hook_event_name"], "SessionStart")
        self.assertNotIn("transcript_path", call["payload"], "no mirror exists yet at session start")
        self.assertNotIn("\\", json.dumps(call["payload"]))
        cache = Path(self.env["REMEMBER_BRIDGE_ROOT"]) / "grok" / "inject" / f"{GROK_SID}.md"
        self.assertEqual(cache.read_text(encoding="utf-8"), "=== MEMORY ===\nremembered things\n")

    def test_grok_pre_tool_use_injects_exactly_once_without_upstream(self):
        runner = FakeRunner(stdout="block\n")
        run_main(["--host", "grok", "--event", "SessionStart"], self.grok_payload("session_start"), self.env, runner)
        rc, out, _ = run_main(["--host", "grok", "--event", "PreToolUse"], self.grok_payload("pre_tool_use", toolName="Bash"), self.env, runner)
        self.assertEqual(rc, 0)
        decoded = json.loads(out)
        self.assertEqual(decoded["hookSpecificOutput"]["hookEventName"], "PreToolUse")
        self.assertEqual(decoded["hookSpecificOutput"]["additionalContext"], "block\n")
        rc, out, _ = run_main(["--host", "grok", "--event", "PreToolUse"], self.grok_payload("pre_tool_use", toolName="Bash"), self.env, runner)
        self.assertEqual((rc, out), (0, ""))
        self.assertEqual(len(runner.calls), 1, "PreToolUse never calls upstream")

    def test_grok_injection_is_clipped(self):
        runner = FakeRunner(stdout="x" * 20000)
        run_main(["--host", "grok", "--event", "SessionStart"], self.grok_payload("session_start"), self.env, runner)
        _, out, _ = run_main(["--host", "grok", "--event", "PreToolUse"], self.grok_payload("pre_tool_use"), self.env, runner)
        context = json.loads(out)["hookSpecificOutput"]["additionalContext"]
        self.assertLessEqual(len(context), bridge.INJECT_CLIP)
        self.assertTrue(context.endswith(bridge.CLIP_MARKER))

    def test_kimi_user_prompt_prints_cache_then_upstream_once(self):
        runner = FakeRunner(stdout="=== MEMORY ===\nkimi memory\n")
        run_main(["--host", "kimi", "--event", "SessionStart"], self.kimi_payload("SessionStart", source="startup"), self.env, runner)
        self.assertEqual(runner.calls[0]["payload"]["source"], "startup")
        self.assertEqual(runner.calls[0]["payload"]["session_id"], KIMI_UUID)
        runner.stdout = "[12:00 CEST -- Sev]\n"
        rc, out, _ = run_main(["--host", "kimi", "--event", "UserPromptSubmit"], self.kimi_payload("UserPromptSubmit", prompt="hi"), self.env, runner)
        self.assertEqual(rc, 0)
        self.assertEqual(out, "=== MEMORY ===\nkimi memory\n[12:00 CEST -- Sev]\n")
        self.assertTrue(runner.calls[-1]["script"].endswith("user-prompt-hook.sh"))
        rc, out, _ = run_main(["--host", "kimi", "--event", "UserPromptSubmit"], self.kimi_payload("UserPromptSubmit", prompt="again"), self.env, runner)
        self.assertEqual(out, "[12:00 CEST -- Sev]\n")

    def test_kimi_pre_tool_use_is_a_no_op(self):
        runner = FakeRunner(stdout="never")
        rc, out, _ = run_main(["--host", "kimi", "--event", "PreToolUse"], self.kimi_payload("PreToolUse", tool_name="Bash"), self.env, runner)
        self.assertEqual((rc, out, runner.calls), (0, "", []))

    def test_post_tool_use_mirrors_then_calls_upstream_with_transcript_path(self):
        runner = FakeRunner()
        rc, out, _ = run_main(["--host", "grok", "--event", "PostToolUse"], self.grok_payload("post_tool_use", toolName="Bash"), self.env, runner)
        self.assertEqual((rc, out), (0, ""))
        mirror = self.mirror_path("grok", GROK_SID)
        self.assertTrue(mirror.exists())
        self.assertEqual(len(read_jsonl(mirror)), 4)
        call = runner.calls[0]
        self.assertTrue(call["script"].endswith("post-tool-hook.sh"))
        self.assertEqual(call["payload"]["transcript_path"], str(mirror).replace("\\", "/"))
        self.assertEqual(call["env"]["CLAUDE_CONFIG_DIR"], self.env["REMEMBER_BRIDGE_ROOT"].replace("\\", "/") + "/grok")
        self.assertEqual(call["cwd"], str(self.project).replace("\\", "/"))

    def test_kimi_session_end_mirrors_main_agent_and_passes_reason(self):
        runner = FakeRunner()
        rc, out, _ = run_main(["--host", "kimi", "--event", "SessionEnd"], self.kimi_payload("SessionEnd", reason="exit"), self.env, runner)
        self.assertEqual((rc, out), (0, ""))
        mirror = self.mirror_path("kimi", KIMI_UUID)
        self.assertEqual([r["type"] for r in read_jsonl(mirror)], ["user", "assistant", "assistant"])
        call = runner.calls[0]
        self.assertTrue(call["script"].endswith("session-end-hook.sh"))
        self.assertEqual(call["payload"]["reason"], "exit")
        self.assertEqual(call["payload"]["session_id"], KIMI_UUID)

    def test_invalid_session_id_skips_capture_but_not_session_start(self):
        runner = FakeRunner(stdout="mem")
        rc, _, _ = run_main(["--host", "kimi", "--event", "PostToolUse"], self.kimi_payload("PostToolUse", session_id="weird id"), self.env, runner)
        self.assertEqual((rc, runner.calls), (0, []))
        rc, _, _ = run_main(["--host", "kimi", "--event", "SessionStart"], self.kimi_payload("SessionStart", session_id="weird id"), self.env, runner)
        self.assertEqual(rc, 0)
        self.assertEqual(len(runner.calls), 1)
        self.assertNotIn("session_id", runner.calls[0]["payload"])

    def test_missing_native_transcript_still_calls_upstream(self):
        runner = FakeRunner()
        payload = self.grok_payload("session_end")
        payload["sessionId"] = "0199aaaa-0000-7000-8000-000000000001"
        rc, _, _ = run_main(["--host", "grok", "--event", "SessionEnd"], payload, self.env, runner)
        self.assertEqual(rc, 0)
        self.assertEqual(len(runner.calls), 1)
        self.assertNotIn("transcript_path", runner.calls[0]["payload"])

    def test_unknown_event_and_host_exit_zero(self):
        runner = FakeRunner()
        rc, out, err = run_main(["--host", "grok", "--event", "Stop"], self.grok_payload("stop"), self.env, runner)
        self.assertEqual((rc, out, runner.calls), (0, "", []))
        rc, out, err = run_main(["--host", "gemini", "--event", "SessionStart"], {}, self.env, runner)
        self.assertEqual((rc, out, runner.calls), (0, "", []))

    def test_bad_stdin_exits_zero(self):
        runner = FakeRunner()
        rc, out, _ = run_main(["--host", "grok", "--event", "PostToolUse"], "this is not json", self.env, runner)
        self.assertEqual((rc, out), (0, ""))

    def test_missing_bash_is_logged_not_fatal(self):
        env = dict(self.env)
        env["REMEMBER_BRIDGE_BASH"] = str(self.root / "no-such-bash.exe")
        env["PATH"] = str(self.root)
        rc, out, _ = run_main(["--host", "grok", "--event", "SessionStart"], self.grok_payload("session_start"), env, None)
        self.assertEqual((rc, out), (0, ""))
        log = (Path(env["REMEMBER_BRIDGE_ROOT"]) / "grok" / "logs" / "bridge.log").read_text(encoding="utf-8")
        self.assertIn("bash", log)

    def test_every_event_writes_one_bridge_log_line(self):
        runner = FakeRunner()
        run_main(["--host", "grok", "--event", "PostToolUse"], self.grok_payload("post_tool_use"), self.env, runner)
        run_main(["--host", "grok", "--event", "PreToolUse"], self.grok_payload("pre_tool_use"), self.env, runner)
        log = (Path(self.env["REMEMBER_BRIDGE_ROOT"]) / "grok" / "logs" / "bridge.log").read_text(encoding="utf-8")
        lines = [line for line in log.splitlines() if line.strip()]
        self.assertEqual(len(lines), 2)
        self.assertIn("event=PostToolUse", lines[0])
        self.assertIn("new_records=4", lines[0])
        self.assertIn("event=PreToolUse", lines[1])
        self.assertIn("injected=no", lines[1])

    def test_store_log_gets_the_same_line_when_config_resolves(self):
        home = Path(self.env["USERPROFILE"])
        (home / ".remember").mkdir(parents=True, exist_ok=True)
        store_root = self.root / "store"
        (home / ".remember" / "config.json").write_text(json.dumps({"data_dir": str(store_root).replace("\\", "/") + "/{slug}"}), encoding="utf-8")
        runner = FakeRunner()
        run_main(["--host", "grok", "--event", "PostToolUse"], self.grok_payload("post_tool_use"), self.env, runner)
        slug = bridge.session_dir_slug(str(self.project).replace("\\", "/"))
        logs = list((store_root / slug / "logs").glob("memory-*.log"))
        self.assertEqual(len(logs), 1)
        self.assertIn("[bridge]", logs[0].read_text(encoding="utf-8"))


# ── real bash: the bridge must not wait for a grandchild ─────────────────────

@unittest.skipUnless(HAVE_BASH, "Git Bash not available")
class GrandchildTests(unittest.TestCase):
    def test_upstream_runner_returns_when_the_direct_child_exits(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "fixture-hook.sh"
            script.write_text("#!/bin/bash\nread -r payload\necho \"hello ${payload}\"\n( sleep 8 ) </dev/null >/dev/null 2>&1 &\ndisown 2>/dev/null || true\nexit 0\n", encoding="utf-8")
            cfg = bridge.BridgeConfig.from_env({"USERPROFILE": tmp, "PATH": os.environ.get("PATH", "")})
            self.assertIsNotNone(cfg.bash)
            started = time.monotonic()
            result = bridge.run_upstream(cfg, str(script), "{}", dict(os.environ), None)
            elapsed = time.monotonic() - started
            self.assertEqual(result.rc, 0)
            self.assertEqual(result.stdout.strip(), "hello {}")
            self.assertLess(elapsed, 5.0, f"bridge waited {elapsed:.1f}s -- it must not wait for the grandchild")

    def test_upstream_runner_survives_a_grandchild_holding_stdout(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "fixture-hook.sh"
            script.write_text("#!/bin/bash\necho first\nsleep 6 &\nexit 0\n", encoding="utf-8")
            cfg = bridge.BridgeConfig.from_env({"USERPROFILE": tmp, "PATH": os.environ.get("PATH", "")})
            started = time.monotonic()
            result = bridge.run_upstream(cfg, str(script), "{}", dict(os.environ), None)
            elapsed = time.monotonic() - started
            self.assertEqual(result.stdout.strip(), "first")
            self.assertLess(elapsed, 4.0, f"a grandchild inheriting stdout must not block the bridge ({elapsed:.1f}s)")


# ── end-to-end against the pinned checkout ───────────────────────────────────

@unittest.skipUnless(HAVE_BASH and HAVE_PLUGIN, "needs Git Bash and the pinned Remember checkout")
class EndToEndTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.home = self.root / "home"
        (self.home / ".remember").mkdir(parents=True)
        self.store_root = self.root / "store"
        (self.home / ".remember" / "config.json").write_text(json.dumps({"data_dir": str(self.store_root).replace("\\", "/") + "/{slug}", "thresholds": {"min_human_messages": 1}}), encoding="utf-8")
        self.project = self.root / "proj"
        self.project.mkdir()
        self.env = {
            "PATH": os.environ.get("PATH", ""),
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", r"C:\Windows"),
            "TEMP": os.environ.get("TEMP", self.tmp.name),
            "TMP": os.environ.get("TMP", self.tmp.name),
            "USERPROFILE": str(self.home),
            "HOME": str(self.home).replace("\\", "/"),
            "REMEMBER_BRIDGE_PLUGIN_ROOT": str(PLUGIN_ROOT),
            "REMEMBER_BRIDGE_ROOT": str(self.root / "bridge"),
            "GROK_HOME": str(self.root / "grok"),
            "KIMI_CODE_HOME": str(self.root / "kimi"),
        }
        if GIT_BASH.exists():
            self.env["REMEMBER_BRIDGE_BASH"] = str(GIT_BASH)
        write_jsonl(self.root / "grok" / "sessions" / "D%3A%5Cproj" / GROK_SID / "chat_history.jsonl", grok_lines())

    def tearDown(self):
        self.tmp.cleanup()

    def store_log_text(self):
        slug = bridge.session_dir_slug(str(self.project).replace("\\", "/"))
        logs = sorted((self.store_root / slug / "logs").glob("memory-*.log"))
        return "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in logs)

    def test_pinned_pipeline_reads_the_mirror_as_claude_code(self):
        payload = {"hookEventName": "post_tool_use", "sessionId": GROK_SID, "cwd": str(self.project), "workspaceRoot": str(self.project), "toolName": "Bash"}
        out = io.StringIO()
        err = io.StringIO()
        rc = bridge.main(["--host", "grok", "--event", "PostToolUse"], stdin=io.StringIO(json.dumps(payload)), stdout=out, stderr=err, env=self.env)
        self.assertEqual(rc, 0, err.getvalue())
        slug = bridge.session_dir_slug(str(self.project).replace("\\", "/"))
        mirror = self.root / "bridge" / "grok" / "projects" / slug / f"{GROK_SID}.jsonl"
        self.assertTrue(mirror.exists())
        cfg = bridge.BridgeConfig.from_env(self.env)
        env = bridge.upstream_env(cfg, "grok", str(self.project).replace("\\", "/"), self.env)
        env["REMEMBER_TRANSCRIPT_PATH"] = str(mirror).replace("\\", "/")
        result = subprocess.run([cfg.bash, str(PLUGIN_ROOT / "scripts" / "save-session.sh"), GROK_SID, "--dry"], env=env, cwd=str(self.project), capture_output=True, text=True, timeout=120)
        log = self.store_log_text()
        self.assertIn("[extract] session " + GROK_SID, log, result.stderr + "\n" + log)
        self.assertIn("[extract] 4 exchanges (2 human)", log, log)
        self.assertNotIn("unrecognised", log)
        self.assertIn("[bridge]", log)
        self.assertTrue((self.store_root / slug).is_dir())


if __name__ == "__main__":
    unittest.main()
