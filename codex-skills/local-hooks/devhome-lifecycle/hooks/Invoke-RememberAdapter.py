"""Privacy-preserving process bridge for the machine-local Remember adapter."""

import argparse
import ctypes
import hashlib
import hmac
import json
import msvcrt
import os
import re
import subprocess
import sys
import tempfile
import threading
from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, ContextManager, Iterator

ALLOWED_EVENTS = frozenset({"SessionStart", "UserPromptSubmit", "PostToolUse", "Stop"})
PYTHON_EXE = Path(r"C:\Program Files\Python314\python.exe")
GIT_BASH_EXE = Path(r"C:\Program Files\Git\bin\bash.exe")
HOOK_SCRIPTS = {
    "SessionStart": "session-start-hook.sh",
    "UserPromptSubmit": "user-prompt-hook.sh",
    "PostToolUse": "post-tool-hook.sh",
    "Stop": "post-tool-hook.sh",
}
UPSTREAM_TIMEOUTS = {
    "SessionStart": 15.0,
    "UserPromptSubmit": 3.0,
    "PostToolUse": 3.0,
    "Stop": 3.0,
}
DIAGNOSTIC_LIMIT_BYTES = 1024 * 1024
CREATE_SUSPENDED = 0x00000004
JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS = 9
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
TH32CS_SNAPTHREAD = 0x00000004
THREAD_SUSPEND_RESUME = 0x0002
THREAD_TERMINATE = 0x0001
INVALID_DWORD = 0xFFFFFFFF
ERROR_NOT_FOUND = 1168
ERROR_OPERATION_ABORTED = 995
ERROR_BROKEN_PIPE = 109
ERROR_NO_DATA = 232
PAYLOAD_WRITE_CHUNK_BYTES = 1024
PIPE_NOWAIT = 0x00000001
PAYLOAD_PIPE_POLL_SECONDS = 0.001
SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
VERSION_PATTERN = re.compile(r"^\d+(?:\.\d+)*$")
MAX_SOURCE_LINE_BYTES = 8 * 1024 * 1024
CHECKPOINT_SCHEMA_VERSION = 1
CHECKPOINT_INTEGRITY_FIELDS = (
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


class AdapterError(RuntimeError):
    """A bounded adapter failure safe for conversion to fail-open output."""


@dataclass(frozen=True)
class HookContext:
    event: str
    session_id: str
    cwd: Path
    transcript_path: Path


@dataclass(frozen=True)
class AdapterLayout:
    root: Path
    claude_config: Path
    checkpoints: Path
    locks: Path
    logs: Path

    @classmethod
    def for_home(cls, codex_home: Path) -> "AdapterLayout":
        root = Path(codex_home) / "remember-adapter"
        return cls(
            root=root,
            claude_config=root / "claude-config",
            checkpoints=root / "checkpoints",
            locks=root / "locks",
            logs=root / "logs",
        )

    def mirror_path(self, context: HookContext) -> Path:
        return (
            self.claude_config
            / "projects"
            / slug_project(context.cwd)
            / f"{context.session_id}.jsonl"
        )

    def checkpoint_path(self, context: HookContext) -> Path:
        return self.checkpoints / f"{context.session_id}.json"


@dataclass(frozen=True)
class SyncResult:
    source_offset: int
    mirror_bytes: int
    mirror_lines: int
    translated_records: int


class _FailOpenArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise AdapterError("arguments-invalid")


class _JobObjectBasicLimitInformation(ctypes.Structure):
    _fields_ = (
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    )


class _IoCounters(ctypes.Structure):
    _fields_ = (
        ("ReadOperationCount", ctypes.c_uint64),
        ("WriteOperationCount", ctypes.c_uint64),
        ("OtherOperationCount", ctypes.c_uint64),
        ("ReadTransferCount", ctypes.c_uint64),
        ("WriteTransferCount", ctypes.c_uint64),
        ("OtherTransferCount", ctypes.c_uint64),
    )


class _JobObjectExtendedLimitInformation(ctypes.Structure):
    _fields_ = (
        ("BasicLimitInformation", _JobObjectBasicLimitInformation),
        ("IoInfo", _IoCounters),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    )


class _ThreadEntry32(ctypes.Structure):
    _fields_ = (
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ThreadID", wintypes.DWORD),
        ("th32OwnerProcessID", wintypes.DWORD),
        ("tpBasePri", wintypes.LONG),
        ("tpDeltaPri", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
    )


_KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)
_KERNEL32.CreateJobObjectW.argtypes = (ctypes.c_void_p, wintypes.LPCWSTR)
_KERNEL32.CreateJobObjectW.restype = wintypes.HANDLE
_KERNEL32.SetInformationJobObject.argtypes = (
    wintypes.HANDLE,
    ctypes.c_int,
    ctypes.c_void_p,
    wintypes.DWORD,
)
_KERNEL32.SetInformationJobObject.restype = wintypes.BOOL
_KERNEL32.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
_KERNEL32.AssignProcessToJobObject.restype = wintypes.BOOL
_KERNEL32.TerminateJobObject.argtypes = (wintypes.HANDLE, wintypes.UINT)
_KERNEL32.TerminateJobObject.restype = wintypes.BOOL
_KERNEL32.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
_KERNEL32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
_KERNEL32.Thread32First.argtypes = (wintypes.HANDLE, ctypes.POINTER(_ThreadEntry32))
_KERNEL32.Thread32First.restype = wintypes.BOOL
_KERNEL32.Thread32Next.argtypes = (wintypes.HANDLE, ctypes.POINTER(_ThreadEntry32))
_KERNEL32.Thread32Next.restype = wintypes.BOOL
_KERNEL32.OpenThread.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
_KERNEL32.OpenThread.restype = wintypes.HANDLE
_KERNEL32.ResumeThread.argtypes = (wintypes.HANDLE,)
_KERNEL32.ResumeThread.restype = wintypes.DWORD
_KERNEL32.CancelSynchronousIo.argtypes = (wintypes.HANDLE,)
_KERNEL32.CancelSynchronousIo.restype = wintypes.BOOL
_KERNEL32.WriteFile.argtypes = (
    wintypes.HANDLE,
    ctypes.c_void_p,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
    ctypes.c_void_p,
)
_KERNEL32.WriteFile.restype = wintypes.BOOL
_KERNEL32.SetNamedPipeHandleState.argtypes = (
    wintypes.HANDLE,
    ctypes.POINTER(wintypes.DWORD),
    ctypes.c_void_p,
    ctypes.c_void_p,
)
_KERNEL32.SetNamedPipeHandleState.restype = wintypes.BOOL
_KERNEL32.CloseHandle.argtypes = (wintypes.HANDLE,)
_KERNEL32.CloseHandle.restype = wintypes.BOOL


class _WindowsJob:
    """Own one Windows child tree and kill remaining members when closed."""

    def __init__(self) -> None:
        self._handle = _KERNEL32.CreateJobObjectW(None, None)
        if not self._handle:
            raise AdapterError("job-create-failed") from ctypes.WinError(
                ctypes.get_last_error()
            )
        limits = _JobObjectExtendedLimitInformation()
        limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not _KERNEL32.SetInformationJobObject(
            self._handle,
            JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
            ctypes.byref(limits),
            ctypes.sizeof(limits),
        ):
            error = ctypes.WinError(ctypes.get_last_error())
            self.close()
            raise AdapterError("job-configuration-failed") from error

    def assign(self, process: subprocess.Popen[str]) -> None:
        if not _KERNEL32.AssignProcessToJobObject(
            self._handle, wintypes.HANDLE(int(process._handle))
        ):
            raise AdapterError("job-assignment-failed") from ctypes.WinError(
                ctypes.get_last_error()
            )

    def terminate(self) -> None:
        if self._handle and not _KERNEL32.TerminateJobObject(self._handle, 1):
            raise AdapterError("job-termination-failed") from ctypes.WinError(
                ctypes.get_last_error()
            )

    def close(self) -> None:
        if self._handle:
            _KERNEL32.CloseHandle(self._handle)
            self._handle = None


class _PayloadWriter:
    """Own an anonymous stdin pipe and a bounded, cancellable parent writer."""

    def __init__(self, payload: bytes) -> None:
        self._payload = payload
        self._read_fd: int | None = None
        self._write_fd: int | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._error: BaseException | None = None
        try:
            self._read_fd, self._write_fd = os.pipe()
            write_handle = wintypes.HANDLE(msvcrt.get_osfhandle(self._write_fd))
            mode = wintypes.DWORD(PIPE_NOWAIT)
            if not _KERNEL32.SetNamedPipeHandleState(
                write_handle, ctypes.byref(mode), None, None
            ):
                raise AdapterError("stdin-pipe-nonblocking-failed") from ctypes.WinError(
                    ctypes.get_last_error()
                )
        except BaseException:
            self.close_parent_read()
            self._close_write_fd()
            raise

    @property
    def child_read_fd(self) -> int:
        if self._read_fd is None:
            raise AdapterError("stdin-read-pipe-closed")
        return self._read_fd

    def close_parent_read(self) -> None:
        if self._read_fd is not None:
            os.close(self._read_fd)
            self._read_fd = None

    def start(self) -> None:
        if self._thread is not None:
            raise AdapterError("stdin-writer-already-started")
        thread = threading.Thread(
            target=self._write_payload,
            name=f"RememberPayloadWriter-{id(self):x}",
            daemon=False,
        )
        thread.start()
        self._thread = thread

    def _write_payload(self) -> None:
        try:
            handle = wintypes.HANDLE(msvcrt.get_osfhandle(self._write_fd))
            payload = memoryview(self._payload)
            offset = 0
            while offset < len(self._payload) and not self._stop.is_set():
                chunk_size = min(PAYLOAD_WRITE_CHUNK_BYTES, len(self._payload) - offset)
                chunk = (ctypes.c_char * chunk_size).from_buffer_copy(
                    payload[offset : offset + chunk_size]
                )
                written = wintypes.DWORD()
                if not _KERNEL32.WriteFile(
                    handle,
                    chunk,
                    chunk_size,
                    ctypes.byref(written),
                    None,
                ):
                    error_code = ctypes.get_last_error()
                    if error_code in {
                        ERROR_OPERATION_ABORTED,
                        ERROR_BROKEN_PIPE,
                    }:
                        return
                    if error_code == ERROR_NO_DATA:
                        self._stop.wait(PAYLOAD_PIPE_POLL_SECONDS)
                        continue
                    raise AdapterError("stdin-write-failed") from ctypes.WinError(
                        error_code
                    )
                if written.value == 0:
                    self._stop.wait(PAYLOAD_PIPE_POLL_SECONDS)
                    continue
                offset += written.value
        except BaseException as error:
            self._error = error
        finally:
            self._close_write_fd()

    def close(self) -> None:
        """Stop delivery and join within a fixed bound, cancelling blocked I/O."""
        self.close_parent_read()
        thread = self._thread
        if thread is None:
            self._close_write_fd()
            return
        self._stop.set()
        if thread.is_alive():
            try:
                self._cancel_writer_io(thread)
            except BaseException:
                pass
            thread.join(1.0)
        self._close_write_fd()
        if thread.is_alive():
            thread.join(1.0)
        if thread.is_alive():
            raise AdapterError("stdin-writer-stuck")

    def raise_if_failed(self) -> None:
        if self._error is not None:
            raise AdapterError("stdin-writer-failed") from self._error

    def _cancel_writer_io(self, thread: threading.Thread) -> None:
        if thread.native_id is None:
            raise AdapterError("stdin-writer-native-id-missing")
        thread_handle = _KERNEL32.OpenThread(
            THREAD_TERMINATE, False, thread.native_id
        )
        if not thread_handle:
            raise AdapterError("stdin-writer-open-failed") from ctypes.WinError(
                ctypes.get_last_error()
            )
        try:
            if not _KERNEL32.CancelSynchronousIo(thread_handle):
                error_code = ctypes.get_last_error()
                if error_code != ERROR_NOT_FOUND:
                    raise AdapterError("stdin-writer-cancel-failed") from ctypes.WinError(
                        error_code
                    )
        finally:
            _KERNEL32.CloseHandle(thread_handle)

    def _close_write_fd(self) -> None:
        if self._write_fd is not None:
            try:
                os.close(self._write_fd)
            except OSError:
                pass
            self._write_fd = None


def _resume_suspended_process(process: subprocess.Popen[str]) -> None:
    """Resume every initial thread only after its process belongs to the job."""
    snapshot = _KERNEL32.CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0)
    if snapshot == ctypes.c_void_p(-1).value:
        raise AdapterError("thread-snapshot-failed") from ctypes.WinError(
            ctypes.get_last_error()
        )
    resumed = 0
    try:
        entry = _ThreadEntry32()
        entry.dwSize = ctypes.sizeof(entry)
        present = _KERNEL32.Thread32First(snapshot, ctypes.byref(entry))
        while present:
            if entry.th32OwnerProcessID == process.pid:
                thread = _KERNEL32.OpenThread(
                    THREAD_SUSPEND_RESUME, False, entry.th32ThreadID
                )
                if not thread:
                    raise AdapterError("thread-open-failed") from ctypes.WinError(
                        ctypes.get_last_error()
                    )
                try:
                    if _KERNEL32.ResumeThread(thread) == INVALID_DWORD:
                        raise AdapterError("thread-resume-failed") from ctypes.WinError(
                            ctypes.get_last_error()
                        )
                    resumed += 1
                finally:
                    _KERNEL32.CloseHandle(thread)
            present = _KERNEL32.Thread32Next(snapshot, ctypes.byref(entry))
    finally:
        _KERNEL32.CloseHandle(snapshot)
    if resumed == 0:
        raise AdapterError("primary-thread-missing")


