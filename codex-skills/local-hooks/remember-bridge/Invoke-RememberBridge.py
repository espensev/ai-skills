"""Remember bridge for Grok and Kimi Code CLI.

Runs as the hook command on a host whose hook payload and transcript Remember
(pinned 0.27.0 checkout) does not understand. Per event it:

1. normalises the native payload (camelCase to snake_case, Kimi `session_`
   prefix stripped, id lower-cased),
2. locates the host's own transcript (Grok `chat_history.jsonl`, Kimi
   `agents/main/wire.jsonl`) and mirrors new lines into a Claude-shaped JSONL
   under `<bridge_root>/<host>/projects/<slug>/<session_id>.jsonl`,
3. runs the upstream hook script through Git Bash with the environment Claude
   Code would have provided (`CLAUDE_PLUGIN_ROOT`, `CLAUDE_PROJECT_DIR`,
   `CLAUDE_CONFIG_DIR`, `HOME`) and a flat snake_case payload on stdin,
4. caches the SessionStart memory block and injects it once: Grok on the first
   PreToolUse (`additionalContext`), Kimi on the first UserPromptSubmit,
5. writes one `[bridge]` log line per event to `<bridge_root>/<host>/logs/`
   and, when the Remember user config resolves, into the store's own log.

It never blocks the host: every path exits 0. It never waits for or kills
upstream's backgrounded save (a grandchild of the bash it launches).

Usage:
    py -3 Invoke-RememberBridge.py                         # print resolved configuration
    py -3 Invoke-RememberBridge.py --host grok --event SessionStart < payload.json
    py -3 Invoke-RememberBridge.py --host kimi --event PostToolUse  < payload.json

Environment (all optional):
    REMEMBER_BRIDGE_PLUGIN_ROOT  pinned Remember checkout (default D:/DevHome/state/remember/artifacts/remember-current)
    REMEMBER_BRIDGE_ROOT         bridge state root            (default D:/DevHome/state/remember/bridge)
    REMEMBER_BRIDGE_BASH         bash to run upstream with    (default C:/Program Files/Git/bin/bash.exe, then PATH)
    GROK_HOME, KIMI_CODE_HOME    host homes                   (default ~/.grok, ~/.kimi-code)
"""

from __future__ import annotations

import datetime as _dt
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from urllib.parse import unquote

HOSTS = ("grok", "kimi")
HOOK_SCRIPTS = {
    "SessionStart": "session-start-hook.sh",
    "UserPromptSubmit": "user-prompt-hook.sh",
    "PostToolUse": "post-tool-hook.sh",
    "SessionEnd": "session-end-hook.sh",
    "PreToolUse": None,
}
CAPTURE_EVENTS = ("PostToolUse", "SessionEnd")
DEFAULT_PLUGIN_ROOT = "D:/DevHome/state/remember/artifacts/remember-current"
DEFAULT_BRIDGE_ROOT = "D:/DevHome/state/remember/bridge"
GIT_BASH = "C:/Program Files/Git/bin/bash.exe"
INJECT_CLIP = 9500
CLIP_MARKER = "\n[remember-bridge: memory block clipped at 9,500 characters]"
UPSTREAM_WAIT_SECONDS = 300
SESSION_ID_RE = re.compile(r"^[a-f0-9][a-f0-9-]*$")
SESSION_START_SOURCES = frozenset({"startup", "resume", "clear", "compact", "fork"})
REASON_RE = re.compile(r"^[A-Za-z0-9_]+$")
USER_QUERY_RE = re.compile(r"<user_query>(.*?)</user_query>", re.S)
SLUG_MAX = 200
_BASE36 = "0123456789abcdefghijklmnopqrstuvwxyz"


# ── small helpers ────────────────────────────────────────────────────────────

def forward(path: str) -> str:
    return path.replace("\\", "/")


def _strip_dir(path: str) -> str:
    path = forward(path.strip())
    while len(path) > 1 and path.endswith("/") and not (len(path) == 3 and path[1] == ":"):
        path = path[:-1]
    return path


def _norm_cmp(path: str) -> str:
    return _strip_dir(path).lower()


