# Review - CC Workflow Merge Fit

**Date:** 2026-07-08
**Surface:** Source review of the operator-gated CC Workflow material, the SQ-Control workflow packet, and existing run-observer contract against the Codex skill package.
**Spec source:** User request: review the team workflow and suggest whether it can merge into the Codex workflow. Follow-up clarified the primary target as the chief/operator-style workflow.
**Standards sources:** `README.md`, `codex-skills/AGENTS.md`, `codex-skills/skills/planner/SKILL.md`, `codex-skills/skills/manager/SKILL.md`, `codex-skills/skills/parallel-agents-light/SKILL.md`
**Verdict:** PASS WITH NOTES
**Adaptation result:** Ported the archived local `audit-gated-subagents` skill into the Codex package as an optional skill.

## Findings

### High

- None.

### Medium

- [axis: spec] `cc-workflow/workflows/sq-control-final-fan-control-2026-07-01/sq-control-real-logging-restore-2026-07-01.workflow.json:29` - The strongest reusable idea is the operator-as-final-authority pattern, not the domain-specific SQ-Control content.
  Evidence: The workflow says agents collect evidence and recommend pass/block, while the operator chooses every gate decision and final handoff; manual gates then require operator choices before restore edits, tests, log-shot collection, and pass-marker authorization (`sq-control-real-logging-restore-2026-07-01.workflow.json:80`, `:146`, `:195`, `:227`, `:289`). Codex light-parallel guidance already keeps live hardware, production, and operator-owned actions with the controller (`codex-skills/skills/parallel-agents-light/SKILL.md:62`).
  Impact: This is directly mergeable into Codex operating behavior as a durable rule for high-risk flows: helpers may prepare evidence and recommendations, but only the controller/operator may approve irreversible gates, pass markers, live actions, and final handoff.
  Recommendation: Extract an optional `chief-operator` or `operator-gates` guidance section/skill for Codex that formalizes this split: agents gather/verify/report, controller/operator authorizes gate transitions.
  Status: Implemented as `codex-skills/skills/audit-gated-subagents/SKILL.md`, preserving the archived source skill name while adding explicit chief/operator gate language.

- [axis: spec] `cc-workflow/workflows/sq-control-final-fan-control-2026-07-01/plan.md:38` - The SQ-Control workflow packet should not be merged directly into the Codex skill package.
  Evidence: The packet is explicitly three SQ-Control workflows (`Workflow A`, `Workflow B`, `Workflow C`) with SQ-specific live-control boundaries and markers (`SQ-A-REAL-LOGGING-SHOT-PASSED`, `SQ-B-WRITE-READINESS-PASSED`, `SQ-C-FAN-MODE-CONTROL-PASSED`). The plan also forbids agents from setting `writes_enabled=true` and reserves HIL/live actions for the operator (`plan.md:12`, `plan.md:277`, `plan.md:284`).
  Impact: Directly importing it into Codex defaults would mix a domain-specific HIL control packet into portable workflow guidance and could imply live-control behavior that belongs only in SQ-Control.
  Recommendation: Keep the SQ-Control JSON workflows as worked examples under `cc-workflow/workflows/`. Extract only the reusable pattern: explicit entry locks, evidence-backed sub-agent steps, human-held gates, terminal pass/manual/blocked end states, and no hidden live mutation.

- [axis: standards] `cc-workflow/cc-wf-studio/docs/cc-workflow-builder/SKILL.md:8` - `cc-workflow-builder` is useful, but not ready to manifest-list as a Codex skill without adaptation.
  Evidence: The file labels itself a draft skill seed and says to install under `~/.claude/skills/...`; the repo shipping surface is manifest-driven (`README.md:8-10`) and imported/source-only material stays out of ready exports unless manifest-listed (`README.md:22-25`). The builder also depends on CC Workflow Studio MCP methods and an open editor (`cc-workflow-studio-reference.md:19`, `cc-workflow-studio-reference.md:21`).
  Impact: A direct copy into `codex-skills/skills/` would create a provider/path mismatch and a brittle dependency on a local Studio runtime.
  Recommendation: Promote it first as a source-only or optional Codex skill candidate after rewriting the trigger, removing Claude install wording, adding Codex/tool availability fallback behavior, and packaging `cc-workflow-studio-reference.md` plus `workflow-authoring-playbook.md` as supporting files.

- [axis: regression] `cc-workflow/cc-wf-studio/docs/cc-workflow-builder/cc-workflow-studio-reference.md:95` - The Studio workflow is a definition, not an executor, so it should not replace Codex manager/planner execution flow.
  Evidence: The reference says there is no run/execute MCP tool and an agent must execute each node; Codex already separates planning from execution through `planner` and `manager`, with manager owning worktrees, merge, and verification (`codex-skills/skills/manager/SKILL.md:38`, `codex-skills/skills/manager/SKILL.md:301`, `codex-skills/skills/manager/SKILL.md:613`).
  Impact: Treating the Studio canvas as the runner would bypass Codex's existing task-manager state, worktree isolation, merge handling, and verification gates.
  Recommendation: Merge the Studio model as a visualization/authoring aid and runner discipline, not as a replacement for `planner`/`manager`.

### Low