def discover_remember_plugin(codex_home: Path) -> Path:
    """Select the highest numeric Remember version containing every hook."""
    cache_root = (
        Path(codex_home)
        / "plugins"
        / "cache"
        / "claude-plugins-official"
        / "remember"
    )
    candidates: list[tuple[tuple[int, ...], Path]] = []
    try:
        children = cache_root.iterdir()
        for child in children:
            if not child.is_dir() or not VERSION_PATTERN.fullmatch(child.name):
                continue
            if all((child / "scripts" / script).is_file() for script in HOOK_SCRIPTS.values()):
                candidates.append((tuple(int(part) for part in child.name.split(".")), child))
    except OSError as error:
        raise AdapterError("remember-discovery-failed") from error
    if not candidates:
        raise AdapterError("remember-plugin-missing")
    return max(candidates, key=lambda candidate: candidate[0])[1]


def invoke_upstream(
    context: HookContext,
    layout: AdapterLayout,
    plugin_root: Path,
    raw_payload: str,
) -> subprocess.CompletedProcess[str]:
    """Run one unchanged Remember hook through the explicit Git Bash boundary."""
    claude_exe = Path.home() / ".local" / "bin" / "claude.exe"
    hook_name = HOOK_SCRIPTS.get(context.event)
    if hook_name is None:
        raise AdapterError("unsupported-event")
    hook_script = Path(plugin_root) / "scripts" / hook_name
    wrapper = Path(__file__).with_name("Invoke-RememberClaude.cmd")
    for executable, code in (
        (GIT_BASH_EXE, "git-bash-missing"),
        (claude_exe, "claude-missing"),
        (wrapper, "claude-wrapper-missing"),
    ):
        if not executable.is_file():
            raise AdapterError(code)
    if not hook_script.is_file():
        raise AdapterError("remember-hook-missing")

    layout.claude_config.mkdir(parents=True, exist_ok=True)
    upstream_env = os.environ.copy()
    upstream_env.update(
        {
            "CLAUDE_PLUGIN_ROOT": str(plugin_root),
            "CLAUDE_PROJECT_DIR": str(context.cwd),
            "CLAUDE_CONFIG_DIR": str(layout.claude_config),
            "REMEMBER_CLAUDE_BIN": str(wrapper),
            "REMEMBER_REAL_CLAUDE_BIN": str(claude_exe),
        }
    )
    command = [str(GIT_BASH_EXE), "--noprofile", "--norc", hook_script.as_posix()]
    return _run_contained_process(
        command,
        raw_payload,
        UPSTREAM_TIMEOUTS[context.event],
        upstream_env,
    )


