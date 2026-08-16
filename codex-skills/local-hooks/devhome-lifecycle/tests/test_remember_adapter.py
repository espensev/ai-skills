import ctypes
import gc
import hashlib
import importlib.util
import json
import os
import re
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

HOOKS_ROOT = Path(__file__).resolve().parents[1] / "hooks"
MODULE_PATH = HOOKS_ROOT / "Invoke-RememberAdapter.py"
WRAPPER_PATH = HOOKS_ROOT / "Invoke-RememberClaude.cmd"
MODULE_EXISTS = MODULE_PATH.exists()
adapter = None
if MODULE_EXISTS:
    module_spec = importlib.util.spec_from_file_location("remember_adapter", MODULE_PATH)
    if module_spec is None or module_spec.loader is None:
        raise RuntimeError("unable to construct adapter import spec")
    adapter = importlib.util.module_from_spec(module_spec)
    sys.modules[module_spec.name] = adapter
    module_spec.loader.exec_module(adapter)

SYNC_API_EXISTS = all(
    hasattr(adapter, name)
    for name in ("AdapterLayout", "SyncResult", "sync_transcript", "session_lock")
)
BRIDGE_API_EXISTS = all(
    hasattr(adapter, name)
    for name in ("discover_remember_plugin", "invoke_upstream", "main")
)
CONTAINMENT_API_EXISTS = hasattr(adapter, "_run_contained_process")
ASYNC_STDIN_API_EXISTS = hasattr(adapter, "_PayloadWriter")
SCRIPT_NAMES = ("session-start-hook.sh", "user-prompt-hook.sh", "post-tool-hook.sh")


class BootstrapTests(unittest.TestCase):
    def test_production_adapter_exists(self):
        self.assertTrue(MODULE_EXISTS, "production adapter must exist")


def codex_record(payload_type: str, **fields: object) -> dict[str, object]:
    return {"type": "response_item", "payload": {"type": payload_type, **fields}}


def user_record(text: str) -> dict[str, object]:
    return codex_record("message", role="user", content=[{"type": "input_text", "text": text}])


def assistant_record(text: str) -> dict[str, object]:
    return codex_record("message", role="assistant", content=[{"type": "output_text", "text": text}])


