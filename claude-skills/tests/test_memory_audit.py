"""Tests for scripts/memory_audit.py — memory-management schema audit."""

from __future__ import annotations

from pathlib import Path

import memory_audit
import pytest

VALID_FILE = """---
name: {name}
description: scenario keywords plus core conclusion for {name}
metadata:
  type: {mem_type}
---

# {name}

Body text.
{extra}
"""


def write_memory(tmp_path: Path, filename: str, *, name: str | None = None, mem_type: str = "project", extra: str = "") -> Path:
    name = name if name is not None else filename.removesuffix(".md")
    path = tmp_path / filename
    path.write_text(VALID_FILE.format(name=name, mem_type=mem_type, extra=extra), encoding="utf-8")
    return path


def write_index(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "MEMORY.md"
    path.write_text(body, encoding="utf-8")
    return path


# ---------- dir resolution / exit codes ----------


def test_missing_dir_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    missing = tmp_path / "nope"
    assert memory_audit.main(["--dir", str(missing)]) == 2
    assert "does not exist" in capsys.readouterr().err


def test_empty_dir_reports_zero_files_and_full_compliance(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert memory_audit.main(["--dir", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "0 files" in out
    assert "100%" in out


def test_unreadable_file_during_audit_exits_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    write_memory(tmp_path, "share-topology.md")

    def _raise(path: Path) -> memory_audit.FileReport:
        raise OSError("permission denied")

    monkeypatch.setattr(memory_audit, "audit_file", _raise)
    assert memory_audit.main(["--dir", str(tmp_path)]) == 2
    assert "cannot read memory directory" in capsys.readouterr().err


def test_env_var_beats_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLAUDE_MEMORY_DIR", str(tmp_path))
    assert memory_audit.resolve_memory_dir(None) == tmp_path


def test_cli_dir_beats_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    other = tmp_path / "other"
    monkeypatch.setenv("CLAUDE_MEMORY_DIR", str(other))
    assert memory_audit.resolve_memory_dir(str(tmp_path)) == tmp_path


def test_slug_derivation_maps_windows_path_chars(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("CLAUDE_MEMORY_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    resolved = memory_audit.resolve_memory_dir(None)
    slug = resolved.parent.name
    assert ":" not in slug and "\\" not in slug and "/" not in slug
    assert resolved.name == "memory"
    assert resolved.parent.parent.name == "projects"


# ---------- per-file hard checks ----------


def test_valid_nested_metadata_file_is_clean(tmp_path: Path) -> None:
    path = write_memory(tmp_path, "share-topology.md")
    report = memory_audit.audit_file(path)
    assert report.hard == []
    assert report.mem_type == "project"


def test_flat_type_accepted_as_legacy(tmp_path: Path) -> None:
    path = tmp_path / "legacy-entry.md"
    path.write_text(
        "---\nname: legacy-entry\ndescription: legacy flat type entry\ntype: reference\n---\n\n# Legacy\n",
        encoding="utf-8",
    )
    report = memory_audit.audit_file(path)
    assert report.hard == []
    assert report.mem_type == "reference"


def test_missing_frontmatter_is_hard_violation(tmp_path: Path) -> None:
    path = tmp_path / "no-frontmatter.md"
    path.write_text("# Just a heading\n", encoding="utf-8")
    report = memory_audit.audit_file(path)
    assert any("frontmatter" in v for v in report.hard)


def test_crlf_frontmatter_still_detected(tmp_path: Path) -> None:
    path = tmp_path / "crlf-entry.md"
    content = "---\r\nname: crlf-entry\r\ndescription: crlf file\r\nmetadata:\r\n  type: project\r\n---\r\n\r\n# CRLF\r\n"
    path.write_bytes(content.encode("utf-8"))
    report = memory_audit.audit_file(path)
    assert report.hard == []


def test_missing_required_fields_flagged(tmp_path: Path) -> None:
    path = tmp_path / "no-fields.md"
    path.write_text("---\nname: no-fields\n---\n\n# Body\n", encoding="utf-8")
    report = memory_audit.audit_file(path)
    assert any("description" in v for v in report.hard)
    assert any("type" in v for v in report.hard)


def test_invalid_type_value_flagged(tmp_path: Path) -> None:
    path = write_memory(tmp_path, "bad-type.md", mem_type="journal")
    report = memory_audit.audit_file(path)
    assert any("journal" in v for v in report.hard)


def test_feedback_without_why_flagged(tmp_path: Path) -> None:
    path = write_memory(tmp_path, "trap-lesson.md", mem_type="feedback")
    report = memory_audit.audit_file(path)
    assert any("Why" in v for v in report.hard)


@pytest.mark.parametrize("why_marker", ["## Why", "## Root cause", "**Why:** because", "**Root cause:** because"])
def test_feedback_why_forms_accepted(tmp_path: Path, why_marker: str) -> None:
    path = write_memory(tmp_path, "trap-lesson.md", mem_type="feedback", extra=f"\n{why_marker}\nreasoning\n")
    report = memory_audit.audit_file(path)
    assert report.hard == []


def test_non_kebab_filename_flagged(tmp_path: Path) -> None:
    path = write_memory(tmp_path, "feedback_snake_case.md", name="feedback_snake_case")
    report = memory_audit.audit_file(path)
    assert any("kebab" in v for v in report.hard)


def test_name_filename_mismatch_flagged(tmp_path: Path) -> None:
    path = write_memory(tmp_path, "actual-name.md", name="different-name")
    report = memory_audit.audit_file(path)
    assert any("does not match" in v for v in report.hard)


# ---------- per-file soft checks ----------


def test_oversize_line_count_is_soft(tmp_path: Path) -> None:
    path = write_memory(tmp_path, "big-topic.md", extra="\n".join(f"line {i}" for i in range(120)))
    report = memory_audit.audit_file(path)
    assert report.hard == []
    assert any("100 lines" in s for s in report.soft)


def test_five_h2_sections_is_soft(tmp_path: Path) -> None:
    extra = "\n".join(f"## Section {i}\ntext\n" for i in range(5))
    path = write_memory(tmp_path, "many-topics.md", extra=extra)
    report = memory_audit.audit_file(path)
    assert any("H2" in s for s in report.soft)


# ---------- index checks ----------


def test_broken_link_detected_and_digit_links_resolve(tmp_path: Path) -> None:
    write_memory(tmp_path, "bug-2013-fix.md")
    index = write_index(tmp_path, "# Index\n\n- [bug-2013-fix](bug-2013-fix.md) — hook\n- [ghost](ghost-entry.md) — hook\n")
    report = memory_audit.audit_index(index, {"bug-2013-fix.md"})
    assert report.broken_links == ["ghost-entry.md"]


def test_unindexed_uses_exact_match_not_substring(tmp_path: Path) -> None:
    index = write_index(tmp_path, "# Index\n\n- [foo-bar](foo-bar.md) — hook\n")
    report = memory_audit.audit_index(index, {"foo-bar.md", "foo.md"})
    assert report.unindexed == ["foo.md"]


def test_index_budget_boundaries(tmp_path: Path) -> None:
    exact = write_index(tmp_path, "x" * 23_000)
    report = memory_audit.audit_index(exact, set())
    assert report.over_budget is False
    over = write_index(tmp_path, "x" * 23_001)
    report = memory_audit.audit_index(over, set())
    assert report.over_budget is True


def test_index_line_budget_boundary(tmp_path: Path) -> None:
    exact = write_index(tmp_path, "\n".join("line" for _ in range(190)))
    assert memory_audit.audit_index(exact, set()).over_budget is False
    over = write_index(tmp_path, "\n".join("line" for _ in range(191)))
    assert memory_audit.audit_index(over, set()).over_budget is True


def test_long_entry_line_flagged_but_aggregate_exempt(tmp_path: Path) -> None:
    long_single = "- [one](one-entry.md) — " + "d" * 160
    long_aggregate = "- topic → [a](a-entry.md) · [b](b-entry.md) — " + "d" * 160
    index = write_index(tmp_path, f"# Index\n\n{long_single}\n{long_aggregate}\n")
    report = memory_audit.audit_index(index, {"one-entry.md", "a-entry.md", "b-entry.md"})
    assert len(report.long_entry_lines) == 1
    assert "one-entry" in report.long_entry_lines[0]


def test_group_overload_detected(tmp_path: Path) -> None:
    entries = "\n".join(f"- [e-{i}](e-{i}.md) — hook" for i in range(15))
    index = write_index(tmp_path, f"# Index\n\n## Big Group\n\n{entries}\n")
    report = memory_audit.audit_index(index, {f"e-{i}.md" for i in range(15)})
    assert report.overloaded_groups == ["Big Group"]


# ---------- compliance formula ----------


def test_compliance_is_per_file_boolean_never_negative(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad = tmp_path / "bad_file_name.md"
    bad.write_text("no frontmatter at all\n", encoding="utf-8")  # multiple violations in one file
    write_memory(tmp_path, "good-entry.md")
    write_index(tmp_path, "- [good-entry](good-entry.md) — hook\n- [bad](bad_file_name.md) — hook\n")
    assert memory_audit.main(["--dir", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "50%" in out
    assert "1 clean" in out
