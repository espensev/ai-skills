---
name: codex-state-cleanup
description: "Audit, compress, and safely prune a local Codex home, native memory, archived sessions, databases, caches, logs, and temporary state. Use when asked to clean, shrink, compact, or reclaim space under $CODEX_HOME. Do not use for deciding what facts belong in memory, ordinary repository cleanup, or deleting active credentials and sessions."
---

# Codex State Cleanup

Reclaim local storage with measured evidence, exact targets, and recovery proof.
Audit first. Mutate only when the user asked for cleanup.

## Scope

- Resolve the physical Codex home. `$CODEX_HOME` may be unset, redirected, or
  reached through a junction or symlink.
- Audit native memory, sessions, archived sessions, SQLite databases, caches,
  logs, packages, plugins, skills, attachments, and temporary trees.
- Route memory-content decisions to `memory-management`. This skill owns disk
  hygiene and safe compaction mechanics.
- Preserve unrelated repositories and dirty worktrees.

## Hard Boundaries

- Read every applicable `AGENTS.md` before machine-sensitive work.
- Run the declared local-machine verifier immediately before mutation. Require
  the expected controller identity. Do not infer identity from a path.
- Resolve and validate absolute targets. Refuse broad roots, unresolved
  variables, unexpected reparse points, and paths outside the intended home or
  cold-storage directory.
- Preserve active sessions, credentials, current config, current task files,
  packages, and provider-owned state unless a narrower verified rule permits
  change.
- Never hand-edit generated native memory. Use only the runtime-declared update
  queue after explicit user authorization.
- Never VACUUM an active database. Never delete live WAL or SHM files.
- Do not put live Codex state in synchronized storage: no databases, WAL/SHM,
  sessions, histories, caches, logs, credentials, or auth state.
- Prefer recovery archives or quarantine for valuable or ambiguous data.
- If a required identity, budget, provenance, archive, or integrity gate fails,
  stop that lane. Continue only with independent safe lanes.

## Workflow

### 1. Establish authority

1. Resolve the logical and physical Codex-home paths.
2. Record controller identity, Codex version, active Codex processes, and the
   applicable local rules.
3. Confirm whether the request authorizes read-only audit, compression,
   deletion, offline database work, or all four.
4. Keep synchronized machine-data roots separate. Store only a sanitized
   recovery manifest there when local policy explicitly allows it.

### 2. Inventory

Measure bytes, file counts, oldest/newest timestamps, and link type for each
top-level directory. List large root files separately.

For SQLite files, read only:

- `PRAGMA journal_mode`
- `PRAGMA page_size`
- `PRAGMA page_count`
- `PRAGMA freelist_count`

Estimate offline reclaim as `page_size * freelist_count`. Do not mutate yet.

Classify every candidate:

| Class | Typical state | Action |
|---|---|---|
| Preserve | active sessions, credentials, config, packages, live DB sidecars | none |
| Archive | old archived sessions, valuable historical logs | verified cold storage |
| Delete | proved stale backups, disposable temp, empty trees | exact removal |
| Offline | database free pages, live-file ambiguity | defer until Codex closes |
| Blocked | unknown ownership, failed gate, reparse-boundary doubt | report only |

Show projected gross and net reclaimed bytes before deletion.

### 3. Compact native memory

1. Run the native-memory audit and measure generated file lines, bytes,
   repeated nonblank lines, and update-note count.
2. Keep durable preferences, safety rules, machine provenance, active project
   families, reusable traps, and evidence pointers.
3. Request merging of duplicate facts, resolved one-offs, superseded gates,
   and filler through one terse typed update note.
4. Do not claim savings until the memory system regenerates and a new audit
   measures them.

### 4. Cold-pack archived sessions

Warn that archived chats disappear from Codex history views until restored.
Use local, unsynchronized cold storage outside the Codex home.

1. Count source files and bytes.
2. Create one timestamped compressed archive plus a restore manifest.
3. Test the archive with its native test command.
4. Compare archived file count and uncompressed bytes with the source.
5. Record SHA-256, archive bytes, source bytes, tool version, and restore path.
6. Verify the archive before deleting its source.
7. Re-resolve the source boundary. Confirm it is not an unexpected reparse
   point. Remove only the proved source tree.

Do not remove the source when any count, byte total, hash, or archive test is
missing or inconsistent.

### 5. Remove disposable state

- Keep the current config and a justified newest recovery copy when no other
  rollback exists.
- Remove stale corrupt copies, abandoned transactional backups, old daily
  sandbox logs, proved task-temp directories, and recursively empty trees.
- Preserve same-day or in-use task evidence unless the user names it.
- Re-scan each directory before recursive removal. Fail closed if contents
  changed after preview.
- Report permanent deletions and recovery limits.

### 6. Gate caches, plugins, and skills

Run the live Codex skill-budget or configuration classifier required by local
rules before changing plugin, skill, marketplace, or provider caches. A
missing helper, failed classifier, active-process hold, or uncertain install
record blocks this lane. Large size alone is not deletion proof.

### 7. Compact databases offline

If this session owns the live Codex process, do not terminate it. Report the
offline gate for a later session.

With Codex fully closed:

1. Confirm no Codex process or file handle remains.
2. Copy the database and sidecars to local rollback storage.
3. Run `PRAGMA integrity_check`.
4. Run `VACUUM` only when the integrity check passes.
5. Re-run integrity and launch checks.
6. Retain rollback until the repaired runtime starts cleanly.

### 8. Verify

- Re-measure top-level bytes and exact net savings.
- Re-test recovery archives and hashes.
- Confirm deleted sources are absent and preserved config exists.
- Run the memory audit again.
- Confirm Codex starts without mutating active session history.
- Recheck repository status. Preserve unrelated dirt.

## Output

Use terse sections:

- `Outcome`: reclaimed bytes and completed lanes.
- `Compressed`: archive path, source/archive bytes, hash, test result.
- `Deleted`: exact classes, counts, bytes, recoverability.
- `Preserved`: active and blocked state.
- `Next gate`: largest safe remaining reclaim.
- `Run closeout`: elapsed time, measured token source, tool/failure/approval/
  agent counts when exposed, verification, changed surfaces, highest risk.

## Official References

- [Codex memories](https://learn.chatgpt.com/docs/customization/memories)
- [Codex troubleshooting and session paths](https://learn.chatgpt.com/docs/reference/troubleshooting)