def _run_contained_process(
    command: Sequence[str],
    raw_payload: str,
    timeout: float,
    environment: Mapping[str, str],
    *,
    job_factory: Callable[[], object] = _WindowsJob,
    resume_process: Callable[[subprocess.Popen[str]], None] = _resume_suspended_process,
) -> subprocess.CompletedProcess[str]:
    """Launch suspended, assign to an owned Job Object, then resume and wait."""
    job: object | None = None
    writer: _PayloadWriter | None = None
    process: subprocess.Popen[str] | None = None
    try:
        job = job_factory()
        writer = _PayloadWriter(raw_payload.encode("utf-8"))
        process = subprocess.Popen(
            command,
            stdin=writer.child_read_fd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
            creationflags=CREATE_SUSPENDED | subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        writer.close_parent_read()
        try:
            job.assign(process)
            resume_process(process)
            writer.start()
        except BaseException:
            job.close()
            _bounded_process_cleanup(process)
            raise
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as error:
            try:
                job.terminate()
            except BaseException:
                pass
            job.close()
            _bounded_process_cleanup(process)
            raise error
        writer.close()
        writer.raise_if_failed()
        return subprocess.CompletedProcess(
            list(command), process.returncode, stdout, stderr
        )
    finally:
        cleanup_error: BaseException | None = None
        for cleanup in (
            None if job is None else job.close,
            None if process is None else lambda: _close_process_handles(process),
            None if writer is None else writer.close,
        ):
            if cleanup is None:
                continue
            try:
                cleanup()
            except BaseException as error:
                if cleanup_error is None:
                    cleanup_error = error
        if cleanup_error is not None:
            raise cleanup_error


def _bounded_process_cleanup(process: subprocess.Popen[str]) -> None:
    """Bound pipe draining and root-handle cleanup after containment failure."""
    try:
        process.kill()
    except BaseException:
        pass
    try:
        process.communicate(timeout=1.0)
        return
    except BaseException:
        pass
    _close_process_pipes(process)
    try:
        process.wait(timeout=1.0)
    except BaseException:
        pass


def _close_process_pipes(process: subprocess.Popen[str]) -> None:
    for stream in (process.stdin, process.stdout, process.stderr):
        if stream is not None:
            try:
                stream.close()
            except BaseException:
                pass


def _close_process_handles(process: subprocess.Popen[str]) -> None:
    _close_process_pipes(process)
    try:
        process._handle.Close()
    except BaseException:
        pass


def _record_bounded_diagnostic(layout: AdapterLayout, line: str) -> None:
    """Append one fixed diagnostic line with bounded single-file rotation."""
    try:
        layout.logs.mkdir(parents=True, exist_ok=True)
        active = layout.logs / "adapter-errors.log"
        rotated = layout.logs / "adapter-errors.log.1"
        if active.exists() and active.stat().st_size > DIAGNOSTIC_LIMIT_BYTES:
            os.replace(active, rotated)
        with active.open("a", encoding="ascii", newline="\n") as stream:
            stream.write(f"{line}\n")
    except OSError:
        pass


def _record_bridge_diagnostic(layout: AdapterLayout, category: str) -> None:
    """Append one fixed bridge category without captured content."""
    _record_bounded_diagnostic(layout, f"adapter-failure {category}")


def _safe_emit(output: str) -> None:
    """Attempt one stdout emission without allowing write/flush failures to escape."""
    try:
        sys.stdout.write(output)
        sys.stdout.flush()
    except BaseException:
        try:
            with open(os.devnull, "w", encoding="utf-8") as devnull:
                os.dup2(devnull.fileno(), sys.stdout.fileno())
            sys.stdout.flush()
        except BaseException:
            pass


def main(argv: Sequence[str] | None = None) -> int:
    """Synchronize and invoke Remember, converting every failure to a neutral hook result."""
    try:
        output = "{}\n"
        layout: AdapterLayout | None = None
        stage = "initialization"
        try:
            configured_home = os.environ.get("CODEX_HOME")
            codex_home = (
                Path(configured_home)
                if configured_home is not None
                else Path.home() / ".codex"
            )
            layout = AdapterLayout.for_home(codex_home)

            stage = "arguments"
            parser = _FailOpenArgumentParser(add_help=False)
            parser.add_argument("--event", required=True, choices=tuple(HOOK_SCRIPTS))
            arguments = parser.parse_args(argv)

            stage = "input"
            raw_payload = sys.stdin.buffer.read().decode("utf-8")
            payload = json.loads(raw_payload)
            if not isinstance(payload, Mapping):
                raise AdapterError("payload-not-object")

            stage = "validation"
            context = validate_hook_payload(payload, arguments.event, codex_home)
            if context is None:
                raise AdapterError("payload-invalid")

            stage = "sync"
            sync_transcript(context, layout)
            stage = "discovery"
            plugin_root = discover_remember_plugin(codex_home)
            stage = "upstream"
            upstream_payload = raw_payload
            if context.event == "Stop":
                upstream_payload = json.dumps(
                    {
                        "hook_event_name": "PostToolUse",
                        "session_id": context.session_id,
                        "cwd": str(context.cwd),
                        "tool_name": "CodexStop",
                        "tool_input": {},
                        "tool_response": {},
                    },
                    separators=(",", ":"),
                )
            result = invoke_upstream(context, layout, plugin_root, upstream_payload)
            if result.returncode != 0:
                raise AdapterError("upstream-nonzero")
            output = result.stdout
        except BaseException:
            if layout is not None:
                _record_bridge_diagnostic(layout, stage)
        _safe_emit(output)
    except BaseException:
        pass
    return 0


def session_lock(
    layout: AdapterLayout, context: HookContext
) -> ContextManager[None]:
    """Return a non-blocking, one-byte lock for one Codex session."""
    return _session_lock(layout, context)


@contextmanager
def _session_lock(layout: AdapterLayout, context: HookContext) -> Iterator[None]:
    layout.locks.mkdir(parents=True, exist_ok=True)
    lock_path = layout.locks / f"{context.session_id}.lock"
    lock_stream = lock_path.open("a+b")
    acquired = False
    try:
        lock_stream.seek(0, os.SEEK_END)
        if lock_stream.tell() == 0:
            lock_stream.write(b"\0")
            lock_stream.flush()
        lock_stream.seek(0)
        try:
            msvcrt.locking(lock_stream.fileno(), msvcrt.LK_NBLCK, 1)
            acquired = True
        except OSError as error:
            raise AdapterError("lock-contention") from error
        yield
    finally:
        if acquired:
            try:
                lock_stream.seek(0)
                msvcrt.locking(lock_stream.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
        lock_stream.close()


def sync_transcript(context: HookContext, layout: AdapterLayout) -> SyncResult:
    """Incrementally mirror complete, privacy-filtered rollout records."""
    with session_lock(layout, context):
        return _sync_locked(context, layout)


def _sync_locked(context: HookContext, layout: AdapterLayout) -> SyncResult:
    checkpoint_path = layout.checkpoint_path(context)
    mirror_path = layout.mirror_path(context)
    checkpoint = _load_checkpoint(checkpoint_path)

    if checkpoint is not None and not _mirror_checkpoint_matches(mirror_path, checkpoint):
        checkpoint = None

    source_path = context.transcript_path.resolve(strict=False)
    try:
        source_stream = source_path.open("rb")
    except FileNotFoundError as error:
        if context.event != "SessionStart":
            raise AdapterError("source-missing") from error
        return _rebuild_mirror(context, layout, None, source_path)
    except OSError as error:
        raise AdapterError("source-open-failed") from error

    with source_stream:
        source_stat = os.fstat(source_stream.fileno())
        rebuild = (
            checkpoint is None
            or checkpoint["source_path"] != str(source_path)
            or checkpoint["source_dev"] != source_stat.st_dev
            or checkpoint["source_ino"] != source_stat.st_ino
            or source_stat.st_size < checkpoint["source_offset"]
        )
        if rebuild:
            return _rebuild_mirror(context, layout, source_stream, source_path)
        return _append_mirror(context, layout, source_stream, source_path, checkpoint)


def _load_checkpoint(path: Path) -> dict[str, object] | None:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except UnicodeError:
        return None
    try:
        value = json.loads(text)
    except (ValueError, RecursionError):
        return None
    if not isinstance(value, dict) or any(
        key not in value for key in (*CHECKPOINT_INTEGRITY_FIELDS, "integrity")
    ):
        return None
    schema_version = value["schema_version"]
    if type(schema_version) is not int or schema_version != CHECKPOINT_SCHEMA_VERSION:
        return None
    if not isinstance(value["source_path"], str):
        return None
    for key in ("source_offset", "mirror_bytes", "mirror_lines"):
        item = value[key]
        if not isinstance(item, int) or isinstance(item, bool) or item < 0:
            return None
    for key in ("source_dev", "source_ino"):
        item = value[key]
        if item is not None and (not isinstance(item, int) or isinstance(item, bool)):
            return None
    for key in ("mirror_dev", "mirror_ino", "mirror_size", "mirror_mtime_ns"):
        item = value[key]
        if not isinstance(item, int) or isinstance(item, bool) or item < 0:
            return None
    if (value["mirror_bytes"] == 0) != (value["mirror_lines"] == 0):
        return None
    if value["mirror_size"] != value["mirror_bytes"]:
        return None
    integrity = value["integrity"]
    if not isinstance(integrity, str) or not hmac.compare_digest(
        integrity, _checkpoint_integrity(value)
    ):
        return None
    return value


def _checkpoint_integrity(checkpoint: Mapping[str, object]) -> str:
    canonical = {key: checkpoint[key] for key in CHECKPOINT_INTEGRITY_FIELDS}
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _mirror_checkpoint_matches(path: Path, checkpoint: Mapping[str, object]) -> bool:
    try:
        mirror_stat = path.stat()
    except FileNotFoundError:
        return False
    except OSError as error:
        raise AdapterError("mirror-stat-failed") from error
    if (
        mirror_stat.st_dev != checkpoint["mirror_dev"]
        or mirror_stat.st_ino != checkpoint["mirror_ino"]
        or mirror_stat.st_size != checkpoint["mirror_size"]
        or mirror_stat.st_mtime_ns != checkpoint["mirror_mtime_ns"]
    ):
        return False
    if checkpoint["mirror_bytes"] == 0:
        return True
    try:
        with path.open("rb") as stream:
            stream.seek(checkpoint["mirror_bytes"] - 1)
            return stream.read(1) == b"\n"
    except OSError as error:
        raise AdapterError("mirror-read-failed") from error


def _rebuild_mirror(
    context: HookContext,
    layout: AdapterLayout,
    source_stream: BinaryIO | None,
    source_path: Path,
) -> SyncResult:
    mirror_path = layout.mirror_path(context)
    mirror_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w+b",
            prefix=f".{mirror_path.name}.",
            suffix=".tmp",
            dir=mirror_path.parent,
            delete=False,
        ) as mirror_stream:
            temporary_path = Path(mirror_stream.name)
            if source_stream is None:
                source_offset = 0
                translated_records = 0
                mirror_lines = 0
                source_stat = None
            else:
                source_stream.seek(0)
                source_offset, translated_records, mirror_lines = _copy_complete_records(
                    source_stream, mirror_stream, layout
                )
                source_stat = os.fstat(source_stream.fileno())
            mirror_stream.flush()
            os.fsync(mirror_stream.fileno())
            mirror_bytes = mirror_stream.tell()
        os.replace(temporary_path, mirror_path)
        temporary_path = None
        mirror_stat = mirror_path.stat()
    except OSError as error:
        raise AdapterError("mirror-rebuild-failed") from error
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    checkpoint = _checkpoint_value(
        source_path,
        source_stat,
        source_offset,
        mirror_bytes,
        mirror_lines,
        mirror_stat,
    )
    _replace_checkpoint(layout.checkpoint_path(context), checkpoint)
    return SyncResult(source_offset, mirror_bytes, mirror_lines, translated_records)


def _append_mirror(
    context: HookContext,
    layout: AdapterLayout,
    source_stream: BinaryIO,
    source_path: Path,
    checkpoint: dict[str, object],
) -> SyncResult:
    mirror_path = layout.mirror_path(context)
    mirror_path.parent.mkdir(parents=True, exist_ok=True)
    source_stream.seek(checkpoint["source_offset"])
    if os.fstat(source_stream.fileno()).st_size == checkpoint["source_offset"]:
        return SyncResult(
            checkpoint["source_offset"],
            checkpoint["mirror_bytes"],
            checkpoint["mirror_lines"],
            0,
        )
    try:
        with mirror_path.open("a+b") as mirror_stream:
            mirror_stream.seek(0, os.SEEK_END)
            source_offset, translated_records, added_lines = _copy_complete_records(
                source_stream, mirror_stream, layout
            )
            mirror_stream.flush()
            os.fsync(mirror_stream.fileno())
            mirror_bytes = mirror_stream.tell()
            mirror_stat = os.fstat(mirror_stream.fileno())
    except OSError as error:
        raise AdapterError("mirror-append-failed") from error

    mirror_lines = checkpoint["mirror_lines"] + added_lines
    source_stat = os.fstat(source_stream.fileno())
    value = _checkpoint_value(
        source_path,
        source_stat,
        source_offset,
        mirror_bytes,
        mirror_lines,
        mirror_stat,
    )
    _replace_checkpoint(layout.checkpoint_path(context), value)
    return SyncResult(source_offset, mirror_bytes, mirror_lines, translated_records)


def _copy_complete_records(
    source_stream: BinaryIO, mirror_stream: BinaryIO, layout: AdapterLayout
) -> tuple[int, int, int]:
    source_offset = source_stream.tell()
    translated_records = 0
    mirror_lines = 0
    while True:
        line_start = source_stream.tell()
        line, complete, oversized = _read_source_line(source_stream)
        if line is None:
            source_offset = line_start
            break
        if not complete:
            source_stream.seek(line_start)
            source_offset = line_start
            break
        source_offset = source_stream.tell()
        if oversized:
            _record_sync_diagnostic(layout, "oversized-source-line")
            continue
        try:
            text = line.decode("utf-8")
        except UnicodeError:
            _record_sync_diagnostic(layout, "malformed-source-line")
            continue
        try:
            record = json.loads(text)
        except (ValueError, RecursionError):
            _record_sync_diagnostic(layout, "malformed-source-line")
            continue
        if not isinstance(record, Mapping):
            _record_sync_diagnostic(layout, "malformed-source-line")
            continue
        for translated in translate_record(record):
            encoded = json.dumps(
                translated, ensure_ascii=False, separators=(",", ":")
            ).encode("utf-8") + b"\n"
            mirror_stream.write(encoded)
            translated_records += 1
            mirror_lines += 1
    return source_offset, translated_records, mirror_lines


def _read_source_line(source_stream: BinaryIO) -> tuple[bytes | None, bool, bool]:
    first = source_stream.readline(MAX_SOURCE_LINE_BYTES + 1)
    if not first:
        return None, True, False
    if first.endswith(b"\n"):
        return first, True, len(first) > MAX_SOURCE_LINE_BYTES
    if len(first) <= MAX_SOURCE_LINE_BYTES:
        return first, False, False

    while True:
        chunk = source_stream.readline(MAX_SOURCE_LINE_BYTES + 1)
        if not chunk:
            return b"", False, True
        if chunk.endswith(b"\n"):
            return b"", True, True


def _checkpoint_value(
    source_path: Path,
    source_stat: os.stat_result | None,
    source_offset: int,
    mirror_bytes: int,
    mirror_lines: int,
    mirror_stat: os.stat_result,
) -> dict[str, object]:
    if mirror_stat.st_size != mirror_bytes:
        raise AdapterError("mirror-size-changed")
    checkpoint = {
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "source_path": str(source_path),
        "source_dev": None if source_stat is None else source_stat.st_dev,
        "source_ino": None if source_stat is None else source_stat.st_ino,
        "source_offset": source_offset,
        "mirror_bytes": mirror_bytes,
        "mirror_lines": mirror_lines,
        "mirror_dev": mirror_stat.st_dev,
        "mirror_ino": mirror_stat.st_ino,
        "mirror_size": mirror_stat.st_size,
        "mirror_mtime_ns": mirror_stat.st_mtime_ns,
    }
    checkpoint["integrity"] = _checkpoint_integrity(checkpoint)
    return checkpoint


def _replace_checkpoint(path: Path, checkpoint: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            json.dump(checkpoint, stream, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    except OSError as error:
        raise AdapterError("checkpoint-write-failed") from error
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _record_sync_diagnostic(layout: AdapterLayout, code: str) -> None:
    """Record only a fixed diagnostic code, never source content."""
    _record_bounded_diagnostic(layout, f"sync-warning {code}")


def slug_project(cwd: str | Path) -> str:
    """Return a stable, path-safe project label without changing path case."""
    normalized = str(cwd).replace("\\", "/")
    if len(normalized) >= 2 and normalized[0].isalpha() and normalized[1] == ":":
        normalized = normalized[0].lower() + normalized[1:]
    return re.sub(r"[^A-Za-z0-9]", "-", normalized)


def validate_hook_payload(
    payload: Mapping[str, object], expected_event: str, codex_home: Path
) -> HookContext | None:
    """Validate only the fields needed to safely read a Codex session transcript."""
    try:
        if expected_event not in ALLOWED_EVENTS or payload.get("hook_event_name") != expected_event:
            return None

        session_id = payload.get("session_id")
        cwd = payload.get("cwd")
        transcript = payload.get("transcript_path")
        if (
            not isinstance(session_id, str)
            or not SESSION_ID_PATTERN.fullmatch(session_id)
            or not isinstance(cwd, (str, Path))
            or not isinstance(transcript, (str, Path))
        ):
            return None

        cwd_path = Path(cwd)
        if not cwd_path.is_absolute():
            return None

        transcript_path = Path(transcript)
        if not transcript_path.is_absolute():
            return None

        sessions_root = (Path(codex_home) / "sessions").resolve(strict=False)
        transcript_path = transcript_path.resolve(strict=False)
        if not transcript_path.is_relative_to(sessions_root):
            return None
        if transcript_path.exists() and not transcript_path.is_file():
            return None
        if expected_event != "SessionStart" and not transcript_path.exists():
            return None

        return HookContext(expected_event, session_id, cwd_path, transcript_path)
    except (OSError, RuntimeError, ValueError):
        return None


def translate_record(record: Mapping[str, object]) -> list[dict[str, object]]:
    """Translate one Codex record, omitting all non-user-visible data."""
    try:
        if record.get("type") != "response_item":
            return []
        payload = record.get("payload")
        if not isinstance(payload, Mapping):
            return []

        payload_type = payload.get("type")
        if payload_type == "message":
            return _translate_message(payload)
        if payload_type in {"function_call", "custom_tool_call"}:
            return _translate_tool_call(payload)
    except (AttributeError, TypeError, ValueError):
        return []
    return []


def _translate_message(payload: Mapping[str, object]) -> list[dict[str, object]]:
    role = payload.get("role")
    if role not in {"user", "assistant"}:
        return []

    content = payload.get("content")
    if not isinstance(content, list):
        return []
    expected_type = "input_text" if role == "user" else "output_text"
    blocks: list[dict[str, str]] = []
    for item in content:
        if not isinstance(item, Mapping) or item.get("type") != expected_type:
            continue
        text = item.get("text")
        if isinstance(text, str) and text:
            blocks.append({"type": "text", "text": text})
    if not blocks:
        return []
    return [{"type": role, "message": {"role": role, "content": blocks}}]


def _translate_tool_call(payload: Mapping[str, object]) -> list[dict[str, object]]:
    call_id = payload.get("call_id")
    name = payload.get("name")
    if not isinstance(call_id, str) or not isinstance(name, str):
        return []
    tool_use = {"type": "tool_use", "id": call_id, "name": name, "input": {}}
    return [{"type": "assistant", "message": {"role": "assistant", "content": [tool_use]}}]


if __name__ == "__main__":
    raise SystemExit(main())
