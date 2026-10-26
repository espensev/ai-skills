# Review - Skills and Hooks vs Usage Data, 2026-10-26

**Date:** 2026-10-26
**Surface:** installed Claude and Codex skills and hooks on `snd-desk`, read
against the packages in this repository at `6d56eb3`
(`fix/ai-skills-online-followups-20260825`)
**Spec source:** user request ("review and improve the skills and hooks based
on data, Claude primarily, OpenAI where clear"); package promises in
`skills-src/manifest.json`, both `package/install-manifest.json`, and the
`skill-authoring` contract
**Standards sources:** `CLAUDE.md`, `AGENTS.md`, `claude-skills/CLAUDE.md`,
`claude-skills/tests/test_skill_docs_contract.py`, the DevHome environment
policy (global `CLAUDE.md`), the 2026-09-25 skills-vs-data audit
**Verdict:** FAIL before repair (Claude hooks dead for three weeks); the
repairs below were applied and verified in the same session

## Method

Read-only measurement, then targeted repair:

- Claude: every `projects/*/*.jsonl` transcript under `$env:CLAUDE_CONFIG_DIR`
  modified since 2026-09-01, excluding the invocation-check fixtures under the
  temp directory (152 sessions). Counted `Skill`, `Agent`, and other tool
  uses, the user text preceding each `handoff` and `verify` selection, tool
  calls between a `handoff` selection and the first `Edit`/`Write`, and the
  last timestamp of each hook status message. Cross-checked with Claude Code's
  own `skillUsage` counters in `.claude.json`.
- Codex: `$env:CODEX_HOME\sessions` rollouts since 2026-09-01 (197 files,
  36 interactive) through `scripts/measure_hook_cost.py --days 30`.
- Installed state: `Install-AgentSkills.ps1 -Check` for both providers,
  `Install-DevHomeClaudeHandoffRelay.ps1 -Check`,
  `Install-DevHomeCodexHooks.ps1 -Check`, and a diff of the current Claude
  `settings.json` against the 2026-09-25 relay backup.

Counts below are from this session's scripts (kept in the session scratchpad,
not committed); they are indicative, not a general selection rate.

## Findings

### High

