---
name: loop-master
description: Backward-compatible alias for multi-round orchestration. Routes to repo-conventions for the immediate bounded step and to planner/manager for durable multi-agent campaigns. Use when older references invoke loop-master; do not implement separate orchestration logic here.
---

# Loop Master - Alias

`loop-master` no longer carries its own orchestration body. It remains only so
older references keep resolving.

Route the request to the narrow owning skill:

- **Immediate bounded step** - follow `repo-conventions` for one
  inspect-edit-verify objective.
- **Bounded unknown before planning or editing** - follow `discover`.
- **Durable multi-agent campaign design** - follow `planner` (add
  `--mode refactor` for phased refactors or migrations).
- **Executing an approved campaign plan** - follow `manager`.
- **Round-end validation and regression checks** - follow `qa`.
- **Staging or packaging finished work** - follow `ship`.

## Parallelism

Keep the immediate critical-path task local. Spawn sidecar work only when scopes
are disjoint and materially useful, normally with two to four workstreams at
most. For anything larger, hand off to `planner` and `manager` rather than
coordinating here.
