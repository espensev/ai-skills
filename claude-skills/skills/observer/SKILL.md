---
name: observer
description: "Passive project intelligence — observe, note, and synthesize patterns over time without interfering"
argument-hint: "/observe [note|review|synthesize|status] — project observation system"
allowed-tools: Read, Glob, Grep, Bash, Agent, Edit, Write
user-invocable: true
---

# Observer — Passive Project Intelligence

A non-interfering observation system that accumulates project knowledge over
time. Records decisions, spots patterns, flags drift, and synthesizes a living
intelligence document — without interrupting active work.

The observer never runs automatically. It only acts when you invoke it.

**Storage:** File-based JSONL at `data/observations.jsonl` by default. Repos with
a richer backend (e.g., SQLite campaign DB) can configure `[observer].backend`
in `project.toml` to use backend-specific commands instead.

## Invocation

```
/observe note <category> <summary>      # record an observation
/observe review                          # scan context, suggest observations
/observe synthesize                      # update project-intelligence.md
/observe status                          # show observation counts
```

---

## Commands

### `/observe note <category> <summary>`

Record a single observation. Category must be one of:

| Category | What It Captures |
|----------|-----------------|
| `decision` | Architectural or design choices made |
| `pattern` | Recurring code or workflow patterns |
| `drift` | Divergence from plans or attention imbalance |
| `risk` | Potential problems spotted |
| `progress` | Milestones and completions |
| `question` | Unresolved design questions |
| `debt` | Technical debt accumulating |

Optional flags:
- `--detail "longer explanation"` — expanded context
- `--files "file1.c,file2.h"` — related files (comma-separated)
- `--plan <plan-id>` — link to a campaign plan
- `--agent <agent-id>` — link to a campaign agent
- `--confidence 0.8` — certainty level (0.0-1.0, default 0.5)

**How to record:**

1. Get current timestamp:
   ```bash
   date -u +"%Y-%m-%dT%H:%M:%SZ"
   ```

2. Build the JSON observation object:
   ```jsonl
   {"ts":"2026-03-21T14:30:00Z","cat":"decision","summary":"chose JSONL over SQLite for portability","status":"open","detail":"...","files":["src/storage.py"],"plan":null,"agent":null,"confidence":0.5}
   ```

3. Append to `data/observations.jsonl`:
   ```bash
   echo '{"ts":"...","cat":"...","summary":"...","status":"open"}' >> data/observations.jsonl
   ```

### `/observe review`

Read the current project context and suggest new observations. This is the
primary way to build up observations passively over time.

**Pipeline:**

1. Load existing observations from `data/observations.jsonl`:
   ```bash
   cat data/observations.jsonl 2>/dev/null | wc -l
   ```
   Parse JSON lines to understand what has already been recorded.

2. Read recent context:
   - `git log --oneline -20` — recent commits
   - `git diff --stat HEAD~5` — recent file changes
   - Read tracker file from `[paths].tracker` — current campaign state
   - `docs/observer/project-intelligence.md` — last synthesis (if exists)

3. Analyze for:
   - **Decisions** made in recent commits or sessions
   - **Patterns** — files changing together, repeated error types
   - **Drift** — areas with no recent activity vs. active areas
   - **Risks** — missing tests, growing complexity, unresolved TODOs
   - **Questions** — ambiguities in recent work, undecided design choices
   - **Debt** — TODO/FIXME/HACK comments, workarounds

4. For each candidate observation:
   - Check if a similar observation already exists (avoid duplicates)
   - If new, present it to the user for approval
   - On approval, record via append to `data/observations.jsonl`

5. Summarize: how many new observations recorded, category breakdown

**Non-interference contract:**
- Never auto-records without user approval during review
- Never modifies code or plans
- Only reads project state and suggests observations

### `/observe synthesize`

Read all observations and produce the living intelligence document at
`docs/observer/project-intelligence.md`.

**Pipeline:**

1. Read all observations from `data/observations.jsonl`:
   ```bash
   cat data/observations.jsonl
   ```

2. Cluster observations by theme:
   - Group by category
   - Within categories, cluster by related files or topics
   - Count recurrence (similar observations = stronger signal)

3. Write `docs/observer/project-intelligence.md` with sections:
   - **Active Themes** — top patterns by frequency, sorted by confidence
   - **Decisions Log** — category: decision, reverse chronological
   - **Drift & Risks** — unresolved drift + risk observations
   - **Emerging Patterns** — category: pattern, with occurrence count
   - **Open Questions** — category: question, unresolved
   - **Technical Debt** — category: debt, unresolved
   - **Recently Resolved** — last 10 resolved observations

4. Save compact summary to memory:
   - File: project memory `observer_summary.md`
   - Contents: top 3 themes, unresolved risk count, open question count
   - Purpose: auto-loaded in future sessions for passive context

### `/observe status`

Show observation counts by category and status.

```bash
cat data/observations.jsonl 2>/dev/null
```

Parse the JSONL and display:

```
Observations: 23 total (18 open, 3 resolved, 2 stale)

  decision:  5 (3 open)
  pattern:   4 (4 open)
  drift:     3 (2 open, 1 stale)
  risk:      4 (3 open, 1 resolved)
  progress:  3 (2 open, 1 resolved)
  question:  2 (2 open)
  debt:      2 (2 open, 1 stale)

Last observation: 2026-03-21
Last synthesis:   2026-03-20
```

---

## Observation Lifecycle

```
note/review  ->  open  ->  noted  ->  resolved
                  |                    ^
                  +--- stale ----------+
                    (auto after 14d)   (if revisited)
```

- **open** — newly recorded, active
- **noted** — acknowledged, being tracked
- **resolved** — addressed, keeps history
- **stale** — mark after 14 days unresolved (update the status field in JSONL)

To update an observation's status, read the JSONL, find the matching entry by
timestamp + category + summary, and rewrite the file with the updated status.

---

## Integration with Other Skills

| Skill | How It Uses Observer |
|-------|---------------------|
| `/discover` | Reads `project-intelligence.md` as input context before research |
| `/planner` | Checks unresolved risks/drift before planning campaigns |
| `/manager verify` | Flags unresolved `risk` and `drift` observations in verify output |
| `/qa` | Uses `pattern` observations to prioritize test coverage gaps |
| `/observe-test` | Worktree observations get promoted to this JSONL after merge |

---

## Storage

- **Observations:** `data/observations.jsonl` — append-only JSONL file
- **Living doc:** `docs/observer/project-intelligence.md` — synthesized output
- **Memory:** project memory `observer_summary.md` — cross-session context

---

## Non-Interference Contract

1. Observer **never** runs automatically — no hooks, no cron, no background processes
2. Observer **never** modifies code, plans, or campaign state
3. Observer **only** reads project state and writes to its own outputs
4. During `/observe review`, every suggested observation requires user approval
5. The observer is purely additive — it records, it does not act
