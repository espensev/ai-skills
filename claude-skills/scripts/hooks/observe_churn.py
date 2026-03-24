#!/usr/bin/env python3
"""PostToolUse hook for Edit|Write: track file edit frequency and record churn.

Maintains a session-local counter in temp directory. When a file is edited 3+
times, records a churn observation directly to observations.jsonl.

Standalone — no dependency on skill scripts or task_manager. Writes to
whichever observations file exists (worktree-local or project-level).
If neither exists, silently exits (observer not initialized).
"""
import json
import os
import sys
import tempfile
from datetime import datetime, timezone


def find_observations_file(cwd: str) -> str | None:
    """Find the observations file, preferring worktree-local."""
    local = os.path.join(cwd, "observations.jsonl")
    if os.path.isfile(local):
        return local
    project = os.path.join(cwd, "data", "observations.jsonl")
    if os.path.isfile(project):
        return project
    return None


def is_duplicate(path: str, cat: str, summary: str) -> bool:
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obs = json.loads(line)
                    if (obs.get("cat") == cat
                            and obs.get("summary") == summary
                            and obs.get("status", "open") == "open"):
                        return True
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        pass
    return False


def get_counter_path(session_id: str) -> str:
    return os.path.join(tempfile.gettempdir(), f"claude_observe_churn_{session_id}.json")


def load_counters(path: str) -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_counters(path: str, counters: dict):
    with open(path, "w") as f:
        json.dump(counters, f)


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    file_path = data.get("tool_input", {}).get("file_path", "")
    if not file_path:
        sys.exit(0)

    session_id = data.get("session_id", "default")
    counter_path = get_counter_path(session_id)

    counters = load_counters(counter_path)
    counters[file_path] = counters.get(file_path, 0) + 1
    save_counters(counter_path, counters)

    count = counters[file_path]

    # Only record on first crossing of threshold (exactly 3)
    if count != 3:
        sys.exit(0)

    # Find observations file — exit silently if observer not initialized
    cwd = data.get("cwd", os.getcwd())
    obs_path = find_observations_file(cwd)
    if not obs_path:
        sys.exit(0)

    summary = f"{file_path} edited {count}+ times — possible design instability"

    if is_duplicate(obs_path, "churn", summary):
        sys.exit(0)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    obs = {
        "ts": now,
        "cat": "churn",
        "summary": summary,
        "severity": "warning",
        "status": "open",
        "files": [file_path],
        "actor": "hook:observe_churn",
    }

    with open(obs_path, "a") as f:
        f.write(json.dumps(obs, separators=(",", ":")) + "\n")

    json.dump(
        {"additionalContext": f"[observer] Recorded churn (warning): {summary}"},
        sys.stdout,
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