def to_snake(key: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", key).lower()


def parse_payload(text: str) -> dict:
    try:
        obj = json.loads(text) if text and text.strip() else {}
    except (ValueError, TypeError):
        return {}
    return obj if isinstance(obj, dict) else {}


def normalize_payload(raw: object) -> dict:
    if not isinstance(raw, dict):
        return {}
    out = {to_snake(str(key)): value for key, value in raw.items()}
    sid = out.get("session_id")
    if isinstance(sid, str):
        raw_sid = sid.strip()
        out["raw_session_id"] = raw_sid
        bare = raw_sid[len("session_"):] if raw_sid.startswith("session_") else raw_sid
        out["session_id"] = bare.lower()
    return out


def valid_session_id(sid: object) -> bool:
    return isinstance(sid, str) and bool(SESSION_ID_RE.match(sid))


def project_dir_from(payload: dict, env) -> str | None:
    for candidate in (payload.get("cwd"), payload.get("workspace_root"), env.get("CLAUDE_PROJECT_DIR")):
        if isinstance(candidate, str) and candidate.strip():
            return _strip_dir(candidate)
    return None


# ── Claude Code's session-directory slug (port of pipeline/slug.py) ──────────

def _utf16_units(text: str) -> list[int]:
    raw = text.encode("utf-16-le", "surrogatepass")
    return [raw[i] | (raw[i + 1] << 8) for i in range(0, len(raw), 2)]


def _base36(value: int) -> str:
    if value == 0:
        return "0"
    digits = []
    while value:
        value, digit = divmod(value, 36)
        digits.append(_BASE36[digit])
    return "".join(reversed(digits))


def path_hash(path: str) -> str:
    acc = 0
    for unit in _utf16_units(path):
        acc = (acc * 31 + unit) & 0xFFFFFFFF
    if acc >= 0x80000000:
        acc -= 0x100000000
    return _base36(abs(acc))


def session_dir_slug(path: str) -> str:
    if len(path) >= 2 and path[1] == ":" and "A" <= path[0] <= "Z":
        path = path[0].lower() + path[1:]
    slug = "".join(c if c.isascii() and c.isalnum() else "-" * (2 if ord(c) > 0xFFFF else 1) for c in path)
    if len(slug) <= SLUG_MAX:
        return slug
    return slug[:SLUG_MAX] + "-" + path_hash(path)


# ── configuration ────────────────────────────────────────────────────────────

@dataclass
class BridgeConfig:
    plugin_root: str
    bridge_root: str
    bash: str | None
    home: str
    grok_home: str
    kimi_home: str
    remember_config: str | None
    data_dir: str | None

    @classmethod
    def from_env(cls, env, exists=os.path.exists, which=shutil.which) -> "BridgeConfig":
        home = forward(env.get("HOME") or env.get("USERPROFILE") or os.path.expanduser("~"))
        home = _strip_dir(home)
        plugin_root = _strip_dir(env.get("REMEMBER_BRIDGE_PLUGIN_ROOT") or DEFAULT_PLUGIN_ROOT)
        bridge_root = _strip_dir(env.get("REMEMBER_BRIDGE_ROOT") or DEFAULT_BRIDGE_ROOT)
        override = env.get("REMEMBER_BRIDGE_BASH")
        if override:
            bash = forward(override)
        elif exists(GIT_BASH):
            bash = GIT_BASH
        else:
            found = which("bash")
            bash = forward(found) if found else None
        grok_home = _strip_dir(env.get("GROK_HOME") or (home + "/.grok"))
        kimi_home = _strip_dir(env.get("KIMI_CODE_HOME") or (home + "/.kimi-code"))
        remember_config, data_dir = _find_remember_config(plugin_root, home, exists)
        return cls(plugin_root, bridge_root, bash, home, grok_home, kimi_home, remember_config, data_dir)

    def host_root(self, host: str) -> str:
        return f"{self.bridge_root}/{host}"

    def script_path(self, event: str) -> str | None:
        name = HOOK_SCRIPTS.get(event)
        return f"{self.plugin_root}/scripts/{name}" if name else None


def _find_remember_config(plugin_root: str, home: str, exists) -> tuple[str | None, str | None]:
    """First config file carrying data_dir, in Remember's own layering order."""
    for candidate in (f"{plugin_root}/config.json", f"{home}/.remember/config.json"):
        if not exists(candidate):
            continue
        try:
            with open(candidate, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            continue
        data_dir = data.get("data_dir") if isinstance(data, dict) else None
        if isinstance(data_dir, str) and data_dir.strip():
            return candidate, _strip_dir(data_dir)
    return None, None


def store_dir_for(cfg: BridgeConfig, slug: str | None) -> str | None:
    if not cfg.data_dir or not slug:
        return None
    return cfg.data_dir.replace("{slug}", slug)


def upstream_env(cfg: BridgeConfig, host: str, project: str | None, base_env) -> dict:
    env = {key: value for key, value in base_env.items() if key != "REMEMBER_TRANSCRIPT_PATH"}
    env["CLAUDE_PLUGIN_ROOT"] = cfg.plugin_root
    env["PLUGIN_ROOT"] = cfg.plugin_root
    if project:
        env["CLAUDE_PROJECT_DIR"] = project
    env["CLAUDE_CONFIG_DIR"] = cfg.host_root(host)
    if not env.get("HOME"):
        env["HOME"] = cfg.home
    return env


# ── translators: native records -> Claude-shaped records ─────────────────────

def _record(role: str, blocks: list) -> dict:
    return {"type": role, "message": {"role": role, "content": blocks}}


def _text_block(text: str) -> dict:
    return {"type": "text", "text": text}


def _tool_block(call_id, name, args) -> dict:
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except ValueError:
            args = {"raw": args}
    if not isinstance(args, dict):
        args = {}
    block = {"type": "tool_use", "name": name or "?", "input": args}
    if call_id:
        block["id"] = call_id
    return block


class GrokTranslator:
    """`chat_history.jsonl`: one record per line, roles as `type`."""

    SKIP = frozenset({"system", "reasoning", "tool_result", "backend_tool_call"})

    def __init__(self) -> None:
        self.unknown: dict[str, int] = {}

    def idle(self) -> bool:
        return True

    def flush(self) -> list:
        return []

    def translate(self, obj) -> list:
        if not isinstance(obj, dict) or "type" not in obj:
            self.unknown["<none>"] = self.unknown.get("<none>", 0) + 1
            return []
        kind = obj.get("type")
        if kind in self.SKIP:
            return []
        if kind == "user":
            if "synthetic_reason" in obj:
                return []
            texts = [cleaned for cleaned in (self._user_text(t) for t in _texts_of(obj.get("content"))) if cleaned]
            return [_record("user", [_text_block("\n".join(texts))])] if texts else []
        if kind == "assistant":
            blocks = [_text_block(t) for t in _texts_of(obj.get("content"))]
            for call in obj.get("tool_calls") or []:
                if isinstance(call, dict):
                    blocks.append(_tool_block(call.get("id"), call.get("name"), call.get("arguments")))
            return [_record("assistant", blocks)] if blocks else []
        self.unknown[str(kind)] = self.unknown.get(str(kind), 0) + 1
        return []

    @staticmethod
    def _user_text(text: str) -> str | None:
        stripped = text.strip()
        if not stripped:
            return None
        if "<user_query>" in stripped:
            inner = "\n".join(m.strip() for m in USER_QUERY_RE.findall(stripped) if m.strip())
            return inner or None
        if stripped.startswith("<user_info>") or "<system-reminder>" in stripped:
            return None
        return stripped


def _texts_of(content) -> list[str]:
    if isinstance(content, str):
        return [content.strip()] if content.strip() else []
    texts = []
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text")
                if isinstance(text, str) and text.strip():
                    texts.append(text.strip())
    return texts


class KimiTranslator:
    """`agents/main/wire.jsonl`: prompts at `turn.prompt`, answers as loop events per step."""

    LOOP_KNOWN = frozenset({"step.begin", "content.part", "tool.call", "tool.result", "step.end"})
    FLUSH_ON = frozenset({"turn.ended", "turn.step.interrupted", "turn.cancel", "prompt.aborted"})

    def __init__(self) -> None:
        self.step: dict | None = None
        self.unknown: dict[str, int] = {}

    def idle(self) -> bool:
        return self.step is None

    def flush(self) -> list:
        step, self.step = self.step, None
        if not step:
            return []
        blocks = []
        if step["text"]:
            blocks.append(_text_block("\n".join(step["text"])))
        blocks.extend(step["tools"])
        return [_record("assistant", blocks)] if blocks else []

    def _ensure_step(self) -> dict:
        if self.step is None:
            self.step = {"text": [], "tools": []}
        return self.step

    def translate(self, obj) -> list:
        if not isinstance(obj, dict) or obj.get("agentId", "main") != "main":
            return []
        kind = obj.get("type")
        if kind in ("turn.prompt", "turn.steer"):
            origin = obj.get("origin") or {}
            if not isinstance(origin, dict) or origin.get("kind") != "user":
                return []
            texts = _texts_of(obj.get("input"))
            return [_record("user", [_text_block("\n".join(texts))])] if texts else []
        if kind == "context.append_loop_event":
            event = obj.get("event") or {}
            etype = event.get("type") if isinstance(event, dict) else None
            if etype == "step.begin":
                out = self.flush()
                self.step = {"text": [], "tools": []}
                return out
            if etype == "content.part":
                part = event.get("part") or {}
                if isinstance(part, dict) and part.get("type") == "text":
                    text = part.get("text")
                    if isinstance(text, str) and text.strip():
                        self._ensure_step()["text"].append(text.strip())
                return []
            if etype == "tool.call":
                self._ensure_step()["tools"].append(_tool_block(event.get("toolCallId"), event.get("name"), event.get("args")))
                return []
            if etype == "step.end":
                return self.flush()
            if etype not in self.LOOP_KNOWN:
                self.unknown[str(etype)] = self.unknown.get(str(etype), 0) + 1
            return []
        if kind in self.FLUSH_ON:
            return self.flush()
        return []


def make_translator(host: str):
    return GrokTranslator() if host == "grok" else KimiTranslator()


# ── transcript location ──────────────────────────────────────────────────────

def grok_transcript(grok_home: str, session_id: str, cwd: str | None) -> str | None:
    matches = glob.glob(f"{glob.escape(_strip_dir(grok_home))}/sessions/*/{glob.escape(session_id)}/chat_history.jsonl")
    if not matches:
        return None
    if len(matches) > 1 and cwd:
        want = _norm_cmp(cwd)
        for match in matches:
            encoded = os.path.basename(os.path.dirname(os.path.dirname(match)))
            if _norm_cmp(unquote(encoded)) == want:
                return forward(match)
    return forward(max(matches, key=os.path.getmtime))


def kimi_transcript(kimi_home: str, raw_session_id: str) -> str | None:
    home = _strip_dir(kimi_home)
    candidates = [raw_session_id]
    if not raw_session_id.startswith("session_"):
        candidates.append("session_" + raw_session_id)
    index = f"{home}/session_index.jsonl"
    found = None
    if os.path.isfile(index):
        try:
            with open(index, encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    try:
                        row = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(row, dict) and row.get("sessionId") in candidates and isinstance(row.get("sessionDir"), str):
                        found = row["sessionDir"]
        except OSError:
            found = None
    if found:
        wire = f"{_strip_dir(found)}/agents/main/wire.jsonl"
        if os.path.isfile(wire):
            return wire
    matches = []
    for candidate in candidates:
        matches.extend(glob.glob(f"{glob.escape(home)}/sessions/*/{glob.escape(candidate)}/agents/main/wire.jsonl"))
    if matches:
        return forward(max(matches, key=os.path.getmtime))
    return None


def locate_native(cfg: BridgeConfig, host: str, raw_sid: str, sid: str, project: str | None) -> str | None:
    if host == "grok":
        return grok_transcript(cfg.grok_home, sid, project)
    return kimi_transcript(cfg.kimi_home, raw_sid or sid)


# ── incremental mirror ───────────────────────────────────────────────────────

@dataclass
class MirrorResult:
    native: str
    mirror: str
    new_records: int = 0
    offset: int = 0
    corrupt: int = 0
    note: str = ""
    unknown: dict = field(default_factory=dict)


def _load_state(state_path: str) -> dict:
    try:
        with open(state_path, encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_state(state_path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(state_path), exist_ok=True)
    tmp = state_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle)
    os.replace(tmp, state_path)


def mirror_transcript(host: str, native: str, mirror: str, state_path: str, session_id: str) -> MirrorResult:
    result = MirrorResult(native=native, mirror=mirror)
    if not os.path.isfile(native):
        result.note = "native transcript missing"
        return result
    state = _load_state(state_path)
    offset = state.get("offset", 0) if isinstance(state.get("offset"), int) else 0
    size = os.path.getsize(native)
    if offset > size:
        offset = 0
        result.note = "native shrank; restarted from 0"
    translator = make_translator(host)
    records: list[dict] = []
    pending: list[dict] = []
    commit = offset
    with open(native, "rb") as handle:
        handle.seek(offset)
        while True:
            line = handle.readline()
            if not line or not line.endswith(b"\n"):
                break
            try:
                obj = json.loads(line.decode("utf-8", "replace"))
            except ValueError:
                result.corrupt += 1
                obj = None
            if obj is not None:
                pending.extend(translator.translate(obj))
            if translator.idle():
                commit = handle.tell()
                records.extend(pending)
                pending = []
    if records:
        os.makedirs(os.path.dirname(mirror), exist_ok=True)
        needs_newline = False
        if os.path.isfile(mirror) and os.path.getsize(mirror) > 0:
            with open(mirror, "rb") as existing:
                existing.seek(-1, os.SEEK_END)
                needs_newline = existing.read(1) != b"\n"
        chunk = "".join(json.dumps({**rec, "sessionId": session_id, "bridgeHost": host}, ensure_ascii=False) + "\n" for rec in records)
        with open(mirror, "a", encoding="utf-8") as out:
            if needs_newline:
                out.write("\n")
            out.write(chunk)
    _save_state(state_path, {"native": forward(native), "offset": commit, "native_size": size, "updated_utc": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
    result.new_records = len(records)
    result.offset = commit
    result.unknown = dict(translator.unknown)
    return result


# ── upstream runner ──────────────────────────────────────────────────────────

@dataclass
class UpstreamResult:
    rc: int | None
    stdout: str
    stderr: str
    elapsed_ms: int


def _read_and_discard(path: str) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            text = handle.read()
    except OSError:
        text = ""
    try:
        os.unlink(path)
    except OSError:
        pass
    return text


def run_upstream(cfg: BridgeConfig, script: str, payload_text: str, env: dict, cwd: str | None) -> UpstreamResult:
    """Run `bash <script>` with the payload on stdin; wait for that child only.

    stdout/stderr go to temp files, not pipes: a backgrounded grandchild that
    inherits a pipe would otherwise keep it open and block us until it exits.
    """
    started = time.monotonic()
    if not cfg.bash:
        return UpstreamResult(-1, "", "bash not found (REMEMBER_BRIDGE_BASH, Git for Windows, PATH)", 0)
    out_fd, out_path = tempfile.mkstemp(prefix="remember-bridge-", suffix=".out")
    err_fd, err_path = tempfile.mkstemp(prefix="remember-bridge-", suffix=".err")
    try:
        with os.fdopen(out_fd, "wb") as out_handle, os.fdopen(err_fd, "wb") as err_handle:
            proc = subprocess.Popen(
                [cfg.bash, script],
                stdin=subprocess.PIPE,
                stdout=out_handle,
                stderr=err_handle,
                env=env,
                cwd=cwd if cwd and os.path.isdir(cwd) else None,
            )
    except OSError as exc:
        _read_and_discard(out_path)
        _read_and_discard(err_path)
        return UpstreamResult(-1, "", f"bash not found or not runnable: {cfg.bash} ({exc})", int((time.monotonic() - started) * 1000))
    try:
        if proc.stdin is not None:
            proc.stdin.write(payload_text.encode("utf-8"))
            proc.stdin.close()
    except OSError:
        pass
    try:
        rc: int | None = proc.wait(timeout=UPSTREAM_WAIT_SECONDS)
    except subprocess.TimeoutExpired:
        rc = None
    elapsed = int((time.monotonic() - started) * 1000)
    return UpstreamResult(rc, _read_and_discard(out_path), _read_and_discard(err_path), elapsed)


# ── inject-once cache ────────────────────────────────────────────────────────

def inject_cache_path(host_root: str, sid: str) -> str:
    return f"{host_root}/inject/{sid}.md"


def store_inject(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def pop_inject(path: str) -> str:
    try:
        with open(path, encoding="utf-8", newline="") as handle:
            text = handle.read()
    except OSError:
        return ""
    try:
        os.unlink(path)
    except OSError:
        pass
    return text


def clip_context(text: str) -> str:
    if len(text) <= INJECT_CLIP:
        return text
    return text[: INJECT_CLIP - len(CLIP_MARKER)] + CLIP_MARKER


# ── logging ──────────────────────────────────────────────────────────────────

class BridgeLogger:
    def __init__(self, host_root: str | None, store_dir: str | None, stderr) -> None:
        self.targets = []
        if host_root:
            self.targets.append(f"{host_root}/logs/bridge.log")
        if store_dir:
            self.targets.append(f"{store_dir}/logs/memory-{_dt.datetime.now().strftime('%Y-%m-%d')}.log")
        self.stderr = stderr

    def line(self, **fields) -> None:
        stamp = _dt.datetime.now().strftime("%H:%M:%S")
        body = " ".join(f"{key}={_log_value(value)}" for key, value in fields.items() if value is not None)
        text = f"{stamp} [bridge] {body}\n"
        written = False
        for target in self.targets:
            try:
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with open(target, "a", encoding="utf-8") as handle:
                    handle.write(text)
                written = True
            except OSError:
                continue
        if not written and self.stderr is not None:
            try:
                self.stderr.write(text)
            except Exception:
                pass


def _log_value(value) -> str:
    text = str(value).replace("\r", " ").replace("\n", " ")
    return text if text else "-"


# ── configuration report ─────────────────────────────────────────────────────

def print_config(cfg: BridgeConfig, stdout) -> None:
    lines = [
        "remember-bridge: Grok/Kimi hook bridge for the pinned Remember plugin",
        f"plugin_root={cfg.plugin_root} (exists={'yes' if os.path.isdir(cfg.plugin_root) else 'no'})",
        f"bridge_root={cfg.bridge_root}",
        f"bash={cfg.bash or 'not found'} (exists={'yes' if cfg.bash and os.path.isfile(cfg.bash) else 'no'})",
        f"home={cfg.home}",
        f"grok_home={cfg.grok_home} (exists={'yes' if os.path.isdir(cfg.grok_home) else 'no'})",
        f"kimi_home={cfg.kimi_home} (exists={'yes' if os.path.isdir(cfg.kimi_home) else 'no'})",
        f"remember_config={cfg.remember_config or 'none'}",
        f"data_dir={cfg.data_dir or 'none (Remember will use its own default)'}",
    ]
    for event, script in HOOK_SCRIPTS.items():
        if script:
            path = cfg.script_path(event)
            lines.append(f"hook {event}: {path} (exists={'yes' if path and os.path.isfile(path) else 'no'})")
        else:
            lines.append(f"hook {event}: bridge-only (inject-once on Grok, no-op on Kimi)")
    lines.append("usage: py -3 Invoke-RememberBridge.py --host grok|kimi --event SessionStart|UserPromptSubmit|PreToolUse|PostToolUse|SessionEnd < payload.json")
    stdout.write("\n".join(lines) + "\n")


# ── argv ─────────────────────────────────────────────────────────────────────

def parse_args(argv: list[str]) -> tuple[str | None, str | None, list[str]]:
    host = event = None
    problems = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("--host", "--event") and i + 1 < len(argv):
            if arg == "--host":
                host = argv[i + 1]
            else:
                event = argv[i + 1]
            i += 2
            continue
        if arg.startswith("--host="):
            host = arg.split("=", 1)[1]
        elif arg.startswith("--event="):
            event = arg.split("=", 1)[1]
        elif arg in ("-h", "--help"):
            problems.append("help")
        else:
            problems.append(f"unexpected argument {arg!r}")
        i += 1
    return host, event, problems


# ── main ─────────────────────────────────────────────────────────────────────

def main(argv=None, *, stdin=None, stdout=None, stderr=None, env=None, runner=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    stdin = sys.stdin if stdin is None else stdin
    stdout = sys.stdout if stdout is None else stdout
    stderr = sys.stderr if stderr is None else stderr
    env = os.environ if env is None else env
    runner = runner or run_upstream
    host, event, problems = parse_args(argv)
    cfg = BridgeConfig.from_env(env)
    if host is None and event is None and not problems:
        print_config(cfg, stdout)
        return 0
    if "help" in problems:
        print_config(cfg, stdout)
        return 0
    try:
        return _run_event(cfg, host, event, problems, stdin, stdout, stderr, env, runner)
    except Exception as exc:  # a hook must never block the host
        try:
            BridgeLogger(cfg.host_root(host) if host in HOSTS else None, None, stderr).line(host=host, event=event, error=f"{type(exc).__name__}: {exc}")
        except Exception:
            pass
        return 0
    finally:
        try:
            stdout.flush()
        except Exception:
            pass


def _run_event(cfg, host, event, problems, stdin, stdout, stderr, env, runner) -> int:
    if host not in HOSTS:
        BridgeLogger(None, None, stderr).line(host=host, event=event, error="unknown host; expected grok or kimi")
        return 0
    host_root = cfg.host_root(host)
    if event not in HOOK_SCRIPTS or problems:
        BridgeLogger(host_root, None, stderr).line(host=host, event=event, error="unsupported event or arguments: " + "; ".join(problems or ["expected SessionStart|UserPromptSubmit|PreToolUse|PostToolUse|SessionEnd"]))
        return 0

    started = time.monotonic()
    payload = normalize_payload(parse_payload(stdin.read()))
    sid = payload.get("session_id") or ""
    if not sid and host == "grok":
        sid = (env.get("GROK_SESSION_ID") or "").strip().lower()
    raw_sid = payload.get("raw_session_id") or sid
    sid_ok = valid_session_id(sid)
    project = project_dir_from(payload, env)
    slug = session_dir_slug(project) if project else None
    logger = BridgeLogger(host_root, store_dir_for(cfg, slug), stderr)
    mirror_path = f"{host_root}/projects/{slug}/{sid}.jsonl" if sid_ok and slug else None
    fields: dict = {"host": host, "event": event, "session": sid or "-", "project": project or "-"}
    if not sid_ok:
        fields["session_note"] = "unusable session id, capture disabled"

    if event == "PreToolUse":
        injected = "no"
        if host == "grok" and sid_ok:
            cached = pop_inject(inject_cache_path(host_root, sid))
            if cached.strip():
                stdout.write(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": clip_context(cached)}}, ensure_ascii=False) + "\n")
                injected = "yes"
        logger.line(**fields, injected=injected, upstream="none", ms=int((time.monotonic() - started) * 1000))
        return 0

    if event in CAPTURE_EVENTS:
        if not sid_ok or not project:
            fields["capture"] = "skipped (no usable session id or project)"
            logger.line(**fields, upstream="none", ms=int((time.monotonic() - started) * 1000))
            return 0
        native = locate_native(cfg, host, raw_sid, sid, project)
        if native and mirror_path:
            mirrored = mirror_transcript(host, native, mirror_path, f"{host_root}/state/{sid}.json", sid)
            fields.update(native=native, native_offset=mirrored.offset, new_records=mirrored.new_records)
            if mirrored.corrupt:
                fields["corrupt_lines"] = mirrored.corrupt
            if mirrored.unknown:
                fields["unknown_records"] = json.dumps(mirrored.unknown, sort_keys=True)
            if mirrored.note:
                fields["mirror_note"] = mirrored.note
        else:
            fields["mirror_note"] = "native transcript not found"

    prefix = ""
    if event == "UserPromptSubmit" and host == "kimi" and sid_ok:
        prefix = pop_inject(inject_cache_path(host_root, sid))
    fields["injected"] = "yes" if prefix.strip() else "no"

    script = cfg.script_path(event)
    fields["upstream"] = os.path.basename(script) if script else "none"
    if mirror_path and os.path.isfile(mirror_path):
        fields["mirror"] = mirror_path
    if not script or not os.path.isfile(script):
        fields["error"] = f"upstream script missing: {script}"
        if prefix:
            stdout.write(prefix)
        logger.line(**fields, ms=int((time.monotonic() - started) * 1000))
        return 0

    upstream_payload: dict = {"hook_event_name": event}
    if sid_ok:
        upstream_payload["session_id"] = sid
    if mirror_path and os.path.isfile(mirror_path):
        upstream_payload["transcript_path"] = mirror_path
    if project:
        upstream_payload["cwd"] = project
    if event == "SessionStart" and payload.get("source") in SESSION_START_SOURCES:
        upstream_payload["source"] = payload["source"]
    if event == "SessionEnd":
        reason = payload.get("reason")
        if isinstance(reason, str) and REASON_RE.match(reason):
            upstream_payload["reason"] = reason

    result = runner(cfg, script, json.dumps(upstream_payload, ensure_ascii=False) + "\n", upstream_env(cfg, host, project, env), project)
    fields["rc"] = "timeout" if result.rc is None else result.rc
    fields["upstream_ms"] = result.elapsed_ms
    if result.stderr.strip():
        fields["stderr"] = result.stderr.strip()[-300:]

    if event == "SessionStart":
        if result.stdout.strip():
            if sid_ok:
                store_inject(inject_cache_path(host_root, sid), result.stdout)
                fields["cached_chars"] = len(result.stdout)
            else:
                fields["cache_note"] = "memory block dropped: no usable session id"
    elif event == "UserPromptSubmit":
        stdout.write(prefix + result.stdout)
    logger.line(**fields, ms=int((time.monotonic() - started) * 1000))
    return 0


if __name__ == "__main__":
    sys.exit(main())