def append_jsonl(path: Path, *records: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as stream:
        for record in records:
            stream.write(json.dumps(record, separators=(",", ":")).encode("utf-8") + b"\n")


def provider_cache_inventory(root: Path) -> dict[str, tuple[int, str]]:
    return {
        path.relative_to(root).as_posix(): (
            path.stat().st_size,
            hashlib.sha256(path.read_bytes()).hexdigest(),
        )
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def run_installed_remember_parser(
    plugin_root: Path, mirror_path: Path
) -> tuple[list[tuple[str, str]], dict[str, tuple[int, str]], dict[str, tuple[int, str]]]:
    before = provider_cache_inventory(plugin_root)
    program = (
        "import json, sys\n"
        "sys.path.insert(0, sys.argv[1])\n"
        "from pipeline.extract import extract_messages\n"
        "print(json.dumps(extract_messages(sys.argv[2]), separators=(',', ':')))\n"
    )
    completed = subprocess.run(
        [sys.executable, "-B", "-c", program, str(plugin_root), str(mirror_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
        check=True,
    )
    after = provider_cache_inventory(plugin_root)
    messages = [tuple(item) for item in json.loads(completed.stdout)]
    return messages, before, after


def test_checkpoint_integrity(checkpoint: dict[str, object]) -> str:
    canonical = {
        key: checkpoint[key]
        for key in (
            "schema_version",
            "source_path",
            "source_dev",
            "source_ino",
            "source_offset",
            "mirror_bytes",
            "mirror_lines",
            "mirror_dev",
            "mirror_ino",
            "mirror_size",
            "mirror_mtime_ns",
        )
    }
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def make_sync_fixture(testcase: unittest.TestCase):
    raw = testcase.enterContext(tempfile.TemporaryDirectory())
    codex_home = Path(raw) / "codex"
    source = codex_home / "sessions" / "2026" / "08" / "13" / "rollout-session-1.jsonl"
    source.parent.mkdir(parents=True)
    context = adapter.HookContext("PostToolUse", "session-1", Path(r"D:\Devtools"), source)
    return source, context, adapter.AdapterLayout.for_home(codex_home)


def make_fake_plugin(
    home: Path,
    version: str,
    complete: bool,
    body: str = "#!/bin/bash\nexit 0\n",
) -> Path:
    root = home / "plugins" / "cache" / "claude-plugins-official" / "remember" / version
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    count = len(SCRIPT_NAMES) if complete else len(SCRIPT_NAMES) - 1
    for name in SCRIPT_NAMES[:count]:
        (scripts / name).write_text(body, encoding="utf-8", newline="\n")
    return root


def make_echo_plugin(home: Path, version: str) -> Path:
    body = '#!/bin/bash\nprintf "%s\\n%s\\n" "$CLAUDE_CONFIG_DIR" "$CLAUDE_PROJECT_DIR" >&2\ncat\n'
    return make_fake_plugin(home, version, complete=True, body=body)


def process_fixture(testcase: unittest.TestCase, event: str = "PostToolUse"):
    raw = testcase.enterContext(tempfile.TemporaryDirectory())
    home = Path(raw) / "codex"
    source = home / "sessions" / "2026" / "08" / "13" / "rollout-session-1.jsonl"
    append_jsonl(source, user_record("smoke"))
    context = adapter.HookContext(event, "session-1", Path(r"D:\Devtools"), source)
    return home, context, adapter.AdapterLayout.for_home(home)


def hook_payload(context: object, prompt: str = "smoke") -> dict[str, object]:
    return {
        "hook_event_name": context.event,
        "session_id": context.session_id,
        "cwd": str(context.cwd),
        "transcript_path": str(context.transcript_path),
        "prompt": prompt,
        "tool_name": "shell_command",
        "tool_input": {},
        "tool_response": {},
        "tool_use_id": "tool-1",
        "turn_id": "turn-1",
        "model": "gpt-5",
        "permission_mode": "default",
    }


def stop_payload(context: object) -> dict[str, object]:
    return {
        "hook_event_name": "Stop",
        "session_id": context.session_id,
        "cwd": str(context.cwd),
        "transcript_path": str(context.transcript_path),
        "last_assistant_message": "private-stop-assistant",
        "turn_id": "private-stop-turn",
        "model": "private-stop-model",
        "permission_mode": "private-stop-permission",
        "stop_hook_active": False,
        "tool_input": {"private-stop-input": True},
        "tool_output": {"private-stop-output": True},
    }


def large_hook_payload(context: object) -> str:
    return json.dumps(hook_payload(context, "p" * (1024 * 1024 + 4096)))


def current_process_handle_count() -> int:
    kernel32 = ctypes.windll.kernel32
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    kernel32.GetProcessHandleCount.argtypes = (
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_ulong),
    )
    kernel32.GetProcessHandleCount.restype = ctypes.c_int
    value = ctypes.c_ulong()
    if not kernel32.GetProcessHandleCount(
        kernel32.GetCurrentProcess(), ctypes.byref(value)
    ):
        raise ctypes.WinError()
    return value.value


_HANDLE_ENVIRONMENT_STABILIZED = False


def stabilized_process_handle_count() -> int:
    """Let delayed ETW registration settle before taking leak baselines."""
    global _HANDLE_ENVIRONMENT_STABILIZED
    if not _HANDLE_ENVIRONMENT_STABILIZED:
        deadline = time.perf_counter() + 1.5
        while time.perf_counter() < deadline:
            time.sleep(0.05)
            current_process_handle_count()
        _HANDLE_ENVIRONMENT_STABILIZED = True
    return current_process_handle_count()


def run_adapter_process(testcase: unittest.TestCase, prompt: str, hook_exit: int):
    home, context, layout = process_fixture(testcase)
    body = f"#!/bin/bash\ncat >/dev/null\nexit {hook_exit}\n"
    make_fake_plugin(home, "0.20.0", complete=True, body=body)
    environment = os.environ.copy()
    environment["CODEX_HOME"] = str(home)
    completed = subprocess.run(
        [sys.executable, str(MODULE_PATH), "--event", context.event],
        input=json.dumps(hook_payload(context, prompt)),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=environment,
        timeout=10,
        check=False,
    )
    return completed, layout


def run_adapter_case(
    testcase: unittest.TestCase,
    *,
    hook_body: str = "#!/bin/bash\nexit 0\n",
    install_plugin: bool = True,
    cli_event: str = "PostToolUse",
    payload_event: str | None = None,
    stdin_text: str | None = None,
):
    home, context, layout = process_fixture(testcase, payload_event or cli_event)
    if install_plugin:
        make_fake_plugin(home, "0.20.0", complete=True, body=hook_body)
    environment = os.environ.copy()
    environment["CODEX_HOME"] = str(home)
    hook_input = stdin_text if stdin_text is not None else json.dumps(hook_payload(context))
    started = time.perf_counter()
    completed = subprocess.run(
        [sys.executable, str(MODULE_PATH), "--event", cli_event],
        input=hook_input,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=environment,
        timeout=10,
        check=False,
    )
    return completed, layout, context, time.perf_counter() - started


def native_git_bash_path(value: str) -> Path:
    match = re.fullmatch(r"/([A-Za-z])(?:/(.*))?", value)
    if match is None:
        return Path(value)
    suffix = (match.group(2) or "").replace("/", "\\")
    return Path(f"{match.group(1).upper()}:\\{suffix}")


def make_descendant_hook(heartbeat: Path, root_exits: bool) -> str:
    root_action = "exit 0" if root_exits else 'while [ "$SECONDS" -lt 8 ]; do :; done'
    return f'''#!/bin/bash
(
  (
    while [ "$SECONDS" -lt 8 ]; do
      printf x >> "{heartbeat.as_posix()}"
      sleep 0.02
    done
  ) &
  wait
) &
{root_action}
'''


@unittest.skipUnless(MODULE_EXISTS, "production adapter is not installed yet")
class TranslationTests(unittest.TestCase):
    def test_user_and_assistant_text_become_claude_messages(self):
        user = codex_record("message", role="user", content=[{"type": "input_text", "text": "remember this"}])
        assistant = codex_record("message", role="assistant", content=[{"type": "output_text", "text": "noted"}])
        self.assertEqual(adapter.translate_record(user)[0]["type"], "user")
        self.assertEqual(adapter.translate_record(assistant)[0]["message"]["content"][0]["text"], "noted")

    def test_private_record_types_are_omitted(self):
        records = [
            codex_record("message", role="developer", content=[{"type": "input_text", "text": "secret policy"}]),
            codex_record("reasoning", summary=[{"type": "summary_text", "text": "hidden"}]),
            codex_record("function_call_output", output="private output"),
            {"type": "event_msg", "payload": {"type": "agent_message", "message": "duplicate"}},
        ]
        self.assertEqual([adapter.translate_record(item) for item in records], [[], [], [], []])

    def test_tool_calls_retain_only_identity_and_name(self):
        record = codex_record("function_call", name="shell_command", call_id="call-7", arguments='{"command":"token-value"}')
        block = adapter.translate_record(record)[0]["message"]["content"][0]
        self.assertEqual(block, {"type": "tool_use", "id": "call-7", "name": "shell_command", "input": {}})
        self.assertNotIn("token-value", json.dumps(block))

    def test_empty_text_blocks_are_omitted_without_reordering_nonempty_text(self):
        mixed = codex_record(
            "message",
            role="user",
            content=[
                {"type": "input_text", "text": ""},
                {"type": "input_text", "text": "first"},
                {"type": "input_text", "text": " "},
                {"type": "input_text", "text": ""},
                {"type": "input_text", "text": "second"},
            ],
        )
        all_empty = codex_record(
            "message",
            role="assistant",
            content=[
                {"type": "output_text", "text": ""},
                {"type": "output_text", "text": ""},
            ],
        )

        translated = adapter.translate_record(mixed)
        self.assertEqual(
            [block["text"] for block in translated[0]["message"]["content"]],
            ["first", " ", "second"],
        )
        self.assertEqual(adapter.translate_record(all_empty), [])


@unittest.skipUnless(MODULE_EXISTS, "production adapter is not installed yet")
class ValidationTests(unittest.TestCase):
    def test_missing_session_start_source_is_permitted(self):
        with tempfile.TemporaryDirectory() as raw:
            codex_home = Path(raw)
            missing = codex_home / "sessions" / "2026" / "08" / "13" / "missing.jsonl"
            payload = {"hook_event_name": "SessionStart", "session_id": "session-1", "cwd": r"D:\Devtools", "transcript_path": str(missing)}
            self.assertIsNotNone(adapter.validate_hook_payload(payload, "SessionStart", codex_home))

    def test_existing_session_start_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            codex_home = Path(raw)
            directory = codex_home / "sessions" / "2026" / "08" / "13" / "not-a-transcript"
            directory.mkdir(parents=True)
            payload = {
                "hook_event_name": "SessionStart",
                "session_id": "session-1",
                "cwd": r"D:\Devtools",
                "transcript_path": str(directory),
            }
            self.assertIsNone(adapter.validate_hook_payload(payload, "SessionStart", codex_home))

    def test_valid_payload_is_confined_to_codex_sessions(self):
        with tempfile.TemporaryDirectory() as raw:
            codex_home = Path(raw)
            source = codex_home / "sessions" / "2026" / "08" / "13" / "rollout-session-1.jsonl"
            source.parent.mkdir(parents=True)
            payload = {"hook_event_name": "SessionStart", "session_id": "session-1", "cwd": r"D:\Devtools", "transcript_path": str(source)}
            context = adapter.validate_hook_payload(payload, "SessionStart", codex_home)
            self.assertEqual(context.session_id, "session-1")
            self.assertEqual(adapter.slug_project(context.cwd), "d--Devtools")

    def test_escape_path_and_invalid_session_id_are_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            codex_home = Path(raw)
            outside = codex_home.parent / "outside.jsonl"
            bad_path = {"hook_event_name": "PostToolUse", "session_id": "safe", "cwd": r"D:\Devtools", "transcript_path": str(outside)}
            bad_id = dict(bad_path, transcript_path=str(codex_home / "sessions" / "x.jsonl"), session_id="../escape")
            self.assertIsNone(adapter.validate_hook_payload(bad_path, "PostToolUse", codex_home))
            self.assertIsNone(adapter.validate_hook_payload(bad_id, "PostToolUse", codex_home))

    def test_absolute_windows_cwd_is_preserved(self):
        with tempfile.TemporaryDirectory() as raw:
            codex_home = Path(raw)
            source = codex_home / "sessions" / "2026" / "08" / "14" / "rollout.jsonl"
            append_jsonl(source, user_record("cwd validation"))
            for cwd in (r"D:\Devtools", r"\\server\share\project"):
                with self.subTest(cwd=cwd):
                    payload = {
                        "hook_event_name": "Stop",
                        "session_id": "session-1",
                        "cwd": cwd,
                        "transcript_path": str(source),
                    }
                    context = adapter.validate_hook_payload(payload, "Stop", codex_home)
                    self.assertIsNotNone(context)
                    self.assertEqual(str(context.cwd), cwd)


class SyncApiTests(unittest.TestCase):
    def test_sync_api_exists(self):
        self.assertTrue(SYNC_API_EXISTS, "incremental sync API must exist")


class BridgeApiTests(unittest.TestCase):
    def test_bridge_api_and_wrapper_exist(self):
        self.assertTrue(BRIDGE_API_EXISTS, "Remember process bridge API must exist")
        self.assertTrue(WRAPPER_PATH.exists(), "Claude wrapper must exist")

    def test_handle_owned_containment_api_exists(self):
        self.assertTrue(
            CONTAINMENT_API_EXISTS,
            "race-free Windows Job Object containment API must exist",
        )

    def test_bounded_async_stdin_api_exists(self):
        self.assertTrue(
            ASYNC_STDIN_API_EXISTS,
            "bounded asynchronous stdin delivery API must exist",
        )


@unittest.skipUnless(BRIDGE_API_EXISTS, "Remember process bridge is not installed yet")
class BridgeTests(unittest.TestCase):
    def test_stop_process_syncs_final_assistant_and_sanitizes_upstream_payload(self):
        home, context, layout = process_fixture(self, "Stop")
        final_text = "durable-final-assistant"
        append_jsonl(context.transcript_path, assistant_record(final_text))
        make_fake_plugin(
            home,
            "0.20.0",
            complete=True,
            body="#!/bin/bash\ncat\n",
        )
        environment = os.environ.copy()
        environment["CODEX_HOME"] = str(home)
        raw_payload = json.dumps(stop_payload(context))
        completed = subprocess.run(
            [sys.executable, str(MODULE_PATH), "--event", context.event],
            input=raw_payload,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=environment,
            timeout=10,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(
            json.loads(completed.stdout),
            {
                "hook_event_name": "PostToolUse",
                "session_id": context.session_id,
                "cwd": str(context.cwd),
                "tool_name": "CodexStop",
                "tool_input": {},
                "tool_response": {},
            },
        )
        mirror_records = [
            json.loads(line)
            for line in layout.mirror_path(context).read_text(encoding="utf-8").splitlines()
        ]
        assistant_text = [
            block["text"]
            for record in mirror_records
            if record["type"] == "assistant"
            for block in record["message"]["content"]
            if block["type"] == "text"
        ]
        self.assertEqual(assistant_text, [final_text])
        for private_value in (
            final_text,
            "private-stop-assistant",
            "private-stop-turn",
            "private-stop-model",
            "private-stop-permission",
            "private-stop-input",
            "private-stop-output",
            "transcript_path",
            "last_assistant_message",
            "stop_hook_active",
        ):
            self.assertNotIn(private_value, completed.stdout)

    def test_existing_events_forward_original_payload_unchanged(self):
        for event in ("SessionStart", "UserPromptSubmit", "PostToolUse"):
            with self.subTest(event=event):
                home, context, _ = process_fixture(self, event)
                make_fake_plugin(
                    home,
                    "0.20.0",
                    complete=True,
                    body="#!/bin/bash\ncat\n",
                )
                environment = os.environ.copy()
                environment["CODEX_HOME"] = str(home)
                raw_payload = json.dumps(hook_payload(context), indent=2)
                completed = subprocess.run(
                    [sys.executable, str(MODULE_PATH), "--event", event],
                    input=raw_payload,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    env=environment,
                    timeout=10,
                    check=False,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertEqual(completed.stdout, raw_payload)

    def test_invalid_stop_transcript_paths_fail_open(self):
        for label in ("null", "outside"):
            with self.subTest(label=label):
                home, context, layout = process_fixture(self, "Stop")
                make_fake_plugin(home, "0.20.0", complete=True)
                payload = stop_payload(context)
                payload["transcript_path"] = (
                    None if label == "null" else str(home.parent / "outside.jsonl")
                )
                environment = os.environ.copy()
                environment["CODEX_HOME"] = str(home)
                completed = subprocess.run(
                    [sys.executable, str(MODULE_PATH), "--event", "Stop"],
                    input=json.dumps(payload),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    env=environment,
                    timeout=10,
                    check=False,
                )
                self.assertEqual(
                    (completed.returncode, completed.stdout.strip(), completed.stderr),
                    (0, "{}", ""),
                )
                self.assertFalse(layout.mirror_path(context).exists())

    def test_stop_rejects_nonabsolute_native_cwd_before_sync_and_upstream(self):
        for cwd in ("", ".", r"D:relative", r"relative\project"):
            with self.subTest(cwd=cwd):
                home, context, layout = process_fixture(self, "Stop")
                upstream_marker = home.parent / "upstream-invoked"
                hook_body = (
                    "#!/bin/bash\n"
                    f'printf invoked > "{upstream_marker.as_posix()}"\n'
                    "printf '{}\\n'\n"
                )
                make_fake_plugin(
                    home,
                    "0.20.0",
                    complete=True,
                    body=hook_body,
                )
                payload = stop_payload(context)
                payload["cwd"] = cwd
                environment = os.environ.copy()
                environment["CODEX_HOME"] = str(home)
                completed = subprocess.run(
                    [sys.executable, str(MODULE_PATH), "--event", "Stop"],
                    input=json.dumps(payload),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    env=environment,
                    timeout=10,
                    check=False,
                )
                self.assertEqual(
                    (completed.returncode, completed.stdout.strip(), completed.stderr),
                    (0, "{}", ""),
                )
                mirror_files = (
                    list(layout.claude_config.rglob("*.jsonl"))
                    if layout.claude_config.exists()
                    else []
                )
                self.assertEqual(
                    (
                        len(mirror_files),
                        (layout.checkpoints / f"{context.session_id}.json").exists(),
                        layout.claude_config.exists(),
                        upstream_marker.exists(),
                    ),
                    (0, False, False, False),
                )

    def test_stop_rejects_nonabsolute_transcript_before_resolve_sync_and_upstream(self):
        for case in ("empty", "dot", "drive-relative", "native-relative"):
            with self.subTest(case=case):
                home, context, layout = process_fixture(self, "Stop")
                transcript = {
                    "empty": "",
                    "dot": ".",
                    "drive-relative": (
                        f"{context.transcript_path.drive}{context.transcript_path.name}"
                    ),
                    "native-relative": context.transcript_path.name,
                }[case]
                upstream_marker = home.parent / "upstream-invoked"
                make_fake_plugin(
                    home,
                    "0.20.0",
                    complete=True,
                    body=(
                        "#!/bin/bash\n"
                        f'printf invoked > "{upstream_marker.as_posix()}"\n'
                        "printf '{}\\n'\n"
                    ),
                )
                payload = stop_payload(context)
                payload["transcript_path"] = transcript
                environment = os.environ.copy()
                environment["CODEX_HOME"] = str(home)
                completed = subprocess.run(
                    [sys.executable, str(MODULE_PATH), "--event", "Stop"],
                    input=json.dumps(payload),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    env=environment,
                    cwd=context.transcript_path.parent,
                    timeout=10,
                    check=False,
                )
                self.assertEqual(
                    (completed.returncode, completed.stdout.strip(), completed.stderr),
                    (0, "{}", ""),
                )
                mirror_files = (
                    list(layout.claude_config.rglob("*.jsonl"))
                    if layout.claude_config.exists()
                    else []
                )
                self.assertEqual(
                    (
                        len(mirror_files),
                        (layout.checkpoints / f"{context.session_id}.json").exists(),
                        layout.claude_config.exists(),
                        upstream_marker.exists(),
                    ),
                    (0, False, False, False),
                )

    def test_custom_tool_call_process_sync_keeps_only_identity_and_name(self):
        home, context, layout = process_fixture(self)
        append_jsonl(
            context.transcript_path,
            codex_record(
                "custom_tool_call",
                id="private-item-id",
                status="completed",
                call_id="custom-call-7",
                name="shell_command",
                input='{"command":"private-custom-input"}',
                namespace="private-namespace",
                internal_chat_message_metadata_passthrough={
                    "turn_id": "private-metadata"
                },
            ),
            codex_record(
                "custom_tool_call_output",
                call_id="custom-call-7",
                output="private-custom-output",
            ),
        )
        make_fake_plugin(home, "0.20.0", complete=True)
        environment = os.environ.copy()
        environment["CODEX_HOME"] = str(home)
        completed = subprocess.run(
            [sys.executable, str(MODULE_PATH), "--event", context.event],
            input=json.dumps(hook_payload(context)),
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=environment,
            timeout=10,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

        mirror_path = layout.mirror_path(context)
        mirror_records = [
            json.loads(line)
            for line in mirror_path.read_text(encoding="utf-8").splitlines()
        ]
        tool_blocks = [
            block
            for record in mirror_records
            for block in record["message"]["content"]
            if block["type"] == "tool_use"
        ]
        self.assertEqual(
            tool_blocks,
            [
                {
                    "type": "tool_use",
                    "id": "custom-call-7",
                    "name": "shell_command",
                    "input": {},
                }
            ],
        )
        serialized_mirror = json.dumps(mirror_records)
        for private_value in (
            "private-item-id",
            "completed",
            "private-custom-input",
            "private-namespace",
            "private-metadata",
            "private-custom-output",
        ):
            self.assertNotIn(private_value, serialized_mirror)

        actual_home = Path(os.environ.get("CODEX_HOME", r"D:\DevHome\state\codex"))
        plugin_root = adapter.discover_remember_plugin(actual_home)
        messages, cache_before, cache_after = run_installed_remember_parser(
            plugin_root, mirror_path
        )
        self.assertEqual(cache_after, cache_before)
        self.assertEqual(
            messages,
            [
                ("HUMAN", "smoke"),
                ("AGENT", "[TOOL: shell_command]"),
            ],
        )

    def test_discovery_selects_highest_complete_numeric_version(self):
        home = Path(self.enterContext(tempfile.TemporaryDirectory()))
        make_fake_plugin(home, "0.19.9", complete=True)
        make_fake_plugin(home, "0.20.0", complete=True)
        make_fake_plugin(home, "0.21.0", complete=False)
        self.assertEqual(adapter.discover_remember_plugin(home).name, "0.20.0")

    def test_real_git_bash_receives_private_environment_and_payload(self):
        home, context, layout = process_fixture(self)
        plugin = make_echo_plugin(home, "0.20.0")
        payload_text = json.dumps(hook_payload(context))
        result = adapter.invoke_upstream(context, layout, plugin, payload_text)
        self.assertEqual(json.loads(result.stdout)["session_id"], context.session_id)
        private_root, project_dir = result.stderr.splitlines()
        self.assertEqual(native_git_bash_path(private_root), layout.claude_config)
        self.assertEqual(native_git_bash_path(project_dir), context.cwd)

    def test_installed_post_tool_hook_bootstraps_capture_markers(self):
        raw = Path(self.enterContext(tempfile.TemporaryDirectory()))
        home = raw / "codex"
        user_home = raw / "home"
        project = raw / "project"
        project.mkdir()
        config_path = user_home / ".remember" / "config.json"
        config_path.parent.mkdir(parents=True)
        config_path.write_text(
            json.dumps({"thresholds": {"delta_lines_trigger": 1_000_000}}),
            encoding="utf-8",
        )
        fake_claude = user_home / ".local" / "bin" / "claude.exe"
        fake_claude.parent.mkdir(parents=True)
        fake_claude.write_bytes(b"must-not-run")
        source = home / "sessions" / "2026" / "08" / "14" / "rollout-probe.jsonl"
        context = adapter.HookContext(
            "PostToolUse",
            "11111111-2222-4333-8444-555555555555",
            project,
            source,
        )
        layout = adapter.AdapterLayout.for_home(home)
        append_jsonl(
            source,
            *(user_record(f"installed hook probe {index}") for index in range(60)),
        )
        adapter.sync_transcript(context, layout)

        actual_home = Path(os.environ.get("CODEX_HOME", r"D:\DevHome\state\codex"))
        plugin = adapter.discover_remember_plugin(actual_home)
        payload_text = json.dumps(hook_payload(context))
        with mock.patch.dict(
            os.environ,
            {"HOME": str(user_home), "USERPROFILE": str(user_home)},
            clear=False,
        ):
            for name in tuple(os.environ):
                if name == "REMEMBER_NESTED_SUMMARIZER" or name.startswith("_LIB_"):
                    os.environ.pop(name)
            result = adapter.invoke_upstream(context, layout, plugin, payload_text)

        self.assertEqual(result.returncode, 0, result.stderr)
        remember_tmp = project / ".remember" / "tmp"
        self.assertTrue((remember_tmp / "post-tool-ran").is_file(), result.stderr)
        self.assertTrue(
            (remember_tmp / "capture-alive.d" / context.session_id).is_file(),
            result.stderr,
        )
        self.assertEqual(
            (remember_tmp / "capture-alive").read_text(encoding="utf-8"),
            context.session_id,
        )
        time.sleep(0.2)
        self.assertFalse((remember_tmp / "save-session.pid").exists())
        self.assertFalse((remember_tmp / "last-save.json").exists())
        self.assertFalse((remember_tmp / "last-save-ts").exists())
        autonomous_logs = project / ".remember" / "logs" / "autonomous"
        self.assertEqual(list(autonomous_logs.glob("*")), [])
        self.assertEqual(fake_claude.read_bytes(), b"must-not-run")

    def test_upstream_failure_is_neutral_and_diagnostics_are_redacted(self):
        result, layout = run_adapter_process(self, prompt="do not log this value", hook_exit=9)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "{}")
        log_path = layout.logs / "adapter-errors.log"
        self.assertNotIn("do not log this value", log_path.read_text(encoding="utf-8"))

    def test_malformed_stdin_and_missing_plugin_are_fail_open(self):
        malformed, _, _, _ = run_adapter_case(self, stdin_text="{")
        missing, _, _, _ = run_adapter_case(self, install_plugin=False)
        self.assertEqual((malformed.returncode, malformed.stdout.strip()), (0, "{}"))
        self.assertEqual((missing.returncode, missing.stdout.strip()), (0, "{}"))

    def test_event_mismatch_is_fail_open(self):
        result, _, _, _ = run_adapter_case(
            self, cli_event="PostToolUse", payload_event="SessionStart"
        )
        self.assertEqual((result.returncode, result.stdout.strip()), (0, "{}"))

    def test_upstream_timeout_is_bounded_and_fail_open(self):
        result, _, _, elapsed = run_adapter_case(
            self, hook_body="#!/bin/bash\nwhile true; do :; done\n"
        )
        self.assertEqual((result.returncode, result.stdout.strip()), (0, "{}"))
        self.assertLess(elapsed, 6.0)

    def test_exited_root_with_pipe_holding_grandchild_is_contained(self):
        heartbeat = Path(self.enterContext(tempfile.TemporaryDirectory())) / "heartbeat"
        result, _, _, elapsed = run_adapter_case(
            self, hook_body=make_descendant_hook(heartbeat, root_exits=True)
        )
        self.assertEqual((result.returncode, result.stdout.strip()), (0, "{}"))
        self.assertLess(elapsed, 6.0)
        self.assertTrue(heartbeat.exists())
        stopped_size = heartbeat.stat().st_size
        time.sleep(0.2)
        self.assertEqual(heartbeat.stat().st_size, stopped_size)

    def test_timed_out_root_and_grandchild_are_contained(self):
        heartbeat = Path(self.enterContext(tempfile.TemporaryDirectory())) / "heartbeat"
        result, _, _, elapsed = run_adapter_case(
            self, hook_body=make_descendant_hook(heartbeat, root_exits=False)
        )
        self.assertEqual((result.returncode, result.stdout.strip()), (0, "{}"))
        self.assertLess(elapsed, 6.0)
        self.assertTrue(heartbeat.exists())
        stopped_size = heartbeat.stat().st_size
        time.sleep(0.2)
        self.assertEqual(heartbeat.stat().st_size, stopped_size)

    def test_large_payload_nonreader_is_bounded_and_fail_open(self):
        home, context, layout = process_fixture(self)
        heartbeat = home / "large-heartbeat"
        body = make_descendant_hook(heartbeat, root_exits=False)
        make_fake_plugin(home, "0.20.0", complete=True, body=body)
        environment = os.environ.copy()
        environment["CODEX_HOME"] = str(home)
        raw_payload = large_hook_payload(context)
        started = time.perf_counter()
        result = subprocess.run(
            [sys.executable, str(MODULE_PATH), "--event", context.event],
            input=raw_payload,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=environment,
            timeout=10,
            check=False,
        )
        elapsed = time.perf_counter() - started
        self.assertGreater(len(raw_payload.encode("utf-8")), 1024 * 1024)
        self.assertEqual((result.returncode, result.stdout.strip()), (0, "{}"))
        self.assertLess(elapsed, 6.0)
        stopped_size = heartbeat.stat().st_size
        time.sleep(0.2)
        self.assertEqual(heartbeat.stat().st_size, stopped_size)
        self.assertNotIn(
            "p" * 64,
            (layout.logs / "adapter-errors.log").read_text(encoding="utf-8"),
        )

    def test_large_payload_success_is_forwarded_byte_for_byte(self):
        home, context, _ = process_fixture(self)
        make_fake_plugin(
            home,
            "0.20.0",
            complete=True,
            body="#!/bin/bash\ncat\n",
        )
        environment = os.environ.copy()
        environment["CODEX_HOME"] = str(home)
        raw_payload = large_hook_payload(context)
        result = subprocess.run(
            [sys.executable, str(MODULE_PATH), "--event", context.event],
            input=raw_payload,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=environment,
            timeout=10,
            check=False,
        )
        self.assertEqual((result.returncode, result.stderr), (0, ""))
        self.assertEqual(result.stdout.encode("utf-8"), raw_payload.encode("utf-8"))

    def test_error_log_rotates_without_captured_content(self):
        home, context, layout = process_fixture(self)
        layout.logs.mkdir(parents=True)
        active_log = layout.logs / "adapter-errors.log"
        active_log.write_bytes(b"a" * (1024 * 1024 + 1))
        body = "#!/bin/bash\ncat >/dev/null\nexit 9\n"
        make_fake_plugin(home, "0.20.0", complete=True, body=body)
        environment = os.environ.copy()
        environment["CODEX_HOME"] = str(home)
        result = subprocess.run(
            [sys.executable, str(MODULE_PATH), "--event", context.event],
            input=json.dumps(hook_payload(context, "private prompt")),
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=environment,
            timeout=10,
            check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertTrue((layout.logs / "adapter-errors.log.1").exists())
        self.assertNotIn("private prompt", active_log.read_text(encoding="utf-8"))

    def test_session_start_context_output_passes_through(self):
        result, _, _, _ = run_adapter_case(
            self,
            cli_event="SessionStart",
            hook_body="#!/bin/bash\ncat >/dev/null\nprintf 'context-line\\n'\n",
        )
        self.assertEqual((result.returncode, result.stdout), (0, "context-line\n"))

    def test_claude_wrapper_clears_private_config_and_forwards_arguments(self):
        temp_root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        fake = temp_root / "fake-claude.cmd"
        fake.write_text(
            "@echo off\nif defined CLAUDE_CONFIG_DIR exit /b 41\necho %*\n",
            encoding="utf-8",
        )
        environment = os.environ.copy()
        environment["CLAUDE_CONFIG_DIR"] = str(temp_root / "private")
        environment["REMEMBER_REAL_CLAUDE_BIN"] = str(fake)
        result = subprocess.run(
            ["cmd.exe", "/d", "/c", str(WRAPPER_PATH), "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=environment,
            timeout=5,
            check=False,
        )
        self.assertEqual((result.returncode, result.stdout.strip()), (0, "--version"))

    def test_initialization_without_home_is_fail_open(self):
        environment = os.environ.copy()
        for name in ("CODEX_HOME", "HOME", "USERPROFILE", "HOMEDRIVE", "HOMEPATH"):
            environment.pop(name, None)
        result = subprocess.run(
            [sys.executable, str(MODULE_PATH), "--event", "PostToolUse"],
            input="{",
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=environment,
            timeout=5,
            check=False,
        )
        self.assertEqual((result.returncode, result.stdout.strip(), result.stderr), (0, "{}", ""))

    def test_broken_stdout_is_nonthrowing_and_silent(self):
        home = Path(self.enterContext(tempfile.TemporaryDirectory())) / "codex"
        environment = os.environ.copy()
        environment["CODEX_HOME"] = str(home)
        read_fd, write_fd = os.pipe()
        os.close(read_fd)
        try:
            result = subprocess.run(
                [sys.executable, str(MODULE_PATH), "--event", "PostToolUse"],
                input="{",
                stdout=write_fd,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                env=environment,
                timeout=5,
                check=False,
            )
        finally:
            os.close(write_fd)
        self.assertEqual((result.returncode, result.stderr), (0, ""))

    def test_invalid_cli_shapes_are_fail_open(self):
        home = Path(self.enterContext(tempfile.TemporaryDirectory())) / "codex"
        environment = os.environ.copy()
        environment["CODEX_HOME"] = str(home)
        for arguments in ([], ["--event"], ["--event", "Unknown"], ["--help"]):
            with self.subTest(arguments=arguments):
                result = subprocess.run(
                    [sys.executable, str(MODULE_PATH), *arguments],
                    input="{}",
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    env=environment,
                    timeout=5,
                    check=False,
                )
                self.assertEqual(
                    (result.returncode, result.stdout.strip(), result.stderr),
                    (0, "{}", ""),
                )


@unittest.skipUnless(
    CONTAINMENT_API_EXISTS,
    "handle-owned process containment is not installed yet",
)
class ContainmentFailureTests(unittest.TestCase):
    class TrackingJob:
        def __init__(self, reject_assignment: bool = False):
            self.reject_assignment = reject_assignment
            self.assigned = False
            self.closed = False

        def assign(self, process):
            self.assigned = True
            if self.reject_assignment:
                raise adapter.AdapterError("injected-job-assignment-failure")

        def terminate(self):
            pass

        def close(self):
            self.closed = True

    def command_fixture(self):
        raw = self.enterContext(tempfile.TemporaryDirectory())
        marker = Path(raw) / "executed"
        script = Path(raw) / "hook.sh"
        script.write_text(
            f'#!/bin/bash\nprintf executed > "{marker.as_posix()}"\n',
            encoding="utf-8",
            newline="\n",
        )
        command = [str(adapter.GIT_BASH_EXE), "--noprofile", "--norc", str(script)]
        return command, marker

    def test_assignment_failure_closes_boundary_before_hook_executes(self):
        command, marker = self.command_fixture()
        job = self.TrackingJob(reject_assignment=True)
        with self.assertRaisesRegex(adapter.AdapterError, "assignment"):
            adapter._run_contained_process(
                command,
                "",
                1.0,
                os.environ.copy(),
                job_factory=lambda: job,
            )
        self.assertEqual((job.assigned, job.closed, marker.exists()), (True, True, False))

    def test_resume_failure_closes_real_job_before_hook_executes(self):
        command, marker = self.command_fixture()

        def reject_resume(process):
            raise adapter.AdapterError("injected-resume-failure")

        with self.assertRaisesRegex(adapter.AdapterError, "resume"):
            adapter._run_contained_process(
                command,
                "",
                1.0,
                os.environ.copy(),
                resume_process=reject_resume,
            )
        self.assertFalse(marker.exists())

    def test_boundary_closes_on_success_and_launch_error(self):
        command, marker = self.command_fixture()
        success_job = self.TrackingJob()
        result = adapter._run_contained_process(
            command,
            "",
            1.0,
            os.environ.copy(),
            job_factory=lambda: success_job,
        )
        self.assertEqual((result.returncode, success_job.closed, marker.exists()), (0, True, True))

        launch_job = self.TrackingJob()
        with self.assertRaises(OSError):
            adapter._run_contained_process(
                [str(Path(self.enterContext(tempfile.TemporaryDirectory())) / "missing.exe")],
                "",
                1.0,
                os.environ.copy(),
                job_factory=lambda: launch_job,
            )
        self.assertTrue(launch_job.closed)


@unittest.skipUnless(
    ASYNC_STDIN_API_EXISTS,
    "bounded asynchronous stdin delivery is not installed yet",
)
class AsyncStdinLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.raw_payload = "x" * (1024 * 1024 + 4096)
        self.raw = self.enterContext(tempfile.TemporaryDirectory())
        self.script = Path(self.raw) / "hook.sh"
        self.script.write_text(
            "#!/bin/bash\nwhile true; do :; done\n",
            encoding="utf-8",
            newline="\n",
        )
        self.command = [
            str(adapter.GIT_BASH_EXE),
            "--noprofile",
            "--norc",
            str(self.script),
        ]

    def writer_threads(self):
        return [
            thread
            for thread in threading.enumerate()
            if thread.name.startswith("RememberPayloadWriter")
        ]

    def warm_runtime(self):
        success = Path(self.raw) / "warm-success.sh"
        success.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8", newline="\n")
        command = [
            str(adapter.GIT_BASH_EXE),
            "--noprofile",
            "--norc",
            str(success),
        ]
        for _ in range(10):
            adapter._run_contained_process(command, "", 1.0, os.environ.copy())

    def test_large_timeout_stops_writer_and_preserves_stabilized_handles(self):
        success = Path(self.raw) / "success.sh"
        success.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8", newline="\n")
        success_command = [
            str(adapter.GIT_BASH_EXE),
            "--noprofile",
            "--norc",
            str(success),
        ]
        for _ in range(10):
            adapter._run_contained_process(success_command, "", 1.0, os.environ.copy())
        before = stabilized_process_handle_count()
        for _ in range(3):
            with self.assertRaises(subprocess.TimeoutExpired):
                adapter._run_contained_process(
                    self.command,
                    self.raw_payload,
                    0.1,
                    os.environ.copy(),
                )
        self.assertEqual(self.writer_threads(), [])
        self.assertEqual(current_process_handle_count(), before)

    def test_writer_construction_failure_closes_job_without_process_or_pipe(self):
        self.warm_runtime()
        before = stabilized_process_handle_count()
        job = ContainmentFailureTests.TrackingJob()
        with mock.patch.object(
            adapter, "_PayloadWriter", side_effect=OSError("injected-constructor")
        ):
            with self.assertRaisesRegex(OSError, "injected-constructor"):
                adapter._run_contained_process(
                    self.command,
                    self.raw_payload,
                    1.0,
                    os.environ.copy(),
                    job_factory=lambda: job,
                )
        self.assertTrue(job.closed)
        self.assertEqual(self.writer_threads(), [])
        self.assertEqual(current_process_handle_count(), before)

    def test_thread_start_failure_preserves_original_and_closes_pipe(self):
        self.warm_runtime()
        before = stabilized_process_handle_count()
        writer = adapter._PayloadWriter(self.raw_payload.encode("utf-8"))
        self.addCleanup(writer._close_write_fd)
        self.addCleanup(writer.close_parent_read)
        with mock.patch.object(
            threading.Thread, "start", side_effect=OSError("injected-thread-start")
        ):
            with self.assertRaisesRegex(OSError, "injected-thread-start"):
                writer.start()
        writer.close()
        self.assertEqual(self.writer_threads(), [])
        self.assertEqual(current_process_handle_count(), before)

    def test_cancellation_failure_cannot_skip_join_or_pipe_cleanup(self):
        self.warm_runtime()
        before = stabilized_process_handle_count()
        writer = adapter._PayloadWriter(self.raw_payload.encode("utf-8"))
        held_reader = os.dup(writer.child_read_fd)
        writer.close_parent_read()
        writer.start()
        time.sleep(0.05)
        original_cancel = writer._cancel_writer_io
        close_error = None
        alive_after_close = None
        try:
            with mock.patch.object(
                writer,
                "_cancel_writer_io",
                side_effect=adapter.AdapterError("injected-cancel-failure"),
            ):
                try:
                    writer.close()
                except BaseException as error:
                    close_error = error
                alive_after_close = writer._thread.is_alive()
        finally:
            os.close(held_reader)
            if writer._thread is not None and writer._thread.is_alive():
                original_cancel(writer._thread)
                writer._thread.join(1.0)
            writer._close_write_fd()
        self.assertIsNone(close_error)
        self.assertFalse(alive_after_close)
        self.assertEqual(self.writer_threads(), [])
        self.assertEqual(current_process_handle_count(), before)

    def test_large_nonreader_uses_owned_nondaemon_writer(self):
        outcome = []

        def invoke():
            try:
                adapter._run_contained_process(
                    self.command,
                    self.raw_payload,
                    0.5,
                    os.environ.copy(),
                )
            except BaseException as error:
                outcome.append(error)

        runner = threading.Thread(target=invoke, name="AsyncStdinTestRunner")
        runner.start()
        deadline = time.perf_counter() + 2.0
        writers = []
        while time.perf_counter() < deadline:
            writers = self.writer_threads()
            if writers:
                break
            time.sleep(0.01)
        self.assertEqual(len(writers), 1)
        self.assertFalse(writers[0].daemon)
        self.assertFalse(
            any(thread.name.endswith("(_writerthread)") for thread in threading.enumerate())
        )
        runner.join(3.0)
        self.assertFalse(runner.is_alive())
        self.assertEqual(len(outcome), 1)
        self.assertIsInstance(outcome[0], subprocess.TimeoutExpired)
        self.assertEqual(self.writer_threads(), [])

    def test_large_assignment_and_resume_failures_leave_no_writer(self):
        assignment_job = ContainmentFailureTests.TrackingJob(reject_assignment=True)
        with self.assertRaises(adapter.AdapterError):
            adapter._run_contained_process(
                self.command,
                self.raw_payload,
                1.0,
                os.environ.copy(),
                job_factory=lambda: assignment_job,
            )
        self.assertEqual(self.writer_threads(), [])

        def reject_resume(process):
            raise adapter.AdapterError("injected-large-resume-failure")

        with self.assertRaises(adapter.AdapterError):
            adapter._run_contained_process(
                self.command,
                self.raw_payload,
                1.0,
                os.environ.copy(),
                resume_process=reject_resume,
            )
        self.assertEqual(self.writer_threads(), [])

    def test_blocked_writer_cancellation_has_no_stabilized_handle_growth(self):
        def cancel_blocked_writer(assert_blocked=False):
            writer = adapter._PayloadWriter(self.raw_payload.encode("utf-8"))
            held_reader = os.dup(writer.child_read_fd)
            try:
                writer.close_parent_read()
                writer.start()
                time.sleep(0.05)
                if assert_blocked:
                    self.assertTrue(self.writer_threads())
                started = time.perf_counter()
                writer.close()
                self.assertLess(time.perf_counter() - started, 2.0)
                self.assertEqual(self.writer_threads(), [])
            finally:
                os.close(held_reader)
                writer.close()

        stabilized_process_handle_count()
        handle_counts = []
        for batch in range(2):
            for iteration in range(10):
                cancel_blocked_writer(assert_blocked=(batch == 0 and iteration == 0))
            gc.collect()
            self.assertEqual(self.writer_threads(), [])
            handle_counts.append(current_process_handle_count())

        self.assertLessEqual(
            handle_counts[1],
            handle_counts[0] + 1,
            f"handles grew across stabilized batches: {handle_counts}",
        )


@unittest.skipUnless(SYNC_API_EXISTS, "incremental sync API is not installed yet")
class SyncTests(unittest.TestCase):
    def test_installed_remember_parser_accepts_mirror(self):
        source, context, layout = make_sync_fixture(self)
        append_jsonl(
            source,
            user_record("remember this"),
            assistant_record("noted"),
            codex_record(
                "function_call",
                name="shell_command",
                call_id="tool-9",
                arguments='{"command":"private"}',
            ),
        )
        adapter.sync_transcript(context, layout)
        actual_home = Path(os.environ.get("CODEX_HOME", r"D:\DevHome\state\codex"))
        plugin_root = adapter.discover_remember_plugin(actual_home)
        messages, cache_before, cache_after = run_installed_remember_parser(
            plugin_root, layout.mirror_path(context)
        )
        self.assertEqual(cache_after, cache_before)
        self.assertEqual(
            messages,
            [
                ("HUMAN", "remember this"),
                ("AGENT", "noted"),
                ("AGENT", "[TOOL: shell_command]"),
            ],
        )

        slug_result = subprocess.run(
            [
                str(adapter.GIT_BASH_EXE),
                "--noprofile",
                "--norc",
                "-c",
                'source "$1"; session_dir_slug "$2"',
                "slug-check",
                str(plugin_root / "scripts" / "lib-slug.sh"),
                r"D:\Devtools",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=5,
            check=True,
        )
        self.assertEqual(slug_result.stdout.strip(), adapter.slug_project(r"D:\Devtools"))

    def test_incremental_sync_appends_once(self):
        source, context, layout = make_sync_fixture(self)
        append_jsonl(source, user_record("first"))
        first = adapter.sync_transcript(context, layout)
        append_jsonl(source, assistant_record("second"))
        second = adapter.sync_transcript(context, layout)
        adapter.sync_transcript(context, layout)
        mirror_lines = layout.mirror_path(context).read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(mirror_lines), 2)
        self.assertEqual((first.translated_records, second.translated_records), (1, 1))

    def test_incomplete_tail_is_retried(self):
        source, context, layout = make_sync_fixture(self)
        complete = json.dumps(user_record("whole")).encode() + b"\n"
        partial = json.dumps(assistant_record("later")).encode()
        source.write_bytes(complete + partial[:10])
        first = adapter.sync_transcript(context, layout)
        source.write_bytes(complete + partial + b"\n")
        second = adapter.sync_transcript(context, layout)
        self.assertEqual((first.mirror_lines, second.mirror_lines), (1, 2))

    def test_uncommitted_mirror_tail_is_truncated_before_replay(self):
        source, context, layout = make_sync_fixture(self)
        append_jsonl(source, user_record("once"))
        adapter.sync_transcript(context, layout)
        mirror = layout.mirror_path(context)
        with mirror.open("ab") as stream:
            stream.write(b'{"partial":')
        adapter.sync_transcript(context, layout)
        self.assertEqual(len(mirror.read_text(encoding="utf-8").splitlines()), 1)
        self.assertNotIn("partial", mirror.read_text(encoding="utf-8"))

    def test_source_truncation_rebuilds_mirror(self):
        source, context, layout = make_sync_fixture(self)
        append_jsonl(source, user_record("old"), assistant_record("old reply"))
        adapter.sync_transcript(context, layout)
        source.write_text(json.dumps(user_record("new")) + "\n", encoding="utf-8")
        adapter.sync_transcript(context, layout)
        text = layout.mirror_path(context).read_text(encoding="utf-8")
        self.assertIn("new", text)
        self.assertNotIn("old reply", text)

    def test_corrupt_checkpoint_rebuilds_from_source(self):
        source, context, layout = make_sync_fixture(self)
        append_jsonl(source, user_record("recover"))
        checkpoint = layout.checkpoint_path(context)
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        checkpoint.write_text("{broken", encoding="utf-8")
        result = adapter.sync_transcript(context, layout)
        self.assertEqual(result.mirror_lines, 1)
        self.assertIn("recover", layout.mirror_path(context).read_text(encoding="utf-8"))

    def test_oversized_source_line_is_skipped_without_leaking_content(self):
        source, context, layout = make_sync_fixture(self)
        oversized = b'x' * (adapter.MAX_SOURCE_LINE_BYTES + 1) + b"\n"
        source.write_bytes(oversized + json.dumps(user_record("after large line")).encode("utf-8") + b"\n")
        result = adapter.sync_transcript(context, layout)
        mirror_text = layout.mirror_path(context).read_text(encoding="utf-8")
        self.assertEqual(result.mirror_lines, 1)
        self.assertEqual(mirror_text.count("after large line"), 1)
        self.assertNotIn("xxxx", mirror_text)

    def test_missing_session_start_source_creates_empty_mirror(self):
        source, _, layout = make_sync_fixture(self)
        source.unlink(missing_ok=True)
        context = adapter.HookContext("SessionStart", "session-1", Path(r"D:\Devtools"), source)
        result = adapter.sync_transcript(context, layout)
        self.assertEqual((result.source_offset, result.mirror_bytes, result.mirror_lines), (0, 0, 0))
        self.assertEqual(layout.mirror_path(context).read_bytes(), b"")

    def test_malformed_complete_line_is_skipped_and_next_record_survives(self):
        source, context, layout = make_sync_fixture(self)
        source.write_bytes(b"{broken}\n" + json.dumps(user_record("survives")).encode("utf-8") + b"\n")
        result = adapter.sync_transcript(context, layout)
        self.assertEqual(result.mirror_lines, 1)
        self.assertIn("survives", layout.mirror_path(context).read_text(encoding="utf-8"))

    def test_sync_warning_rotates_and_bounds_the_shared_diagnostic_log(self):
        source, context, layout = make_sync_fixture(self)
        layout.logs.mkdir(parents=True)
        active_log = layout.logs / "adapter-errors.log"
        active_log.write_bytes(b"a" * (adapter.DIAGNOSTIC_LIMIT_BYTES + 1))
        source.write_bytes(b"{broken}\n")

        adapter.sync_transcript(context, layout)

        rotated_log = layout.logs / "adapter-errors.log.1"
        self.assertTrue(rotated_log.is_file())
        self.assertEqual(
            rotated_log.stat().st_size,
            adapter.DIAGNOSTIC_LIMIT_BYTES + 1,
        )
        self.assertLessEqual(active_log.stat().st_size, adapter.DIAGNOSTIC_LIMIT_BYTES)
        self.assertEqual(
            active_log.read_text(encoding="ascii"),
            "sync-warning malformed-source-line\n",
        )

    def test_source_integer_digit_limit_rejection_is_skipped(self):
        source, context, layout = make_sync_fixture(self)
        too_many_digits = b"9" * (sys.get_int_max_str_digits() + 1)
        rejected = b'{"number":' + too_many_digits + b"}\n"
        source.write_bytes(rejected + json.dumps(user_record("after integer")).encode("utf-8") + b"\n")
        result = adapter.sync_transcript(context, layout)
        self.assertEqual(result.source_offset, source.stat().st_size)
        self.assertEqual(result.mirror_lines, 1)
        self.assertIn("after integer", layout.mirror_path(context).read_text(encoding="utf-8"))

    def test_source_recursion_limit_rejection_is_skipped(self):
        source, context, layout = make_sync_fixture(self)
        depth = 20_000
        rejected = b"[" * depth + b"0" + b"]" * depth + b"\n"
        source.write_bytes(rejected + json.dumps(user_record("after nesting")).encode("utf-8") + b"\n")
        result = adapter.sync_transcript(context, layout)
        self.assertEqual(result.source_offset, source.stat().st_size)
        self.assertEqual(result.mirror_lines, 1)
        self.assertIn("after nesting", layout.mirror_path(context).read_text(encoding="utf-8"))

    def test_checkpoint_integer_digit_limit_rejection_rebuilds(self):
        source, context, layout = make_sync_fixture(self)
        append_jsonl(source, user_record("recover integer checkpoint"))
        checkpoint = layout.checkpoint_path(context)
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        too_many_digits = b"9" * (sys.get_int_max_str_digits() + 1)
        checkpoint.write_bytes(b'{"source_offset":' + too_many_digits + b"}")
        result = adapter.sync_transcript(context, layout)
        self.assertEqual(result.mirror_lines, 1)
        self.assertIn("recover integer checkpoint", layout.mirror_path(context).read_text(encoding="utf-8"))

    def test_checkpoint_recursion_limit_rejection_rebuilds(self):
        source, context, layout = make_sync_fixture(self)
        append_jsonl(source, user_record("recover nested checkpoint"))
        checkpoint = layout.checkpoint_path(context)
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        depth = 20_000
        checkpoint.write_bytes(b"[" * depth + b"0" + b"]" * depth)
        result = adapter.sync_transcript(context, layout)
        self.assertEqual(result.mirror_lines, 1)
        self.assertIn("recover nested checkpoint", layout.mirror_path(context).read_text(encoding="utf-8"))

    def test_checkpoint_io_error_propagates_from_sync(self):
        source, context, layout = make_sync_fixture(self)
        append_jsonl(source, user_record("do not hide checkpoint io"))
        checkpoint = layout.checkpoint_path(context)
        checkpoint.mkdir(parents=True)
        with self.assertRaises(OSError):
            adapter.sync_transcript(context, layout)

    def test_structurally_invalid_checkpoints_rebuild(self):
        corruptions = [
            ("wrong schema", "set", "schema_version", 2),
            ("bool schema", "set", "schema_version", True),
            ("float schema", "set", "schema_version", 1.0),
            ("missing required field", "delete", "source_offset", None),
            ("missing integrity", "delete", "integrity", None),
            ("bool counter", "set", "source_offset", True),
            ("negative offset", "set", "source_offset", -1),
            ("negative byte count", "set", "mirror_bytes", -1),
            ("negative line count", "set", "mirror_lines", -1),
            ("wrong source path type", "set", "source_path", 7),
            ("wrong source device type", "set", "source_dev", "device"),
            ("wrong source inode type", "set", "source_ino", "inode"),
        ]
        for label, operation, field, corrupt_value in corruptions:
            with self.subTest(label=label):
                source, context, layout = make_sync_fixture(self)
                append_jsonl(source, user_record(f"recover {label}"))
                adapter.sync_transcript(context, layout)
                checkpoint_path = layout.checkpoint_path(context)
                checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
                if operation == "delete":
                    del checkpoint[field]
                else:
                    checkpoint[field] = corrupt_value
                if label in {"bool schema", "float schema"}:
                    checkpoint["integrity"] = test_checkpoint_integrity(checkpoint)
                checkpoint_path.write_text(json.dumps(checkpoint), encoding="utf-8")

                result = adapter.sync_transcript(context, layout)
                persisted = json.loads(checkpoint_path.read_text(encoding="utf-8"))
                persisted_bytes = checkpoint_path.read_bytes()
                persisted_stat = checkpoint_path.stat()
                self.assertEqual((result.translated_records, result.mirror_lines), (1, 1))
                self.assertEqual(persisted["schema_version"], 1)
                self.assertEqual(persisted["source_offset"], source.stat().st_size)
                self.assertEqual(persisted["mirror_bytes"], layout.mirror_path(context).stat().st_size)
                self.assertEqual(persisted["mirror_lines"], 1)
                second = adapter.sync_transcript(context, layout)
                self.assertEqual(
                    (
                        second.source_offset,
                        second.mirror_bytes,
                        second.mirror_lines,
                        second.translated_records,
                    ),
                    (source.stat().st_size, layout.mirror_path(context).stat().st_size, 1, 0),
                )
                second_stat = checkpoint_path.stat()
                self.assertEqual(checkpoint_path.read_bytes(), persisted_bytes)
                self.assertEqual(
                    (second_stat.st_ino, second_stat.st_mtime_ns),
                    (persisted_stat.st_ino, persisted_stat.st_mtime_ns),
                )

    def test_noop_sync_reads_only_the_committed_mirror_tail_byte(self):
        source, context, layout = make_sync_fixture(self)
        append_jsonl(source, user_record("hot path"))
        adapter.sync_transcript(context, layout)
        mirror = layout.mirror_path(context)
        checkpoint = layout.checkpoint_path(context)
        checkpoint_before = checkpoint.stat()
        checkpoint_bytes = checkpoint.read_bytes()
        real_open = Path.open
        mirror_read_sizes = []
        testcase = self

        class GuardedMirrorReader:
            def __init__(self, stream):
                self.stream = stream

            def __enter__(self):
                self.stream.__enter__()
                return self

            def __exit__(self, *args):
                return self.stream.__exit__(*args)

            def __getattr__(self, name):
                return getattr(self.stream, name)

            def read(self, size=-1):
                testcase.assertEqual(size, 1, "steady-state mirror validation must read only its tail byte")
                mirror_read_sizes.append(size)
                return self.stream.read(size)

        def guarded_open(path, *args, **kwargs):
            mode = args[0] if args else kwargs.get("mode", "r")
            if Path(path) == mirror and mode != "rb":
                testcase.fail("a no-op sync must not reopen the committed mirror for writing")
            stream = real_open(path, *args, **kwargs)
            if Path(path) == mirror:
                return GuardedMirrorReader(stream)
            return stream

        with mock.patch.object(Path, "open", new=guarded_open):
            result = adapter.sync_transcript(context, layout)
        self.assertEqual(
            (
                result.source_offset,
                result.mirror_bytes,
                result.mirror_lines,
                result.translated_records,
            ),
            (source.stat().st_size, mirror.stat().st_size, 1, 0),
        )
        self.assertEqual(mirror_read_sizes, [1])
        checkpoint_after = checkpoint.stat()
        self.assertEqual(checkpoint.read_bytes(), checkpoint_bytes)
        self.assertEqual(
            (checkpoint_after.st_ino, checkpoint_after.st_mtime_ns),
            (checkpoint_before.st_ino, checkpoint_before.st_mtime_ns),
        )

    def test_checkpoint_integrity_tampering_rebuilds(self):
        source, context, layout = make_sync_fixture(self)
        append_jsonl(source, user_record("integrity protected"))
        adapter.sync_transcript(context, layout)
        checkpoint_path = layout.checkpoint_path(context)
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        checkpoint["source_offset"] = 0
        checkpoint_path.write_text(json.dumps(checkpoint), encoding="utf-8")
        result = adapter.sync_transcript(context, layout)
        mirror_text = layout.mirror_path(context).read_text(encoding="utf-8")
        self.assertEqual((result.translated_records, result.mirror_lines), (1, 1))
        self.assertEqual(mirror_text.count("integrity protected"), 1)

    def test_same_size_mirror_mutation_rebuilds(self):
        source, context, layout = make_sync_fixture(self)
        append_jsonl(source, user_record("original"))
        adapter.sync_transcript(context, layout)
        mirror = layout.mirror_path(context)
        expected = mirror.read_bytes()
        mutated = expected.replace(b"original", b"mutated!")
        self.assertEqual(len(mutated), len(expected))
        mirror.write_bytes(mutated)
        self.assertEqual(mirror.stat().st_size, len(expected))
        adapter.sync_transcript(context, layout)
        self.assertEqual(mirror.read_bytes(), expected)

    def test_wrong_positive_checkpoint_line_count_rebuilds(self):
        source, context, layout = make_sync_fixture(self)
        append_jsonl(source, user_record("line count"))
        adapter.sync_transcript(context, layout)
        checkpoint_path = layout.checkpoint_path(context)
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        checkpoint["mirror_lines"] = 4
        checkpoint_path.write_text(json.dumps(checkpoint), encoding="utf-8")
        result = adapter.sync_transcript(context, layout)
        persisted = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        self.assertEqual((result.mirror_lines, persisted["mirror_lines"]), (1, 1))

    def test_checkpoint_byte_boundary_without_newline_rebuilds(self):
        source, context, layout = make_sync_fixture(self)
        append_jsonl(source, user_record("complete boundary"))
        adapter.sync_transcript(context, layout)
        mirror = layout.mirror_path(context)
        expected = mirror.read_bytes()
        checkpoint_path = layout.checkpoint_path(context)
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        checkpoint["mirror_bytes"] -= 1
        checkpoint_path.write_text(json.dumps(checkpoint), encoding="utf-8")
        adapter.sync_transcript(context, layout)
        self.assertEqual(mirror.read_bytes(), expected)
        self.assertTrue(mirror.read_bytes().endswith(b"\n"))

    def test_short_committed_mirror_rebuilds(self):
        source, context, layout = make_sync_fixture(self)
        append_jsonl(source, user_record("restore short mirror"))
        adapter.sync_transcript(context, layout)
        mirror = layout.mirror_path(context)
        expected = mirror.read_bytes()
        mirror.write_bytes(expected[:3])
        result = adapter.sync_transcript(context, layout)
        self.assertEqual(result.mirror_lines, 1)
        self.assertEqual(mirror.read_bytes(), expected)

    def test_source_identity_change_rebuilds(self):
        source, context, layout = make_sync_fixture(self)
        append_jsonl(source, user_record("old identity"))
        adapter.sync_transcript(context, layout)
        replacement = source.with_suffix(".replacement")
        append_jsonl(replacement, user_record("new identity"))
        os.replace(replacement, source)
        adapter.sync_transcript(context, layout)
        text = layout.mirror_path(context).read_text(encoding="utf-8")
        self.assertIn("new identity", text)
        self.assertNotIn("old identity", text)

    def test_source_path_change_rebuilds(self):
        source, context, layout = make_sync_fixture(self)
        append_jsonl(source, user_record("old path"))
        adapter.sync_transcript(context, layout)
        new_source = source.with_name("rollout-session-2.jsonl")
        append_jsonl(new_source, user_record("new path"))
        new_context = adapter.HookContext(context.event, context.session_id, context.cwd, new_source)
        adapter.sync_transcript(new_context, layout)
        text = layout.mirror_path(new_context).read_text(encoding="utf-8")
        self.assertIn("new path", text)
        self.assertNotIn("old path", text)

    def test_skipped_source_offsets_persist_across_second_sync(self):
        source, context, layout = make_sync_fixture(self)
        malformed = b"{broken}\n"
        oversized = b"x" * (adapter.MAX_SOURCE_LINE_BYTES + 1) + b"\n"
        surviving = json.dumps(user_record("only once")).encode("utf-8") + b"\n"
        source.write_bytes(malformed + oversized + surviving)
        first = adapter.sync_transcript(context, layout)
        second = adapter.sync_transcript(context, layout)
        mirror_text = layout.mirror_path(context).read_text(encoding="utf-8")
        self.assertEqual((first.source_offset, second.source_offset), (source.stat().st_size,) * 2)
        self.assertEqual((first.translated_records, second.translated_records), (1, 0))
        self.assertEqual(mirror_text.count("only once"), 1)

    def test_second_session_lock_is_rejected_without_waiting(self):
        _, context, layout = make_sync_fixture(self)
        with adapter.session_lock(layout, context):
            with self.assertRaisesRegex(adapter.AdapterError, "lock-contention"):
                with adapter.session_lock(layout, context):
                    self.fail("a second lock must not be acquired")


@unittest.skipUnless(MODULE_EXISTS, "production adapter is not installed yet")
class BenchmarkEntryPointTests(unittest.TestCase):
    def test_benchmark_entry_point_runs_twenty_complete_processes(self):
        environment = os.environ.copy()
        environment["REMEMBER_ADAPTER_BENCHMARK"] = "1"
        completed = subprocess.run(
            [sys.executable, str(Path(__file__).resolve())],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=environment,
            timeout=30,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertRegex(
            completed.stdout.strip(),
            r'^\{"samples": 20, "median_ms": [0-9.]+, "max_ms": [0-9.]+\}$',
            "benchmark mode must emit one 20-sample JSON summary",
        )


def run_benchmark() -> None:
    with tempfile.TemporaryDirectory() as raw:
        home = Path(raw) / "codex"
        source = home / "sessions" / "2026" / "08" / "13" / "rollout-benchmark.jsonl"
        append_jsonl(source, user_record("benchmark"))
        context = adapter.HookContext("PostToolUse", "benchmark", Path(r"D:\Devtools"), source)
        make_fake_plugin(home, "0.20.0", complete=True)
        environment = os.environ.copy()
        environment["CODEX_HOME"] = str(home)
        command = [sys.executable, str(MODULE_PATH), "--event", "PostToolUse"]
        hook_input = json.dumps(hook_payload(context))
        subprocess.run(
            command,
            input=hook_input,
            text=True,
            capture_output=True,
            env=environment,
            timeout=10,
            check=True,
        )
        samples = []
        for _ in range(20):
            started = time.perf_counter()
            subprocess.run(
                command,
                input=hook_input,
                text=True,
                capture_output=True,
                env=environment,
                timeout=10,
                check=True,
            )
            samples.append((time.perf_counter() - started) * 1000)
        print(
            json.dumps(
                {
                    "samples": len(samples),
                    "median_ms": statistics.median(samples),
                    "max_ms": max(samples),
                }
            )
        )


if __name__ == "__main__" and os.environ.get("REMEMBER_ADAPTER_BENCHMARK") == "1":
    run_benchmark()
elif __name__ == "__main__":
    unittest.main()
