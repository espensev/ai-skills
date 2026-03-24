#!/usr/bin/env python3
"""PostToolUse hook for Bash: parse test/build output and record observations.

Reads hook JSON from stdin. If the Bash command output contains test results
or build errors, appends an observation directly to observations.jsonl and
injects a brief confirmation into the conversation.

Standalone — no dependency on skill scripts or task_manager. Writes to
whichever observations file exists (worktree-local or project-level).
If neither exists, silently exits (observer not initialized).
"""
import json
import os
import re
import sys
from datetime import datetime, timezone


def find_observations_file(cwd: str) -> str | None:
    """Find the observations file, preferring worktree-local."""
    # Worktree-local (observer-test initialized)
    local = os.path.join(cwd, "observations.jsonl")
    if os.path.isfile(local):
        return local
    # Project-level
    project = os.path.join(cwd, "data", "observations.jsonl")
    if os.path.isfile(project):
        return project
    return None


def is_duplicate(path: str, cat: str, summary: str) -> bool:
    """Check if an identical open observation already exists."""
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


def append_observation(path: str, obs: dict):
    """Append a JSONL observation line."""
    with open(path, "a") as f:
        f.write(json.dumps(obs, separators=(",", ":")) + "\n")


def parse_test_output(output: str) -> dict | None:
    """Detect test framework output and extract pass/fail counts."""
    # pytest: "5 passed, 2 failed, 1 error"
    m = re.search(
        r"(\d+) passed(?:.*?(\d+) failed)?(?:.*?(\d+) error)?", output
    )
    if m:
        passed = int(m.group(1))
        failed = int(m.group(2) or 0)
        errors = int(m.group(3) or 0)
        if failed > 0 or errors > 0:
            return {
                "cat": "test-fail",
                "severity": "warning",
                "summary": f"pytest: {failed} failed, {errors} errors ({passed} passed)",
            }
        return {
            "cat": "test-pass",
            "severity": "info",
            "summary": f"pytest: {passed} passed",
        }

    # dotnet test: "Failed:  2, Passed:  8, Skipped:  0"
    m = re.search(
        r"Failed:\s*(\d+),\s*Passed:\s*(\d+)(?:,\s*Skipped:\s*(\d+))?", output
    )
    if m:
        failed = int(m.group(1))
        passed = int(m.group(2))
        if failed > 0:
            return {
                "cat": "test-fail",
                "severity": "warning",
                "summary": f"dotnet test: {failed} failed, {passed} passed",
            }
        return {
            "cat": "test-pass",
            "severity": "info",
            "summary": f"dotnet test: {passed} passed",
        }

    # Generic FAIL pattern (only if clearly test-related)
    if re.search(r"\bFAIL(?:ED|URE)?\b", output, re.IGNORECASE):
        return {
            "cat": "test-fail",
            "severity": "warning",
            "summary": "Test failure detected in output",
        }

    return None


def parse_build_output(output: str) -> dict | None:
    """Detect build errors from compiler/linker output."""
    if re.search(r"Build FAILED", output):
        error_count = len(re.findall(r"error \w+:", output))
        return {
            "cat": "build-error",
            "severity": "critical",
            "summary": f"Build failed with {error_count} error(s)",
        }

    if re.search(r"undefined reference to", output):
        symbols = re.findall(r"undefined reference to [`'](\w+)'", output)
        sym_str = ", ".join(symbols[:3])
        return {
            "cat": "build-error",
            "severity": "critical",
            "summary": f"Linker error: undefined reference to {sym_str}",
        }

    if re.search(r"CMake Error", output):
        return {
            "cat": "build-error",
            "severity": "critical",
            "summary": "CMake configuration failed",
        }

    return None


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    tool_output = data.get("tool_output", "")
    if not tool_output or not isinstance(tool_output, str):
        sys.exit(0)

    command = data.get("tool_input", {}).get("command", "")

    test_keywords = ("test", "pytest", "jest", "mocha", "cargo test", "go test")
    build_keywords = ("build", "make", "cmake", "gcc", "clang", "dotnet build", "cargo build")
    is_test = any(kw in command.lower() for kw in test_keywords)
    is_build = any(kw in command.lower() for kw in build_keywords)

    if not is_test and not is_build:
        sys.exit(0)

    suggestion = None
    if is_test:
        suggestion = parse_test_output(tool_output)
    if not suggestion and is_build:
        suggestion = parse_build_output(tool_output)

    if not suggestion:
        sys.exit(0)

    # Find observations file — exit silently if observer not initialized
    cwd = data.get("cwd", os.getcwd())
    obs_path = find_observations_file(cwd)
    if not obs_path:
        sys.exit(0)

    cat = suggestion["cat"]
    sev = suggestion["severity"]
    summary = suggestion["summary"]

    # Deduplicate
    if is_duplicate(obs_path, cat, summary):
        sys.exit(0)

    # Record directly
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    obs = {
        "ts": now,
        "cat": cat,
        "summary": summary,
        "severity": sev,
        "status": "open",
        "actor": "hook:observe_test_output",
    }
    append_observation(obs_path, obs)

    # Brief context confirmation
    json.dump(
        {"additionalContext": f"[observer] Recorded {cat} ({sev}): {summary}"},
        sys.stdout,
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
