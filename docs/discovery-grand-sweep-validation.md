# Discovery — Grand Sweep Validation

**Goal:** Continue improving and validating the grand-sweep workflow.
**Date:** 2026-10-01
**Status:** Partial: local engine documentation is available; live workflow tools are not exposed in this session.
**Recommended next:** Direct source-only checker regression fix and documented engine-contract refinements.

## Questions

1. Where is the selected local ZCode workflow contract, and what recovery guarantees does it describe?
2. Which checks can validate source-only grand-sweep without pretending it is portable or executing a campaign?

## Findings

### Q1: Installed engine contract

The installed distribution contains `C:/Program Files/ZCode/resources/glm/packages/bundled-skills/skills/dynamic-workflows/{SKILL.md,patterns.md,examples.md}`. The executable's ProductVersion and FileVersion are `3.14.4.7912`; its installed companion SKILL.md has SHA256 `370E8B89C4FAE16ED306E5564372C8C1C8CDEAC021011BE174DC25A9F38AA722`. This identifies the inspected documentation; it does not prove runtime tool availability.

Evidence in the installed companion:

- `SKILL.md:761`–`:775`: errored runs cannot resume; amend their script. Stopped runs can resume unless superseded. User-stopped runs require the user's request; provider stops require resolving the cause. An amendment's successor is the live run.
- `SKILL.md:787`–`:802`: amendment starts a successor and imports finished work by stable subagent names and byte-identical ask sequences. The first live workspace write or live `world.run` invalidates workspace-dependent cached reads/asks; editing ask instructions forces that ask live.
- `SKILL.md:1324`–`:1326`: resumed `world.run` calls replay journaled outputs. Resume is crash recovery, not fresh verification.
- `SKILL.md:779`–`:783`: transient provider failures are retried internally without a limit. A campaign's script-level retry allowance must not be described as an engine retry cap.
- `SKILL.md:755`–`:759`: `TaskOutput` waits for runs started by the session; `GetWorkflowRun` is a snapshot, including runs owned elsewhere.
- `SKILL.md:115`, `:955` and `:960`: subagent models are run-wide; model/concurrency overrides require the user's requested settings. Separate authorized model tiers need separate linked runs.
- `SKILL.md:932`, `:997`–`:1004` and installed `zcode.cjs:124`: Create/Amend expose no token/time/provider-retry ceiling, and `ask(instructions)` has no token or timeout option. Script dispatch limits cannot cap a pending ask. `TaskStop` is a documented controller stop primitive; token/time ceilings remain advisory without a verified external enforcer.

The installed implementation at `C:/Program Files/ZCode/resources/glm/zcode.cjs:124` declares `GetWorkflowRun` fields including `usage.spentTokens`, actor token counts and `subagentsTruncated`. Its `toGetWorkflowRunSubagents` function at `:14453` truncates the returned actor list to 64. Campaigns with more actors cannot obtain complete tier totals by blindly summing that snapshot.

The cached guide under `D:/DevHome/state/zcode/cli/plugins/cache/zcode-plugins-official/zcode-guide/0.2.0/` also contains the companion; the installed bundled source provides the relevant local contract. The current session's callable tools contain no ZCode workflow tools. No ZCode process, provider connection or campaign was started.

### Q2: Source-only checker boundary

Before this continuation, `scripts/Test-ReadyPackages.ps1:396`–`:423` validated frontmatter, local support references and portable script/command requirements only for default/optional skills. Original lines `:430`–`:442` counted source-only directories and checked their presence. Consequently a source-only directory without valid SKILL.md metadata could pass.

Reuse `Test-RequiredPath` (`:44`), `Test-SkillDescription` (`:96`) and `Test-SkillSupportReferences` (`:122`) in a separate source-only loop. Keep portable `Test-SkillScriptReferences` (`:150`) and `Test-SkillCommandReferences` (`:199`) installable-only. Keep shipping and source-only counts separate and retain the manifest overlap guard at `:400`.

The repository already uses synthetic copied-script Pester fixtures in `scripts/tests/Compare-AgentSkillRoots.Tests.ps1:1`. A copied checker computes its own repository root, so fixtures need no production test seam. Child PowerShell processes capture checker exit status safely; smoke flags prevent fixture exports or installation.

## Constraints And Verification Scope

- Preserve provider-owned/source-only classification, README selection and manifests.
- Change only checker source, a focused synthetic-fixture test and workflow/review documentation.
- Regression tests must demonstrate missing metadata failures before the fix, positive external-dependency behavior after it, and preservation of existing overlap/portable-command checks.
- Installed schemas and documentation are source evidence. Compilation, launch, live retries and recovery behavior remain unverified without callable engine tools.

## Recommendation

Proceed with the narrow checker fix and make the recovery/accounting rules reflect the installed contract. Keep live campaign validation as a separately identified limitation; do not substitute a mock engine or launch another backend.

## Implementation Evidence

- Added a separate eight-line source-only metadata/support loop to `scripts/Test-ReadyPackages.ps1:425` without adding source-only skills to the shipping list.
- Added `scripts/tests/Test-ReadyPackages.SourceOnly.Tests.ps1`, using fresh fixtures and native checker processes. Builder evidence: before the fix, eight new negative cases failed while five existing-boundary cases passed; after the fix, all 13 cases passed. Independent verification is recorded in the review report.
- Stronger checking exposed missing discovery triggers in `claude-skills/skills/cc-workflow-builder/SKILL.md:3` and `claude-skills/skills/verify/SKILL.md:3`. Corrected only those descriptions; source-only selection and behavior were preserved.
- Refined grand-sweep preflight, recovery, limits and accounting using the installed contract. No applications, live workflows or external stop controller were run.
