# Discovery - Useful Upgrades

**Goal:** Review what is useful in this repo and suggest upgrades.
**Date:** 2026-06-26
**Status:** complete
**Recommended next:** live-verify the Antigravity workflow layout when
Antigravity CLI is available; only reconcile legacy Gemini wrapper drift if the
legacy package is reactivated for a release.

## Implementation Note - 2026-06-26

The first upgrade batch and the Google-provider split have been applied:

- Added `scripts/Test-ReadyPackages.ps1` as a root ready-package validation and export-smoke gate.
- Promoted `diagnosing-bugs` as a portable optional skill across `claude-skills`, `codex-skills`, and `gemini-skills`.
- Added `antigravity-skills` as the active Google-facing ready package with 29 skills and 29 workflows.
- Kept `gemini-skills` as a legacy source package for Gemini CLI enterprise/API-key compatibility.
- Updated package manifests and README counts to 81 install-ready skills: Claude 20, Codex 32, Antigravity 29.
- Left the larger imported Gemini/ECC tree as reference material, not part of the ready-package export.
- Remaining legacy hygiene: the tracked Gemini wrappers `continuous-learning.toml`, `tdd.toml`, and `telemetry-live-ops.toml` still exist outside `package/install-manifest.json`, but they are no longer in the default ready export path.

---

## Questions

1. What are the durable surfaces in this repo: skills, provider packages, scripts, tests, and docs?
2. Which parts look production-useful versus imported, stale, or local-only?
3. What validation already exists for manifests, package contracts, and export?
4. Where are the current upgrade gaps?
5. What upgrade sequence is worth doing next?

---

## Findings

### Q1: What are the durable surfaces in this repo?

**Answer:** The useful product surface is the manifest-driven provider packages plus the export/bootstrap tooling. `wt-cli` is useful, but it is a separate source-only tool rather than part of the skill export.

**Evidence:**
- `README.md:12` - documents 81 install-ready skills across three provider-specific packages.
- `README.md:9-12` - splits the shipped surface into `claude-skills`, `codex-skills`, `gemini-skills`, and the separate `wt-cli` row.
- `README.md:14` - says Gemini's count is the curated adapter set and that additional imported domain skills are not part of the installable adapter.
- `release-manifest.json:7-24` - marks the three provider packages `ready`, with `portable-runtime` for Claude/Codex and `gemini-adapter` for Gemini.
- `release-manifest.json:29-34` - keeps `wt-cli` as `source-only` tooling, not a skill bundle package.
- `scripts/export-ready-skill-packages.ps1:35-120` - exports only `ready` packages and uses package strategy to decide what to copy.

**Implications:**
- Treat manifests as the source of truth for shipping.
- Keep imported trees as candidate material until a specific skill is adapted and added to package manifests.
- Do not mix `wt-cli` release work with skill-package export work unless the release manifest deliberately changes.

### Q2: Which parts are production-useful versus imported, stale, or local-only?

**Answer:** Production-useful: the three curated provider packages, the `review` skill promotion, delegation/eval/token/session telemetry contracts, Gemini bootstrap, and the `wt-cli` source package. Candidate-only: the imported top-level `skills/` tree and the larger untracked Gemini/ECC import. Local-only: `telemetry-live-ops`.

**Evidence:**
- `docs/skill-directory-review-2026-06-25.md:12` - states the imported `skills/` tree is a reference source, not an exported package.
- `docs/skill-directory-review-2026-06-25.md:24-31` - documents the promoted portable `review` skill across all three providers and its durable review-output behavior.
- `docs/skill-directory-review-2026-06-25.md:77-80` - says future promotions should extract behavior, adapt it to the provider surface, add manifests, and validate export paths.
- `docs/release-readiness.md:10-12` - marks Claude, Codex, and Gemini packages ready.
- `docs/release-readiness.md:18-19` - marks `wt-cli` and `telemetry-live-ops` outside the skill export.
- `docs/ollama-telemetry-integration.md:10-20` - splits portable delegation/analytics/eval from source-only live ops.
- Command output: `git status --short` showed existing dirty changes in README/manifests/Gemini wrappers and large untracked imports under `.antigravitycli/`, top-level `skills/`, and `gemini-skills/{agents,commands,docs,hooks,manifests,mcp-configs,rules,schemas,scripts}`.

**Implications:**
- The repo is in an integration state, not a clean release state.
- Upgrade work should stay selective: promote the useful behavior, not whole imported directories.
- `telemetry-live-ops` should remain available locally but excluded from ready exports.

### Q3: What validation already exists?

**Answer:** Claude and Codex have Python contract tests for package layout, manifest membership, and local-only exclusions. Gemini has bootstrap-time missing-file checks and imported CI validators, but the root repo lacks one unified ready-package validation command.

