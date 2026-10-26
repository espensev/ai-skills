# Review - Claude and Codex skills, hooks, and local ownership

**Date:** 2026-10-26
**Surface:** repository baseline `4ce0d8c`, working changes, and the selected
Claude/Codex installations on snd-desk
**Spec source:** owner request to compare the providers and update as needed
**Standards:** repository and provider `AGENTS.md`/`CLAUDE.md`, shared skill
manifest, DevHome environment policy and installed-shell runtime contract
**Verdict:** PASS WITH NOTES after the repairs below. Full environment
acceptance remains incomplete; this is not a new accepted environment lock.

## Findings and repairs

1. **Medium / regression: verification guidance could validate the wrong code.**
   At `4ce0d8c`, `claude-skills/skills/verify/SKILL.md:10` said a fresh shell
   runs the checkout. The older Codex-discovered copy under
   `DevHome/state/agents/skills/verify` made the same claim. DevHome's current
   `docs/devhome-shell-runtime.md` requires installed implementations on the
   tools volume. Both recipes now separate source tests from installed console
   evidence, retain the 5.1 module-path and real-console precautions, and use a
   narrow trigger that excludes ordinary handoff and test verification.

2. **Medium / regression: the Codex recipe had no maintained source path.**
   The installed agents-root file differed from Claude's recipe, and full
   package checks intentionally excluded this machine-specific skill.
   `skills-src/verify/SKILL.src.md` now generates both provider sources.
   `scripts/Install-AgentSkills.ps1:17` adds `-AllowSourceOnly`, requiring
   named skills, one provider, and explicit targets. It supports install,
   preview, and drift checks without changing full installs or exports.
   Both existing local `verify` paths were updated through this installer;
   their selected `-Check` calls pass. No extra discovery copy was added.

3. **Medium / regression: Claude's startup verifier could disappear unnoticed.**
   The baseline profile observed only the managed Stop relay. The existing
   `Test-HandoffNote.ps1` SessionStart registration was outside its coverage.
   `scripts/AiEnvironment/profiles/snd-desk.json:87` now declares it as an
   observed resource. The adapter checks its event, matcher, command, timeout,
   synchronous execution, script presence, matching duplicates, and
   `disableAllHooks`. Fixtures remove or alter each part and prove drift is
   reported without executing the script or writing settings. Live observation
   reports `RegistrationPresent=true`. DevHome still owns the verifier source;
   this change does not add an installer or imply session execution.

4. **Medium / standards: root selection embedded one machine's drive.**
   The installer and root comparator hardcoded the DevHome provider roots.
   Both now derive them from `MACHINE_CODE_ROOT` and reject a relative value.
   Native `CODEX_HOME` and `CLAUDE_CONFIG_DIR`, existing compatibility roots,
   and explicit target selection are preserved. Disposable-root tests cover
   both providers and both scripts. The local-access guide also now documents
   `CLAUDE_CONFIG_DIR` and the explicit source-only maintenance commands.

5. **Low / maintenance: one inert lifecycle cache file was stale.**
   Initial plugin check reported only `Install-DevHomeCodexHooks.ps1` differed,
   with `LoadedDrift=[]`. The source synchronizer refreshed the cache and its
   subsequent check is `CURRENT`. The native refresh changed Codex's config
   file and requested a restart and `/hooks` review; hook trust was not edited
   by this review. Claude settings and Codex runtime `hooks.json` are byte
   unchanged against their pre-refresh hashes.

## Provider comparison

| Surface | Claude | Codex |
|---|---|---|
| Current CLI version | 2.1.310 | 0.164.0 |
| Portable skills | 17 | 26 |
| Source-only skills after repair | 7 | 3 |
| Shared generation | 17 source pairs, including local `verify` | Same canonical sources with explicit provider bindings |
| Declared independent pairs | `review-controller`, `telemetry-live-ops` | Native orchestration and machine-local presentation differences retained |
| Registered hooks reviewed | SessionStart verifier and Stop relay | PreToolUse guard, UserPromptSubmit checks/relay preparation, Stop relay; plugin SessionStart reconciler |
| Portable install checks | PASS | PASS |
| Local hook projection checks | CURRENT | CURRENT |

The nine extra portable Codex skills cover repository conventions, gated and
parallel workflows, state cleanup, documentation/search, MCP patterns, and
verification. Claude-only source workflows were not promoted just to make the
counts match. `release-manifest.json` currently ships only these two providers;
historical Gemini/Grok/Kimi material is not a current release target.

Codex's filesystem budget inventory remained at 43 active skills, 66 disabled,
and zero active duplicate names. Description characters changed from 13,469 to
13,635. This is the CLI inventory, not proof of this app's effective catalog or
automatic model selection. Other installed skills and plugins retain their
existing owners. The restored Claude deny list still has 15 entries.

## Verification

- `scripts/Test-ReleaseReadiness.ps1`: PASS; 305 Pester tests, 68 repository
  Python tests, 54 package contract tests, export/install smoke checks,
  generated-package parity, README counts, and whitespace checks.
- Required provider suites (`test_skill_docs_contract`, `test_task_manager`,
  `test_task_manager_portability`, `test_plan_lifecycle`): Claude 142 passed;
  Codex 144 passed. These overlap the contract checks above.
- `scripts/tests/Compare-AgentSkillRoots.Tests.ps1`: 7 passed.
- Final installer rerun, including source-only drift rejection and repair:
  35 passed.
- Full `Install-AgentSkills.ps1 -Provider Both -Check`, root comparison, and
  explicit source-only checks for both installed `verify` copies: PASS.
- Both lifecycle projection checks and plugin-cache check: CURRENT.
- New startup registration: live observation passes. Full environment observer:
  `ACCEPTANCE_FAILED`, with the existing candidate-lock and acceptance reasons.
- Local mutation identity: installed LocalApplicationData verifier returned one
  `VERIFIED` result for the enrolled snd-desk instance before synchronization.

## Remaining decisions and limits

1. Review the Codex SessionStart reconciler in `/hooks` after restart, as the
   native plugin refresh requests. Cache convergence alone does not prove trust
   or hook execution in a fresh session.
2. Claude's fresh `plugin list --json` reports the locally installed plugins
   disabled, including official Remember 0.43.1 and pinned Remember 0.27.0;
   eight synced plugins remain enabled. This confirms the earlier handoff's
   unresolved enablement choice. No plugin selection or capture behavior was
   changed here.
3. The 2026-09-25 candidate environment lock still names older provider versions,
   source and payload hashes, trust evidence, and an unrun Remember acceptance
   gate. It needs a separate deliberate rebaseline and behavioral acceptance.
   This review leaves those failures visible and does not mark the lock accepted.

Coverage was deep for the changed recipes, installer, comparator, observer,
schemas, fixtures, and local lifecycle projections. Remaining skill bodies were
covered by existing parity/package contracts, not individually rewritten or
tested through paid model sessions. Foreign plugin implementations and shell
deployment were outside this repair.

Provider contracts checked against current official guidance:
[Codex skill discovery and triggers](https://learn.chatgpt.com/docs/build-skills),
[OpenAI plugin hook trust](https://developers.openai.com/plugins/build/plugins),
and [Claude hook configuration](https://code.claude.com/docs/en/hooks).
