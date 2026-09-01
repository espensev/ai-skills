#!/usr/bin/env python3
"""Aggregate measured Codex token counters over a rolling time window.

The collector reads native Codex session JSONL files and sums deltas between
cumulative ``token_count`` events. This avoids double-counting repeated events
and keeps cached-input and reasoning-output counters as subsets.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

TOKEN_FIELDS = (
    "input_tokens",
    "cached_input_tokens",
    "cache_write_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
    "total_tokens",
)
SESSION_ID_RE = re.compile(
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$",
    re.IGNORECASE,
)


def parse_timestamp(value: Any) -> datetime:
    """Parse an ISO-8601 timestamp and normalize it to UTC."""
    if not isinstance(value, str):
        raise ValueError("timestamp is not a string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp has no UTC offset")
    return parsed.astimezone(timezone.utc)


def token_values(value: Any) -> dict[str, int]:
    """Return all supported counters as non-negative integers."""
    mapping = value if isinstance(value, dict) else {}
    result: dict[str, int] = {}
    for field in TOKEN_FIELDS:
        raw = mapping.get(field, 0)
        result[field] = max(0, int(raw)) if raw is not None else 0
    return result


def counter_delta(
    current: dict[str, int],
    previous: dict[str, int] | None,
    last_usage: dict[str, int],
) -> tuple[dict[str, int], bool]:
    """Calculate a cumulative delta, falling back when counters reset."""
    if previous is None:
        return dict(current), False
    delta = {field: current[field] - previous[field] for field in TOKEN_FIELDS}
    if any(value < 0 for value in delta.values()):
        return dict(last_usage or current), True
    return delta, False


def recent_session_files(sessions_root: Path, cutoff: datetime) -> Iterable[Path]:
    """Yield JSONL files whose modification time overlaps the window."""
    cutoff_epoch = cutoff.timestamp()
    for path in sessions_root.rglob("*.jsonl"):
        try:
            if path.stat().st_mtime >= cutoff_epoch:
                yield path
        except OSError:
            yield path


def session_id(path: Path) -> str:
    match = SESSION_ID_RE.search(path.stem)
    return match.group(1) if match else path.stem


def collect_usage(
    codex_home: Path,
    *,
    hours: float = 24,
    now: datetime | None = None,
    top_sessions: int = 10,
) -> dict[str, Any]:
    """Collect measured token totals from native Codex sessions."""
    if hours <= 0:
        raise ValueError("hours must be greater than zero")
    window_end = now or datetime.now(timezone.utc)
    if window_end.tzinfo is None:
        raise ValueError("now must include a UTC offset")
    window_end = window_end.astimezone(timezone.utc)
    window_start = window_end - timedelta(hours=hours)
    sessions_root = codex_home / "sessions"
    if not sessions_root.is_dir():
        raise FileNotFoundError(f"Codex sessions directory not found: {sessions_root}")

    totals = {field: 0 for field in TOKEN_FIELDS}
    rows: list[dict[str, Any]] = []
    files_scanned = 0
    token_count_events = 0
    positive_usage_events = 0
    duplicate_events = 0
    reset_events = 0
    parse_errors = 0
    timestamp_errors = 0
    partial_lines = 0
    read_errors = 0
    latest_timestamp: datetime | None = None
    latest_rate_limits: dict[str, Any] | None = None

    for path in recent_session_files(sessions_root, window_start):
        files_scanned += 1
        previous: dict[str, int] | None = None
        per_session = {field: 0 for field in TOKEN_FIELDS}
        per_session_events = 0
        try:
            with path.open("r", encoding="utf-8") as handle:
                for raw_line in handle:
                    if '"token_count"' not in raw_line:
                        continue
                    try:
                        event = json.loads(raw_line)
                    except json.JSONDecodeError:
                        if not raw_line.endswith("\n"):
                            partial_lines += 1
                        else:
                            parse_errors += 1
                        continue
                    payload = event.get("payload", {})
                    info = payload.get("info") or {}
                    if (
                        event.get("type") != "event_msg"
                        or payload.get("type") != "token_count"
                        or not isinstance(info.get("total_token_usage"), dict)
                    ):
                        continue

                    current = token_values(info["total_token_usage"])
                    last_usage = token_values(info.get("last_token_usage"))
                    delta, reset = counter_delta(current, previous, last_usage)
                    previous = current
                    if reset:
                        reset_events += 1
                    try:
                        timestamp = parse_timestamp(event.get("timestamp"))
                    except (TypeError, ValueError):
                        timestamp_errors += 1
                        continue
                    if timestamp < window_start or timestamp > window_end:
                        continue

                    token_count_events += 1
                    if delta["total_tokens"] <= 0:
                        duplicate_events += 1
                        continue
                    positive_usage_events += 1
                    per_session_events += 1
                    for field in TOKEN_FIELDS:
                        totals[field] += delta[field]
                        per_session[field] += delta[field]
                    if latest_timestamp is None or timestamp > latest_timestamp:
                        latest_timestamp = timestamp
                        rate_limits = payload.get("rate_limits")
                        latest_rate_limits = rate_limits if isinstance(rate_limits, dict) else None
        except (OSError, UnicodeError):
            read_errors += 1
            continue

        if per_session["total_tokens"] > 0:
            rows.append(
                {
                    "session_id": session_id(path),
                    "events": per_session_events,
                    **per_session,
                }
            )

    reconciled_total = totals["input_tokens"] + totals["output_tokens"]
    rows.sort(key=lambda row: row["total_tokens"], reverse=True)
    return {
        "schema_version": 1,
        "scope": {
            "included": ["Codex native session token_count events in this Codex home"],
            "excluded": [
                "ChatGPT web/app conversations",
                "API or Codex usage recorded under another Codex home",
            ],
        },
        "window": {
            "hours": hours,
            "start": window_start.isoformat(),
            "end": window_end.isoformat(),
        },
        "data_tier": "tier_1_measured",
        "source": "native_codex_token_count_cumulative_deltas",
        "totals": {
            **totals,
            "noncached_input_tokens": max(
                0, totals["input_tokens"] - totals["cached_input_tokens"]
            ),
            "input_plus_output_check": reconciled_total,
            "reconciliation_delta": totals["total_tokens"] - reconciled_total,
        },
        "coverage": {
            "files_scanned": files_scanned,
            "sessions_with_usage": len(rows),
            "token_count_events": token_count_events,
            "positive_usage_events": positive_usage_events,
            "duplicate_events": duplicate_events,
            "counter_reset_events": reset_events,
            "parse_errors": parse_errors,
            "timestamp_errors": timestamp_errors,
            "partial_lines_skipped": partial_lines,
            "read_errors": read_errors,
            "latest_counter_timestamp": (
                latest_timestamp.isoformat() if latest_timestamp else None
            ),
        },
        "latest_rate_limits": latest_rate_limits,
        "top_sessions": rows[: max(0, top_sessions)],
    }


def default_codex_home() -> Path:
    configured = os.environ.get("CODEX_HOME")
    return Path(configured).expanduser() if configured else Path.home() / ".codex"


def render_text(result: dict[str, Any]) -> str:
    totals = result["totals"]
    coverage = result["coverage"]
    window = result["window"]
    return "\n".join(
        (
            f"Codex usage - rolling {window['hours']:g}h (Tier 1 measured)",
            f"Window: {window['start']} to {window['end']}",
            f"Input: {totals['input_tokens']:,}",
            f"Output: {totals['output_tokens']:,}",
            f"Total: {totals['total_tokens']:,}",
            f"Cached input subset: {totals['cached_input_tokens']:,}",
            f"Reasoning output subset: {totals['reasoning_output_tokens']:,}",
            (
                "Coverage: "
                f"{coverage['sessions_with_usage']} sessions, "
                f"{coverage['positive_usage_events']} completed model steps"
            ),
            "Excluded: ChatGPT web/app conversations and other Codex homes",
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Aggregate measured native Codex usage over a rolling window."
    )
    parser.add_argument("--hours", type=float, default=24.0)
    parser.add_argument("--codex-home", type=Path, default=default_codex_home())
    parser.add_argument("--top-sessions", type=int, default=10)
    parser.add_argument("--now", help="ISO-8601 window end; intended for tests/replay")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args(argv)

    try:
        now = parse_timestamp(args.now) if args.now else None
        result = collect_usage(
            args.codex_home.expanduser(),
            hours=args.hours,
            now=now,
            top_sessions=args.top_sessions,
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        if args.json:
            print(json.dumps({"error": str(exc)}, indent=2))
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(render_text(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