- [axis: spec] `cc-workflow/cc-wf-studio/docs/run-observer-contract.md:1` - The run observer contract already exists; the remaining Codex merge work is producer guidance, not a new contract.
  Evidence: The contract defines JSONL shape and producer rules (`run-observer-contract.md:12`, `run-observer-contract.md:46`), the core package publishes the schema (`workflow-run-event.schema.json:3`), the core parser normalizes JSONL events (`workflow-run-event.ts:178`), and the CLI preview command consumes `--run-events` (`packages/cli/src/commands/preview.ts:117`).
  Impact: This would give Codex visible progress and reusable workflow replay without coupling the core agent workflow to Studio internals.
  Recommendation: Teach Codex long-running/multi-agent flows to emit `start` / `finish` / `branch` / `error` / `note` events to this existing JSONL shape when a workflow file or run observer path is present.

## What To Merge Into Codex

Merge the following ideas:

- Chief/operator authority split: agents gather evidence, run checks, and recommend; controller/operator authorizes gate transitions, markers, live actions, and final handoff.
- Evidence-gated workflow nodes: every phase should have a concrete artifact, command output, or tracked note before a gate can pass.
- Human-held gates for live, destructive, deploy, or HIL actions.
- Terminal states that distinguish passed, manual pause, and blocked instead of treating every stop as failure.
- One-run scope: define what one workflow run means, then repeat externally rather than modeling canvas loops.
- Run events: append JSONL progress records so long-running workflows can be reviewed after the fact.

Do not merge directly:

- The SQ-Control packet as a default Codex skill.
- Claude-specific install paths from the draft builder skill.
- Studio-only execution assumptions, especially anything that implies a canvas can run itself.

## Suggested Merge Shape

1. Add a small Codex guidance surface for chief/operator gates, either as an optional `operator-gates` skill or as a section in `parallel-agents-light` / `manager`.
2. Wire that guidance to the existing run-observer contract so gate transitions can emit JSONL evidence events.
3. Create or adapt a Codex optional skill named `cc-workflow-builder` only after provider cleanup.
4. Keep the two reference files as progressive-disclosure support files.
5. Keep `lane-pipeline` and the SQ-Control packet as source-only examples, not default Codex behavior.

## Verification

- `node .\cc-workflow\cc-wf-studio\packages\cli\dist\cli.js validate cc-workflow\workflows\sq-control-final-fan-control-2026-07-01\sq-control-real-logging-restore-2026-07-01.workflow.json` - pass
- `node .\cc-workflow\cc-wf-studio\packages\cli\dist\cli.js validate cc-workflow\workflows\sq-control-final-fan-control-2026-07-01\sq-control-write-readiness-2026-07-01.workflow.json` - pass
- `node .\cc-workflow\cc-wf-studio\packages\cli\dist\cli.js validate cc-workflow\workflows\sq-control-final-fan-control-2026-07-01\sq-control-fan-mode-control-2026-07-01.workflow.json` - pass
- `rg -uuu -n "chief-operator|chief operator|chief_operator|Chief Operator|chief" .` - no literal chief-operator artifact found in this workspace; one transient `.antigravitycli` missing-file warning was reported by `rg`.
- `git grep -n -i "chief" $(git rev-list --all)` - no historical tracked `chief` hit.
- Found archived source skill: `D:\DevHome\state\codex\archived-skills\20260706-lean-default-first-pass\disabled-local-only\audit-gated-subagents\SKILL.md`.
- `python -m pytest tests\test_skill_docs_contract.py -q` from `codex-skills` - pass, 9 passed.
- `python -m json.tool package\install-manifest.json > $null` from `codex-skills` - pass.
- `git diff --check -- README.md codex-skills\README.md codex-skills\package\install-manifest.json codex-skills\tests\test_skill_docs_contract.py codex-skills\skills\audit-gated-subagents\SKILL.md codex-skills\skills\audit-gated-subagents\references\pass0-and-gates.md docs\reviews\review-2026-07-08-cc-workflow-merge-fit.md` - pass, with CRLF normalization warnings only.

## Coverage Notes

- Files reviewed deeply: `cc-workflow/cc-wf-studio/docs/run-observer-contract.md`, `cc-workflow/cc-wf-studio/packages/core/src/types/workflow-run-event.ts`, `cc-workflow/cc-wf-studio/packages/core/resources/workflow-run-event.schema.json`, `cc-workflow/cc-wf-studio/docs/cc-workflow-builder/SKILL.md`, `cc-workflow/cc-wf-studio/docs/cc-workflow-builder/README.md`, `cc-workflow/cc-wf-studio/docs/cc-workflow-builder/cc-workflow-studio-reference.md`, `cc-workflow/cc-wf-studio/docs/cc-workflow-builder/workflow-authoring-playbook.md`, `cc-workflow/docs/discovery-cc-workflow-visual-overview.md`, `cc-workflow/workflows/sq-control-final-fan-control-2026-07-01/plan.md`, `codex-skills/skills/planner/SKILL.md`, `codex-skills/skills/manager/SKILL.md`, `codex-skills/skills/parallel-agents-light/SKILL.md`, `codex-skills/package/install-manifest.json`.
- Source skill adapted: `D:\DevHome\state\codex\archived-skills\20260706-lean-default-first-pass\disabled-local-only\audit-gated-subagents\SKILL.md` plus `references/pass0-and-gates.md`.
- Files sampled: the three SQ-Control `.workflow.json` files, using line search plus CLI validation and topology extraction.
- Existing unrelated worktree state: broad deletions under `antigravity-skills/` and `gemini-skills/`, plus untracked `skill-authoring` directories, were present before this review and were not modified.

## Open Questions

- Should `audit-gated-subagents` remain the exported name, or should a future alias skill named `chief-operator` route to it?
- Should the first Codex-side integration be documentation-only, or should `manager` emit JSONL run events for long campaigns?
