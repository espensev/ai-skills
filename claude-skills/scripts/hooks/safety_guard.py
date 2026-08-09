#!/usr/bin/env python3
"""PreToolUse hook: block destructive commands and protected file edits.

Intercepts Bash, Edit, and Write tool calls. Blocks patterns known to be
destructive or dangerous in an automated agent context. Returns exit code 2
with a reason on stderr to block the action.

Standalone — no dependency on skill scripts or task_manager.
Configure blocked patterns via environment or keep the built-in defaults.

Input:  JSON on stdin (Claude Code PreToolUse hook payload)
Output: exit 0 to allow, exit 2 + stderr message to block
"""
import json
import re
import sys

# --- Dangerous Bash command patterns ---
# Each tuple: (compiled regex, human-readable reason)
DANGEROUS_COMMANDS = [
    (re.compile(r"\brm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+|--force\s+).*(/|\*|~)"),
     "rm with force flag on broad path"),
    (re.compile(r"\brm\s+-rf\s"),
     "rm -rf"),
    (re.compile(r"\bgit\s+push\s+.*--force\b"),
     "git push --force"),
    (re.compile(r"\bgit\s+push\s+-f\b"),
     "git push -f (force)"),
    (re.compile(r"\bgit\s+reset\s+--hard\b"),
     "git reset --hard"),
    (re.compile(r"\bgit\s+clean\s+-[a-zA-Z]*f"),
     "git clean with force"),
    (re.compile(r"\bgit\s+checkout\s+--\s*\."),
     "git checkout -- . (discard all changes)"),
    (re.compile(r"\bgit\s+branch\s+-D\b"),
     "git branch -D (force delete)"),
    (re.compile(r"\bDROP\s+(TABLE|DATABASE|SCHEMA)\b", re.IGNORECASE),
     "SQL DROP statement"),
    (re.compile(r"\bTRUNCATE\s+TABLE\b", re.IGNORECASE),
     "SQL TRUNCATE TABLE"),
    (re.compile(r"\bDELETE\s+FROM\s+\w+\s*;?\s*$", re.IGNORECASE),
     "SQL DELETE without WHERE clause"),
    (re.compile(r"\bdocker\s+system\s+prune\b"),
     "docker system prune"),
    (re.compile(r"\bdocker\s+rm\s+-f\b"),
     "docker force remove"),
    (re.compile(r"\bkubectl\s+delete\s+(namespace|ns)\b"),
     "kubectl delete namespace"),
    (re.compile(r"\b(chmod|chown)\s+.*-R\s+.*/\s*$"),
     "recursive permission change on root-like path"),
    (re.compile(r"\bmkfs\b"),
     "filesystem format"),
    (re.compile(r"\bdd\s+.*of=/dev/"),
     "dd to device"),
    (re.compile(r":>\s*/"),
     "truncate file with redirect to root path"),
    (re.compile(r">\s*/dev/sda"),
     "write to raw device"),
    (re.compile(r"\bnpm\s+unpublish\b"),
     "npm unpublish"),
    (re.compile(r"\bpip\s+install\b(?!.*\s-e\s)(?!.*\s--editable\b)"),
     None),  # None = don't block, just note (pip install is usually fine)
]

# --- Protected file patterns (Edit/Write) ---
PROTECTED_FILES = [
    (re.compile(r"(^|[\\/])\.env($|\.local|\.prod|\.secret)", re.IGNORECASE),
     "environment secrets file"),
    (re.compile(r"(^|[\\/])credentials\.(json|yaml|yml|toml)$", re.IGNORECASE),
     "credentials file"),
    (re.compile(r"(^|[\\/])\.ssh[\\/]", re.IGNORECASE),
     "SSH directory"),
    (re.compile(r"(^|[\\/])id_rsa|id_ed25519", re.IGNORECASE),
     "SSH private key"),
    (re.compile(r"(^|[\\/])\.aws[\\/]credentials$", re.IGNORECASE),
     "AWS credentials"),
    (re.compile(r"(^|[\\/])\.kube[\\/]config$", re.IGNORECASE),
     "Kubernetes config"),
]


def check_bash(command: str) -> str | None:
    """Return a block reason if command is dangerous, else None."""
    if not command:
        return None
    for pattern, reason in DANGEROUS_COMMANDS:
        if reason is None:
            continue  # Skip note-only patterns
        if pattern.search(command):
            return reason
    return None


def check_file(file_path: str) -> str | None:
    """Return a block reason if file is protected, else None."""
    if not file_path:
        return None
    for pattern, reason in PROTECTED_FILES:
        if pattern.search(file_path):
            return reason
    return None


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})
    if not isinstance(tool_input, dict):
        tool_input = {}

    reason = None

    if tool_name == "Bash":
        command = tool_input.get("command", "")
        reason = check_bash(command)

    elif tool_name in ("Edit", "Write"):
        file_path = tool_input.get("file_path", "")
        reason = check_file(file_path)

    if reason:
        print(
            f"[safety-guard] Blocked: {reason}. "
            f"If this is intentional, ask the user to confirm.",
            file=sys.stderr,
        )
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
