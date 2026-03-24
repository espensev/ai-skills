#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Append a lightweight observer note to data/observations.jsonl.")
    parser.add_argument("summary", help="One-line observation summary.")
    parser.add_argument("--repo-root", default=".", help="Repo root that owns data/observations.jsonl.")
    parser.add_argument("--category", default="note", help="Observation category, for example risk or drift.")
    parser.add_argument("--detail", default="", help="Optional longer detail.")
    parser.add_argument("--severity", default="info", choices=["info", "warning", "critical"])
    parser.add_argument("--status", default="open", choices=["open", "resolved", "stale"])
    parser.add_argument("--files", nargs="*", default=[], help="Related repo-relative file paths.")
    parser.add_argument("--actor", default="local-observer")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    target = repo_root / "data" / "observations.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "ts": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "cat": args.category,
        "summary": args.summary,
        "detail": args.detail,
        "files": args.files,
        "status": args.status,
        "severity": args.severity,
        "actor": args.actor,
    }

    with target.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
