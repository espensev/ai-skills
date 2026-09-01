# Compress Pass — Clean a Memory Store

Procedure for "reduce the memories, cut dead words, remove redundant/old
entries, filter out false or irrelevant info". Run as
`/memory-management compress`, or as the second half of a bare
`/memory-management` invocation. Proven 2026-08-25 on a 28-file store:
28 → 15 files, 54.5k → 31.7k chars, index 45 → 23 lines, zero facts lost.

## 0. Ground rules

- **Back up first**: copy the whole memory directory to a scratch location
  before touching anything. Every deletion below is only safe because this
  exists.
- **Write bodies with `Write`/`Edit`, never Bash heredocs.** Memory bodies are
  full of Windows paths; heredocs decode backslashes into control bytes and
  the file looks fine in the tool result while corrupt on disk. Any helper
  script goes in a *file* and builds backslashes as `chr(92)`.
- **Verify drift before writing.** Any fact that can change — a PR state, a
  hook's shape, whether a doc still exists — gets checked live. In the proven
  run, 3 of 3 checked facts had drifted and changed the plan (a tombstone, a
  closed action item, a deleted doc that had to stay in memory).
- **An empty search is unproven.** Before declaring anything "gone", re-run
  the same search against a file you know exists. On Windows Git Bash a bare
  drive letter (`find D: ...`) errors to stderr and reads exactly like "no
  matches"; `grep` BRE with escaped backslashes silently misses path literals
  that `grep -F` finds.
- **Two action tiers.** Once the backup exists, safe classes apply without
  re-asking: filler and narration cuts, duplicates of always-loaded context,
  tombstones verified gone live, false-claim rewrites backed by evidence
  captured this run, and the index rebuild. Confirm first: deleting a file
  whose subject cannot be verified live, anything with machine scope
  `remote` or `unknown`, and whole-store restructures.

## 1. Inventory

```
wc -c -l *.md | sort -rn
```

Read every topic file once. For each, note in one line: type, what it
duplicates, whether its subject still exists.

## 2. Classify — in this order, biggest win first

| Class | Test | Action |
|---|---|---|
| **Duplicate of always-loaded context** | The rule already appears verbatim in `CLAUDE.md` / AGENTS.md | Delete the rule text; keep only what the summary drops (verbatim quotes, worked examples, the Why). Merge all such files into one. |
| **False or drifted claim** | The memory asserts current state that live verification contradicts | Rewrite to the verified truth, citing the check, or supersede. A procedure that would cause harm if followed is priority zero — fix it before anything else. |
| **Irrelevant** | No imaginable future question from this project reaches it: one-off trivia, another project's fact, transient state long past | Delete, or move it to the store it belongs to. |
| **Tombstone** | Subject is finished, merged, deleted, or superseded, with no resurrection risk | Delete. Verify live first (`gh pr view`, path exists, etc.). |
| **Same trap, split across files** | Two files a future question would want together (both about one tool's state, both about one sync service) | Merge into one file named for the *scenario*, not the incident. |
| **Answered action item** | "Check whether X needs fixing" and X is already fixed | Compress to a one-line confirmation with the verify date. |
| **Stale pointer** | Names a path/doc that no longer exists | Repoint to the surviving surface, or if none survives, say so explicitly so nobody hunts. |
| **Dense** | Mostly literal values, registry keys, fingerprints, recipes | Leave alone. This is the floor. |

Do **not** compress index descriptions to save space — that is the last
resort in the slimming order (SKILL.md §5) and self-harms recall.

## 3. Rewrite the survivors

Per file, one pass:

- Kill narration ("On <date> I discovered that…", "it turned out…") — keep the
  date only if it dates a still-relevant fact.
- One statement per trap. If the body and the **How to apply** say the same
  thing, keep the one with the recipe.
- Bold-lead each paragraph with its conclusion so a skim finds the answer.
- Keep every literal: path, GUID, fingerprint, registry key, command, error
  string, byte count. These are why the file exists.
- `feedback` files keep a **Why** and a reuse trigger.
- Filename = `name:` slug; rename when a merge changes the subject.

## 4. Rebuild the index

- Crown entries (≤160 chars, "read before X") first, no group header.
- Then 3–5 groups; one line per file; scenario keywords + conclusion.
- Short labels, never the filename twice.

## 5. Verify — all of these, every time

```bash
python scripts/verify_memory.py <memory-dir>   # control bytes, wikilinks, index coverage, budget
python scripts/memory_audit.py --dir <memory-dir>   # schema / compliance audit
```

`verify_memory.py` ships in this skill's `scripts/`; `memory_audit.py` ships
with the package runtime (see SKILL.md → Audit tool). Pass criteria: zero
control bytes below 0x20 (tab/CR/LF excepted), zero dangling `[[wikilinks]]`,
every topic file indexed, every index link resolves, `feedback` has a Why,
index under budget, audit exit 0. Compare any soft stale-path flag **count**
before and after — an unchanged count is evidence no compression dropped or
added a path.

## 6. Report

Before/after table (files, chars, index lines/chars), the merge list, the
deletions, every false claim fixed (with the live check that proved it), the
irrelevant entries removed, and every drift found. Be explicit that only
`MEMORY.md` is session-loaded, so topic-file shrink is a per-recall win, not
session speed.

## Known stopping point

When every remaining file fails the "Dense" test above — literal values and
recipes with no narration left — stop. Further cuts trade recipes for tokens.
