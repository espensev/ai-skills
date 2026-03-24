#!/usr/bin/env python3
"""SessionStart hook: inject observer briefing into session context.

On session startup, reads current observations and metrics to provide
project health context. Read-only — never writes observations.

Standalone — no dependency on skill scripts or task_manager. Reads from
whichever observations/metrics files exist. If none exist, silently exits.
"""
import json
import os
import sys


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

    # Try both possible locations
    obs_path = os.path.join(cwd, "data", "observations.jsonl")
    metrics_path = os.path.join(cwd, "data", "metrics.jsonl")

    observations = load_jsonl(obs_path)
    metrics_raw = load_jsonl(metrics_path)

    if not observations and not metrics_raw:
        sys.exit(0)

    open_obs = [o for o in observations if o.get("status") == "open"]
    critical = [o for o in open_obs if o.get("severity") == "critical"]
    warnings = [o for o in open_obs if o.get("severity") == "warning"]

    metrics = {}
    for m in metrics_raw:
        key = m.get("key", "")
        if key:
            metrics[key] = m.get("value")

    if critical:
        health = "unhealthy"
    elif warnings:
        health = "degraded"
    else:
        health = "healthy"

    lines = [
        f"[observer] Project health: {health} "
        f"({len(critical)} critical, {len(warnings)} warning, {len(open_obs)} open)"
    ]

    if critical:
        lines.append("Critical:")
        for item in critical[:5]:
            lines.append(f"  - [{item.get('cat')}] {item.get('summary')}")

    if warnings:
        lines.append("Warnings:")
        for item in warnings[:5]:
            lines.append(f"  - [{item.get('cat')}] {item.get('summary')}")

    if metrics:
        parts = [f"{k}={v}" for k, v in metrics.items()]
        lines.append(f"Metrics: {', '.join(parts)}")

    json.dump({"additionalContext": "\n".join(lines)}, sys.stdout)
    sys.exit(0)


if __name__ == "__main__":
    main()
