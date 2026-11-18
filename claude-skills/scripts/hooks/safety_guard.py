#!/usr/bin/env python3
"""PreToolUse hook: block destructive commands and protected file edits.

Intercepts Bash, Edit, Write, MultiEdit, and NotebookEdit tool calls. Blocks
patterns known to be destructive or dangerous in an automated agent context.
Returns exit code 2 with a reason on stderr to block the action.

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
    (re.compile(r"\brm\b(?=[^\n;|&]*(?:\s-[a-zA-Z]*[rR]|\s--recursive\b))(?=[^\n;|&]*(?:\s-[a-zA-Z]*f|\s--force\b))"),
     "rm with recursive and force flags"),
    (re.compile(r"\bgit\s+push\s+.*--force\b"),
     "git push --force"),
    (re.compile(r"\bgit\s+push\s+-f\b"),
     "git push -f (force)"),
    (re.compile(r"\bgit\s+push\b[^\n;|&]*\s\+[A-Za-z0-9_./-]+"),
     "git push +refspec (force)"),
    (re.compile(r"\bgit\s+reset\s+--hard\b"),
     "git reset --hard"),
    (re.compile(r"\bgit\s+clean\s+-[a-zA-Z]*f"),
     "git clean with force"),
    (re.compile(r"\bgit\s+(?:checkout|restore)\s+(?:--\s*)?\.(?:\s|$)"),
     "git checkout/restore . (discard all changes)"),
    (re.compile(r"\bgit\s+branch\s+-D\b"),
     "git branch -D (force delete)"),
    (re.compile(r"\b(?:Remove-Item|ri|rm|del|erase|rd|rmdir)\b(?=[^\n;|&]*\s-(?:Recurse|r)\b)(?=[^\n;|&]*\s-(?:Force|fo)\b)", re.IGNORECASE),
     "PowerShell recursive force deletion"),
    (re.compile(r"\b(?:rd|rmdir)\b(?=[^\n;|&]*\s/s\b)(?=[^\n;|&]*\s/q\b)", re.IGNORECASE),
     "CMD rd /s /q"),
    (re.compile(r"\b(?:del|erase)\b(?=[^\n;|&]*\s/f\b)(?=[^\n;|&]*\s/s\b)(?=[^\n;|&]*\s/q\b)", re.IGNORECASE),
     "CMD del /f /s /q"),
    (re.compile(r"\b(?:Format-Volume|Clear-Disk)\b", re.IGNORECASE),
     "disk format or wipe cmdlet"),
    (re.compile(r"\breg(?:\.exe)?\s+delete\b", re.IGNORECASE),
     "Windows registry delete"),
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

# --- Protected file patterns (Edit/Write/MultiEdit/NotebookEdit) ---
PROTECTED_FILES = [
    (re.compile(r"(^|[\\/])\.env($|\.local|\.prod|\.secret)", re.IGNORECASE),
     "environment secrets file"),
    (re.compile(r"(^|[\\/])credentials\.(json|yaml|yml|toml)$", re.IGNORECASE),
     "credentials file"),
    (re.compile(r"(^|[\\/])\.ssh[\\/]", re.IGNORECASE),
     "SSH directory"),
    (re.compile(r"(^|[\\/])(id_rsa|id_ed25519)($|\.)", re.IGNORECASE),
     "SSH private key"),
    (re.compile(r"(^|[\\/])administrators_authorized_keys$", re.IGNORECASE),
     "SSH administrators authorized keys"),
    (re.compile(r"(^|[\\/])\.aws[\\/]credentials$", re.IGNORECASE),
     "AWS credentials"),
    (re.compile(r"(^|[\\/])\.kube[\\/]config$", re.IGNORECASE),
     "Kubernetes config"),
    (re.compile(r"(^|[\\/])apikeys([\\/]|$)", re.IGNORECASE),
     "API keys directory"),
    (re.compile(r"\.(pfx|p12|pem|key)$", re.IGNORECASE),
     "private key or certificate bundle"),
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
        try:
            raw_bytes = (
                sys.stdin.buffer.read()
                if hasattr(sys.stdin, "buffer") and sys.stdin.buffer is not None
                else sys.stdin.read().encode("utf-8", errors="replace")
            )
            if not raw_bytes.strip():
                sys.exit(0)
            data = json.loads(raw_bytes.decode("utf-8", errors="replace"))
        except (json.JSONDecodeError, EOFError):
            sys.exit(0)

        if not isinstance(data, dict):
            sys.exit(0)

        tool_name = data.get("tool_name", "")
        tool_input = data.get("tool_input", {})
        if not isinstance(tool_input, dict):
            tool_input = {}

        reason = None

        if tool_name == "Bash":
            command = tool_input.get("command", "")
            reason = check_bash(command)

        elif tool_name in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
            file_path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
            reason = check_file(file_path)

        if reason:
            print(
                f"[safety-guard] Blocked: {reason}. "
                f"If this is intentional, ask the user to confirm.",
                file=sys.stderr,
            )
            sys.exit(2)

        sys.exit(0)
    except Exception as exc:
        print(
            f"[safety-guard] Blocked due to internal guard error: {type(exc).__name__}",
            file=sys.stderr,
        )
        sys.exit(2)


if __name__ == "__main__":
    main()