- [axis: regression] `$env:CLAUDE_CONFIG_DIR\settings.json` - Every Claude
  hook stopped firing on 2026-10-05.
  Evidence: the last transcript lines carrying `Handoff Relay: preparing
  next-session context` and `Handoff verify: checking remember.md claims`
  are dated 2026-10-05T21:10Z and 2026-10-05T20:10Z; the `wtcli.exe
  agent-hook` line last appears 2026-10-03. `Install-DevHomeClaudeHandoffRelay.ps1
  -Check` reported `settings.json expected one Handoff Relay registration,
  found 0`. The current file (rewritten 2026-10-25 22:06) has no `hooks`
  key at all; the 2026-09-25 backup under `hook-backups\handoff-relay\` has
  the Stop relay and the SessionStart `Test-HandoffNote.ps1 -Summary`
  registration. No Claude `Edit`/`Write` tool call touched `settings.json`
  in that window, so the rewrite came from outside the transcripts.
  Impact: the `handoff` skill was selected 49 times in the period and reads
  the relay's output; since 10-05 Claude sessions produced no relay drafts
  and no handoff-note verification report, while Codex kept relaying.
  Recommendation (applied): SessionStart registration restored from the
  backup with its script path resolved from `MACHINE_CODE_ROOT` at
  generation time; relay re-registered through the source installer
  (`INSTALLED`, then `-Check` = `CURRENT`); pre-change file saved under
  `hook-backups\manual-restore\`. Takes effect at the next session start.
  Gap: `Test-HandoffNote.ps1` has no owning installer and the AiEnvironment
  profile tracks only the relay registration, so this hook can vanish again
  unnoticed.

- [axis: regression] `claude-skills/skills/verify/SKILL.md:3` - A
  machine-local DevHome shell recipe was the most automatically selected
  skill, including in projects it does not apply to.
  Evidence: 25 `verify` selections in the period (Claude's own counter: 27,
  more than `handoff` at 25). 7 of the 25 ran in sessions whose preceding
  context never mentioned `shell/powershell`, the profile bootstrap,
  PSReadLine, or the DevHome shell tests (Thermals SQ-control x4, LibreHW
  x2, AI4000 x1). In 8 cases the message immediately before the selection
  was the body of another skill (`handoff`, `ship`, `review`,
  `pcloud-transfer`) that says "verify every claim". The old description
  began "Use when verifying ..." with no exclusion, and
  `agent-definitions/builder.md:24` told every builder subagent to "invoke
  the `verify` skill if available".
  Impact: wasted selections load a 4.7 KB recipe about `PSModulePath` and
  `-UseNewEnvironment` into unrelated sessions, and builder subagents are
  pointed at the wrong verification contract.
  Recommendation (applied): trigger-first description with an explicit
  `Do not use` clause; `verify` added to
  `test_collision_prone_skills_use_trigger_first_descriptions`; builder
  routing changed to `superpowers:verification-before-completion` with
  `verify` reserved for `shell/powershell` assignments. The name stays
  `verify`: Codex sessions read
  `$env:MACHINE_CODE_ROOT\DevHome\state\agents\skills\verify\SKILL.md` by
  path (69 reads in the period), so a rename would break that.

### Medium

- [axis: standards] `claude-skills/skills/verify/SKILL.md` - Hardcoded
  machine paths (`D:\DevHome\...`, `C:\Users\Sev\Documents\...`) in a
  package skill, against the DevHome environment policy.
  Recommendation (applied): repo-relative prose paths, `Join-Path
  $env:MACHINE_CODE_ROOT 'DevHome'`, and
  `[Environment]::GetFolderPath('MyDocuments')` for the `PSModulePath`
  reset.

- [axis: regression] `$env:CLAUDE_CONFIG_DIR\skills\verify\SKILL.md` - The
  installed copy carried a "Gate launch trap (2026-10-07)" section that the
  source never received (`verify` is `source_only`, so the installer neither
  copies nor checks it).
  Recommendation (applied): section folded into the source; installed copy
  replaced with the source and byte-compared.

- [axis: regression] `$env:CODEX_HOME\skills\scripts\skill_feedback_loop.py`
  - Installed runtime file was the 2026-09-20 version; source changed on
  2026-10-03 (priority-score normalisation and the "no actionable issues"
  wording). `Install-AgentSkills.ps1 -Provider Codex -Check` reported
  `1 drifted`.
  Recommendation (applied): `-Force` reinstall; `-Check` now `PASS`.

- [axis: regression] `$env:CLAUDE_CONFIG_DIR\settings.json` - The same
  rewrite dropped `skillOverrides` (seven Ai-Skills skills were `off`:
  cc-workflow-builder, chief-operator, delegate, diagnosing-bugs, docs-sync,
  planner, resolving-merge-conflicts), `enabledPlugins`,
  `extraKnownMarketplaces`, the `permissions.deny` list (ssh to ops hosts,
  API-key and provider-config reads), `env`, `outputStyle`, `worktree`,
  `autoMemoryEnabled`, and other flags.
  Recommendation: `skillOverrides` restored (skill gating is in scope). The
  rest is an owner decision; the deny list is security-relevant. Backup:
  `hook-backups\handoff-relay\20260925-045258-460\settings.json`.

### Low

- [axis: standards] `$env:MACHINE_CODE_ROOT\DevHome\state\agents\skills\verify\SKILL.md`
  - A third, older (2026-08-17) `verify` document, Codex-flavoured, with no
  owning installer; Codex reads it by path. Not changed here. Decide whether
  it should track the Claude source or stay a separate Codex recipe.

- [axis: standards] `claude-skills/skills/cc-workflow-builder/SKILL.md` -
  Installed description is 1158 characters, repo copy 1009; `source_only`,
  so unmanaged drift. Zero selections in the period and `off` in the
  restored `skillOverrides`. Not changed.

## Measurements

Claude, 2026-09-01..10-26, 152 project sessions, 117 `Skill` calls:

| Skill | Selections |
|---|---:|
| handoff | 49 |
| verify | 25 |
| ship | 11 |
| review | 8 |
| browser-control | 6 |
| pcloud-transfer | 5 |
| memory-management | 5 |
| remember:remember / remember:doctor | 4 |
| skill-authoring, update-config, workflow-authoring, diagnosing-bugs | 1 each |

Zero selections: qa, smart-test, discover, planner, manager, deep-audit,
docs-sync, docs-clean, usage-stats, delegate, chief-operator,
codebase-design, cc-workflow-builder, resolving-merge-conflicts,
review-controller, telemetry-live-ops. A scan of user prompts for "run the
tests"-shaped requests found none, so no mis-selection is shown for `qa` or
`smart-test`; this is an observation, not a defect.

Other Claude signals: `handoff` intake took a median of 23 tool calls before
the first edit (40 sessions with edits) and 9 of 49 sessions never edited;
the user typed `/compact` 50 times and 37 sessions opened from a
context-continuation summary. Agent launches: general-purpose 34,
research-scout 7, builder 5, adversarial-critic 3. 30-day hook cost: 5 Stop
continuations, p50 9.6 s.

Codex, last 30 days (36 interactive, 158 subagent rollouts): ship 92,
review 70, handoff 62, diagnosing-bugs 56, repo-conventions 44, qa 39,
verify 31 (agents-root copy), smart-test 21, discover 15, docs-clean 14,
browser-control 10, docs-sync 8, manager 8. Stop continuations: 7, p50
27.4 s, 15.5 K non-cached input tokens — down from the 98 % / 198-per-15-days
baseline measured on 2026-09-25. `Install-DevHomeCodexHooks.ps1 -Check` =
`CURRENT`. `manager` and `discover` are used although their
`[[skills.config]]` entries are `enabled = false`, as the prior audit
predicted; no change.

## Verification

- `python -m unittest claude-skills.tests.test_skill_docs_contract
  codex-skills.tests.test_skill_docs_contract` - 48 tests OK
- `python -B -m unittest discover -s scripts/tests -p 'test_*.py'` - 68 OK
- `scripts/Test-ReleaseReadiness.ps1` - PASS, exit 0 (Pester 276 tests,
  ready-package validation, parity, whitespace)
- `Install-DevHomeClaudeHandoffRelay.ps1 -Check` - CURRENT
- `Install-AgentSkills.ps1 -Provider Claude -Check` - PASS;
  `-Provider Codex -Check` - PASS after `-Force`
- `cmp` of source and installed `verify/SKILL.md` - identical

## Coverage Notes

- Reviewed deeply: `verify`, `handoff`, `ship`, `review` sources; the Claude
  and Codex hook registrations; both install manifests.
- Sampled: remaining skill descriptions (length and trigger shape only).
- Not reviewed: skill bodies with zero selections; plugin hooks
  (remember, superpowers, hookify) beyond their outcome counts.

## Open Questions

- Who rewrote `settings.json` on 2026-10-05 and 2026-10-25? Not a Claude
  tool call; if it recurs, give `Test-HandoffNote.ps1` an installer or add
  its registration to the AiEnvironment profile so the observer flags it.
- Should the agents-root `verify` copy be retired in favour of a Codex
  package skill, so Codex stops depending on an unmanaged file?
