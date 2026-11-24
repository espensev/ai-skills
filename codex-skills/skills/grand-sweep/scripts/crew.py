# Grand-sweep campaign tool (kit v1, spec v2).
# Usage: python -I crew.py <campaignDir> <command> [options]
#
# Standard library only; never deletes; writes only inside <campaignDir>.
# Exit codes: 0 ok, 1 validation or semantic failure, 2 usage.
# Machine-readable commands print exactly one JSON document plus newline.
import argparse
import datetime
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys

SEVERITIES = ("low", "medium", "high")
SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3}
CONFIRM_VERDICTS = ("confirmed", "refuted", "inconclusive", "duplicate")
PREFIX_RE = re.compile(r"^[a-z][a-z0-9]{0,5}$")
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")
LENS_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
BINARY_EXTS = {".exe", ".dll", ".pub", ".reg"}
SCRIPT_EXTS = {".ps1", ".psm1", ".psd1", ".sh", ".bat", ".cmd"}
SOURCE_EXTS = {".py", ".ts", ".tsx", ".js", ".mjs", ".cjs", ".cs", ".go", ".rs",
               ".c", ".h", ".cpp", ".hpp", ".java", ".rb", ".php", ".mjs"}
DOC_EXTS = {".md", ".txt", ".rst"}
CONFIG_EXTS = {".json", ".yaml", ".yml", ".toml", ".xml", ".ini", ".cfg", ".config",
               ".editorconfig", ".gitignore"}


class Fail(Exception):
    """Validation or semantic failure (exit 1)."""


class Usage(Exception):
    """Usage error (exit 2)."""


def note(message):
    print(message, file=sys.stderr)


def emit(doc):
    sys.stdout.write(json.dumps(doc, ensure_ascii=False) + "\n")


def load_json(path, what):
    try:
        with open(path, "r", encoding="utf-8-sig") as fh:
            return json.load(fh)
    except OSError:
        raise Fail("cannot read %s: %s" % (what, path))
    except (ValueError, UnicodeDecodeError) as exc:
        raise Fail("malformed %s: %s: %s" % (what, path, exc))


def write_bytes(campaign, rel, data):
    """Write bytes to rel under campaign, refusing any escape (no deletes)."""
    root = os.path.realpath(campaign)
    target = os.path.realpath(os.path.join(root, rel.replace("/", os.sep)))
    if os.path.normcase(target) != os.path.normcase(root) and \
            not os.path.normcase(target).startswith(os.path.normcase(root) + os.sep):
        raise Fail("refusing to write outside the campaign directory: %s" % rel)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "wb") as fh:
        fh.write(data)


