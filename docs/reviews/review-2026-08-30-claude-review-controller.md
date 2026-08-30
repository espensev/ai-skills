# Review - Claude Review Controller

**Date:** 2026-08-30

**Surface:** installed and repo-local Claude `review-controller` workflow

**Decision supported:** retain the Claude design and build a provider-native
Codex counterpart

**Verdict:** PASS WITH CHANGES as a machine-local Claude workflow; FAIL as a
portable package. Its controller/worker split, bounded lenses, evidence IDs,
return gates, and reconciliation registry are strong. The evidence set is not
mechanically frozen, not every accepted claim is verified, and the repo copy is
not wired into the Claude package.

## Findings

### High

- [axis: evidence integrity] `claude-skills/skills/review-controller/SKILL.md:36`
  calls paths and URLs "frozen" evidence, but no content hashes are recorded.
  Lines 63-66 allow a URL itself to remain an E-id, and there is no freshness
  check before Wave 2 or final judgement. A file or live URL can change between
  mapping, inspection, verification, and reporting while every citation still
  appears valid. Capture volatile sources, hash every E-id, and recheck the full
  fingerprint before accepting returns and writing the report.

- [axis: package readiness] The repo copy under
  `claude-skills/skills/review-controller/` is tracked in commit `2d27dd3`, but
  `claude-skills/package/install-manifest.json` does not list it. The skill also
  requires a separately copied worker at lines 16-19 even though its installer
  does not manage agent files. Installed skill and worker copies are
  byte-identical to the repo copies, so the live workflow is aligned, but a
  clean package install cannot reproduce it. Its concurrent Claude owner must
  decide how to package both artifacts; this Codex task must not assume that
  ownership.

### Medium

- [axis: claim verification]
  `claude-skills/skills/review-controller/SKILL.md:89-97` independently confirms
  only Critical/High and disputed claims. Citation gates do not establish that
  accepted Medium or Low claims are true. The controller should directly check
  every accepted finding and every accepted no-issue coverage claim, using a
  second worker only where direct verification is insufficient or independent
  falsification is decision-critical.

- [axis: execution portability]
  `claude-skills/skills/review-controller/SKILL.md:12-19,32-35,50-58` fixes all
  specialists to Opus/high and permits four agents per wave without discovering
  available capacity. Its fallback changes agent type but keeps the model and
  slot assumptions. The Codex counterpart should be model-neutral, use two
  workers by default, cap at three when a distinct lens and capacity justify
  it, and run the same packets sequentially if parallel launch is unavailable.

- [axis: synthesis bias]
  `claude-skills/skills/review-controller/SKILL.md:74-77,221-235` makes the
  controller predict and publish three findings, then judges a wave by matches.
  Agreement is not evidence, and this can anchor synthesis. Keep pre-wave risks
  private and judge delegation by evidence quality and added coverage.

- [axis: safety enforcement]
  `claude-skills/skills/review-controller/agent-definitions/review-specialist.md:5`
  grants Bash and WebFetch while lines 57-63 impose read-only behavior only in
  prose. Prefer controller-captured evidence, omit mutation-capable tools where
  the runtime supports it, and verify source/repo state after each wave.

### Low

- [axis: report contract] `claude-skills/skills/review-controller/SKILL.md:188-208`
  puts executive assessment before findings. That suits a product stakeholder
  report but conflicts with this repository's findings-first convention. The
  Codex counterpart should lead with findings, then give the leader judgement.

## Strengths To Retain

- The controller owns framing, mapping, reconciliation, judgement, and report;
  specialists do bounded inspection.
- One role, one question, explicit evidence, exclusions, stop conditions, and
  a fixed return shape make worker packets auditable.
- Journey, usability, information architecture, functional, risk/edge-case,
  accessibility, verification, and adversarial lenses fit product review while
  explicitly excluding branch/PR review.
- Findings require an affected user or system, consequence, evidence pointer,
  severity, confidence, recommendation, and validation step.
- The registry merges duplicates and resolves conflict by evidence, not vote.
- Wave 2 is conditional and claim-specific; small/tightly coupled inputs stay
  solo.

## Codex Counterpart Specification

### Routing and scope

- Add optional Codex skill `review-controller` for an explicitly led,
  multi-lens review of a product, feature, system, flow, journey, or screens.
- Route branch/PR/diff/document merge review to `review`, generic subagents to
  `parallel-agents-light`, broad audit/remediation gates to
  `audit-gated-subagents`, implementation campaigns to `manager`, and QA,
  performance, security, or known-regression work to their dedicated skills.
- Do not trigger on a code symbol named `ReviewController`.
- Product/source edits, worker writes, external posts, install, deploy, and live
  mutations are out of scope. Only the controller writes
  `docs/reviews/review-controller-{date}-{slug}.md`; task-specific scratch notes
  may be disposable.

### Evidence and controller authority

- The controller frames the decision, users, journey, boundaries, evidence,
  focus areas, lanes, gates, and output before delegation.
- Capture volatile evidence first. Each E-id records a stable location, type,
  byte length where applicable, and SHA-256 or equally immutable content ID. A
  changing URL alone is not frozen evidence.
- Recompute the E-id fingerprint before reconciliation and before the report.
  If changed, reject stale returns and rerun affected lanes on one state.
- The controller maps the whole journey before selecting lenses and keeps any
  risk hypotheses private. They guide coverage, not truth scoring.
- Only the controller accepts, rejects, merges, reclassifies, verifies, judges,
  and writes the final report.

