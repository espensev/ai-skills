"""Measure hook cost and usage from local Claude Code and Codex CLI transcripts.

Consolidates three throwaway scratch scripts (mine_claude2.py, mine_codex2.py,
mine_codex.py) into one reusable, tested tool. Stdlib only, Python 3.11+,
Windows paths.

Usage:
    python scripts/measure_hook_cost.py [--days 30] [--provider claude|codex|both]
        [--claude-root PATH] [--codex-root PATH] [--json]

Defaults to both providers, a 30-day window, and a human-readable report.
Metrics include records whose outer timestamp is at or after the cutoff,
regardless of file mtime. Missing, malformed, or timezone-free timestamps are
excluded. Metadata may classify a session regardless of its timestamp, but a
session is counted only when it has an eligible non-metadata record. Files are
streamed line-by-line; malformed JSONL lines are tolerated.

Stop continuations require both endpoints in the window. Excluded records
reset pending continuations so partial spans do not leak into durations or
token totals. Codex token deltas additionally require in-window cumulative
snapshots before and after the prompt; missing snapshots contribute no tokens,
while complete durations still count. Thus token totals cover measured spans,
not necessarily every counted continuation. token_measured_n and
token_unmeasured_n expose that coverage. Missing or invalid counters and
decreasing cumulative counters make a span unmeasured.

Tests, from the repo root:
    python -m unittest scripts.tests.test_measure_hook_cost
or directly:
    python scripts/tests/test_measure_hook_cost.py
(the test file inserts the repo root onto sys.path itself, so both work; no
scripts/__init__.py is needed since implicit namespace packages cover -m).

Two deviations from the literal task spec, verified against ~470 real Codex
rollouts before writing:

* Subagent rollouts. payload["id"] always equals the rollout's own filename
  UUID (that's how the file is named), so comparing filename UUID to
  payload.id never fires. The field that actually distinguishes a spawned
  subagent thread is payload["session_id"] (the root session's id, shared by
  every thread spawned under it): a rollout is a subagent when session_id is
  present and differs from id. Agreed 472/472 with an independent signal
  (payload["source"] being a dict with a "subagent" key) on the local corpus.
  Only the FIRST session_meta counts: forked subagent rollouts follow their
  own meta with a copy of the parent's (usually source "cli").
* Exec sessions. The spec names interactive/subagent/exec but only defines
  subagent. We use originator == "codex_exec" or source == "exec", checked
  after the subagent test (an exec-spawned subagent is still a subagent).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional

DEFAULT_CLAUDE_ROOT = Path(r"D:\DevHome\state\claude")
DEFAULT_CODEX_ROOT = Path(r"D:\DevHome\state\codex")

HOOK_ATTACHMENT_TYPES = {
    "hook_success",
    "hook_non_blocking_error",
    "hook_blocking_error",
    "hook_system_message",
    "hook_additional_context",
    "hook_cancelled",
}

SKILL_PATH_RE = re.compile(r"skills[\\/]+([A-Za-z0-9_.-]+)[\\/]+SKILL\.md")


def _iter_jsonl(path: Path) -> Iterator[dict]:
    """Stream all parsed records, preserving metadata before the cutoff."""
    try:
        fh = open(path, encoding="utf-8", errors="replace")
    except OSError:
        return
    with fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            if isinstance(rec, dict):
                yield rec


def _parse_ts(ts: Optional[str]) -> Optional[datetime]:
    if not isinstance(ts, str) or not ts:
        return None
    try:
        parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _within_window(rec: dict, cutoff_ts: float) -> bool:
    timestamp = _parse_ts(rec.get("timestamp"))
    return timestamp is not None and timestamp.timestamp() >= cutoff_ts


def _seconds_between(start: Optional[str], end: Optional[str]) -> Optional[float]:
    t0, t1 = _parse_ts(start), _parse_ts(end)
    if t0 is None or t1 is None:
        return None
    seconds = (t1 - t0).total_seconds()
    return seconds if seconds >= 0 else None


def _duration_stats(seconds: Iterable[float]) -> dict:
    s = sorted(x for x in seconds if x is not None)
    n = len(s)
    if not n:
        return {"n": 0, "p50": 0.0, "p90": 0.0, "max": 0.0, "total_minutes": 0.0}
    idx90 = min(int(n * 0.9), n - 1)
    return {
        "n": n,
        "p50": round(s[n // 2], 1),
        "p90": round(s[idx90], 1),
        "max": round(s[-1], 1),
        "total_minutes": round(sum(s) / 60, 1),
    }


def _empty_claude_result() -> dict:
    return {
        "sessions_by_entrypoint": {},
        "hook_outcomes": [],
        "non_success_top15": [],
        "stop_continuations": _duration_stats([]),
        "continuations_by_project": {},
        "skill_usage": {},
        "agent_launches": [],
    }


def collect_claude(root: Path, cutoff_ts: float) -> dict:
    """Walk `<root>/projects/*/*.jsonl` and compute the Claude-side metrics."""
    projects_dir = Path(root) / "projects"
    if not projects_dir.is_dir():
        return _empty_claude_result()

    sessions_by_entrypoint: Counter = Counter()
    hook_outcomes: Counter = Counter()  # (event, type)
    non_success: Counter = Counter()  # (type, exit_code, command[:80])
    continuations_by_project: Counter = Counter()
    skill_usage: Counter = Counter()
    agent_launches: Counter = Counter()  # (subagent_type, model)
    stop_seconds: list[float] = []

    for proj_dir in sorted(p for p in projects_dir.iterdir() if p.is_dir()):
        project = proj_dir.name
        for path in sorted(proj_dir.glob("*.jsonl")):
            entrypoint: Optional[str] = None
            has_events = False
            pending_stop_ctx: Optional[str] = None
            for rec in _iter_jsonl(path):
                if entrypoint is None:
                    ep = rec.get("entrypoint")
                    if ep is not None:
                        entrypoint = ep
                if not _within_window(rec, cutoff_ts):
                    pending_stop_ctx = None
                    continue
                has_events = True
                rtype = rec.get("type")
                if rtype == "attachment":
                    att = rec.get("attachment") or {}
                    at = att.get("type") or ""
                    if at not in HOOK_ATTACHMENT_TYPES:
                        continue
                    event = att.get("hookEvent")
                    hook_outcomes[(event, at)] += 1
                    if at != "hook_success":
                        cmd = (att.get("command") or "")[:80]
                        non_success[(at, att.get("exitCode"), cmd)] += 1
                    if event == "Stop":
                        ts = rec.get("timestamp")
                        if at == "hook_additional_context":
                            pending_stop_ctx = ts
                        elif at == "hook_success":
                            if pending_stop_ctx and ts:
                                secs = _seconds_between(pending_stop_ctx, ts)
                                if secs is not None:
                                    stop_seconds.append(secs)
                                    continuations_by_project[project] += 1
                            pending_stop_ctx = None
                elif rtype == "assistant":
                    content = (rec.get("message") or {}).get("content")
                    if not isinstance(content, list):
                        continue
                    for blk in content:
                        if not isinstance(blk, dict) or blk.get("type") != "tool_use":
                            continue
                        name = blk.get("name")
                        inp = blk.get("input") or {}
                        if name == "Skill":
                            skill = inp.get("skill")
                            if skill:
                                skill_usage[skill] += 1
                        elif name == "Agent":
                            subagent_type = inp.get("subagent_type") or "(unspecified)"
                            model = inp.get("model") or "(default)"
                            agent_launches[(subagent_type, model)] += 1
            if has_events:
                sessions_by_entrypoint[entrypoint or "unknown"] += 1

    return {
        "sessions_by_entrypoint": dict(sessions_by_entrypoint),
        "hook_outcomes": [
            {"event": e, "type": t, "count": c}
            for (e, t), c in hook_outcomes.most_common()
        ],
        "non_success_top15": [
            {"type": t, "exit_code": ec, "command": cmd, "count": c}
            for (t, ec, cmd), c in non_success.most_common(15)
        ],
        "stop_continuations": _duration_stats(stop_seconds),
        "continuations_by_project": dict(continuations_by_project),
        "skill_usage": dict(skill_usage),
        "agent_launches": [
            {"subagent_type": st, "model": m, "count": c}
            for (st, m), c in agent_launches.most_common()
        ],
    }


def _empty_codex_result() -> dict:
    stats = _duration_stats([])
    stats.update(
        noncached_input_tokens_total=0,
        output_tokens_total=0,
        token_measured_n=0,
        token_unmeasured_n=0,
    )
    return {
        "sessions_by_kind": {},
        "stop_continuations": stats,
        "continuations_by_kind": {},
        "injected_context": {},
        "skill_usage": {},
    }


def _codex_session_kind(payload: dict) -> str:
    session_id = payload.get("session_id")
    own_id = payload.get("id")
    if session_id and own_id and session_id != own_id:
        return "subagent"
    if payload.get("originator") == "codex_exec" or payload.get("source") == "exec":
        return "exec"
    return "interactive"


def _codex_token_totals(payload: dict) -> Optional[dict[str, int]]:
    info = payload.get("info")
    if not isinstance(info, dict):
        return None
    usage = info.get("total_token_usage")
    if not isinstance(usage, dict):
        return None
    totals = {"total": usage.get("total_tokens"), "in": usage.get("input_tokens"),
              "cached": usage.get("cached_input_tokens"), "out": usage.get("output_tokens")}
    if any(type(value) is not int or value < 0 for value in totals.values()):
        return None
    return totals if totals["cached"] <= totals["in"] else None


def _injected_context_kind(text: str) -> Optional[str]:
    if text.startswith("=== HANDOFF"):
        return "handoff"
    if text.startswith("Handoff Relay: an active draft"):
        return "draft"
    if text.startswith("## Memory"):
        return "memory"
    if text.startswith("<skills_instructions>"):
        return "skills_instructions"
    return None


def _injected_context_bytes(texts: list[str]) -> dict[str, int]:
    """Attribute a developer message's bytes per content item.

    Codex sends memory, the skills catalog, and permissions/collaboration/apps/
    plugins blocks as separate items of one startup message. Unrecognised items
    count as "other" only inside a message that also carries a known kind (in
    practice the startup message, including any role prompt folded into it);
    a standalone developer message with no known kind is excluded.
    """
    out: Counter = Counter()
    for t in texts:
        if not t:
            continue
        out[_injected_context_kind(t) or "other"] += len(t.encode("utf-8"))
    if set(out) == {"other"}:
        return {}
    return dict(out)


def collect_codex(root: Path, cutoff_ts: float) -> dict:
    """Walk `<root>/sessions/**/*.jsonl` and compute the Codex-side metrics."""
    sessions_dir = Path(root) / "sessions"
    if not sessions_dir.is_dir():
        return _empty_codex_result()

    sessions_by_kind: Counter = Counter()
    continuations_by_kind: Counter = Counter()
    injected_context: dict[str, dict[str, int]] = {}
    skill_usage: Counter = Counter()
    total_secs: list[float] = []
    noncached_input_tokens: list[int] = []
    output_tokens: list[int] = []

    for path in sorted(sessions_dir.glob("**/*.jsonl")):
        kind: Optional[str] = None
        has_events = False
        last_tokens: Optional[dict] = None
        hook_at: Optional[str] = None
        hook_tokens: Optional[dict] = None
        hook_observed_tokens = False
        for rec in _iter_jsonl(path):
            rtype = rec.get("type")
            payload = rec.get("payload") or {}
            if not isinstance(payload, dict):
                continue
            ptype = payload.get("type")
            ts = rec.get("timestamp") or ""
            if rtype == "session_meta":
                if kind is None:
                    kind = _codex_session_kind(payload)
                continue
            if not _within_window(rec, cutoff_ts):
                last_tokens = None
                hook_at = None
                hook_tokens = None
                hook_observed_tokens = False
                continue
            has_events = True
            if rtype == "event_msg":
                if ptype == "token_count":
                    current_tokens = _codex_token_totals(payload)
                    if current_tokens is None or (
                        last_tokens is not None and (
                            any(current_tokens[key] < last_tokens[key] for key in last_tokens)
                            or current_tokens["in"] - current_tokens["cached"]
                            < last_tokens["in"] - last_tokens["cached"]
                        )
                    ):
                        hook_tokens = None
                    last_tokens = current_tokens
                    if hook_at and current_tokens is not None:
                        hook_observed_tokens = True
                elif ptype in ("task_complete", "turn_aborted") and hook_at:
                    secs = _seconds_between(hook_at, ts)
                    if secs is not None:
                        total_secs.append(secs)
                        continuations_by_kind[kind or "unknown"] += 1
                        if hook_tokens is not None and last_tokens is not None and hook_observed_tokens:
                            deltas = {key: last_tokens[key] - hook_tokens[key] for key in last_tokens}
                            noncached = deltas["in"] - deltas["cached"]
                            if min(deltas.values()) >= 0 and noncached >= 0:
                                noncached_input_tokens.append(noncached)
                                output_tokens.append(deltas["out"])
                    hook_at = None
                    hook_tokens = None
                    hook_observed_tokens = False
            elif rtype == "response_item":
                if ptype == "message":
                    role = payload.get("role")
                    content = payload.get("content")
                    texts = (
                        [c.get("text", "") for c in content if isinstance(c, dict)]
                        if isinstance(content, list)
                        else []
                    )
                    text = "".join(texts)
                    if role == "developer":
                        for ictx_kind, nbytes in _injected_context_bytes(texts).items():
                            entry = injected_context.setdefault(
                                ictx_kind, {"count": 0, "bytes": 0}
                            )
                            entry["count"] += 1
                            entry["bytes"] += nbytes
                    elif role == "user" and "<hook_prompt" in text:
                        hook_at = ts
                        hook_tokens = dict(last_tokens) if last_tokens is not None else None
                        hook_observed_tokens = False
                elif ptype in ("function_call", "custom_tool_call", "local_shell_call"):
                    dumped = json.dumps(payload)
                    for m in SKILL_PATH_RE.finditer(dumped):
                        skill_usage[m.group(1)] += 1
        if has_events:
            sessions_by_kind[kind or "unknown"] += 1

    stats = _duration_stats(total_secs)
    stats.update(
        noncached_input_tokens_total=sum(noncached_input_tokens),
        output_tokens_total=sum(output_tokens),
        token_measured_n=len(output_tokens),
        token_unmeasured_n=len(total_secs) - len(output_tokens),
    )
    return {
        "sessions_by_kind": dict(sessions_by_kind),
        "stop_continuations": stats,
        "continuations_by_kind": dict(continuations_by_kind),
        "injected_context": injected_context,
        "skill_usage": dict(skill_usage),
    }


def _append_counts(lines: list[str], label: str, mapping: dict) -> None:
    lines.append(label)
    for k, v in sorted(mapping.items(), key=lambda kv: -kv[1]):
        lines.append(f"  {v:6d}  {k}")


def _stop_line(s: dict, extra: str = "") -> str:
    if not s["n"]:
        return "Stop continuations: none"
    return (
        f"Stop continuations: n={s['n']} p50={s['p50']}s p90={s['p90']}s "
        f"max={s['max']}s total={s['total_minutes']}min{extra}"
    )


def render_text(results: dict, days: int) -> str:
    lines = [f"Hook cost report - last {days} day(s)"]

    if "claude" in results:
        c = results["claude"]
        lines += ["", "=== Claude ==="]
        _append_counts(lines, "Sessions by entrypoint:", c["sessions_by_entrypoint"])
        lines.append("Hook outcomes by (event, type):")
        for row in c["hook_outcomes"]:
            lines.append(f"  {row['count']:6d}  {row['event']} / {row['type']}")
        lines.append("Non-success hooks (top 15) by (type, exitCode, command):")
        for row in c["non_success_top15"]:
            lines.append(
                f"  {row['count']:6d}  {row['type']} exit={row['exit_code']} "
                f"cmd={row['command']!r}"
            )
        lines.append(_stop_line(c["stop_continuations"]))
        _append_counts(lines, "Continuations by project:", c["continuations_by_project"])
        _append_counts(lines, "Skill usage:", c["skill_usage"])
        lines.append("Agent launches by (subagent_type, model):")
        for row in c["agent_launches"]:
            lines.append(f"  {row['count']:6d}  {row['subagent_type']} / {row['model']}")

    if "codex" in results:
        x = results["codex"]
        s = x["stop_continuations"]
        extra = (
            f" noncached_input_tokens={s['noncached_input_tokens_total']} "
            f"output_tokens={s['output_tokens_total']} "
            f"token_measured_n={s['token_measured_n']} "
            f"token_unmeasured_n={s['token_unmeasured_n']}"
            if s["n"]
            else ""
        )
        lines += ["", "=== Codex ==="]
        _append_counts(lines, "Sessions by kind:", x["sessions_by_kind"])
        lines.append(_stop_line(s, extra))
        _append_counts(lines, "Continuations by session kind:", x["continuations_by_kind"])
        lines.append("Injected context kinds (messages containing kind, bytes; 'other' = rest of those messages):")
        for k, v in sorted(x["injected_context"].items(), key=lambda kv: -kv[1]["count"]):
            lines.append(f"  {v['count']:6d}  {v['bytes']:8d}B  {k}")
        _append_counts(lines, "Skill usage:", x["skill_usage"])

    return "\n".join(lines)


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Measure Claude Code / Codex hook cost from local transcripts."
    )
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--provider", choices=("claude", "codex", "both"), default="both")
    p.add_argument("--claude-root", type=Path, default=DEFAULT_CLAUDE_ROOT)
    p.add_argument("--codex-root", type=Path, default=DEFAULT_CODEX_ROOT)
    p.add_argument("--json", action="store_true")
    return p


def run(args: argparse.Namespace) -> dict:
    cutoff_ts = time.time() - args.days * 86400
    results: dict[str, Any] = {}
    if args.provider in ("claude", "both"):
        results["claude"] = collect_claude(Path(args.claude_root), cutoff_ts)
    if args.provider in ("codex", "both"):
        results["codex"] = collect_codex(Path(args.codex_root), cutoff_ts)
    return results


def main(argv: Optional[list[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    results = run(args)
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(render_text(results, args.days))
    return 0


if __name__ == "__main__":
    sys.exit(main())