def write_json(campaign, rel, doc):
    write_bytes(campaign, rel, (json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
                .encode("utf-8"))


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def normkey(path):
    return os.path.normcase(os.path.realpath(path))


def safe_name(value, what):
    value = str(value)
    if not NAME_RE.match(value):
        raise Fail("unsafe %s name: %r" % (what, value))
    return value


def load_campaign(campaign):
    manifest = load_json(os.path.join(campaign, "manifest.json"), "manifest")
    units_doc = load_json(os.path.join(campaign, "units.json"), "unit plan")
    if not isinstance(manifest, dict) or not isinstance(units_doc, dict):
        raise Fail("manifest.json or units.json is not an object")
    return manifest, units_doc


def lane_names(manifest):
    return [lane["name"] for lane in manifest["lanes"]]


def check_lane(manifest, lane):
    names = lane_names(manifest)
    if lane not in names:
        raise Fail("unknown lane %r; known lanes: %s" % (lane, ", ".join(names)))
    return lane


# --------------------------------------------------------------------------
# Verdict readers (tolerant, BOM-safe)
# --------------------------------------------------------------------------

def _sidecar_attempts_path(campaign, lane, unit_id):
    return os.path.join(campaign, "staging", "breadth", lane, unit_id + ".attempts")


def _read_sidecar_attempts(campaign, lane, unit_id):
    try:
        with open(_sidecar_attempts_path(campaign, lane, unit_id), "r",
                  encoding="utf-8-sig") as fh:
            return max(0, int(str(fh.read()).strip()))
    except (OSError, ValueError):
        return 0


def _bump_sidecar_attempts(campaign, lane, unit_id):
    """Record one more attempt for a verdict that carries no attempts field."""
    value = _read_sidecar_attempts(campaign, lane, unit_id) + 1
    path = _sidecar_attempts_path(campaign, lane, unit_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(str(value) + "\n")
    return value


def read_breadth_verdict(campaign, lane, unit_id):
    """Return a detail record for one unit's verdict file.

    Attempts are max(attempts in the file, sidecar .attempts count); a
    malformed file, or one without an attempts field, bumps the sidecar so
    repeated garbage eventually reaches terminal-failed.
    """
    path = os.path.join(campaign, "staging", "breadth", lane, unit_id + ".json")
    detail = {"id": unit_id, "status": "pending", "attempts": 0,
              "verdictPath": None, "findings": [], "summary": "", "reason": None}
    if not os.path.isfile(path):
        detail["reason"] = "missing-verdict"
        return detail
    detail["verdictPath"] = path.replace("\\", "/")
    sidecar = _read_sidecar_attempts(campaign, lane, unit_id)
    try:
        with open(path, "r", encoding="utf-8-sig") as fh:
            v = json.load(fh)
        if not isinstance(v, dict) or v.get("status") not in ("completed", "failed"):
            raise ValueError("bad status")
        if "unitId" not in v:
            raise ValueError("unitId-missing")
        if str(v["unitId"]) != str(unit_id):
            raise ValueError("verdict unitId %r does not match path unit %r"
                             % (v["unitId"], unit_id))
        detail["status"] = v["status"]
        attempts = v.get("attempts")
        if isinstance(attempts, int) and attempts > 0:
            detail["attempts"] = max(attempts, sidecar)
        elif detail["status"] == "completed":
            detail["attempts"] = max(1, sidecar)
        else:
            detail["attempts"] = max(1, _bump_sidecar_attempts(campaign, lane, unit_id))
        findings = []
        for f in v.get("findings") or []:
            if not isinstance(f, dict):
                continue
            severity = f.get("severity")
            if severity not in SEVERITIES:
                severity = "low"
            findings.append({
                "severity": severity,
                "where": str(f.get("where", "")),
                "what": str(f.get("what", "")),
                "evidence": str(f.get("evidence", "")),
            })
        detail["findings"] = findings
        detail["summary"] = str(v.get("summary", ""))
    except (ValueError, OSError, UnicodeDecodeError) as exc:
        detail["status"] = "failed"
        detail["attempts"] = max(1, _bump_sidecar_attempts(campaign, lane, unit_id))
        detail["reason"] = "malformed-verdict: %s" % exc
    if detail["status"] == "failed" and detail["attempts"] >= 3:
        detail["status"] = "terminal-failed"
    return detail


def lane_unit_states(campaign, manifest, units_doc, lane):
    """Verdict detail per unit of one lane, in unit-id order."""
    out = []
    for unit in sorted((u for u in units_doc["units"] if u["lane"] == lane),
                       key=lambda u: u["id"]):
        detail = read_breadth_verdict(campaign, lane, unit["id"])
        out.append(detail)
    return out


def lens_sets(campaign):
    """Declared lens sets from build/lenses-<set>.json (set name -> doc)."""
    sets = {}
    build_dir = os.path.join(campaign, "build")
    if not os.path.isdir(build_dir):
        return sets
    for name in sorted(os.listdir(build_dir)):
        if not (name.startswith("lenses-") and name.endswith(".json")):
            continue
        set_name = name[len("lenses-"):-len(".json")]
        doc = load_json(os.path.join(build_dir, name), "lens set file")
        validate_lens_doc(doc, set_name)
        sets[set_name] = doc
    return sets


def validate_lens_doc(doc, set_name):
    if not isinstance(doc, dict) or not isinstance(doc.get("lenses"), list) \
            or not doc["lenses"]:
        raise Fail("lens set %r must be an object with a non-empty lenses array" % set_name)
    seen = set()
    for lens in doc["lenses"]:
        if not isinstance(lens, dict):
            raise Fail("lens set %r has a non-object lens entry" % set_name)
        name = lens.get("name")
        if not isinstance(name, str) or not LENS_NAME_RE.match(name):
            raise Fail("lens set %r has an invalid lens name: %r" % (set_name, name))
        if len(name) > 28:
            raise Fail("lens name %r in set %r exceeds 28 characters" % (name, set_name))
        if name in seen:
            raise Fail("duplicate lens name %r in set %r" % (name, set_name))
        seen.add(name)
        for key in ("title", "brief"):
            if not isinstance(lens.get(key), str):
                raise Fail("lens %r in set %r lacks a string %r" % (name, set_name, key))
        inputs = lens.get("inputs", [])
        if not isinstance(inputs, list) or \
                not all(isinstance(i, str) for i in inputs):
            raise Fail("lens %r in set %r has a bad inputs array" % (name, set_name))
    return doc


def read_lens_verdict(campaign, set_name, lens_name):
    path = os.path.join(campaign, "staging", "lens", set_name, lens_name + ".json")
    detail = {"lens": lens_name, "status": "pending", "candidates": [],
              "clean": [], "notCovered": [], "summary": "", "reason": None}
    if not os.path.isfile(path):
        detail["reason"] = "missing-verdict"
        return detail
    try:
        with open(path, "r", encoding="utf-8-sig") as fh:
            v = json.load(fh)
        if not isinstance(v, dict) or v.get("status") not in ("completed", "failed"):
            raise ValueError("bad status")
        detail["status"] = v["status"]
        candidates = []
        for c in v.get("candidates") or []:
            if not isinstance(c, dict):
                continue
            severity = c.get("severity")
            if severity not in SEVERITIES:
                severity = "low"
            candidates.append({
                "severity": severity,
                "where": str(c.get("where", "")),
                "what": str(c.get("what", "")),
                "evidence": str(c.get("evidence", "")),
            })
        detail["candidates"] = candidates
        detail["clean"] = [str(x) for x in v.get("clean") or []
                           if isinstance(x, (str, int, float))]
        detail["notCovered"] = [str(x) for x in v.get("notCovered") or []
                                if isinstance(x, (str, int, float))]
        detail["summary"] = str(v.get("summary", ""))
    except (ValueError, OSError, UnicodeDecodeError) as exc:
        detail["status"] = "failed"
        detail["reason"] = "malformed-verdict: %s" % exc
    return detail


def validate_seeded_doc(doc):
    """Validate build/seeded.json: {campaign, candidates:[finding+source]}."""
    if not isinstance(doc, dict) or not isinstance(doc.get("candidates"), list):
        raise Fail("seeded candidates file must be an object with a candidates array")
    for entry in doc["candidates"]:
        if not isinstance(entry, dict) or entry.get("severity") not in SEVERITIES \
                or not isinstance(entry.get("where"), str) \
                or not isinstance(entry.get("what"), str) \
                or not isinstance(entry.get("evidence"), str) \
                or not isinstance(entry.get("source"), str) \
                or not entry["source"]:
            raise Fail("seeded candidates file has a malformed entry: %r" % (entry,))
    return doc


def load_seeded(campaign):
    """Seeded (controller-raised) candidate findings; [] when absent."""
    path = os.path.join(campaign, "build", "seeded.json")
    if not os.path.isfile(path):
        return []
    return validate_seeded_doc(load_json(path, "seeded candidates file"))["candidates"]


def read_confirm_verdict(campaign, candidate_id):
    path = os.path.join(campaign, "staging", "confirm", candidate_id + ".json")
    try:
        with open(path, "r", encoding="utf-8-sig") as fh:
            v = json.load(fh)
        if isinstance(v, dict) and v.get("verdict") in CONFIRM_VERDICTS:
            return {"status": "valid", "verdict": v["verdict"], "doc": v}
        return {"status": "invalid", "verdict": None, "doc": v}
    except OSError:
        return {"status": "pending", "verdict": None, "doc": None}
    except (ValueError, UnicodeDecodeError):
        return {"status": "invalid", "verdict": None, "doc": None}


# --------------------------------------------------------------------------
# Candidates
# --------------------------------------------------------------------------

def candidate_identity(where, what):
    where = str(where).strip()
    if where.startswith("./"):
        where = where[2:]
    paren = re.match(r"^(.*)\((\d+)\)$", where)
    if paren:
        where = paren.group(1) + ":" + paren.group(2)
    path, sep, tail = where.rpartition(":")
    if sep and tail.isdigit():
        # Drop a trailing column: path:line:col and path:line are the same hit.
        head, sep2, mid = path.rpartition(":")
        if sep2 and mid.isdigit():
            tail = mid
            path = head
        line = tail.strip()
    else:
        path, line = where, ""
    norm_path = path.replace("\\", "/").strip("/").casefold()
    norm_what = " ".join(str(what).split()).casefold()[:120]
    return "%s|%s|%s" % (norm_path, line, norm_what)


def candidate_id(where, what):
    digest = hashlib.sha256(candidate_identity(where, what).encode("utf-8")).hexdigest()
    return "C-" + digest[:10]


def collect_candidates(campaign, manifest, units_doc):
    """De-duplicated candidates from breadth and lens verdicts on disk."""
    merged = {}

    def add(finding, source):
        cid = candidate_id(finding["where"], finding["what"])
        entry = merged.get(cid)
        if entry is None:
            merged[cid] = {
                "id": cid,
                "severity": finding["severity"],
                "where": finding["where"],
                "what": finding["what"],
                "evidence": finding["evidence"],
                "sources": [source],
            }
        else:
            if SEVERITY_RANK[finding["severity"]] > SEVERITY_RANK[entry["severity"]]:
                entry["severity"] = finding["severity"]
            if source not in entry["sources"]:
                entry["sources"].append(source)

    for seed in load_seeded(campaign):
        add({"severity": seed["severity"], "where": seed["where"],
             "what": seed["what"], "evidence": seed["evidence"]},
            "seed:" + seed["source"])
    for lane in lane_names(manifest):
        for detail in lane_unit_states(campaign, manifest, units_doc, lane):
            if detail["status"] != "completed":
                continue
            for finding in detail["findings"]:
                add(finding, detail["id"])
    for set_name, doc in lens_sets(campaign).items():
        for lens in doc["lenses"]:
            detail = read_lens_verdict(campaign, set_name, lens["name"])
            if detail["status"] != "completed":
                continue
            for finding in detail["candidates"]:
                add(finding, "lens:%s/%s" % (set_name, lens["name"]))
    return sorted(merged.values(), key=lambda c: c["id"])


# --------------------------------------------------------------------------
# freeze
# --------------------------------------------------------------------------

def git_run(root, *argv):
    done = subprocess.run(["git", "-C", root, *argv],
                          capture_output=True, text=True, encoding="utf-8")
    if done.returncode != 0:
        raise Fail("git %s failed in %s: %s" % (" ".join(argv[:1]), root,
                                                (done.stderr or "").strip()))
    return done.stdout


def glob_regex(pattern):
    out = []
    i = 0
    while i < len(pattern):
        ch = pattern[i]
        if ch == "*":
            if pattern[i:i + 2] == "**":
                out.append(".*")
                i += 2
                if pattern[i:i + 1] == "/":
                    i += 1
                continue
            out.append("[^/]*")
            i += 1
        elif ch == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(ch))
            i += 1
    return re.compile("^" + "".join(out) + "$")


def classify_kind(rel):
    lower = rel.lower()
    ext = os.path.splitext(lower)[1]
    base = lower.rsplit("/", 1)[-1]
    if ext in BINARY_EXTS:
        return "binary"
    if "/tests/" in lower or "/test/" in lower or base.startswith("test_") \
            or base.endswith(".tests.ps1") or base.endswith("_test.py") \
            or base.endswith("_test.go") or base.startswith("test-"):
        return "test"
    if ext in SCRIPT_EXTS:
        return "script"
    if ext in DOC_EXTS:
        return "doc"
    if ext in CONFIG_EXTS:
        return "config"
    return "source"


def common_dir(rels):
    if not rels:
        return ""
    parts = [rel.split("/")[:-1] for rel in rels]
    shared = parts[0]
    for candidate in parts[1:]:
        shared = [a for a, b in zip(shared, candidate) if a == b]
        if not shared:
            break
    return "/".join(shared)


def is_prefix_of(prefix, path):
    return path == prefix or path.startswith(prefix + "/")


def utc_stamp():
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    return now.strftime("%Y-%m-%dT%H:%M:%SZ")


def stamp_dirname():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def cmd_freeze(campaign, args):
    scope = load_json(args.scope, "scope file")
    if not isinstance(scope, dict):
        raise Fail("scope file is not a JSON object")
    for key in ("campaign", "root", "commit", "lanes"):
        if key not in scope:
            raise Fail("scope file lacks %r" % key)
    root = str(scope["root"])
    if not os.path.isdir(root):
        raise Fail("scope root is not a directory: %s" % root)
    kit_dir = args.kit
    if not kit_dir:
        raise Usage("freeze requires --kit <packageDir>")
    for sub in ("scripts", "workflows"):
        if not os.path.isdir(os.path.join(kit_dir, sub)):
            raise Fail("kit package directory lacks %s/: %s" % (sub, kit_dir))

    lanes = scope["lanes"]
    if not isinstance(lanes, list) or not lanes:
        raise Fail("scope lanes must be a non-empty array")
    prefixes = {}
    for lane in lanes:
        for key in ("name", "prefix", "include", "unit"):
            if key not in lane:
                raise Fail("lane %r lacks %r" % (lane.get("name"), key))
        if not NAME_RE.match(str(lane["name"])):
            raise Fail("unsafe lane name: %r" % lane["name"])
        if not PREFIX_RE.match(str(lane["prefix"])):
            raise Fail("lane %r has an invalid prefix %r (need ^[a-z][a-z0-9]{0,5}$)"
                       % (lane["name"], lane["prefix"]))
        if lane["prefix"] in prefixes:
            raise Fail("lane prefix %r used by both %r and %r"
                       % (lane["prefix"], prefixes[lane["prefix"]], lane["name"]))
        prefixes[lane["prefix"]] = lane["name"]
        unit = lane["unit"]
        if not isinstance(unit, dict) or not isinstance(unit.get("maxFiles"), int) \
                or not isinstance(unit.get("maxBytes"), int) \
                or unit["maxFiles"] < 1 or unit["maxBytes"] < 1:
            raise Fail("lane %r has a bad unit spec" % lane["name"])
        if not isinstance(lane["include"], list) or not lane["include"]:
            raise Fail("lane %r has no include entries" % lane["name"])

    # Step 1: identity and cleanliness (no override).
    head = git_run(root, "rev-parse", "HEAD").strip()
    if head != str(scope["commit"]):
        raise Fail("scope commit %s does not match HEAD %s" % (scope["commit"], head))
    porcelain = git_run(root, "status", "--porcelain")
    if porcelain.strip():
        raise Fail("root is dirty; a dirty root needs a new freeze, not an override")

    # Step 2: enumerate, overlap check, assignment, exclusions.
    all_includes = []
    for lane in lanes:
        all_includes.extend(str(p) for p in lane["include"])
    for i, lane_a in enumerate(lanes):
        for lane_b in lanes[i + 1:]:
            for inc_a in lane_a["include"]:
                for inc_b in lane_b["include"]:
                    if is_prefix_of(str(inc_a), str(inc_b)) or is_prefix_of(str(inc_b), str(inc_a)):
                        raise Fail("include %r (lane %r) overlaps include %r (lane %r)"
                                   % (inc_a, lane_a["name"], inc_b, lane_b["name"]))
    listing = git_run(root, "ls-files", "-z", "--", *all_includes)
    tracked = [name for name in listing.split("\0") if name]
    exclude_res = [(str(g), glob_regex(str(g))) for g in scope.get("excludeGlobs", [])]
    exclusions = []
    assigned = {}
    matched = set()
    for name in tracked:
        globs = [g for g, rx in exclude_res if rx.match(name)]
        if globs:
            exclusions.append({"path": name, "reason": "matched excludeGlobs " + globs[0]})
            continue
        owners = [lane["name"] for lane in lanes
                  if any(is_prefix_of(str(p), name) for p in lane["include"])]
        if not owners:
            raise Fail("unassigned tracked file under the included prefixes: %s" % name)
        if len(owners) > 1:
            raise Fail("tracked file %s matched several lanes: %s" % (name, ", ".join(owners)))
        assigned[name] = owners[0]
        matched.add(name)
    for lane in lanes:
        for entry in lane["include"]:
            if not any(is_prefix_of(str(entry), name) for name in matched):
                raise Fail("include entry matched no tracked files: %s" % entry)

    # Step 3: hash and classify.
    files = []
    for name in sorted(assigned):
        abs_path = os.path.join(root, name.replace("/", os.sep))
        if not os.path.isfile(abs_path):
            raise Fail("tracked file under an included prefix is missing on disk: %s" % name)
        digest = sha256_file(abs_path)
        size = os.path.getsize(abs_path)
        files.append({
            "id": name,
            "rel": name,
            "path": abs_path.replace("\\", "/"),
            "sha256": digest,
            "bytes": size,
            "kind": classify_kind(name),
            "lane": assigned[name],
        })
    files_by_id = {f["id"]: f for f in files}

    # Subset validation: every subset path must be a manifested file id.
    subsets_out = {}
    for name, sub in (scope.get("subsets") or {}).items():
        if not isinstance(sub, dict) or not isinstance(sub.get("paths", []), list):
            raise Fail("subset %r must be an object with a paths array" % name)
        paths = [str(p) for p in sub.get("paths", [])]
        for p in paths:
            if p not in files_by_id:
                raise Fail("subset %r lists a path that is not a manifested file id: %s"
                           % (name, p))
        subsets_out[str(name)] = {"description": str(sub.get("description", "")),
                                  "paths": sorted(paths)}

    # Declared lens sets: each must already exist on disk and validate.
    declared_sets = []
    for set_name in scope.get("lensSets") or []:
        set_name = safe_name(set_name, "lens set")
        lens_path = os.path.join(campaign, "build", "lenses-%s.json" % set_name)
        if not os.path.isfile(lens_path):
            raise Fail("declared lens set %r has no file: %s"
                       % (set_name, lens_path.replace("\\", "/")))
        validate_lens_doc(load_json(lens_path, "lens set file"), set_name)
        declared_sets.append(set_name)

    # Optional seeded (controller-raised) candidates: validate, record count.
    seeded_count = 0
    seeded_path = os.path.join(campaign, "build", "seeded.json")
    if os.path.isfile(seeded_path):
        seeded_count = len(validate_seeded_doc(
            load_json(seeded_path, "seeded candidates file"))["candidates"])

    # Step 4: pack units per lane.
    solo_at = int(scope.get("soloAtBytes", 250000))
    units = []
    for lane in lanes:
        lane_files = sorted((f for f in files if f["lane"] == lane["name"]),
                            key=lambda f: f["rel"])
        pack = []
        pack_bytes = 0
        counter = 0
        max_files = lane["unit"]["maxFiles"]
        max_bytes = lane["unit"]["maxBytes"]

        def flush(lane=lane):
            nonlocal pack, pack_bytes, counter
            if not pack:
                return
            counter += 1
            rels = [f["rel"] for f in pack]
            units.append({
                "id": "%s-%05d" % (lane["prefix"], counter),
                "lane": lane["name"],
                "dir": common_dir(rels),
                "bytes": pack_bytes,
                "oversize": len(pack) == 1 and pack[0]["bytes"] >= solo_at,
                "files": rels,
            })
            pack = []
            pack_bytes = 0

        for f in lane_files:
            if f["bytes"] >= solo_at:
                flush()
                pack = [f]
                pack_bytes = f["bytes"]
                flush()
                continue
            if pack and (len(pack) >= max_files or pack_bytes + f["bytes"] > max_bytes):
                flush()
            pack.append(f)
            pack_bytes += f["bytes"]
        flush()

    # Step 5: refuse or supersede FIRST, then snapshot the kit, then write.
    revision = 1
    manifest_path = os.path.join(campaign, "manifest.json")
    if os.path.exists(manifest_path):
        if not args.replace:
            raise Fail("manifest.json already exists; pass --replace to supersede it")
        revision = int(load_json(manifest_path, "previous manifest").get("revision", 1)) + 1
        stamp = stamp_dirname()
        dest = os.path.join(campaign, "superseded", stamp)
        suffix = 2
        while os.path.exists(dest):
            dest = os.path.join(campaign, "superseded", "%s-%d" % (stamp, suffix))
            suffix += 1
        os.makedirs(dest, exist_ok=True)
        for name in ("manifest.json", "units.json"):
            source = os.path.join(campaign, name)
            if os.path.exists(source):
                os.replace(source, os.path.join(dest, name))
        note("superseded previous freeze into %s" % dest.replace("\\", "/"))

    kit_files = {}
    for sub in ("scripts", "workflows"):
        base = os.path.join(kit_dir, sub)
        for dirpath, _dirnames, filenames in os.walk(base):
            for filename in sorted(filenames):
                abs_path = os.path.join(dirpath, filename)
                rel = os.path.relpath(abs_path, kit_dir).replace("\\", "/")
                with open(abs_path, "rb") as fh:
                    payload = fh.read()
                kit_files[rel] = hashlib.sha256(payload).hexdigest()
                # Atomic per-file snapshot: land a complete file or none.
                tmp_rel = "build/kit/" + rel + ".tmp"
                write_bytes(campaign, tmp_rel, payload)
                final = os.path.join(campaign, "build", "kit",
                                     rel.replace("/", os.sep))
                os.replace(os.path.join(campaign, "build", "kit",
                                        (rel + ".tmp").replace("/", os.sep)), final)
    try:
        kit_commit = subprocess.run(
            ["git", "-C", kit_dir, "rev-parse", "HEAD"],
            capture_output=True, text=True)
        kit_commit = kit_commit.stdout.strip() if kit_commit.returncode == 0 else None
    except OSError:
        kit_commit = None

    manifest = {
        "campaign": str(scope["campaign"]),
        "revision": revision,
        "root": root.replace("\\", "/"),
        "commit": head,
        "totals": {
            "files": len(files),
            "bytes": sum(f["bytes"] for f in files),
            "units": len(units),
        },
        "exclusions": sorted(exclusions, key=lambda e: e["path"]),
        "subsets": subsets_out,
        "lensSets": declared_sets,
        "seeded": seeded_count,
        "files": files,
        "lanes": [{"name": lane["name"], "prefix": lane["prefix"],
                   "unit": lane["unit"]} for lane in lanes],
    }
    units_doc = {
        "lanes": lane_names(manifest),
        "units": units,
    }
    write_json(campaign, "manifest.json", manifest)
    write_json(campaign, "units.json", units_doc)

    with open(args.scope, "rb") as fh:
        scope_sha = hashlib.sha256(fh.read()).hexdigest()
    manifest_sha = sha256_file(manifest_path)
    units_sha = sha256_file(os.path.join(campaign, "units.json"))
    receipt = {
        "frozenAtUtc": utc_stamp(),
        "scopeSha256": scope_sha,
        "kit": {"packageDir": os.path.realpath(kit_dir).replace("\\", "/"),
                "commit": kit_commit,
                "files": dict(sorted(kit_files.items()))},
        "manifestSha256": manifest_sha,
        "unitsSha256": units_sha,
    }
    write_json(campaign, "build/freeze-receipt.json", receipt)
    emit({"command": "freeze", "campaign": manifest["campaign"],
          "revision": revision, "files": len(files), "units": len(units),
          "excluded": len(exclusions)})
    return 0


# --------------------------------------------------------------------------
# Read-only and aggregate commands
# --------------------------------------------------------------------------

def cmd_lanes(campaign, _args):
    manifest, units_doc = load_campaign(campaign)
    out = []
    for lane in manifest["lanes"]:
        lane_units = [u for u in units_doc["units"] if u["lane"] == lane["name"]]
        file_ids = [fid for u in lane_units for fid in u["files"]]
        files = [f for f in manifest["files"] if f["lane"] == lane["name"]]
        out.append({
            "lane": lane["name"],
            "prefix": lane["prefix"],
            "units": len(lane_units),
            "files": len(files),
            "bytes": sum(f["bytes"] for f in files),
        })
    emit(out)
    return 0


def compact_units(campaign, manifest, units_doc, lane):
    files_by_id = {f["id"]: f for f in manifest["files"]}
    out = []
    for unit in sorted((u for u in units_doc["units"] if u["lane"] == lane),
                       key=lambda u: u["id"]):
        out.append({
            "id": unit["id"],
            "root": manifest["root"],
            "dir": unit["dir"],
            "bytes": unit["bytes"],
            "oversize": unit["oversize"],
            "files": [[files_by_id[fid]["rel"], files_by_id[fid]["sha256"],
                       files_by_id[fid]["bytes"], files_by_id[fid]["kind"]]
                      for fid in unit["files"]],
        })
    return out


def cmd_units(campaign, args):
    manifest, units_doc = load_campaign(campaign)
    check_lane(manifest, safe_name(args.lane, "lane"))
    units = compact_units(campaign, manifest, units_doc, args.lane)
    if args.pending:
        kept = []
        for unit in units:
            detail = read_breadth_verdict(campaign, args.lane, unit["id"])
            if detail["status"] in ("completed", "terminal-failed"):
                continue
            kept.append(unit)
        units = kept
    if args.limit and args.limit > 0:
        units = units[:args.limit]
    emit(units)
    note("units: %d for lane %s" % (len(units), args.lane))
    return 0


def cmd_agg(campaign, args):
    manifest, units_doc = load_campaign(campaign)
    check_lane(manifest, safe_name(args.lane, "lane"))
    details = lane_unit_states(campaign, manifest, units_doc, args.lane)
    counts = {"completed": 0, "failed": 0, "pending": 0, "terminal-failed": 0}
    sev = {"low": 0, "medium": 0, "high": 0}
    for detail in details:
        counts[detail["status"]] += 1
        if detail["status"] == "completed":
            for finding in detail["findings"]:
                sev[finding["severity"]] += 1
    coverage = {
        "lane": args.lane,
        "units": len(details),
        "completed": counts["completed"],
        "failed": counts["failed"],
        "pending": counts["pending"],
        "terminalFailed": counts["terminal-failed"],
        "findingsBySeverity": sev,
        "unitsDetail": details,
    }
    write_json(campaign, "build/breadth-coverage-%s.json" % args.lane, coverage)
    emit({"lane": args.lane, "units": coverage["units"],
          "completed": coverage["completed"], "failed": coverage["failed"],
          "pending": coverage["pending"], "terminalFailed": coverage["terminalFailed"],
          "low": sev["low"], "medium": sev["medium"], "high": sev["high"]})
    return 0


def verify_frozen_commit(repository, commit):
    """Fail cleanly when the repository lacks the frozen commit."""
    try:
        done = subprocess.run(
            ["git", "-C", repository, "rev-parse", "--verify", "--quiet",
             commit + "^{commit}"],
            capture_output=True, text=True)
    except OSError as exc:
        raise Fail("cannot run git against repository %s: %s" % (repository, exc))
    if done.returncode != 0:
        raise Fail("repository %s does not contain the frozen commit %s"
                   % (repository, commit))


def git_blob_sha256(repository, commit, rel):
    """Hash the blob <commit>:<rel> read from the repository's object store."""
    try:
        done = subprocess.run(
            ["git", "-C", repository, "cat-file", "blob", "%s:%s" % (commit, rel)],
            capture_output=True)
    except OSError as exc:
        raise Fail("cannot run git against repository %s: %s" % (repository, exc))
    if done.returncode != 0:
        raise Fail("cannot read blob %s:%s from repository %s"
                   % (commit, rel, repository))
    return hashlib.sha256(done.stdout).hexdigest()


def check_lane_files(manifest, lanes, repository=None):
    changed, missing = [], []
    from_git = 0
    total = 0
    commit = str(manifest.get("commit", ""))
    if repository:
        verify_frozen_commit(repository, commit)
    for f in manifest["files"]:
        if f["lane"] not in lanes:
            continue
        total += 1
        try:
            if sha256_file(f["path"]) != f["sha256"]:
                changed.append(f["path"])
        except OSError:
            if repository:
                # The pinned worktree is gone (retired after the campaign):
                # prove the identity from the frozen commit instead.
                if git_blob_sha256(repository, commit, f["rel"]) == f["sha256"]:
                    from_git += 1
                else:
                    changed.append(f["path"])
            else:
                missing.append(f["path"])
    return {"files": total, "changed": len(changed), "missing": len(missing),
            "fromGit": from_git,
            "repository": repository.replace("\\", "/") if repository else None,
            "changedPaths": changed[:50], "missingPaths": missing[:50]}


def cmd_check(campaign, args):
    manifest, _units_doc = load_campaign(campaign)
    lane = args.lane
    if lane != "all":
        check_lane(manifest, safe_name(lane, "lane"))
        lanes = [lane]
    else:
        lanes = lane_names(manifest)
    emit(check_lane_files(manifest, lanes, getattr(args, "repository", None)))
    return 0


def cmd_subset(campaign, args):
    manifest, units_doc = load_campaign(campaign)
    name = str(args.name)
    sub = manifest.get("subsets", {}).get(name)
    if sub is None:
        raise Fail("unknown subset %r; known: %s"
                   % (name, ", ".join(sorted(manifest.get("subsets", {}))) or "none"))
    unit_of = {}
    lane_of = {f["id"]: f["lane"] for f in manifest["files"]}
    for unit in units_doc["units"]:
        for fid in unit["files"]:
            unit_of[fid] = unit["id"]
    rows = []
    for fid in sub["paths"]:
        lane = lane_of.get(fid, "")
        unit_id = unit_of.get(fid, "")
        status = "unknown"
        if unit_id:
            status = read_breadth_verdict(campaign, lane, unit_id)["status"]
        rows.append({"file": fid, "lane": lane, "unit": unit_id, "status": status})
    emit({"subset": name, "description": sub.get("description", ""), "files": rows})
    return 0


def cmd_lenses(campaign, args):
    manifest, _units_doc = load_campaign(campaign)
    set_name = safe_name(args.set, "lens set")
    path = os.path.join(campaign, "build", "lenses-%s.json" % set_name)
    if not os.path.isfile(path):
        raise Fail("no lens set file: %s" % path.replace("\\", "/"))
    doc = validate_lens_doc(load_json(path, "lens set file"), set_name)
    lenses = [{"name": lens["name"], "title": lens["title"],
               "brief": lens["brief"], "inputs": lens["inputs"]}
              for lens in doc["lenses"]]
    if args.pending:
        lenses = [lens for lens in lenses
                  if read_lens_verdict(campaign, set_name, lens["name"])["status"]
                  != "completed"]
    if args.limit and args.limit > 0:
        lenses = lenses[:args.limit]
    emit({"campaign": doc.get("campaign", ""), "root": manifest["root"],
          "commit": manifest["commit"], "lenses": lenses})
    note("lenses: %d in set %s" % (len(lenses), set_name))
    return 0


def cmd_lensagg(campaign, args):
    set_name = safe_name(args.set, "lens set")
    path = os.path.join(campaign, "build", "lenses-%s.json" % set_name)
    if not os.path.isfile(path):
        raise Fail("no lens set file: %s" % path.replace("\\", "/"))
    doc = validate_lens_doc(load_json(path, "lens set file"), set_name)
    details = []
    with_verdict = 0
    candidates = 0
    sev = {"low": 0, "medium": 0, "high": 0}
    for lens in doc["lenses"]:
        detail = read_lens_verdict(campaign, set_name, lens["name"])
        if detail["status"] == "completed":
            with_verdict += 1
            candidates += len(detail["candidates"])
            for finding in detail["candidates"]:
                sev[finding["severity"]] += 1
        detail["title"] = lens["title"]
        details.append(detail)
    out = {
        "set": set_name,
        "lenses": len(doc["lenses"]),
        "withVerdict": with_verdict,
        "candidates": candidates,
        "bySeverity": sev,
        "lensesDetail": details,
    }
    write_json(campaign, "build/%s-coverage.json" % set_name, out)
    emit({"set": set_name, "lenses": out["lenses"], "withVerdict": with_verdict,
          "candidates": candidates, "bySeverity": sev})
    return 0


def cmd_candidates(campaign, args):
    manifest, units_doc = load_campaign(campaign)
    if args.min_severity not in SEVERITIES:
        raise Usage("--min-severity must be one of %s" % ", ".join(SEVERITIES))
    threshold = SEVERITY_RANK[args.min_severity]
    cands = collect_candidates(campaign, manifest, units_doc)
    out = []
    for cand in cands:
        if SEVERITY_RANK[cand["severity"]] < threshold:
            continue
        if args.pending:
            confirm = read_confirm_verdict(campaign, cand["id"])
            if confirm["verdict"] is not None:
                continue
        entry = dict(cand)
        entry["sources"] = sorted(cand["sources"])
        out.append(entry)
    if args.limit and args.limit > 0:
        out = out[:args.limit]
    emit({"campaign": manifest["campaign"], "root": manifest["root"],
          "commit": manifest["commit"], "candidates": out})
    note("candidates: %d" % len(out))
    return 0


def cmd_confirmagg(campaign, _args):
    manifest, units_doc = load_campaign(campaign)
    cands = collect_candidates(campaign, manifest, units_doc)
    counts = {"confirmed": 0, "refuted": 0, "inconclusive": 0, "duplicate": 0}
    pending = 0
    invalid = 0
    details = []
    for cand in cands:
        confirm = read_confirm_verdict(campaign, cand["id"])
        detail = {"id": cand["id"], "severity": cand["severity"],
                  "where": cand["where"], "sources": cand["sources"],
                  "confirm": confirm["verdict"]}
        if confirm["verdict"] is None:
            if confirm["status"] == "invalid":
                invalid += 1
                detail["confirm"] = "invalid"
            else:
                pending += 1
                detail["confirm"] = "pending"
        else:
            counts[confirm["verdict"]] += 1
        details.append(detail)
    out = {
        "candidates": len(cands),
        **counts,
        "pending": pending,
        "invalid": invalid,
        "details": details,
    }
    write_json(campaign, "build/confirm-coverage.json", out)
    emit({k: v for k, v in out.items() if k != "details"})
    return 0


def cmd_status(campaign, _args):
    """One tender-ready object, computed from staging directly.

    Lens completeness rule: when scope.lensSets declared sets at freeze time,
    every declared set must exist on disk with a completed verdict for every
    lens. When no sets were declared the campaign is breadth-only by explicit
    choice: lensSetsDeclared is false, lensesComplete stays false (never
    vacuously true), and note says no lens sets were declared.
    """
    manifest, units_doc = load_campaign(campaign)
    lanes_out = []
    breadth_complete = True
    for lane in lane_names(manifest):
        details = lane_unit_states(campaign, manifest, units_doc, lane)
        counts = {"completed": 0, "failed": 0, "pending": 0, "terminal-failed": 0}
        for detail in details:
            counts[detail["status"]] += 1
        if counts["completed"] != len(details) or not details:
            breadth_complete = False
        lanes_out.append({
            "lane": lane,
            "units": len(details),
            "completed": counts["completed"],
            "failed": counts["failed"],
            "pending": counts["pending"],
            "terminalFailed": counts["terminal-failed"],
        })

    sets_out = []
    declared = [str(s) for s in manifest.get("lensSets") or []]
    sets_declared = bool(declared)
    if not sets_declared:
        # A breadth-only campaign must declare itself explicitly; without a
        # declaration lensesComplete stays false rather than vacuously true.
        lenses_complete = False
        lens_note = "no lens sets were declared in scope.lensSets; a breadth-only campaign records this explicitly"
    else:
        lens_note = None
        lenses_complete = True
    on_disk = lens_sets(campaign)
    for set_name, doc in on_disk.items():
        counts = {"withVerdict": 0, "failed": 0, "pending": 0}
        for lens in doc["lenses"]:
            status = read_lens_verdict(campaign, set_name, lens["name"])["status"]
            if status == "completed":
                counts["withVerdict"] += 1
            elif status == "failed":
                counts["failed"] += 1
                lenses_complete = False
            else:
                counts["pending"] += 1
                lenses_complete = False
        sets_out.append({"set": set_name, "lenses": len(doc["lenses"]), **counts})
    for set_name in declared:
        if set_name not in on_disk:
            lenses_complete = False
            lens_note = "declared lens set missing on disk: " + set_name

    cands = collect_candidates(campaign, manifest, units_doc)
    notable = [c for c in cands if SEVERITY_RANK[c["severity"]] >= SEVERITY_RANK["medium"]]
    confirmed = 0
    for cand in notable:
        if read_confirm_verdict(campaign, cand["id"])["verdict"] is not None:
            confirmed += 1
    # The candidate set is not final until the raising tiers have settled:
    # confirmation can only be complete behind a closed breadth+lens gate.
    confirm_gate_open = breadth_complete and lenses_complete
    confirm_complete = confirm_gate_open and confirmed == len(notable)

    unit_of = {}
    for unit in units_doc["units"]:
        for fid in unit["files"]:
            unit_of[fid] = unit
    lane_of = {f["id"]: f["lane"] for f in manifest["files"]}
    subsets_out = {}
    for name, sub in manifest.get("subsets", {}).items():
        covered = 0
        for fid in sub["paths"]:
            unit = unit_of.get(fid)
            if unit and read_breadth_verdict(campaign, lane_of[fid], unit["id"])["status"] \
                    == "completed":
                covered += 1
        subsets_out[name] = {"files": len(sub["paths"]), "covered": covered}

    complete = breadth_complete and lenses_complete and confirm_complete
    emit({
        "campaign": manifest["campaign"],
        "lanes": lanes_out,
        "lensSets": sets_out,
        "lensSetsDeclared": sets_declared,
        "note": lens_note,
        "candidates": {"total": len(cands), "notable": len(notable),
                       "confirmed": confirmed, "pending": len(notable) - confirmed,
                       "seeded": len(load_seeded(campaign))},
        "subsets": subsets_out,
        "breadthComplete": breadth_complete,
        "lensesComplete": lenses_complete,
        "confirmGateOpen": confirm_gate_open,
        "confirmComplete": confirm_complete,
        "complete": complete,
    })
    return 0


def cmd_close(campaign, args):
    manifest, units_doc = load_campaign(campaign)
    items = []

    # 1. No lane has a pending or non-terminal failed unit.
    blocking = []
    terminal = []
    for lane in lane_names(manifest):
        for detail in lane_unit_states(campaign, manifest, units_doc, lane):
            if detail["status"] == "pending" or detail["status"] == "failed":
                blocking.append("%s (%s)" % (detail["id"], detail["status"]))
            elif detail["status"] == "terminal-failed":
                terminal.append("%s: %s" % (detail["id"], detail.get("summary")
                                            or detail.get("reason") or "terminal"))
    items.append({"item": "breadth-units", "pass": not blocking,
                  "detail": "; ".join(blocking + terminal) or "all units settled"})

    # 2. Every lens in every lens set has a valid verdict.
    lens_gaps = []
    for set_name, doc in lens_sets(campaign).items():
        for lens in doc["lenses"]:
            status = read_lens_verdict(campaign, set_name, lens["name"])["status"]
            if status != "completed":
                lens_gaps.append("%s/%s (%s)" % (set_name, lens["name"], status))
    items.append({"item": "lens-verdicts", "pass": not lens_gaps,
                  "detail": "; ".join(lens_gaps) or "all lenses have valid verdicts"})

    # 3. No medium/high candidate lacks a confirm verdict.
    cands = collect_candidates(campaign, manifest, units_doc)
    unconfirmed = []
    for cand in cands:
        if SEVERITY_RANK[cand["severity"]] >= SEVERITY_RANK["medium"] \
                and read_confirm_verdict(campaign, cand["id"])["verdict"] is None:
            unconfirmed.append(cand["id"])
    items.append({"item": "candidates-confirmed", "pass": not unconfirmed,
                  "detail": "; ".join(unconfirmed) or "every medium/high candidate confirmed"})

    # 4. check all is clean.
    repository = getattr(args, "repository", None)
    check = check_lane_files(manifest, lane_names(manifest), repository)
    detail = "%d changed, %d missing of %d files" \
        % (check["changed"], check["missing"], check["files"])
    if repository:
        detail += "; %d verified from commit %s via %s" \
            % (check["fromGit"], manifest["commit"], check["repository"])
    items.append({"item": "inputs-clean", "pass": check["changed"] == 0 and
                  check["missing"] == 0,
                  "detail": detail})

    # 5. No runs.json entry is running.
    runs_path = os.path.join(campaign, "build", "runs.json")
    running = []
    if os.path.isfile(runs_path):
        runs = load_json(runs_path, "runs file")
        if isinstance(runs, list):
            running = [str(r.get("runId", "?")) for r in runs
                       if isinstance(r, dict) and r.get("state") == "running"]
        else:
            running = ["runs.json is not an array"]
    else:
        running = ["build/runs.json is missing"]
    items.append({"item": "runs-settled", "pass": not running,
                  "detail": "; ".join(running) or "no run is still running"})

    # 6. accounting.json with usageSource and per-run spend or unavailable.
    acc_path = os.path.join(campaign, "build", "accounting.json")
    acc_problems = []
    if os.path.isfile(acc_path):
        acc = load_json(acc_path, "accounting file")
        if not isinstance(acc, dict) or not str(acc.get("usageSource", "")):
            acc_problems.append("accounting.json lacks a usageSource")
        runs = acc.get("runs") if isinstance(acc, dict) else None
        if not isinstance(runs, list):
            acc_problems.append("accounting.json lacks a per-run list")
        else:
            for run in runs:
                if not isinstance(run, dict) or (
                        not isinstance(run.get("spentTokens"), (int, float))
                        and run.get("unavailable") is not True):
                    acc_problems.append(
                        "run %r has neither spentTokens nor unavailable: true"
                        % run.get("runId", "?"))
    else:
        acc_problems.append("build/accounting.json is missing")
    items.append({"item": "accounting", "pass": not acc_problems,
                  "detail": "; ".join(acc_problems) or "accounting present for every run"})

    # 7. verdict.json with a PASS|FAIL|PARTIAL verdict and an existing doc.
    verdict_path = os.path.join(campaign, "build", "verdict.json")
    verdict_problems = []
    if os.path.isfile(verdict_path):
        verdict = load_json(verdict_path, "verdict file")
        if not isinstance(verdict, dict) or verdict.get("verdict") not in \
                ("PASS", "FAIL", "PARTIAL"):
            verdict_problems.append("verdict is not PASS, FAIL or PARTIAL")
        else:
            doc_path = verdict.get("verdictDoc")
            if not isinstance(doc_path, str) or not os.path.isfile(doc_path):
                verdict_problems.append("verdictDoc does not exist: %r" % doc_path)
    else:
        verdict_problems.append("build/verdict.json is missing")
    items.append({"item": "verdict-recorded", "pass": not verdict_problems,
                  "detail": "; ".join(verdict_problems) or "verdict recorded"})

    passed = all(item["pass"] for item in items)
    emit({"pass": passed, "items": items})
    if not passed:
        for item in items:
            if not item["pass"]:
                note("close failed: %s: %s" % (item["item"], item["detail"]))
    return 0 if passed else 1


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(prog="crew.py", add_help=False)
    parser.add_argument("campaign")
    sub = parser.add_subparsers(dest="command", metavar="command")

    p = sub.add_parser("freeze", add_help=False)
    p.add_argument("--scope", required=True)
    p.add_argument("--kit")
    p.add_argument("--replace", action="store_true")
    p.set_defaults(fn=cmd_freeze)

    p = sub.add_parser("lanes", add_help=False)
    p.set_defaults(fn=cmd_lanes)

    p = sub.add_parser("units", add_help=False)
    p.add_argument("lane")
    p.add_argument("--pending", action="store_true")
    p.add_argument("--limit", type=int, default=0)
    p.set_defaults(fn=cmd_units)

    p = sub.add_parser("agg", add_help=False)
    p.add_argument("lane")
    p.set_defaults(fn=cmd_agg)

    p = sub.add_parser("check", add_help=False)
    p.add_argument("lane")
    p.add_argument("--repository")
    p.set_defaults(fn=cmd_check)

    p = sub.add_parser("subset", add_help=False)
    p.add_argument("name")
    p.set_defaults(fn=cmd_subset)

    p = sub.add_parser("lenses", add_help=False)
    p.add_argument("set")
    p.add_argument("--pending", action="store_true")
    p.add_argument("--limit", type=int, default=0)
    p.set_defaults(fn=cmd_lenses)

    p = sub.add_parser("lensagg", add_help=False)
    p.add_argument("set")
    p.set_defaults(fn=cmd_lensagg)

    p = sub.add_parser("candidates", add_help=False)
    p.add_argument("--min-severity", default="low", dest="min_severity")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--pending", action="store_true")
    p.set_defaults(fn=cmd_candidates)

    p = sub.add_parser("confirmagg", add_help=False)
    p.set_defaults(fn=cmd_confirmagg)

    p = sub.add_parser("status", add_help=False)
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("close", add_help=False)
    p.add_argument("--repository")
    p.set_defaults(fn=cmd_close)
    return parser


def main(argv):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", newline="\n")
        except (AttributeError, ValueError, OSError):
            try:
                stream.reconfigure(encoding="utf-8")
            except (AttributeError, ValueError, OSError):
                pass
    if len(argv) < 2:
        note("usage: python -I crew.py <campaignDir> <command> [options]")
        return 2
    try:
        args = build_parser().parse_args(argv)
    except SystemExit:
        note("usage: python -I crew.py <campaignDir> <command> [options]")
        return 2
    if not getattr(args, "fn", None):
        note("unknown or missing command: %r" % getattr(args, "command", None))
        return 2
    campaign = args.campaign.replace("\\", "/").rstrip("/")
    if not os.path.isdir(campaign):
        # freeze may create it; everything else needs an existing campaign.
        if args.fn is not cmd_freeze:
            note("campaign directory does not exist: %s" % campaign)
            return 1
        os.makedirs(campaign, exist_ok=True)
    try:
        return args.fn(campaign, args)
    except Fail as exc:
        note(str(exc))
        return 1
    except Usage as exc:
        note(str(exc))
        return 2
    except BrokenPipeError:
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
