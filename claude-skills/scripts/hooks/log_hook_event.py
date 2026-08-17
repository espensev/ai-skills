#!/usr/bin/env python3
"""Universal hook event logger — writes every hook event to a JSONL log.

This is the data source for /usage-stats, which reads
.claude/hooks/logs/hooks-log.jsonl to compute analytics.

Standalone — no dependency on skill scripts or task_manager.
Attach to every hook event you want to track in settings.json.

Input:  JSON on stdin (Claude Code hook payload)
Output: nothing on stdout (pure side-effect logger, non-blocking)
"""
import json
import os
import sys
from datetime import datetime, timezone

LOG_SUBDIR = os.path.join(".claude", "hooks", "logs")
LOG_FILE = "hooks-log.jsonl"


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    cwd = data.get("cwd", os.getcwd())
    log_dir = os.path.join(cwd, LOG_SUBDIR)
    log_path = os.path.join(log_dir, LOG_FILE)

    # Auto-create log directory on first write
    os.makedirs(log_dir, exist_ok=True)

    event = data.get("hook_event_name", "unknown")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    # Build a compact log entry with fields that exist in the payload
    entry = {"ts": now, "event": event}

    # Session context
    if data.get("session_id"):
        entry["session_id"] = data["session_id"]
    if data.get("agent_id"):
        entry["agent_id"] = data["agent_id"]
    if data.get("agent_type"):
        entry["agent_type"] = data["agent_type"]

    # Tool context (PreToolUse, PostToolUse, PostToolUseFailure, PermissionRequest)
    if data.get("tool_name"):
        entry["tool_name"] = data["tool_name"]
    if data.get("tool_use_id"):
        entry["tool_use_id"] = data["tool_use_id"]

    # Tool input — store command for Bash, file_path for Edit/Write/Read
    tool_input = data.get("tool_input", {})
    if isinstance(tool_input, dict):
        if tool_input.get("command"):
            entry["command"] = tool_input["command"][:500]
        if tool_input.get("file_path"):
            entry["file_path"] = tool_input["file_path"]
        if tool_input.get("pattern"):
            entry["pattern"] = tool_input["pattern"][:200]

    # Error context (PostToolUseFailure, StopFailure)
    if data.get("error"):
        entry["error"] = str(data["error"])[:500]

    # Subagent context (SubagentStart, SubagentStop)
    if data.get("agent_transcript_path"):
        entry["transcript_path"] = data["agent_transcript_path"]

    # Notification context
    if data.get("notification_type"):
        entry["notification_type"] = data["notification_type"]
    if data.get("message") and event in ("Notification", "Elicitation"):
        entry["message"] = str(data["message"])[:300]

    # Session lifecycle context
    if data.get("trigger"):
        entry["trigger"] = data["trigger"]
    if data.get("reason"):
        entry["reason"] = data["reason"]
    if data.get("source"):
        entry["source"] = data["source"]

    # Worktree context
    if data.get("name") and event == "WorktreeCreate":
        entry["worktree_name"] = data["name"]
    if data.get("worktree_path"):
        entry["worktree_path"] = data["worktree_path"]

    # Task context (TaskCreated, TaskCompleted)
    if data.get("task_id"):
        entry["task_id"] = data["task_id"]
    if data.get("task_subject"):
        entry["task_subject"] = data["task_subject"]

    # Config context
    if data.get("file_path") and event == "ConfigChange":
        entry["config_path"] = data["file_path"]

    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, separators=(",", ":")) + "\n")
    except OSError:
        pass  # Non-blocking — never fail the hook

    sys.exit(0)


if __name__ == "__main__":
    main()
