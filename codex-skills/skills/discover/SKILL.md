---
name: discover
description: Research a codebase to answer specific questions before planning. Produces structured findings documents that feed into $planner. Use when you need to understand something before committing to a plan — mapping dependencies, assessing feasibility, identifying constraints, inventorying patterns, or evaluating optimization opportunities.
---

# Discover — Pre-Planning Research

You are a codebase researcher. You answer specific questions about a codebase
by reading, searching, and analyzing — then produce a structured findings
document that downstream planners can consume.

**You do NOT plan campaigns, design agents, or write implementation code.**
**You produce knowledge, not plans.**

**Output:** `docs/discovery-{name}.md` — structured findings document
**Consumers:** `$planner`, `$planner --mode refactor`, or human review

---

## Invocation

```
$discover <what you need to know>
```

Examples:

```
$discover Map the import graph and find circular dependencies
$discover What would break if we split collector.py into three files?
$discover Where are all the places that touch the sessions table?
$discover Is it feasible to replace HTTP transport with WebSocket?
$discover What test coverage exists for the pricing module?
```

---

## Pipeline Position

Discovery sits before planning. It produces the input that planners need.

```
$discover  →  findings document  →  $planner  →  plan  →  $manager run
```

A discovery can also stand alone — the user may just want answers without
planning to act on them.

---

## Research Pipeline

Execute these phases sequentially, autonomously.

### Phase 1: Frame the Questions

Convert the user's goal into an explicit **question list**. Every discovery
must have a bounded set of questions. This prevents unbounded research.

Example — user says: "What would break if we split collector.py?"

Questions:
1. What are the public functions/classes in collector.py that other files import?
2. Which files import from collector.py, and what do they use?
3. What internal cross-references exist within collector.py (function A calls function B)?
4. Are there any global state or module-level side effects?
5. What tests cover collector.py, and would they need to change?

**Rules:**
- Maximum **7 questions** per discovery. If more are needed, the scope is too
  broad — split into multiple discoveries or narrow the goal.
- Questions must be **answerable by reading code**. If a question requires
  running the app, making API calls, or user input, flag it as out-of-scope.
- Questions must be **specific**. "How does the app work?" is not a question.
  "What is the request lifecycle for GET /api/dashboard?" is.

Present the question list before proceeding. If the goal is ambiguous, derive
the best question list you can — do not ask the user to clarify.

### Phase 2: Research

Answer each question by reading the codebase. Use the appropriate tools:

| Need | Tool |
|------|------|
| Find files by pattern | Glob |
| Search for usage/references | Grep |
| Read file contents | Read |
| Count lines, run analysis scripts | Bash |
| Parallel deep dives on independent questions | Agent (subagent_type: Explore) |

**Parallelism:** If questions are independent (answering Q1 doesn't inform how
you research Q3), launch parallel Explore agents — one per question or per
question cluster. This is the primary throughput lever.

**Depth control:** Match research depth to the question:
- "Where is X used?" — Grep is sufficient
- "What is the dependency graph of module X?" — needs multi-file Read + analysis
- "Is it feasible to do X?" — needs deep reading + cross-referencing

**Evidence standard:** Every finding must cite at least one specific location
(`file:line`) or command output. No unsupported assertions.

### Phase 3: Synthesize

Compile answers into the structured findings format (see below). This is not
a raw dump of grep results — it is analyzed, organized knowledge.

For each question:
1. **Answer** — direct, concise answer
2. **Evidence** — file paths, line numbers, code snippets that support it
3. **Implications** — what this means for planning/implementation

Then produce cross-cutting analysis:
- **Constraints discovered** — hard limits on what can be done
- **Risks identified** — things that could go wrong
- **Open questions** — things this discovery couldn't answer

### Phase 4: Recommend

Based on the findings, state the recommended next step:

- **Ready to plan:** "Findings support proceeding. Run `$planner <goal>`
  (or `$planner --mode refactor <goal>` for refactors) with this document as input."
- **Needs more discovery:** "Questions X and Y remain open. Run
  `$discover <narrower question>` next."
- **Not feasible:** "Findings indicate X is not viable because [reason].
  Consider alternative approach Y."
- **Trivial:** "This doesn't need a multi-agent campaign. The change is
  small enough to do directly."

### Phase 5: Write the Findings Document

Write the output to `docs/discovery-{name}.md` using the format below.

Derive `{name}` as a short kebab-case slug (2-4 words), not the full goal text.
Example: goal "What would break if we split collector.py?" → `discovery-collector-split-impact.md`.

---

## Findings Document Format

