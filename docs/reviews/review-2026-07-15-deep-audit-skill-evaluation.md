# Deep Audit Skill Evaluation

- **Date:** 2026-07-15
- **Donor material:** `Deep-Audit/Deep_Code_Audit_Prompt_Kit/`
- **Target skill:** `deep-audit`
- **Providers:** Claude and Codex
- **Status:** refined, release validation passed, installed to Claude and Codex

## 2026-08-09 follow-up

The current-use audit restored the reset package wiring, retired the missing
Antigravity release surface, and added `skill-authoring` to both ready packages.
The current manifests contain 36 Codex and 23 Claude skills. Deterministic evals
now pass 39/39 for Codex and 22/22 for Claude; Claude's obsolete
`observer-test`, `refactor-planner`, and `worktree-manager` cases were removed.

## Verdict

The donor is a strong runtime-audit prompt kit, but it was not an Agent Skill:
it had no `SKILL.md`, discovery frontmatter, install-manifest entry, provider
package, or trigger evals. Its core method is worth preserving. The refined
package is deliberately narrower than a generic "audit": it investigates
runtime efficiency, amplification, and lifecycle behavior and remains read-only
toward product code unless remediation is separately requested.

## Strong material preserved

- frequency x cardinality x work x amplification x duration cost model
- `FACT`, `INFERENCE`, `HYPOTHESIS`, and `MEASUREMENT REQUIRED` labels
- progressive D/T/F/M/R identifiers and Depth 0-5 ladder
- upstream/downstream execution tracing instead of file-shape review
- adversarial verification and focused measurement packets
- revision-aware resume and honest interim reporting
- timer-overlap depth test that finds an upstream multiplier before optimizing a
  local file read

## Gaps found and refinements made

| Gap in donor kit | Refined contract |
|---|---|
| Manual copy/paste prompts; no skill metadata | Discoverable `deep-audit` `SKILL.md` in both provider packages |
| Bare `#discover`, `#verify`, and similar pseudo-commands | Provider-neutral modes under one skill: discover, trace, audit, deepen, verify, profile, resume, report |
| Conditional write permission conflicted with unconditional state updates | Product code is read-only by default; audit state is conditional; otherwise return the same delta in the response |
| Profiling could execute without a sufficient safety boundary | Plan-first measurement gate; no production load, fault injection, restart, privileged diagnostics, paid workload, or persistent instrumentation without explicit authority |
| No durable trace or verification evidence | `TRACES.md` plus `VERIFICATIONS.md` and stable `T-###`/`V-###` records |
| Parallel/resumed ID allocation could collide | Controller-only state writer and ID allocator; investigators return provisional evidence packets |
| One `.audit/` namespace could collide across audits | `.audit/deep-audit/<audit-slug>/` with schema, repo identity, scope, permissions, and drift fingerprint |
| Resume considered revision but not dirty/untracked changes or source/runtime boundaries | PASS 0 records branch/worktree, dirty fingerprint, authority files, source/runtime boundary, workload, environment, and invalidated records |
| Status, severity, and discovery priority were easy to inflate | Explicit P0-P3 urgency, operational severity, confidence separation, and `Confirmed` measurement/deterministic-proof requirement |
| Generic name overlapped review, discovery, debugging, orchestration, and security | Trigger description and router direct PR diffs to `review`, concrete regressions to `diagnosing-bugs`, bounded research to `discover`, tests to `qa`, security elsewhere, and gated remediation to orchestration |
| Fixed candidate counts could create filler | Zero or more evidence-backed discoveries, normally capped at 12 |
| Finding provenance was implicit | Source revision, exact evidence citations, assumptions, counter-evidence, and unresolved runtime edges are required fields |

## Trigger evaluation matrix

| Prompt shape | Expected primary skill |
|---|---|
| Deep runtime audit of hot paths, memory, I/O, timers, queues, retries, cancellation, and shutdown | `deep-audit` |
| Trace one scheduler from registration through concrete I/O and quantify frequency/cardinality/overlap | `deep-audit` |
| Resume saved audit state, detect drift, and verify a stale finding | `deep-audit` |
| Design a bounded queue-depth/age measurement with thresholds and confounders | `deep-audit` |
| Audit a PR diff against main for merge blockers or regression risk | `review` |
| Map dependencies/feasibility before planning a refactor | `discover` |
| Reproduce and fix a slowdown introduced by a known commit | `diagnosing-bugs` |
| Run tests, coverage, and failure triage | `qa` |
| Audit auth bypass, injection, secrets, or dependency vulnerabilities | security-specific workflow, not `deep-audit` alone |
| Coordinate parallel lanes, approval gates, implementation, and remediation | orchestration primary; `deep-audit` may supply runtime methodology |

The deterministic light-eval suites include three positive cases (new audit,
drift-aware resume, safe profile plan) and four paired boundary cases (`review`,
`diagnosing-bugs`, `discover`, and `manager`). Durable state creation is not
required unless the prompt explicitly authorizes it.

## Package shape

```text
skills/deep-audit/
  SKILL.md
  references/
    mode-contracts.md
    state-and-report-contracts.md
  examples/
    depth-test.md
```

The donor DOCX/ZIP, duplicate master prompt, combined paste prompt, and empty
top-level Markdown artifacts remain unmodified source material and are not part
of either installed skill payload.

## Acceptance gates

- Claude and Codex share the same skill body, references, and example; Claude
  adds provider-native invocation metadata.
- Both manifests list `deep-audit` as optional and package counts match.
- Both docs-contract suites pass.
- All eval case, mock, and template ID sets match and deterministic mock scoring
  has no failures.
- Focused installer smoke copies the complete skill, including references and
  example, to clean Claude and Codex roots.
- Installed roots match package source after synchronization.
- Full ready-package validation is reported separately if unrelated ready
  packages are missing from the current worktree.

## Validation result

- Codex docs contract: `9 passed`
- Claude docs contract: `10 passed`
- Codex deterministic light eval: `38/38` passed, including 3 Deep Audit and 4
  overlap-boundary cases
- Claude deterministic light eval: `26/26` passed, including the same 7 cases
- Provider parity: 1 description variant and 2 provider payload variants; the
  shared body and three support files match, while Claude adds `argument-hint`
  and `user-invocable`
- Clean-root installer smoke: all 4 files copied with matching hashes for both
  providers
- Live roots: all 4 files match source under both
  `D:\DevHome\state\codex\skills\deep-audit` and
  `D:\DevHome\state\claude\skills\deep-audit`; the user-profile paths expose
  the same files through their junctions
- Scoped diff/hygiene: no whitespace errors, missing local links, provider-path
  leakage, temporary flags, or obvious credential patterns

At an intermediate 2026-08-09 reconciliation checkpoint, before
`skill-authoring` was added to Claude, the release contained 36 Codex and 22
Claude skills (58 total). Antigravity had been retired from the ready manifest
after its intentional source deletion. That point-in-time count and live-root
comparison are superseded by the follow-up at the top of this review; they are
not claims about the current installed projections.

The hands-on Claude behavior benchmark is intentionally deferred and specified
in [the evaluation plan](../plans/2026-07-15-deep-audit-claude-evaluation-plan.md).