**Evidence:**
- `claude-skills/tests/test_skill_docs_contract.py:25` and `codex-skills/tests/test_skill_docs_contract.py:25` - define expected exported-file checks.
- `claude-skills/tests/test_skill_docs_contract.py:114-132` - verifies default/optional skills, includes `delegate`, `delegation-eval`, and `review`, and excludes `telemetry-live-ops`.
- `codex-skills/tests/test_skill_docs_contract.py:130-156` - verifies the wider Codex optional set and excludes `telemetry-live-ops`.
- `gemini-skills/scripts/bootstrap.ps1:20-22` - fails when the Gemini install manifest is missing.
- `gemini-skills/scripts/bootstrap.ps1:49` and `gemini-skills/scripts/bootstrap.ps1:73` - fail when manifest entries point to missing skills or command wrappers.
- `gemini-skills/scripts/bootstrap.ps1:79-85` - rewrites source/export wrapper includes to installed `.gemini/skills` paths.
- `docs/skill-directory-review-2026-06-25.md:84-91` - records the prior validation chain for the `review` promotion and export smoke.

**Implications:**
- The validation base is useful, but it is split by package and history.
- A root validation script should become the normal pre-export gate.
- Docs that cite one-off validation commands should either keep those scripts in repo or name them as historical evidence only.

### Q4: Where are the current upgrade gaps?

**Answer:** The strongest gaps are packaging hygiene, root-level validation, and selective promotion of a few high-signal imported skills.

**Evidence:**
- Command output from manifest comparison:

  ```json
  {
    "skillRows": [
      {"package": "claude-skills", "skillCount": 20, "missingSkillFiles": []},
      {"package": "codex-skills", "skillCount": 32, "missingSkillFiles": []},
      {"package": "gemini-skills", "skillCount": 29, "missingSkillFiles": []}
    ],
    "geminiWrappers": {
      "manifestCount": 29,
      "diskCount": 32,
      "diskNotManifest": [
        "continuous-learning.toml",
        "tdd.toml",
        "telemetry-live-ops.toml"
      ],
      "manifestMissingDisk": []
    }
  }
  ```

- `docs/reviews/review-2026-06-25-gemini-adapter-crosspoll.md:34-35` - already records the wrapper drift as deferred.
- `docs/skill-directory-review-2026-06-25.md:84-86` - cites `quick_validate.py`, but `rg --files | rg quick_validate` produced no repo file.
- `skills/skills/engineering/diagnosing-bugs/SKILL.md:3` - defines a hard-bug/performance-regression diagnosis skill.
- `skills/skills/engineering/diagnosing-bugs/SKILL.md:51-60` - requires a tight, red-capable command before hypothesis work.
- `skills/skills/engineering/tdd/SKILL.md:3` - defines a test-first skill for features, bugs, and integration tests.
- `skills/skills/engineering/tdd/SKILL.md:10-29` - emphasizes public-interface behavior tests and vertical test/code slices.
- `skills/skills/engineering/resolving-merge-conflicts/SKILL.md:3-12` - has a useful merge-conflict checklist, but the "always resolve; never abort" behavior needs adaptation before promotion.
- `skills/skills/productivity/writing-great-skills/SKILL.md:3` and `skills/skills/productivity/writing-great-skills/SKILL.md:15-28` - provide useful skill-authoring guidance around invocation, context load, and description pruning.

**Implications:**
- Do not promote `telemetry-live-ops.toml` into Gemini's ready manifest; either remove it from the curated wrapper folder or document it as source-only.
- `diagnosing-bugs` was the best first portable skill candidate and has now been promoted because it fills a distinct workflow gap not fully covered by `qa`, `smart-test`, or `review`.
- `tdd` is useful but needs adaptation: remove hard user-approval gates, replace slash-command references, and align with provider-specific invocation.
- `resolving-merge-conflicts` should be adapted into a safer "merge-conflict-resolution" skill that allows abort/escalation when preserving user work requires it.
- `writing-great-skills` is more useful as an internal authoring/reference skill or lint checklist than as a default model-invoked exported skill.

### Q5: What upgrade sequence is worth doing next?

**Answer:** Do one hygiene batch first, then one portable skill promotion batch. Leave larger Gemini/ECC imports alone until they get their own discovery.

**Evidence:**
- `README.md:100` - says the root export script reads `release-manifest.json` and applies package strategy.
- `docs/ollama-telemetry-integration.md:37-40` - forbids duplicating telemetry implementation, local-model self-judging, unevidenced routing changes, and exporting machine-local live deployment skills.
- `wt-cli/package.json:2-13` - `wt-cli` is a real Node CLI package with build/test scripts.
- `wt-cli/src/cli.ts:22-165` - exposes worktree commands for spawn, merge, teardown, bootstrap, scope, lock/unlock, ports, and diff.
- `wt-cli/tests/unit/worktree.test.ts:1-41` and `wt-cli/tests/unit/merge-planner.test.ts:1-2` - existing Vitest coverage is present for parsing and merge-planner helpers.