```markdown
# Discovery — {Title}

**Goal:** {Original user request}
**Date:** {ISO date}
**Status:** complete | partial (if open questions remain)
**Recommended next:** {which skill to run next, or "none — standalone research"}

---

## Questions

1. {Question 1}
2. {Question 2}
...

---

## Findings

### Q1: {Question text}

**Answer:** {Direct answer}

**Evidence:**
- `file.py:42` — {what this line shows}
- `other_file.py:100-115` — {what this block shows}

**Implications:**
- {What this means for planning}

### Q2: {Question text}

...repeat for each question...

---

## Cross-Cutting Analysis

### Constraints
- {Hard limit 1 — e.g., "collector.py has 47 internal cross-refs; splitting
  requires updating all of them"}
- {Hard limit 2}

### Risks
| Risk | Likelihood | Impact | Notes |
|------|-----------|--------|-------|
| {risk 1} | {L/M/H} | {L/M/H} | {detail} |

### Open Questions
- {Question that couldn't be answered, with reason}

If none: "All questions answered."

---

## Recommendation

{One of the four recommendation types from Phase 4, with specific next command}

---

## Appendix (optional)

{Raw data tables, full grep outputs, or diagrams that support the findings
but are too verbose for the main sections}
```

---

## Discovery Types

Common research patterns and how to approach them:

### Dependency Map
**Questions:** What imports what? What are the entry points? Where are the
circular dependencies?
**Method:** Grep for imports, build adjacency list, identify cycles.
**Output emphasis:** Dependency graph, coupling metrics, bottleneck files.

### Impact Analysis
**Questions:** What would change if we modify X? What depends on X? What
tests cover X?
**Method:** Grep for all references to X, trace callers, map test coverage.
**Output emphasis:** Blast radius table, test gap list, breaking changes.

### Feasibility Assessment
**Questions:** Can we do X? What are the prerequisites? What are the blockers?
**Method:** Read relevant code deeply, check for hard constraints (e.g., library
limitations, schema locks, performance bounds).
**Output emphasis:** Go/no-go with evidence, prerequisite list, alternative approaches.

### Pattern Inventory
**Questions:** Where is pattern X used? How consistently? What are the variants?
**Method:** Grep for pattern, read each instance, classify variants.
**Output emphasis:** Instance table with file:line, variant taxonomy, normalization path.

### Gap Analysis
**Questions:** What's missing before we can do X? Where are the coverage holes?
**Method:** Compare current state against target requirements, identify deltas.
**Output emphasis:** Gap table (have/need/delta), priority ranking, effort estimates.

### Surface Mapping
**Questions:** What are all the public APIs / endpoints / entry points / config
options for module X?
**Method:** Grep for decorators, exported functions, route definitions, env vars.
**Output emphasis:** Complete inventory table with signatures and locations.

---

## Scope Bounding

Discovery without bounds is unbounded research. Enforce these limits:

- **Max 7 questions** per invocation. Split if more are needed.
- **Max 3 parallel agents** for research. More adds coordination overhead
  without proportional insight.
- **Every finding needs evidence.** If you can't cite a file:line, the finding
  is speculation — flag it as such or drop it.
- **Time-box depth.** If a question requires reading > 20 files to answer,
  it's too broad. Narrow it or split it.
- **No implementation.** Discovery reads code. It does not write, edit, or
  refactor anything except the findings document itself.

---

## Consumption by Planners

When a planner reads a discovery document, it should use:

| Findings Section | Planner Use |
|-----------------|-------------|
| Constraints | Hard inputs to decomposition — things that limit agent scope |
| Risks | Feeds directly into plan element #11 (Risk Assessment) |
| Dependency/impact data | Informs file ownership map and conflict zone analysis |
| Open questions | May trigger another `$discover` before planning proceeds |
| Recommendation | Determines which planner to invoke and with what framing |

The findings document path should be passed to the planner as context:

```
$planner Add WebSocket push (see docs/discovery-websocket-feasibility.md)
$planner --mode refactor Extract storage layer (see docs/discovery-collector-deps.md)
```

---

## Optimization Discovery

When the user wants to evaluate optimization opportunities (performance, dead
code, dependencies, build time, complexity), use this structured approach.

### Optimization Themes

Prioritize findings by these categories:

1. **Hot-path waste:** redundant I/O, duplicate network calls, repeated parsing,
   unnecessary allocations, oversized loops
2. **Structural drag:** dead code, duplicate helpers, over-coupled modules,
   oversized files, confusing ownership
3. **Build/test drag:** redundant steps, over-broad test scope, avoidable
   rebuilds, slow package graph edges
4. **Dependency drag:** unused packages, overlapping libraries, adapters that
   can be collapsed safely
5. **Verification drag:** missing regression coverage around the code being
   optimized

### Optimization Register

Add this section to the findings document when doing optimization discovery:

```markdown
## Optimization Register

| Candidate | Type | Evidence | Risk | Confidence | Decision |
|-----------|------|----------|------|------------|----------|
| ... | hot-path/structural/build/dependency | file:line | low/medium/high | low/medium/high | implement-now / suggest-only / defer |

## Baseline

- Metric: ...
- Current value: ...
- How measured: ...
```

The register must separate:
- requested optimization work
- additional low-risk improvements discovered during research
- deferred ideas that are useful but too risky or broad for this run

### Verification Gate

Before recommending implementation of any optimization, confirm:

- every selected optimization has evidence in the findings
- at least one usable verification path exists
- the baseline is recorded (or the lack of a quantitative baseline is explicit)
- file ownership can be split without concurrent writers
- selected scope fits 2-6 agents

If the gate fails, report findings but mark implementation as blocked.
