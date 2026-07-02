"""Audit a Claude Code auto-memory directory against the memory-management schema.

Ported from jau123/claude-memory-manager ``templates/audit-memory.template.sh``
(MIT, (c) 2026 jau123) — see ``skills/memory-management/ATTRIBUTION.md``.

Report-only by design (soft-warning philosophy): the tool never edits files and
exits 0 whenever the audit ran, regardless of violations. Exit 2 means the
memory directory could not be resolved or read. Character counts use decoded
``len(str)``, matching the harness's 25,000-character index load limit.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

VALID_TYPES = ("user", "feedback", "project", "reference")
INDEX_NAME = "MEMORY.md"
HARD_CHAR_CAP = 25_000
HARD_LINE_CAP = 200
WARN_CHARS = 23_000
WARN_LINES = 190
ENTRY_LINE_LIMIT = 160
OVERSIZE_LINES = 100
OVERSIZE_H2 = 5
GROUP_OVERLOAD = 15
STALE_DAYS = 30

_KEBAB = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_LINK_TARGET = re.compile(r"\(([A-Za-z0-9._-]+\.md)\)")
_MD_LINK = re.compile(r"\[[^\]]+\]\([^)]+\)")
_WHY = re.compile(r"^\s*(?:##\s+(?:why|root\s+cause)\b|\*\*(?:why|root\s+cause)\s*:?\s*\*\*)", re.IGNORECASE)
_H2 = re.compile(r"^##[^#]")
_TOP_KEY = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$")
_NESTED_TYPE = re.compile(r"^\s+type:\s*(\S+)\s*$")


@dataclass
class FileReport:
    """Audit result for one memory topic file."""

    path: Path
    hard: list[str] = field(default_factory=list)
    soft: list[str] = field(default_factory=list)
    stale: bool = False
    mem_type: str | None = None


@dataclass
class IndexReport:
    """Audit result for the MEMORY.md index."""

    chars: int = 0
    lines: int = 0
    broken_links: list[str] = field(default_factory=list)
    unindexed: list[str] = field(default_factory=list)
    overloaded_groups: list[str] = field(default_factory=list)
    long_entry_lines: list[str] = field(default_factory=list)
    over_budget: bool = False
    missing: bool = False


def resolve_memory_dir(cli_dir: str | None) -> Path:
    """Resolve the memory dir: --dir > CLAUDE_MEMORY_DIR > cwd-derived default."""
    if cli_dir:
        return Path(cli_dir)
    env_dir = os.environ.get("CLAUDE_MEMORY_DIR")
    if env_dir:
        return Path(env_dir)
    slug = re.sub(r"[:\\/]", "-", str(Path.cwd().resolve()))
    return Path.home() / ".claude" / "projects" / slug / "memory"


def _parse_frontmatter(lines: list[str]) -> tuple[dict[str, str], str | None, int]:
    """Return (top-level fields, resolved type, body start index).

    ``type`` resolves from nested ``metadata.type`` first, then legacy flat
    ``type:``. Body start is the line index after the closing ``---``.
    """
    fields: dict[str, str] = {}
    nested_type: str | None = None
    flat_type: str | None = None
    in_metadata = False
    end = len(lines)
    for i, raw in enumerate(lines[1:], start=1):
        if raw.strip() == "---":
            end = i + 1
            break
        top = _TOP_KEY.match(raw)
        if top and not raw.startswith((" ", "\t")):
            key, value = top.group(1), top.group(2).strip()
            in_metadata = key == "metadata"
            if not in_metadata:
                fields[key] = value
                if key == "type" and value:
                    flat_type = value
            continue
        if in_metadata:
            nested = _NESTED_TYPE.match(raw)
            if nested:
                nested_type = nested.group(1)
    return fields, nested_type or flat_type, end


def audit_file(path: Path) -> FileReport:
    """Run all per-file hard and soft checks on one memory topic file."""
    report = FileReport(path=path)
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    if not lines or lines[0].strip() != "---":
        report.hard.append("missing frontmatter (first line must be ---)")
        body = lines
    else:
        fields, mem_type, body_start = _parse_frontmatter(lines)
        body = lines[body_start:]
        report.mem_type = mem_type
        name = fields.get("name", "")
        if not name:
            report.hard.append("missing frontmatter field: name")
        if not fields.get("description"):
            report.hard.append("missing frontmatter field: description")
        if mem_type is None:
            report.hard.append("missing metadata.type (or legacy flat type)")
        elif mem_type not in VALID_TYPES:
            report.hard.append(f"invalid type '{mem_type}' (expected one of {', '.join(VALID_TYPES)})")
        if name and name != path.stem:
            report.hard.append(f"frontmatter name '{name}' does not match filename")
        if mem_type == "feedback" and not any(_WHY.match(line) for line in body):
            report.hard.append("feedback file missing a Why section (## Why / ## Root cause / **Why:**)")

    if not _KEBAB.match(path.stem):
        report.hard.append(f"filename '{path.name}' is not kebab-case")

    if len(lines) > OVERSIZE_LINES:
        report.soft.append(f"file exceeds {OVERSIZE_LINES} lines ({len(lines)}) — consider a split")
    h2_count = sum(1 for line in lines if _H2.match(line))
    if h2_count >= OVERSIZE_H2:
        report.soft.append(f"file has {h2_count} H2 sections (threshold {OVERSIZE_H2}) — consider a split")

    age_days = (time.time() - path.stat().st_mtime) / 86_400
    report.stale = age_days > STALE_DAYS
    return report


def audit_index(index_path: Path, memory_filenames: set[str]) -> IndexReport:
    """Run index-level checks against MEMORY.md."""
    report = IndexReport()
    if not index_path.is_file():
        report.missing = True
        return report
    text = index_path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    report.chars = len(text)
    report.lines = len(lines)
    report.over_budget = report.chars > WARN_CHARS or report.lines > WARN_LINES

    targets = set(_LINK_TARGET.findall(text))
    report.broken_links = sorted(t for t in targets if t != INDEX_NAME and t not in memory_filenames)
    report.unindexed = sorted(f for f in memory_filenames if f not in targets)

    current_group = ""
    group_counts: dict[str, int] = {}
    for line in lines:
        if line.startswith("## "):
            current_group = line[3:].strip()
        elif line.startswith("- ") and current_group:
            group_counts[current_group] = group_counts.get(current_group, 0) + 1
        if line.startswith("- [") and len(line) > ENTRY_LINE_LIMIT and len(_MD_LINK.findall(line)) < 2:
            report.long_entry_lines.append(line[:80])
    report.overloaded_groups = sorted(g for g, n in group_counts.items() if n >= GROUP_OVERLOAD)
    return report


def _print_list(header: str, items: list[str]) -> None:
    if items:
        print(f"  {header}:")
        for item in items:
            print(f"    - {item}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit a Claude Code auto-memory directory.")
    parser.add_argument("--dir", dest="dir", default=None, help="Memory directory (overrides CLAUDE_MEMORY_DIR and the cwd default).")
    args = parser.parse_args(argv)

    memory_dir = resolve_memory_dir(args.dir)
    if not memory_dir.is_dir():
        print(f"error: memory directory does not exist: {memory_dir}", file=sys.stderr)
        return 2

    try:
        files = sorted(p for p in memory_dir.glob("*.md") if p.name != INDEX_NAME and not p.name.startswith("."))
        reports = [audit_file(p) for p in files]
        index_report = audit_index(memory_dir / INDEX_NAME, {p.name for p in files})
    except OSError as exc:
        print(f"error: cannot read memory directory: {exc}", file=sys.stderr)
        return 2

    total = len(reports)
    clean = sum(1 for r in reports if not r.hard)
    compliance = 100 if total == 0 else round(100 * clean / total)

    print(f"Memory Audit — {memory_dir}")
    print(f"  Files: {total} files")
    for r in reports:
        _print_list(f"HARD {r.path.name}", r.hard)
    for r in reports:
        _print_list(f"soft {r.path.name}", r.soft)
    stale = [r.path.name for r in reports if r.stale]
    _print_list(f"info: untouched > {STALE_DAYS} days (signal, not a violation)", stale)
    if index_report.missing:
        print("  soft: no MEMORY.md index found")
    else:
        cap = f"caps {HARD_CHAR_CAP} chars / {HARD_LINE_CAP} lines, warn > {WARN_CHARS} / > {WARN_LINES}"
        status = "OVER BUDGET" if index_report.over_budget else "OK"
        print(f"  Index: {index_report.chars} chars, {index_report.lines} lines ({cap}) — {status}")
        _print_list("HARD broken index links", index_report.broken_links)
        _print_list("soft not indexed in MEMORY.md", index_report.unindexed)
        _print_list(f"soft groups with >= {GROUP_OVERLOAD} entries", index_report.overloaded_groups)
        _print_list(f"soft entry lines > {ENTRY_LINE_LIMIT} chars (single-link)", index_report.long_entry_lines)
    print(f"  Hard-rule compliance: {compliance}% ({clean} clean files / {total} files) — target >= 95%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