### Native Codex subagents

- Use two read-only Codex subagents by default; use three only when a distinct
  lens adds coverage and exposed capacity allows it. Never pin a model or
  assume fixed slots.
- Launch ready lanes together. If launch/capacity is unavailable, run the same
  packets sequentially and report the fallback.
- Each packet carries one role/question, minimal journey context, include and
  exclude scope, frozen E-id manifest, lens criteria, return shape, and stops.
- Workers inspect assigned evidence, never write or spawn descendants, and
  return no more than eight evidence-pointed findings plus coverage/open items.
- Allow one optional second wave only for dispute, material coverage gap, or
  independent falsification of a decision-critical claim. Never ask it to
  review everything again or reveal a preferred answer.

### Verification and report gate

- Gate returns for scope, shape, evidence identity, affected user/system,
  consequence, confidence, and actionable validation.
- The controller checks every accepted finding and every accepted no-issue
  coverage claim regardless of severity. Agreement is not verification;
  low-confidence claims stay open.
- Merge duplicates by claim/evidence, isolate disagreement, and resolve with
  stronger evidence or a direct test, never votes.
- Lead the report with findings, followed by leader judgement, scope/method,
  system assessment, themes, action plan, open questions, evidence limits,
  roster, and fallbacks.
- Completion requires a matching final fingerprint, coverage/exclusion for each
  focus area, controller verification of all accepted claims, no unresolved
  blocking conflict, no worker mutation, and a durable report.

### Package and validation surface

- Create `codex-skills/skills/review-controller/SKILL.md`, its
  `agents/openai.yaml`, and
  `codex-skills/tests/test_review_controller_skill.py`.
- Wire the Codex optional manifest, both Codex README install examples, root
  catalog/counts, and all three eval fixtures:
  `codex-skills/eval/cases/light-skill-cases.json`,
  `codex-skills/eval/responses.template.json`, and
  `codex-skills/eval/responses.mock.json`. The positive case must route a
  product/flow/journey review to `review-controller`; the negative case must
  route branch/PR/diff review to `review`.
- The same-name Claude and Codex implementations remain provider-owned. Add
  `review-controller` to `provider_owned_shared_skills` and
  `declared_provider_forks` in `skills-src/manifest.json`; the reason must name
  their shared product-review scope and Claude Agent versus Codex native
  collaboration binding. Update root README provider-fork documentation.
- Do not add it to `generated_skills`, edit/package the concurrently owned
  Claude files, or change the Claude manifest.
- Tests must prove product/flow routing, branch/diff exclusion, evidence hashes
  and stale rejection, verification of every accepted claim, model-neutral
  bounded agents with sequential fallback, report ownership, and no
  implementation/live mutation.
- Validation must run the focused test, mock eval scoring, provider generation,
  provider parity, README/manifest count checks, strict package validation,
  and `git diff --check`. Strict validation may fail only on the exactly seven
  externally owned Claude directories already recorded below; any other failure
  is a blocker.

Exact commands:

```powershell
python -m pytest codex-skills/tests/test_review_controller_skill.py -q
$tempEval = Join-Path $env:TEMP 'review-controller-eval.json'
python codex-skills/scripts/eval_skills.py --cases eval/cases/light-skill-cases.json --responses eval/responses.mock.json --out $tempEval
.\scripts\Build-ProviderSkillPackages.ps1 -Check
.\scripts\Compare-ProviderSkillParity.ps1 -FailOnUndeclaredFork
.\scripts\Update-ReadmePackageCounts.ps1 -Check
.\scripts\Test-ReadyPackages.ps1 -StrictSkillManifest -SkipExportSmoke -SkipInstallerSmoke
git diff --check
```

## Live, Source, And Ownership State

- Repo-local Claude skill/worker hashes match both
  `C:\Users\Sev\.claude\...` and `D:\DevHome\state\claude\...` copies.
- Strict package validation reports seven concurrently unmanifested Claude
  directories: `cc-workflow-builder`, `chief-operator`, `codebase-design`,
  `docs-clean`, `resolving-merge-conflicts`, `review-controller`, and `verify`.
  This task owns none of them, so release readiness remains externally blocked.
- An independent critic rejected the first Codex draft because it implemented
  Git/code review and its passing tests encoded the same wrong domain. The
  replacement now implements the product-review contract; the obsolete green
  results remain invalidated.
- No runtime installation, Claude edit, external post, deployment, or product
  change is authorized.

## Verification Performed During Audit

- Read the complete Claude skill, worker definition, and examples.
- Compared SHA-256 hashes across repo, user-profile runtime, and DevHome runtime;
  both skill and worker match.
- Recovered three OneDrive conflict copies into canonical Codex paths only after
  their hashes matched the previously tested artifacts; no conflict copies
  remain.
- Passed 28 focused/contract tests and the full Codex suite: 722 tests plus five
  subtests.
- Both routing evals passed at 5/5. Ruff, provider generation, declared-fork
  parity, README/manifest counts, and diff whitespace checks passed.
- Non-strict ready-package validation plus export/install smoke passed and
  exported the Codex skill byte-identically. Strict validation failed only on
  the seven unmanifested Claude directories above.
- Ran one bounded tools-disabled Claude probe earlier; it stopped at its USD
  budget and established no behavior. No further paid or mutating probe ran.
- Independent implementation review confirmed the replacement contract and
  found only stale pre-commit wording in this report; that wording is corrected.