**Implications:**
- The next changes can be small and verifiable.
- `wt-cli` should either get its own release/readme hardening pass or stay explicitly source-only.
- Promotion should be one skill at a time with provider parity, manifest changes, wrapper changes, README count updates, and export validation.

---

## Cross-Cutting Analysis

### Constraints

- Package export is manifest-driven; unlisted skills/wrappers do not ship.
- The current worktree is dirty, so upgrade implementation should stage explicit files only.
- `telemetry-live-ops` contains local machine assumptions and must stay out of portable manifests.
- Gemini has two layouts to preserve: source/export wrappers point at `../../skills`, while installed wrappers are rewritten to `../skills` by bootstrap.
- Imported top-level `skills/` content has a different taxonomy and invocation style; copying it verbatim would create package drift.

### Risks

| Risk | Likelihood | Impact | Notes |
|---|---:|---:|---|
| Promoting imported skills verbatim leaks slash commands, user-approval assumptions, or non-portable paths | High | Medium | Adapt behavior and frontmatter per provider instead of copying. |
| Extra Gemini wrappers keep creating confusion about what ships | Medium | Medium | Reconcile `continuous-learning.toml`, `tdd.toml`, and `telemetry-live-ops.toml`. |
| Historical validation notes cite missing helper scripts | Medium | Low | Either add `quick_validate.py` or make docs clear those were one-off commands. |
| `wt-cli` drifts without a release lane | Medium | Medium | It has tests and CLI shape, but is explicitly source-only today. |
| Local telemetry code gets exported accidentally | Low | High | Existing tests and docs guard this; keep them in the root validation gate. |

### Open Questions

- Does Gemini CLI's `@{}` resolver definitely treat wrapper paths as file-relative after bootstrap? The previous review says live Gemini CLI was not available for final confirmation.
- Should `wt-cli` become a separately published tool, or remain a local source helper?
- Should the larger untracked Gemini/ECC import be retained in this repo, archived as reference material, or split out?

---

## Upgrade Register

| Candidate | Type | Evidence | Risk | Confidence | Decision |
|---|---|---|---|---|---|
| Add `scripts/Test-ReadyPackages.ps1` root gate | validation | Existing checks are split across package tests and export script | Low | High | implemented 2026-06-26 |
| Reconcile extra Gemini wrappers | packaging | 32 wrapper files on disk, 29 in manifest; extras are `continuous-learning`, `tdd`, `telemetry-live-ops` | Low | High | implement-next |
| Promote `diagnosing-bugs` | workflow skill | Tight-loop/red-capable diagnosis discipline fills a distinct gap | Medium | High | implemented 2026-06-26 |
| Promote/adapt `tdd` | workflow skill | Behavior-test and vertical-slice guidance is useful but needs provider adaptation | Medium | Medium | suggest-only |
| Adapt merge-conflict skill | workflow skill | Checklist is useful, but "never abort" needs safety rewrite | Medium | Medium | suggest-only |
| Add skill-authoring quality reference from `writing-great-skills` | docs/internal skill | Strong guidance on descriptions, invocation, context load, no-op/sprawl | Low | High | implement-next |
| Package or document `wt-cli` release lane | tooling | Existing CLI package and Vitest tests | Medium | Medium | defer |

### Baseline

- Manifest comparison: 20 Claude skills, 32 Codex skills, 29 Gemini skills, with no missing manifest-listed `SKILL.md` files.
- Gemini wrapper comparison: 29 manifest-listed wrappers, 32 wrapper files on disk.
- Source inventory: top-level imported `skills/` tree contains 35 `SKILL.md` files; 33 are not shipped.
- Current checkout: dirty before this discovery; existing changes should be preserved and staged explicitly.

---

## Recommendation

Proceed with a narrow upgrade batch:

1. Add a root validation gate that checks ready-package manifests, missing skill files, Gemini wrapper drift, source-only exclusions, and an export smoke into `D:\tmp`.
2. Reconcile the three extra Gemini wrappers:
   - remove or quarantine `telemetry-live-ops.toml` from the installable wrapper folder,
   - keep `tdd.toml` only if `tdd` is promoted,
   - defer or document `continuous-learning.toml` until that skill is evaluated.
3. Reconcile or intentionally quarantine unmanifested Gemini wrappers.
4. Consider `writing-great-skills` as an internal authoring reference or checklist for future skill promotions.

This does not need a multi-agent campaign unless the decision is to integrate the larger Gemini/ECC import. For the next practical pass, direct implementation is enough.
