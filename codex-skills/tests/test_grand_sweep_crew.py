"""Contract tests for the grand-sweep campaign kit (crew.py and workflows)."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CREW = ROOT / "skills" / "grand-sweep" / "scripts" / "crew.py"
WORKFLOWS = ROOT / "skills" / "grand-sweep" / "workflows"
WORKFLOW_FILES = ["breadth.dwf.ts", "lenses.dwf.ts", "confirm.dwf.ts"]

GIDENT = ["-c", "user.name=Kit Test", "-c", "user.email=kit-test@example.com"]

WHAT = "fixture finding"


def run_crew(campaign, *argv):
    return subprocess.run(
        [sys.executable, "-I", str(CREW), str(campaign), *argv],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def git(repo, *argv):
    done = subprocess.run(
        ["git", "-C", str(repo), *argv],
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode != 0:
        raise AssertionError("git %s failed: %s" % (argv, done.stderr))
    return done.stdout


def candidate_identity(where, what):
    where = where.strip()
    if where.startswith("./"):
        where = where[2:]
    paren = re.match(r"^(.*)\((\d+)\)$", where)
    if paren:
        where = paren.group(1) + ":" + paren.group(2)
    path, sep, tail = where.rpartition(":")
    if sep and tail.isdigit():
        head, sep2, mid = path.rpartition(":")
        if sep2 and mid.isdigit():
            tail = mid
            path = head
        line = tail.strip()
    else:
        path, line = where, ""
    norm_path = path.replace("\\", "/").strip("/").casefold()
    norm_what = " ".join(what.split()).casefold()[:120]
    return "%s|%s|%s" % (norm_path, line, norm_what)


def candidate_id(where, what):
    return "C-" + hashlib.sha256(candidate_identity(where, what).encode("utf-8")).hexdigest()[:10]


class GrandSweepKitFixture:
    """A throwaway git repo, campaign dir, scope.json and kit package dir."""

    def __init__(self, base: Path) -> None:
        self.repo = base / "repo"
        self.repo.mkdir(parents=True)
        git(self.repo, "init", "-q")
        files = {
            "src/a.py": "a" * 200,
            "src/b.py": "b" * 200,
            "src/c.py": "c" * 3000,
            "src/tests/test_a.py": "t" * 100,
            "docs/guide.md": "d" * 100,
            "tools/run.ps1": "r" * 100,
            "src/tool.exe": "x" * 100,
        }
        for rel, text in files.items():
            target = self.repo / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8", newline="\n")
        git(self.repo, *GIDENT, "add", "-A")
        git(self.repo, *GIDENT, "commit", "-q", "-m", "fixture")
        self.commit = git(self.repo, "rev-parse", "HEAD").strip()

        self.campaign = base / "camp"
        self.campaign.mkdir(parents=True)
        self.kit = base / "pkg"
        (self.kit / "scripts").mkdir(parents=True)
        (self.kit / "workflows").mkdir(parents=True)
        (self.kit / "scripts" / "crew.py").write_text("# kit snapshot\n", encoding="utf-8")
        (self.kit / "workflows" / "breadth.dwf.ts").write_text("// kit snapshot\n", encoding="utf-8")
        self.scope = {
            "campaign": "kit-test-20261123-aa00",
            "root": str(self.repo).replace("\\", "/"),
            "commit": self.commit,
            "soloAtBytes": 2500,
            "excludeGlobs": ["**/*.exe"],
            "lanes": [
                {"name": "src", "prefix": "src", "include": ["src"],
                 "unit": {"maxFiles": 2, "maxBytes": 100000}},
                {"name": "docs", "prefix": "doc", "include": ["docs", "tools"],
                 "unit": {"maxFiles": 5, "maxBytes": 100000}},
            ],
            "subsets": {
                "py": {"description": "python files", "paths": ["src/a.py"]},
            },
            "lensSets": ["seam"],
        }
        self.lens_doc = {
            "set": "seam", "campaign": "kit-test-20261123-aa00",
            "lenses": [
                {"name": "one", "title": "First", "brief": "first seam", "inputs": ["src/a.py"]},
                {"name": "two", "title": "Second", "brief": "second seam", "inputs": []},
            ],
        }
        (self.campaign / "build").mkdir(parents=True, exist_ok=True)
        (self.campaign / "build" / "lenses-seam.json").write_text(
            json.dumps(self.lens_doc), encoding="utf-8", newline="\n")
        self.scope_path = self.campaign / "scope.json"
        self.scope_path.write_text(json.dumps(self.scope, indent=1), encoding="utf-8")

    def freeze(self, *extra, campaign=None, scope_path=None):
        return run_crew(
            campaign or self.campaign,
            "freeze",
            "--scope",
            str(scope_path or self.scope_path),
            "--kit",
            str(self.kit),
            *extra,
        )

    def write_scope(self):
        self.scope_path.write_text(json.dumps(self.scope, indent=1), encoding="utf-8")

    def write_verdict(self, lane, unit_id, doc, attempts=None):
        target = self.campaign / "staging" / "breadth" / lane / (unit_id + ".json")
        target.parent.mkdir(parents=True, exist_ok=True)
        if attempts is not None and isinstance(doc, dict):
            doc = dict(doc)
            doc["attempts"] = attempts
        if isinstance(doc, str):
            target.write_text(doc, encoding="utf-8", newline="\n")
        elif doc.get("__bom__"):
            payload = dict(doc)
            payload.pop("__bom__")
            target.write_text("﻿" + json.dumps(payload), encoding="utf-8", newline="\n")
        else:
            target.write_text(json.dumps(doc), encoding="utf-8", newline="\n")

    def write_lens_verdict(self, lens_set, lens, doc):
        target = self.campaign / "staging" / "lens" / lens_set / (lens + ".json")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(doc), encoding="utf-8", newline="\n")

    def write_confirm(self, candidate, verdict):
        target = self.campaign / "staging" / "confirm" / (candidate + ".json")
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(candidate, dict):
            target.write_text(json.dumps(candidate), encoding="utf-8", newline="\n")
            return
        target.write_text(
            json.dumps({
                "candidateId": candidate,
                "verdict": verdict,
                "duplicateOf": None,
                "reasoning": "fixture",
                "evidence": "fixture",
                "counterevidence": "",
                "adjustedSeverity": "low",
            }),
            encoding="utf-8",
            newline="\n",
        )

    def write_lens_set(self, lens_set, doc):
        target = self.campaign / "build" / ("lenses-%s.json" % lens_set)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(doc), encoding="utf-8", newline="\n")

    def build_file(self, name, doc):
        target = self.campaign / "build" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(doc, indent=1), encoding="utf-8", newline="\n")
        return target


def completed(unit_id, where="src/a.py:1", what=WHAT, severity="medium"):
    return {
        "unitId": unit_id,
        "status": "completed",
        "reviewer": "rev-" + unit_id,
        "attempts": 1,
        "findings": [
            {"severity": severity, "where": where, "what": what, "evidence": "line one"},
        ],
        "summary": "fixture verdict",
        "covered": ["src/a.py:1-200"],
    }


def failed(unit_id, attempts=1, reason="input-changed"):
    return {
        "unitId": unit_id,
        "status": "failed",
        "reviewer": "rev-" + unit_id,
        "attempts": attempts,
        "findings": [],
        "summary": reason,
        "covered": [],
    }


class TestGrandSweepCrew(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="gs-kit-")
        self.fx = GrandSweepKitFixture(Path(self._tmp.name))
        self.addCleanup(self._tmp.cleanup)

    def freeze_ok(self):
        done = self.fx.freeze()
        self.assertEqual(done.returncode, 0, done.stderr)
        return done

    # -- freeze -----------------------------------------------------------

    def test_freeze_determinism(self):
        other = Path(self._tmp.name) / "camp2"
        other.mkdir()
        (other / "build").mkdir(parents=True, exist_ok=True)
        (other / "build" / "lenses-seam.json").write_text(
            json.dumps(self.fx.lens_doc), encoding="utf-8", newline="\n")
        first = self.fx.freeze()
        self.assertEqual(first.returncode, 0, first.stderr)
        second = self.fx.freeze(campaign=other)
        self.assertEqual(second.returncode, 0, second.stderr)
        for name in ("manifest.json", "units.json"):
            a = (self.fx.campaign / name).read_bytes()
            b = (other / name).read_bytes()
            self.assertEqual(a, b, "%s must be byte-identical across freezes" % name)
        receipt = json.loads(
            (self.fx.campaign / "build" / "freeze-receipt.json").read_text(encoding="utf-8-sig"))
        for key in ("frozenAtUtc", "scopeSha256", "kit", "manifestSha256", "unitsSha256"):
            self.assertIn(key, receipt)
        self.assertEqual(sorted(receipt["kit"]["files"]),
                         ["scripts/crew.py", "workflows/breadth.dwf.ts"])
        self.assertTrue(receipt["kit"]["packageDir"])
        self.assertTrue((self.fx.campaign / "build" / "kit" / "scripts" / "crew.py").exists())

    def test_manifest_has_no_timestamp_or_kit_path(self):
        self.freeze_ok()
        raw = (self.fx.campaign / "manifest.json").read_text(encoding="utf-8-sig")
        self.assertNotIn(str(self.fx.kit).replace("\\", "/"), raw)
        self.assertNotIn("frozenAt", raw)
        self.assertFalse((self.fx.campaign / "manifest.txt").exists(),
                         "manifest.txt was dropped in spec v2")
        for name in ("manifest.json", "units.json"):
            data = (self.fx.campaign / name).read_bytes()
            self.assertFalse(data.startswith(b"\xef\xbb\xbf"), name + " must not have a BOM")
            self.assertNotIn(b"\r\n", data, name + " must use LF")

    def test_commit_mismatch_refused(self):
        self.fx.scope["commit"] = "0" * 40
        self.fx.write_scope()
        done = self.fx.freeze()
        self.assertEqual(done.returncode, 1)
        self.assertFalse((self.fx.campaign / "manifest.json").exists())

    def test_dirty_root_refused(self):
        (self.fx.repo / "src" / "extra.py").write_text("x", encoding="utf-8")
        done = self.fx.freeze()
        self.assertEqual(done.returncode, 1)
        self.assertIn("dirty", done.stderr.lower())

    def test_overlapping_includes_refused(self):
        self.fx.scope["lanes"][1]["include"] = ["docs", "tools", "src/tests"]
        self.fx.write_scope()
        done = self.fx.freeze()
        self.assertEqual(done.returncode, 1)
        self.assertIn("overlap", done.stderr.lower())

    def test_unassigned_tracked_file_refused(self):
        # An include entry that matches no tracked file (typo) would silently
        # drop files from every lane; freeze must fail closed naming it.
        self.fx.scope["lanes"][0]["include"] = ["src", "src/typo.py"]
        self.fx.write_scope()
        done = self.fx.freeze()
        self.assertEqual(done.returncode, 1)
        self.assertIn("src/typo.py".replace("/", os.sep),
                      done.stderr.replace("\\", os.sep).replace("/", os.sep))

    def test_subset_path_not_manifested_refused(self):
        self.fx.scope["subsets"]["py"]["paths"] = ["src/missing.py"]
        self.fx.write_scope()
        done = self.fx.freeze()
        self.assertEqual(done.returncode, 1)
        self.assertIn("src/missing.py".replace("/", os.sep),
                      done.stderr.replace("\\", os.sep).replace("/", os.sep))

    def test_exclusion_counting(self):
        self.freeze_ok()
        manifest = json.loads((self.fx.campaign / "manifest.json").read_text(encoding="utf-8-sig"))
        self.assertEqual([e["path"] for e in manifest["exclusions"]], ["src/tool.exe"])
        self.assertTrue(manifest["exclusions"][0]["reason"])
        self.assertNotIn("src/tool.exe", [f["rel"] for f in manifest["files"]])

    def test_unit_packing_respects_both_caps(self):
        self.fx.scope["lanes"][0]["unit"] = {"maxFiles": 5, "maxBytes": 450}
        self.fx.write_scope()
        self.freeze_ok()
        units = json.loads((self.fx.campaign / "units.json").read_text(encoding="utf-8-sig"))
        src_units = [u for u in units["units"] if u["lane"] == "src"]
        packs = [[f.split("/")[-1] for f in u["files"]] for u in src_units]
        self.assertIn(["a.py", "b.py"], packs)  # 400 bytes <= 450
        self.assertIn(["test_a.py"], packs)

    def test_oversize_file_is_solo(self):
        self.freeze_ok()
        units = json.loads((self.fx.campaign / "units.json").read_text(encoding="utf-8-sig"))
        solo = [u for u in units["units"] if u["oversize"]]
        self.assertEqual(len(solo), 1)
        self.assertEqual(solo[0]["files"], ["src/c.py"])
        self.assertTrue(solo[0]["bytes"] >= 2500)

    def test_lane_prefixes_unique(self):
        self.fx.scope["lanes"][1]["prefix"] = "src"
        self.fx.write_scope()
        done = self.fx.freeze()
        self.assertEqual(done.returncode, 1)
        self.assertIn("prefix", done.stderr.lower())

    def test_freeze_outputs_and_shapes(self):
        self.freeze_ok()
        manifest = json.loads((self.fx.campaign / "manifest.json").read_text(encoding="utf-8-sig"))
        self.assertEqual(manifest["campaign"], "kit-test-20261123-aa00")
        self.assertEqual(manifest["commit"], self.fx.commit)
        self.assertEqual(manifest["revision"], 1)
        self.assertEqual(manifest["totals"]["files"], 6)
        self.assertEqual(manifest["subsets"]["py"]["paths"], ["src/a.py"])
        kinds = {f["rel"]: f["kind"] for f in manifest["files"]}
        self.assertEqual(kinds["src/a.py"], "source")
        self.assertEqual(kinds["src/tests/test_a.py"], "test")
        self.assertEqual(kinds["docs/guide.md"], "doc")
        self.assertEqual(kinds["tools/run.ps1"], "script")

    def test_freeze_requires_kit(self):
        done = run_crew(self.fx.campaign, "freeze", "--scope", str(self.fx.scope_path))
        self.assertEqual(done.returncode, 2)

    def test_replace_supersedes_without_deleting(self):
        self.freeze_ok()
        git(self.fx.repo, *GIDENT, "commit", "-q", "--allow-empty", "-m", "second")
        self.fx.scope["commit"] = git(self.fx.repo, "rev-parse", "HEAD").strip()
        self.fx.write_scope()
        done = self.fx.freeze("--replace")
        self.assertEqual(done.returncode, 0, done.stderr)
        superseded = list((self.fx.campaign / "superseded").rglob("manifest.json"))
        self.assertEqual(len(superseded), 1, "previous manifest must be retained, not deleted")
        self.assertTrue(list((self.fx.campaign / "superseded").rglob("units.json")))
        manifest = json.loads((self.fx.campaign / "manifest.json").read_text(encoding="utf-8-sig"))
        self.assertEqual(manifest["revision"], 2)
        done = self.fx.freeze()
        self.assertEqual(done.returncode, 1,
                         "freeze without --replace must refuse an existing manifest")
        self.assertIn("replace", done.stderr.lower())

    # -- lanes / units -----------------------------------------------------

    def test_lanes_command(self):
        self.freeze_ok()
        done = run_crew(self.fx.campaign, "lanes")
        self.assertEqual(done.returncode, 0, done.stderr)
        lanes = json.loads(done.stdout)
        self.assertEqual([l["lane"] for l in lanes], ["src", "docs"])
        self.assertEqual(lanes[0]["units"], 3)
        self.assertEqual(lanes[0]["files"], 4)
        self.assertEqual(lanes[1]["units"], 1)

    def test_units_pending_adopts_and_excludes_terminal(self):
        self.freeze_ok()
        all_units = json.loads(run_crew(self.fx.campaign, "units", "src").stdout)
        self.assertEqual([u["id"] for u in all_units],
                         ["src-00001", "src-00002", "src-00003"])
        self.assertEqual(all_units[0]["files"][0][0], "src/a.py")
        self.assertRegex(all_units[0]["files"][0][1], r"^[0-9a-f]{64}$")
        self.assertEqual(all_units[0]["root"], str(self.fx.repo).replace("\\", "/"))
        self.fx.write_verdict("src", "src-00001", completed("src-00001"))
        self.fx.write_verdict("src", "src-00002", failed("src-00002", attempts=2))
        self.fx.write_verdict("src", "src-00003", failed("src-00003", attempts=3))
        pending = json.loads(run_crew(self.fx.campaign, "units", "src", "--pending").stdout)
        self.assertEqual([u["id"] for u in pending], ["src-00002"],
                         "adopted and terminal units must both be dropped")
        limited = json.loads(
            run_crew(self.fx.campaign, "units", "src", "--pending", "--limit", "1").stdout)
        self.assertEqual([u["id"] for u in limited], ["src-00002"])

    # -- agg / check -------------------------------------------------------

    def test_agg_tolerates_bom_bad_json_and_unitid_mismatch(self):
        self.freeze_ok()
        self.fx.write_verdict("src", "src-00001", {"__bom__": True, **completed("src-00001")})
        self.fx.write_verdict("src", "src-00002", "{not json")
        self.fx.write_verdict("src", "src-00003", completed("other-unit"))
        done = run_crew(self.fx.campaign, "agg", "src")
        self.assertEqual(done.returncode, 0, done.stderr)
        agg = json.loads(done.stdout)
        self.assertEqual(agg["units"], 3)
        self.assertEqual(agg["completed"], 1)
        self.assertEqual(agg["failed"], 2)
        self.assertEqual(agg["medium"], 1)
        coverage = json.loads(
            (self.fx.campaign / "build" / "breadth-coverage-src.json")
            .read_text(encoding="utf-8-sig"))
        reasons = [d.get("reason") for d in coverage["unitsDetail"]
                   if d["status"] == "failed"]
        self.assertTrue(all(reasons), "failed verdicts must record a reason")

    def test_check_reports_changed_and_missing(self):
        self.freeze_ok()
        (self.fx.repo / "src" / "a.py").write_text("changed", encoding="utf-8")
        (self.fx.repo / "src" / "b.py").unlink()
        done = run_crew(self.fx.campaign, "check", "src")
        self.assertEqual(done.returncode, 0, done.stderr)
        check = json.loads(done.stdout)
        self.assertEqual(check["files"], 4)
        self.assertEqual(check["changed"], 1)
        self.assertEqual(check["missing"], 1)
        self.assertTrue(any("a.py" in p for p in check["changedPaths"]))
        done_all = run_crew(self.fx.campaign, "check", "all")
        self.assertEqual(done_all.returncode, 0, done_all.stderr)
        self.assertEqual(json.loads(done_all.stdout)["files"], 6)

    # -- subset ------------------------------------------------------------

    def test_subset_maps_files_to_units_and_statuses(self):
        self.freeze_ok()
        self.fx.write_verdict("src", "src-00001", completed("src-00001"))
        done = run_crew(self.fx.campaign, "subset", "py")
        self.assertEqual(done.returncode, 0, done.stderr)
        rows = json.loads(done.stdout)["files"]
        self.assertEqual(rows, [{
            "file": "src/a.py", "lane": "src", "unit": "src-00001", "status": "completed",
        }])
        missing = run_crew(self.fx.campaign, "subset", "nope")
        self.assertEqual(missing.returncode, 1)

    # -- lenses ------------------------------------------------------------

    def test_lenses_validates_shape_and_pending(self):
        self.freeze_ok()
        self.fx.write_lens_set("seam", {
            "set": "seam", "campaign": "kit-test-20261123-aa00",
            "lenses": [
                {"name": "one", "title": "First", "brief": "first seam", "inputs": ["src/a.py"]},
                {"name": "two", "title": "Second", "brief": "second seam", "inputs": []},
            ]})
        listing = json.loads(run_crew(self.fx.campaign, "lenses", "seam").stdout)
        self.assertEqual([l["name"] for l in listing["lenses"]], ["one", "two"])
        self.assertEqual(listing["root"], str(self.fx.repo).replace("\\", "/"))
        self.assertEqual(listing["commit"], self.fx.commit)
        self.assertEqual(listing["campaign"], "kit-test-20261123-aa00")
        self.fx.write_lens_verdict("seam", "one", {
            "lens": "one", "status": "completed",
            "candidates": [{"severity": "high", "where": "tools/run.ps1:3",
                            "what": "lens hit", "evidence": "quoted"}],
            "clean": ["docs"], "notCovered": [], "summary": "ok"})
        pending = json.loads(run_crew(self.fx.campaign, "lenses", "seam", "--pending").stdout)
        self.assertEqual([l["name"] for l in pending["lenses"]], ["two"])
        done = run_crew(self.fx.campaign, "lensagg", "seam")
        self.assertEqual(done.returncode, 0, done.stderr)
        agg = json.loads(done.stdout)
        self.assertEqual(agg["lenses"], 2)
        self.assertEqual(agg["withVerdict"], 1)
        self.assertEqual(agg["candidates"], 1)
        self.assertEqual(agg["bySeverity"]["high"], 1)
        self.assertTrue((self.fx.campaign / "build" / "seam-coverage.json").exists())

    def test_lenses_fails_closed_on_bad_lens_file(self):
        self.freeze_ok()
        for bad in (
            {"set": "seam", "campaign": "x", "lenses": [{"name": "Bad Name"}]},
            {"set": "seam", "campaign": "x", "lenses": [
                {"name": "ok", "title": "t", "brief": "b", "inputs": []},
                {"name": "ok", "title": "t", "brief": "b", "inputs": []}]},
            {"set": "seam", "campaign": "x", "lenses": [
                {"name": "x" * 29, "title": "t", "brief": "b", "inputs": []}]},
            {"set": "seam", "campaign": "x", "lenses": "nope"},
        ):
            self.fx.write_lens_set("seam", bad)
            done = run_crew(self.fx.campaign, "lenses", "seam")
            self.assertEqual(done.returncode, 1, "must fail closed: %s" % json.dumps(bad))
        self.assertEqual(run_crew(self.fx.campaign, "lenses", "missing-set").returncode, 1)

    # -- candidates / confirm ---------------------------------------------

    def test_candidates_dedup_ids_and_sources(self):
        self.freeze_ok()
        self.fx.write_verdict("src", "src-00001", completed("src-00001", severity="low"))
        self.fx.write_verdict("src", "src-00002",
                              completed("src-00002", where="SRC/A.PY:1"))
        self.fx.write_lens_set("seam", {
            "set": "seam", "campaign": "kit-test-20261123-aa00",
            "lenses": [{"name": "one", "title": "T", "brief": "B", "inputs": []}]})
        self.fx.write_lens_verdict("seam", "one", {
            "lens": "one", "status": "completed",
            "candidates": [{"severity": "medium", "where": "src\\a.py:1",
                            "what": WHAT.upper(), "evidence": "q"}],
            "clean": [], "notCovered": [], "summary": "ok"})
        first_doc = json.loads(run_crew(self.fx.campaign, "candidates").stdout)
        first = first_doc["candidates"]
        self.assertEqual(first_doc["root"], str(self.fx.repo).replace("\\", "/"))
        self.assertEqual(first_doc["commit"], self.fx.commit)
        self.assertEqual(first_doc["campaign"], "kit-test-20261123-aa00")
        self.assertEqual(len(first), 1, "case-folded identity must merge")
        expected_id = candidate_id("src/a.py:1", WHAT)
        self.assertEqual(first[0]["id"], expected_id)
        self.assertEqual(first[0]["severity"], "medium")
        self.assertEqual(sorted(first[0]["sources"]),
                         ["lens:seam/one", "src-00001", "src-00002"])
        # Ids stay stable when an earlier-sorting candidate appears later.
        self.fx.write_verdict("docs", "doc-00001",
                              completed("doc-00001", where="docs/guide.md:1",
                                        what="other finding", severity="low"))
        second = json.loads(run_crew(self.fx.campaign, "candidates").stdout)["candidates"]
        by_id = {c["id"]: c for c in second}
        self.assertIn(expected_id, by_id)
        self.assertIn(candidate_id("docs/guide.md:1", "other finding"), by_id)
        self.assertEqual(by_id[expected_id]["sources"], first[0]["sources"])
        # Filters.
        high = json.loads(
            run_crew(self.fx.campaign, "candidates", "--min-severity", "high")
            .stdout)["candidates"]
        self.assertEqual(high, [])
        self.fx.write_confirm(expected_id, "confirmed")
        pending = json.loads(
            run_crew(self.fx.campaign, "candidates", "--pending").stdout)["candidates"]
        self.assertNotIn(expected_id, [c["id"] for c in pending])

    def test_confirmagg_counts(self):
        self.test_candidates_dedup_ids_and_sources()
        done = run_crew(self.fx.campaign, "confirmagg")
        self.assertEqual(done.returncode, 0, done.stderr)
        agg = json.loads(done.stdout)
        self.assertEqual(agg["candidates"], 2)
        self.assertEqual(agg["confirmed"], 1)
        self.assertEqual(agg["pending"], 1)
        self.assertTrue((self.fx.campaign / "build" / "confirm-coverage.json").exists())

    # -- status / close ----------------------------------------------------

    def test_status_computes_from_staging_without_coverage(self):
        self.freeze_ok()
        self.fx.write_verdict("src", "src-00001", completed("src-00001"))
        self.fx.write_verdict("src", "src-00003", failed("src-00003", attempts=3))
        self.fx.write_lens_set("seam", {
            "set": "seam", "campaign": "kit-test-20261123-aa00",
            "lenses": [{"name": "one", "title": "T", "brief": "B", "inputs": []}]})
        done = run_crew(self.fx.campaign, "status")
        self.assertEqual(done.returncode, 0, done.stderr)
        status = json.loads(done.stdout)
        src = [l for l in status["lanes"] if l["lane"] == "src"][0]
        self.assertEqual(src["units"], 3)
        self.assertEqual(src["completed"], 1)
        self.assertEqual(src["pending"], 1)  # src-00002
        self.assertEqual(src["terminalFailed"], 1)  # src-00003
        self.assertEqual(status["lensSets"][0]["lenses"], 1)
        self.assertEqual(status["lensSets"][0]["withVerdict"], 0)
        self.assertFalse(status["breadthComplete"])
        self.assertFalse(status["lensesComplete"])
        self.assertFalse(status["confirmComplete"])
        self.assertFalse(status["complete"])
        self.assertTrue(status["lensSetsDeclared"])
        subsets = status["subsets"]
        self.assertEqual(subsets["py"], {"files": 1, "covered": 1})

    def test_status_declares_lens_sets_explicitly(self):
        # Without scope.lensSets, status must say so and keep lensesComplete
        # false: a breadth-only campaign declares itself, not vacuous truth.
        self.freeze_ok()
        camp3 = Path(self._tmp.name) / "camp3"
        camp3.mkdir()
        scope = dict(self.fx.scope)
        scope.pop("lensSets")
        scope_path = camp3 / "scope.json"
        scope_path.write_text(json.dumps(scope), encoding="utf-8")
        done = self.fx.freeze(campaign=camp3, scope_path=scope_path)
        self.assertEqual(done.returncode, 0, done.stderr)
        status = json.loads(run_crew(camp3, "status").stdout)
        self.assertFalse(status["lensSetsDeclared"])
        self.assertFalse(status["lensesComplete"])
        self.assertFalse(status["complete"])
        self.assertTrue(any("no lens sets" in str(v).lower() for v in [status.get("note")]))
        # Declared but a set file vanished from disk: still not complete.
        (self.fx.campaign / "build" / "lenses-seam.json").unlink()
        status2 = json.loads(run_crew(self.fx.campaign, "status").stdout)
        self.assertFalse(status2["lensesComplete"], "a declared set missing on disk fails completeness")
        self.fx.write_lens_set("seam", self.fx.lens_doc)

    def test_close_fails_on_open_campaign(self):
        self.freeze_ok()
        done = run_crew(self.fx.campaign, "close")
        self.assertEqual(done.returncode, 1)
        checklist = json.loads(done.stdout)
        self.assertEqual(len(checklist["items"]), 7)
        self.assertFalse(checklist["pass"])

    def test_close_lists_terminal_failures(self):
        self.freeze_ok()
        self.fx.write_verdict("src", "src-00003", failed("src-00003", attempts=3))
        self.fx.write_verdict("src", "src-00001", completed("src-00001"))
        self.fx.write_verdict("src", "src-00002", completed("src-00002"))
        self.fx.write_verdict("docs", "doc-00001",
                              completed("doc-00001", where="docs/guide.md:1",
                                        what="other finding", severity="low"))
        self._satisfy_remaining_close_items()
        done = run_crew(self.fx.campaign, "close")
        self.assertEqual(done.returncode, 0, done.stderr)
        checklist = json.loads(done.stdout)
        item1 = [i for i in checklist["items"] if i["item"] == "breadth-units"][0]
        self.assertTrue(item1["pass"], "terminal failures are listed, not fatal")
        self.assertIn("src-00003", item1["detail"])

    def test_close_passes_on_closed_fixture(self):
        self.freeze_ok()
        for unit in ("src-00001", "src-00002", "src-00003"):
            where = "src/c.py:1" if unit == "src-00003" else "src/a.py:1"
            self.fx.write_verdict("src", unit, completed(unit, where=where))
        self.fx.write_verdict("docs", "doc-00001",
                              completed("doc-00001", where="docs/guide.md:1",
                                        what="other finding", severity="low"))
        self.fx.write_lens_set("seam", {
            "set": "seam", "campaign": "kit-test-20261123-aa00",
            "lenses": [{"name": "one", "title": "T", "brief": "B", "inputs": []}]})
        self.fx.write_lens_verdict("seam", "one", {
            "lens": "one", "status": "completed", "candidates": [], "clean": [],
            "notCovered": [], "summary": "ok"})
        self._satisfy_remaining_close_items()
        done = run_crew(self.fx.campaign, "close")
        self.assertEqual(done.returncode, 0, done.stderr)
        checklist = json.loads(done.stdout)
        self.assertTrue(checklist["pass"], checklist)
        status = json.loads(run_crew(self.fx.campaign, "status").stdout)
        self.assertTrue(status["breadthComplete"])
        self.assertTrue(status["lensesComplete"])
        self.assertTrue(status["complete"])

    def test_stdout_is_strict_utf8(self):
        # A1: piped stdout must be UTF-8 even with non-ASCII lens briefs.
        self.freeze_ok()
        self.fx.write_lens_set("seam", {
            "set": "seam", "campaign": "kit-test-20261123-aa00",
            "lenses": [{"name": "uni", "title": "T", "brief": "em—dash é → arrow",
                        "inputs": ["src/a.py"]}]})
        env = os.environ.copy()
        env.pop("PYTHONIOENCODING", None)
        done = subprocess.run(
            [sys.executable, "-I", str(CREW), str(self.fx.campaign), "lenses", "seam"],
            capture_output=True, env=env, check=False)
        text = done.stdout.decode("utf-8")  # strict: raises on cp1252 mojibake
        doc = json.loads(text)
        self.assertEqual(doc["lenses"][0]["brief"], "em—dash é → arrow")

    def test_refreeze_without_replace_leaves_kit_untouched(self):
        # A2: the refusal must happen before any kit snapshot write.
        self.freeze_ok()
        kit_file = self.fx.campaign / "build" / "kit" / "scripts" / "crew.py"
        before = kit_file.read_bytes()
        (self.fx.kit / "scripts" / "crew.py").write_text("# tampered\n", encoding="utf-8")
        done = self.fx.freeze()
        self.assertEqual(done.returncode, 1)
        self.assertEqual(kit_file.read_bytes(), before,
                         "refused freeze must not touch the frozen kit snapshot")
        self.assertFalse((self.fx.campaign / "build" / "kit.tmp").exists())

    def test_candidate_identity_merges_line_column_and_dot_forms(self):
        # B1: path:line, path:line:col, ./path:line and path(line) are one id.
        self.freeze_ok()
        self.fx.write_verdict("src", "src-00001", completed("src-00001", where="src/a.py:1"))
        self.fx.write_verdict("src", "src-00002",
                              completed("src-00002", where="./src/a.py:1:3"))
        self.fx.write_verdict("docs", "doc-00001",
                              completed("doc-00001", where="src\\a.py(1)",
                                        what=WHAT, severity="low"))
        cands = json.loads(
            run_crew(self.fx.campaign, "candidates").stdout)["candidates"]
        self.assertEqual([c["id"] for c in cands], [candidate_id("src/a.py:1", WHAT)])

    def test_verdict_without_unitid_is_failed(self):
        # M2: a missing unitId must not count as a completed verdict.
        self.freeze_ok()
        self.fx.write_verdict("src", "src-00001", {
            "status": "completed", "reviewer": "x", "findings": [],
            "summary": "anonymous", "covered": []})
        done = run_crew(self.fx.campaign, "agg", "src")
        agg = json.loads(done.stdout)
        self.assertEqual(agg["completed"], 0)
        self.assertEqual(agg["failed"], 1)
        coverage = json.loads(
            (self.fx.campaign / "build" / "breadth-coverage-src.json")
            .read_text(encoding="utf-8-sig"))
        reason = coverage["unitsDetail"][0].get("reason") or ""
        self.assertIn("unitId", reason)

    def test_malformed_verdicts_accumulate_attempts_to_terminal(self):
        # M3: repeated garbage must eventually become terminal-failed.
        self.freeze_ok()
        self.fx.write_verdict("src", "src-00001", "{not json")
        for round_index in range(3):
            run_crew(self.fx.campaign, "agg", "src")
        agg = json.loads(run_crew(self.fx.campaign, "agg", "src").stdout)
        self.assertEqual(agg["terminalFailed"], 1)
        pending = json.loads(
            run_crew(self.fx.campaign, "units", "src", "--pending").stdout)
        self.assertNotIn("src-00001", [u["id"] for u in pending])

    def test_subset_not_object_fails_cleanly(self):
        # M5: bad subset shapes fail with a message, not a traceback.
        self.fx.scope["subsets"]["bad"] = "not an object"
        self.fx.write_scope()
        done = self.fx.freeze()
        self.assertEqual(done.returncode, 1)
        self.assertNotIn("Traceback", done.stderr)
        self.assertIn("subset", done.stderr.lower())

    def test_close_fails_on_changed_inputs(self):
        # M6: close item 4 must fail when check reports changed inputs.
        self.test_close_passes_on_closed_fixture()
        (self.fx.repo / "src" / "a.py").write_text("tampered after close", encoding="utf-8")
        done = run_crew(self.fx.campaign, "close")
        self.assertEqual(done.returncode, 1)
        item4 = [i for i in json.loads(done.stdout)["items"]
                 if i["item"] == "inputs-clean"][0]
        self.assertFalse(item4["pass"])
        self.assertIn("1 changed", item4["detail"])

    def test_confirm_gate_blocks_vacuous_completeness(self):
        # Fresh campaign: breadth and lenses have not settled, so the
        # candidate set is not final and confirmComplete must be false.
        self.freeze_ok()
        status = json.loads(run_crew(self.fx.campaign, "status").stdout)
        self.assertFalse(status["confirmGateOpen"])
        self.assertFalse(status["confirmComplete"])
        # Breadth and lenses complete with zero notable candidates: gate open,
        # nothing notable to confirm, so confirmComplete is true.
        for unit in ("src-00001", "src-00002", "src-00003"):
            self.fx.write_verdict("src", unit, {
                "unitId": unit, "status": "completed", "reviewer": "rev-" + unit,
                "attempts": 1, "findings": [], "summary": "clean",
                "covered": []})
        self.fx.write_verdict("docs", "doc-00001", {
            "unitId": "doc-00001", "status": "completed", "reviewer": "rev-doc-00001",
            "attempts": 1, "findings": [], "summary": "clean", "covered": []})
        for lens in self.fx.lens_doc["lenses"]:
            self.fx.write_lens_verdict("seam", lens["name"], {
                "lens": lens["name"], "status": "completed", "candidates": [],
                "clean": [], "notCovered": [], "summary": "ok"})
        status = json.loads(run_crew(self.fx.campaign, "status").stdout)
        self.assertTrue(status["breadthComplete"])
        self.assertTrue(status["lensesComplete"])
        self.assertTrue(status["confirmGateOpen"])
        self.assertTrue(status["confirmComplete"])
        # One unconfirmed notable candidate reopens incompleteness.
        self.fx.write_verdict("src", "src-00001", completed("src-00001"))
        status = json.loads(run_crew(self.fx.campaign, "status").stdout)
        self.assertTrue(status["confirmGateOpen"])
        self.assertFalse(status["confirmComplete"])

    def _write_seeded(self, doc, campaign=None):
        target = (campaign or self.fx.campaign) / "build" / "seeded.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(doc), encoding="utf-8", newline="\n")

    def test_seeded_candidates_validated_recorded_and_merged(self):
        seed_doc = {
            "campaign": "kit-test-20261123-aa00",
            "candidates": [
                {"severity": "medium", "where": "src/a.py:1", "what": WHAT,
                 "evidence": "seeded by gate triage", "source": "gate-triage"},
                {"severity": "low", "where": "docs/guide.md:2",
                 "what": "seed only", "evidence": "seed",
                 "source": "gate-triage"},
            ],
        }
        self._write_seeded(seed_doc)
        self.freeze_ok()
        manifest = json.loads(
            (self.fx.campaign / "manifest.json").read_text(encoding="utf-8-sig"))
        self.assertEqual(manifest["seeded"], 2)
        # A seed duplicating a reviewer finding merges into one candidate.
        self.fx.write_verdict("src", "src-00001", completed("src-00001"))
        cands = json.loads(
            run_crew(self.fx.campaign, "candidates").stdout)["candidates"]
        self.assertEqual(len(cands), 2)
        merged = [c for c in cands
                  if c["id"] == candidate_id("src/a.py:1", WHAT)][0]
        self.assertIn("seed:gate-triage", merged["sources"])
        self.assertIn("src-00001", merged["sources"])
        lone = [c for c in cands if c["id"] == candidate_id("docs/guide.md:2",
                                                           "seed only")][0]
        self.assertEqual(lone["sources"], ["seed:gate-triage"])
        # A seed alone is pending until confirmed.
        pending_ids = [c["id"] for c in json.loads(
            run_crew(self.fx.campaign, "candidates", "--pending").stdout)["candidates"]]
        self.assertIn(lone["id"], pending_ids)
        self.fx.write_confirm(lone["id"], "refuted")
        pending_ids = [c["id"] for c in json.loads(
            run_crew(self.fx.campaign, "candidates", "--pending").stdout)["candidates"]]
        self.assertNotIn(lone["id"], pending_ids)
        # status reports the seeded count.
        status = json.loads(run_crew(self.fx.campaign, "status").stdout)
        self.assertEqual(status["candidates"]["seeded"], 2)

    def test_seeded_file_malformed_fails_freeze_cleanly(self):
        for bad in (
            {"campaign": "x", "candidates": "nope"},
            {"campaign": "x", "candidates": [
                {"severity": "critical", "where": "a:1", "what": "w",
                 "evidence": "e", "source": "s"}]},
            {"campaign": "x", "candidates": [
                {"severity": "low", "what": "w", "evidence": "e", "source": "s"}]},
        ):
            self._write_seeded(bad)
            done = self.fx.freeze()
            self.assertEqual(done.returncode, 1, json.dumps(bad))
            self.assertNotIn("Traceback", done.stderr)
            self.assertIn("seeded", done.stderr.lower())

    def _satisfy_remaining_close_items(self):
        # Every medium/high candidate needs a confirm verdict; item 2 needs a
        # verdict for every lens of every declared set; item 4 needs a clean
        # tree; items 5-7 need runs.json, accounting.json, verdict.json.
        for lens in self.fx.lens_doc["lenses"]:
            self.fx.write_lens_verdict("seam", lens["name"], {
                "lens": lens["name"], "status": "completed", "candidates": [],
                "clean": [], "notCovered": [], "summary": "ok"})
        candidates = json.loads(
            run_crew(self.fx.campaign, "candidates").stdout)["candidates"]
        for cand in candidates:
            if cand["severity"] in ("medium", "high"):
                self.fx.write_confirm(cand["id"], "confirmed")
        self.fx.build_file("runs.json", [
            {"stage": "breadth", "lane": "src", "set": None, "runId": "r1",
             "model": "m", "launchedAtUtc": "2026-11-23T00:00:00Z", "state": "completed"},
        ])
        self.fx.build_file("accounting.json", {
            "usageSource": "fixture",
            "runs": [{"runId": "r1", "spentTokens": 1000}],
        })
        doc = self.fx.campaign / "build" / "verdict-doc.md"
        doc.parent.mkdir(parents=True, exist_ok=True)
        doc.write_text("# verdict\n", encoding="utf-8")
        self.fx.build_file("verdict.json", {
            "verdict": "PASS",
            "verdictDoc": str(doc).replace("\\", "/"),
        })

    def test_close_requires_accounting_and_verdict_docs(self):
        self.test_close_passes_on_closed_fixture()
        # Break item 6: accounting without per-run spend and no unavailable flag.
        self.fx.build_file("accounting.json", {
            "usageSource": "fixture", "runs": [{"runId": "r1"}]})
        done = run_crew(self.fx.campaign, "close")
        self.assertEqual(done.returncode, 1)
        item6 = [i for i in json.loads(done.stdout)["items"]
                 if i["item"] == "accounting"][0]
        self.assertFalse(item6["pass"])
        # Break item 5: a running entry.
        self.fx.build_file("accounting.json", {
            "usageSource": "fixture",
            "runs": [{"runId": "r1", "spentTokens": 1000}],
        })
        self.fx.build_file("runs.json", [
            {"stage": "breadth", "lane": "src", "set": None, "runId": "r1",
             "model": "m", "launchedAtUtc": "2026-11-23T00:00:00Z", "state": "running"},
        ])
        done = run_crew(self.fx.campaign, "close")
        item5 = [i for i in json.loads(done.stdout)["items"]
                 if i["item"] == "runs-settled"][0]
        self.assertFalse(item5["pass"])
        # Break item 7: verdictDoc path that does not exist.
        self.fx.build_file("runs.json", [
            {"stage": "breadth", "lane": "src", "set": None, "runId": "r1",
             "model": "m", "launchedAtUtc": "2026-11-23T00:00:00Z", "state": "completed"},
        ])
        self.fx.build_file("verdict.json", {"verdict": "PASS", "verdictDoc": "X:/nope.md"})
        done = run_crew(self.fx.campaign, "close")
        item7 = [i for i in json.loads(done.stdout)["items"]
                 if i["item"] == "verdict-recorded"][0]
        self.assertFalse(item7["pass"])

    # -- safety --------------------------------------------------------------

    def test_write_outside_campaign_refused(self):
        self.freeze_ok()
        for bad in ("../escape", "..\\escape", "src/../../evil"):
            done = run_crew(self.fx.campaign, "agg", bad)
            self.assertNotEqual(done.returncode, 0, bad)
            self.assertFalse((Path(self._tmp.name) / "escape.json").exists())
            self.assertFalse((Path(self._tmp.name) / "evil.json").exists())

    def test_unknown_command_is_usage_error(self):
        self.assertEqual(run_crew(self.fx.campaign, "bogus").returncode, 2)
        self.assertEqual(run_crew(self.fx.campaign).returncode, 2)


class TestWorkflowStaticContract(unittest.TestCase):
    def _read(self, name):
        path = WORKFLOWS / name
        self.assertTrue(path.exists(), "missing workflow: %s" % path)
        return path.read_text(encoding="utf-8-sig")

    def test_workflows_exist(self):
        for name in WORKFLOW_FILES:
            self._read(name)

    def test_metadata_block_has_no_name_key(self):
        for name in WORKFLOW_FILES:
            text = self._read(name)
            self.assertTrue(text.startswith("/* zcode-workflow"), name)
            block = text.split("*/", 1)[0]
            self.assertNotIn("\nname:", block, name + " metadata must not carry a name key")
            self.assertIn("description:", block)
            self.assertIn("args:", block)

    def test_ask_content_gate_present(self):
        for name in WORKFLOW_FILES:
            text = self._read(name)
            for token in ('"undefined"', '"null"', '"[object"', '"NaN"'):
                self.assertIn(token, text, "%s must gate on %s" % (name, token))
            self.assertIn("gate", text.lower())

    def test_resume_paragraph_covers_both_cases(self):
        for name in WORKFLOW_FILES:
            text = self._read(name)
            self.assertIn("already exists and parses", text, name)
            if name == "breadth.dwf.ts":
                self.assertIn("attempts", text, name + " must instruct attempt incrementing")

    def test_json_escaping_instruction_present(self):
        for name in WORKFLOW_FILES:
            self.assertIn("backslash", self._read(name).lower())

    def test_world_run_carries_timeouts(self):
        # M8: parse actual world.run call sites, not substring counts.
        for name in WORKFLOW_FILES:
            text = self._read(name)
            self.assertIn("timeoutMs: 120000", text, name)
            if name == "breadth.dwf.ts":
                self.assertIn("timeoutMs: 600000", text, name)
            sites = []
            index = text.find("world.run(")
            while index != -1:
                depth = 0
                start = text.index("(", index)
                for offset in range(start, len(text)):
                    if text[offset] == "(":
                        depth += 1
                    elif text[offset] == ")":
                        depth -= 1
                        if depth == 0:
                            sites.append(text[start:offset + 1])
                            break
                index = text.find("world.run(", index + 1)
            self.assertGreaterEqual(len(sites), 2, name + " must call world.run")
            for site in sites:
                self.assertIn("timeoutMs:", site,
                              "%s: every world.run call site must carry timeoutMs: %s"
                              % (name, site[:80]))

    def test_verdict_interfaces_are_supersets_of_asks(self):
        # B2: the typed ask results must accept every key the asks request.
        breadth = self._read("breadth.dwf.ts")
        for member in ("unitId?: string", "reviewer?: string",
                       "attempts?: number", "covered?: string[]"):
            self.assertIn(member, breadth, "UnitVerdict lacks " + member)
        lenses = self._read("lenses.dwf.ts")
        for member in ("status?: string", "summary?: string"):
            self.assertIn(member, lenses, "lens verdict interface lacks " + member)
        confirm = self._read("confirm.dwf.ts")
        self.assertIn("candidateId?: string", confirm)

    def test_confirm_limit_zero_means_all(self):
        # M1: an explicit limit of 0 must mean "all", not fall back to 150.
        confirm = self._read("confirm.dwf.ts")
        self.assertIn("args.limit >= 0", confirm)

    def test_gate_scans_dynamic_fields_only(self):
        # M7: focus stays in the checked dynamic set (word boundaries), and
        # the gate never scans the composed ask for forbidden tokens.
        for name in WORKFLOW_FILES:
            text = self._read(name)
            self.assertIn("for (const value of dynamic)", text, name)
            self.assertNotIn("ask.includes(token)", text,
                             name + ": gate must not scan static rubric text")
        self.assertIn("firstUnit.dir, focus,", self._read("breadth.dwf.ts"))

    def test_markdown_is_trimmed_and_guarded(self):
        for name in WORKFLOW_FILES:
            text = self._read(name)
            self.assertIn("240000", text, name + " must trim the artifact to 240000 bytes")
            self.assertIn("try {", text, name)
            self.assertIn("catch", text, name)
            self.assertIn("artifact.markdown", text)
            index = text.index("artifact.markdown")
            self.assertLess(text.index("try {"), index, name + ": markdown publish is guarded")

    def test_no_forbidden_calls(self):
        forbidden = (
            "Date.now", "Math.random", "fetch(", "require(", "run.id",
            "CreateWorkflow", "AmendWorkflow", "ResumeWorkflowRun",
            "SaveWorkflow", "EvalWorkflowSnippet", "files.glob", "files.read",
        )
        for name in WORKFLOW_FILES:
            text = self._read(name)
            for token in forbidden:
                self.assertNotIn(token, text, "%s must not contain %s" % (name, token))

    def test_unique_name_assertion_and_reports(self):
        for name in WORKFLOW_FILES:
            text = self._read(name)
            self.assertIn("new Set", text, name + " must assert record-name uniqueness")
            self.assertIn("report(", text, name + " must report per record")
            self.assertIn("phase(", text)

    def test_defaults_have_code_fallbacks(self):
        breadth = self._read("breadth.dwf.ts")
        self.assertIn("pendingOnly", breadth)
        self.assertIn("limit", breadth)
        self.assertIn("focus", breadth)
        confirm = self._read("confirm.dwf.ts")
        self.assertIn("150", confirm)
        self.assertIn("minSeverity", confirm)
        lenses = self._read("lenses.dwf.ts")
        self.assertIn("limit", lenses)

    def test_frozen_root_and_counterevidence_instructions(self):
        lenses = self._read("lenses.dwf.ts")
        self.assertIn("Frozen source root: ", lenses)
        self.assertIn("do not read the shared main checkout", lenses)
        confirm = self._read("confirm.dwf.ts")
        self.assertIn("Frozen source root: ", confirm)
        self.assertIn("counterevidence", confirm)
        self.assertIn("none found", confirm)
        self.assertIn("path:line", confirm)
        # Probes are real probes: no resume-skip clause in any probe ask.
        for name in WORKFLOW_FILES:
            text = self._read(name)
            probe_chunk = text[text.index("probe-"):text.index("probe-") + 900]
            self.assertNotIn("already exists", probe_chunk,
                             name + " probe must not skip itself")

    def test_subagent_name_patterns(self):
        checks = {
            "breadth.dwf.ts": ('"probe-" + lane', '"rev-" + unit.id'),
            "lenses.dwf.ts": ('"probe-" + set', '"lens-" +'),
            "confirm.dwf.ts": ("probe-confirm", '"conf-" +'),
        }
        for name, tokens in checks.items():
            text = self._read(name)
            for token in tokens:
                self.assertIn(token, text, "%s must build names as %s" % (name, token))


if __name__ == "__main__":
    unittest.main()
