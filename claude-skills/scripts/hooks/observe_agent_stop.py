#!/usr/bin/env python3
"""SubagentStop hook: summarize worktree observations when an agent finishes.

When a subagent completes, checks for observations.jsonl in the worktree.
If found, parses and injects a summary into the parent conversation so the
manager knows about critical items before continuing.

Read-only — never writes observations. Standalone, no skill dependencies.
"""
import json
import os
import sys


def find_worktree_observations(cwd: str) -> list[str]:
    """Find all observations.jsonl files in worktree locations."""
    paths = []

    # Direct (agent was running in a worktree with observer-test)
    direct = os.path.join(cwd, "observations.jsonl")
    if os.path.isfile(direct):
        paths.append(direct)

    # Search .claude/worktrees/ for any with observations
    worktrees_dir = os.path.join(cwd, ".claude", "worktrees")
    if os.path.isdir(worktrees_dir):
        for name in sorted(os.listdir(worktrees_dir)):
            candidate = os.path.join(worktrees_dir, name, "observations.jsonl")
            if os.path.isfile(candidate) and candidate not in paths:
                paths.append(candidate)

    return paths


def load_jsonl(path: str) -> list:
    entries = []
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except FileNotFoundError:
        pass
    return entries


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    cwd = data.get("cwd", os.getcwd())
    obs_paths = find_worktree_observations(cwd)
    if not obs_paths:
        sys.exit(0)

    # Aggregate all worktree observations
    all_obs = []
    for path in obs_paths:
        all_obs.extend(load_jsonl(path))

    if not all_obs:
        sys.exit(0)

    by_cat = {}
    flagged = []
    for obs in all_obs:
        cat = obs.get("cat", "unknown")
        by_cat[cat] = by_cat.get(cat, 0) + 1
        sev = obs.get("severity", "info")
        if sev in ("warning", "critical") or cat in ("blocker", "regression", "workaround"):
            flagged.append(obs)

    total = len(all_obs)
    critical_count = sum(1 for o in all_obs if o.get("severity") == "critical")
    warning_count = sum(1 for o in all_obs if o.get("severity") == "warning")

    lines = [
        f"[observer] Agent finished with {total} observations "
        f"({critical_count} critical, {warning_count} warning)"
    ]

    parts = [f"{cat}:{count}" for cat, count in sorted(by_cat.items())]
    lines.append(f"  Categories: {', '.join(parts)}")

    if flagged:
        lines.append("  Flagged:")
        for obs in flagged[:10]:
            sev = obs.get("severity", "info")
            lines.append(f"    [{obs.get('cat')}] [{sev}] {obs.get('summary', '?')}")

    if critical_count > 0:
        lines.append("  Review critical items before merge.")

    json.dump({"additionalContext": "\n".join(lines)}, sys.stdout)
    sys.exit(0)


if __name__ == "__main__":
    main()
