import io
import os
import re

import sys
if len(sys.argv) < 2:
    sys.exit("usage: verify_memory.py <memory-dir>")
D = sys.argv[1]
print("=== store:", D)
files = sorted(f for f in os.listdir(D) if f.endswith(".md"))
topics = [f for f in files if f != "MEMORY.md"]

names = {}
bad = []
for f in files:
    raw = io.open(os.path.join(D, f), "rb").read()
    ctl = [b for b in raw if b < 0x20 and b not in (9, 10, 13)]
    if ctl:
        bad.append((f, sorted(set(ctl))))
    txt = raw.decode("utf-8")
    if f != "MEMORY.md":
        m = re.search(r"^name:\s*(\S+)\s*$", txt, re.M)
        names[f] = m.group(1) if m else None

print("=== files:", len(files), "(topics:", len(topics), ")")

print("\n=== control bytes (excluding tab/CR/LF)")
print("  NONE - clean" if not bad else "  CORRUPT: %s" % bad)

print("\n=== frontmatter name matches filename")
for f in topics:
    n = names.get(f)
    ok = n == f[:-3]
    print("  %-40s %s" % (f, "ok" if ok else "MISMATCH name=%r" % n))

print("\n=== required frontmatter + feedback Why")
for f in topics:
    txt = io.open(os.path.join(D, f), encoding="utf-8").read()
    has_desc = re.search(r"^description:\s*\S", txt, re.M) is not None
    tm = re.search(r"^\s+type:\s*(\w+)", txt, re.M)
    t = tm.group(1) if tm else None
    ok_t = t in ("user", "feedback", "project", "reference")
    why = ("**Why:**" in txt) or ("## Why" in txt)
    prob = []
    if not has_desc:
        prob.append("no description")
    if not ok_t:
        prob.append("type=%r" % t)
    if t == "feedback" and not why:
        prob.append("feedback missing Why")
    print("  %-40s %-10s %s" % (f, t, "ok" if not prob else "; ".join(prob)))

print("\n=== wikilink targets")
slugs = set(names.values())
dang = 0
for f in files:
    txt = io.open(os.path.join(D, f), encoding="utf-8").read()
    for link in re.findall(r"\[\[([^\]]+)\]\]", txt):
        if link not in slugs:
            print("  DANGLING %s -> [[%s]]" % (f, link))
            dang += 1
print("  none dangling" if dang == 0 else "  %d dangling" % dang)

print("\n=== index links resolve")
idx = io.open(os.path.join(D, "MEMORY.md"), encoding="utf-8").read()
linked = re.findall(r"\]\(([^)]+\.md)\)", idx)
for t in linked:
    if not os.path.exists(os.path.join(D, t)):
        print("  MISSING TARGET:", t)
missing_from_index = [f for f in topics if f not in linked]
print("  index entries:", len(linked), "| topic files:", len(topics))
print("  not indexed:", missing_from_index or "none")

print("\n=== index budget (hard wall: 200 lines / 25000 chars)")
print("  lines:", len(idx.splitlines()), "| chars:", len(idx))

total = sum(len(io.open(os.path.join(D, f), encoding="utf-8").read()) for f in files)
print("\n=== store total chars:", total)
