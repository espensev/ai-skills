# Skills and hooks vs usage data — audit 2026-09-25

Controller `snd-desk` (v2 verifier VERIFIED 2026-09-25T02:27Z). Source branch
`fix/ai-skills-online-followups-20260825`. Method: seven read-only lanes
(install drift, wipe forensics, Claude skill usage, Codex skill usage, hook
cost, Remember store, context budget) over the last 14–30 days of Claude
transcripts, Codex rollouts, the Remember store and the relay attempt archive,
then two independent adversarial verifiers over all 59 findings (24
confirmed, 32 partially confirmed with corrections, 3 refuted). Numbers below
are the verifier-corrected figures, not the raw lane claims.

This review supersedes the lost 2026-09-10 review
(`AI-related/docs/reviews/review-2026-09-10-skills-hooks-data-audit.md`, gone
with the 09-21 rebuild); its baseline survives only as memory: 29% of Claude
Stop hooks and every Codex Stop prompt cost an extra model turn (p50 18 s /
29 s).

## 1. Root cause: a duplicate-file cleaner deleted installed skills

EaseUS DupFiles Cleaner 3.8.0 (installed 09-16) ran a content-duplicate sweep
on 2026-09-18 21:38:48–21:43:59Z across C:, D: and E:, deleting permanently
(no Recycle Bin) every duplicate file of 10 KiB or more, largest first.
Installed skills are byte copies of repo files, plugin caches and backups, so
their large `SKILL.md` files went in exact size order (usage-stats 35,991 B at
21:41:08 down to delegate 12,272 B at 21:43:22); every smaller file survived.
The same signature recurred 09-19 (E:, F:) and 09-24 (C:, D:, E:, F:, the P:
pCloud backup and E:/dUPEbIN — that run used the Recycle Bin and was
restored by hand, leaving 1,366 D: paths still missing, 161 size-changed and
4 zero-filled per `recycle_check.py`).

Ruled out: `Install-AgentSkills.ps1` (no destination wipe), agent sessions (0
delete calls in the window), scheduled tasks, the SMB probe. There were no
shadow copies before 09-22 and no Recycle Bin copies of the 09-18 losses.

Damage found on 09-25:

| Surface | State before repair |
|---|---|
| Claude skills `qa`, `manager`, `planner`, `delegate`, `usage-stats` | empty directories |
| Claude `deep-audit`, `review-controller` | subfolders only, no `SKILL.md` |
| Claude runtime `scripts/task_manager.py`, `memory_audit.py`, 10 `scripts/analysis`/`task_runtime` files | missing |
| Claude plugin cache | enabled `cloudflare` (wrangler, cloudflare-one-migrations) and `chrome-devtools-mcp` (chrome-devtools-cli) skills lack `SKILL.md`; parked `superpowers`, `plugin-dev`, `claude-code-setup` likewise |
| Codex skills root | 5 third-party Cloudflare copies broken |
| Codex plugin cache | enabled `documents`, `presentations`, `template-creator` (`openai-primary-runtime` 26.819.11345) and `chrome-devtools-mcp@claude-plugins-official` 1.7.0 skills lack `SKILL.md`; disabled `spreadsheets` and `superpowers` likewise; no pristine local copy exists |
| Shared `~/.agents/skills` (read by Codex and Grok) | 8 duplicate copies of Codex package skills (`deep-audit`, `discover`, `manager`, `memory-management`, `planner`, `qa`, `repo-conventions`, `usage-stats`) hollowed 09-18 23:41–43; `sandbox-sdk` is in `.skill-lock.json` but its directory is absent |
| Other repos under `D:\Development` | 10 repos show deleted tracked files; most are under 10 KiB (ordinary uncommitted work), a few large ones match the signature (LinkFix 3, Scribe ~18, appzone 4, SevHQ 1, Tokle 2) |

`qa` and `manager` are routed in the global CLAUDE.md table and `on` in
`skillOverrides`, `deep-audit` is routed by this repo's CLAUDE.md, and
`review-controller` had 26 invocations in the 24 days before the wipe and 0
after — the break was silent for 7 days because nothing checks installed
integrity and the installer skipped existing directories.

## 2. Second incident: Codex hooks rolled back on 09-21

On 2026-09-21 04:39 local, `D:\DevHome\state\codex\hooks\` and `hooks.json`
were restored from an old copy during the pCloud recovery. The live Codex
`Invoke-HandoffRelay.ps1` became blob `c28db723`, which matches only
`f4d85ea` (2026-08-25, the file's first commit): no `Get-SessionKind` gate,
no prompt-time preparation, no 09-20 grok envelope fix. `hooks.json` again
ran the Remember adapter retired in plugin 0.3.1 alongside the enabled
`remember@remember-dev` plugin (double capture), and the lifecycle plugin
cache sat at 0.3.0 against source 0.3.2. The Claude relay was unaffected
(sha256 `7BB7AC1E…` equals source).

## 3. Measurements (verifier-corrected)

Claude, 09-11..09-25:

- sdk gate works: 0 Stop continuations from sdk-cli sessions (baseline: half
  of all Claude waste).
- Interactive cli sessions still continue on ~33% of Stop events (110/337;
  71 in `D--DevHome`), at or above the 29% baseline. 32 of 105 completed
  draft cycles (30%) were rejected as `draft-budget-exceeded`.
- Two resolved outages from the wipe: remember-pinned hook scripts missing
  09-18T23:50Z–09-20T03:14Z (~27 h; 243 SessionStart, 261 UserPromptSubmit,
  ~1,300 PostToolUse `exit=127`), and `Invoke-HandoffRelay.ps1` missing
  09-18T23:58Z–09-20T11:26Z (~35.5 h; 341 Stop `exit=64`, 329 sdk-cli / 12
  cli). Raw 14/30-day aggregates are inflated by both.
- Remember's SessionStart hook re-delivers an unchanged handoff by design
  (`session-start-hook.sh:978`, unconditional `cat` at :1085) with no
  session-kind gate. The AIUsageTracker Monitor storm (up to "delivered 437
  times", 556 sdk sessions, ~2.8 M chars) ended 09-21 ~08:08Z; residual
  re-delivery is ~39 events in real projects 09-22..09-25. Upstream issue.
- `Test-HandoffNote` WARNING fires on 80% of real sessions (67/84); most
  stores still hold pre-rule handoffs without backticked checks.
- Fixed per-session preamble: ~50–70 K chars (~13–17 K tokens), skill
  listing the largest part (~30 K chars, ~130 entries after the claude.ai
  account sync landed on 09-20 15:52Z; 86 before).

Codex, 09-10..09-25 (older rollouts are pruned, so no before/after vs the
09-10 baseline is possible):

- The Stop prompt leads to a continuation on ~98% of interactive prompts
  (198/202; p50 41.7 s, ~232 min and ~1.33 M noncached input tokens per 15
  days). This was measured on the rolled-back 08-25 relay, so it is the
  un-fixed baseline, not a verdict on the 09-11 fix.
- Session kinds by first `session_meta`: 345 interactive / 224 subagent;
  the old `measure_hook_cost.py` reported 548 / 41 because it kept the last
  (copied parent) `session_meta`.
- Handoff text in subagent rollouts (~529 K chars) is parent context
  inherited at fork, not a separate injection.
- `logs_2.sqlite` holds 673 `legacy_notify` hook failures 09-15..09-25:
  `config.toml` `notify` pointed at a removed CodexBeta MSIX path. Rollouts
  do not record hook failures at all.
- The per-session developer preamble (~42 KB) is ~40% native Codex memories
  and ~52% the skills catalog; `measure_hook_cost.py` labelled all of it
  "memory".
- Skill use is top-heavy: usage-stats 206 sessions, handoff 174,
  repo-conventions 118, review 78, ship 76, browser-control 72, qa 62,
  browser-harness 51, verify 42, then 16 and below. All 149
  `[[skills.config]]` entries are `enabled=false`, including heavily used
  skills, so that flag is not the gate it looks like.

## 4. Repairs applied on 2026-09-25

State (installed from a clean `aa29f4b` snapshot worktree, after the v2
verifier):

- `Install-AgentSkills.ps1 -Provider Claude -Force`: 16 skills, 6 runtime
  files, 3 runtime dirs. Every pre-existing stale Claude runtime row was
  checked CRLF-only first, so no local edit was overwritten.
- `review-controller/SKILL.md` copied from source (source-only skill; hash
  `17B425966963` equals source).
- Stray `browser-control\NUL` (a redirected ssh-keyscan line) deleted.
- Codex `config.toml` `notify` commented out (backup
  `D:\DevHome\state\codex\hook-backups\config.toml.20260925-022853.bak`).
- Comparator after repair: zero Claude findings.
- After the source fixes (`9cfda75`): `Install-AgentSkills.ps1 -Provider Codex
  -CodexLocalPlugin DevHomeLifecycle` (plugin REFRESHED, drift empty),
  `Install-DevHomeCodexHooks.ps1` and `Install-DevHomeClaudeHandoffRelay.ps1`
  (both `-Check` CURRENT), Codex `handoff` refreshed with `-Force`. By then
  the lifecycle plugin's startup reconciler had already restored plugin 0.3.2
  and `hooks.json` from a Codex session start; only the relay script still
  differed. Relay sha256 `E7AFB286…` on source, both hook roots and the
  plugin cache. `Install-AgentSkills.ps1 -Check` passes for Claude and Codex;
  the comparator reports 0 findings. Candidate lock refreshed to `9cfda75`
  (relay hash in three resources; all other payload hashes re-verified;
  state stays `candidate`).

Source (`aa29f4b`): the installed Claude handoff skill carried a
provider-neutral verifier paragraph that never reached `skills-src`; it is
now the shared source text. The 09-11 `model: sonnet` pins for
qa-engineer, research-scout and system-fixer are now in
`claude-skills/agent-definitions/` (the `agents/` directory still has no
install or compare path).

Source fixes (test-first, each adversarially reviewed):

- `Install-AgentSkills.ps1`: an existing skill or runtime dir that lost
  files is repaired on a bare run by copying back only the missing files
  (never overwriting without `-Force`); every real run verifies each
  selected source file exists in the target; new read-only `-Check` exits
  non-zero on Missing or Drifted (CRLF folded, NUL-byte files raw). Recreating
  the 09-18 damage on a copy of the Claude root: `-Check` found exactly the 3
  holes, a bare run repaired them, a second `-Check` passed.
- `Compare-AgentSkillRoots.ps1`: CRLF-only differences are no longer Stale;
  a source-only skill dir without `SKILL.md` is Missing; `-IncludeExtra`
  reports orphan dirs without `SKILL.md`; a stray `NUL` file is attributed to
  its skill.
- `measure_hook_cost.py`: Codex session kind from the first `session_meta`
  (14-day run: 338 interactive / 215 subagent / 3 exec, was 512 / 40 / 4);
  injected context split per item (memory 42%, skills catalog 53%, other 5%
  of the old "memory" bucket).
- `Invoke-HandoffRelay.ps1`: new `non-project-cwd` skip for both providers
  when the cwd or its resolved enrolled workspace is a drive root, the
  profile, Desktop, Documents itself, a Codex desktop scratch folder
  (`Documents\Codex`, `%CODEX_HOME%\Documents\Codex`) or the Windows tree.
  Repos directly under Documents keep relaying. The draft-budget rejections
  were investigated: the prompt states every limit the validator enforces,
  so drafts simply overshoot; no change.

## 5. Decisions for the user

1. **EaseUS DupFiles Cleaner.** Uninstall it, or at minimum exclude
   `C:\Users\Sev`, `D:\DevHome`, `D:\Development`, `P:` and `E:\dUPEbIN`,
   and never use permanent delete. These trees are intentionally duplicated.
   Review the 1,366 still-missing / 4 zero-filled D: paths from the 09-24
   restore, and the large deleted tracked files in the repos listed in §1.
2. **Plugin caches.** Reinstall `cloudflare` and `chrome-devtools-mcp`
   through Claude Code's plugin manager; `superpowers`, `plugin-dev` and
   `claude-code-setup` are parked but also damaged. In Codex, the enabled
   `documents`, `presentations` and `template-creator` runtime plugins and
   `chrome-devtools-mcp@claude-plugins-official` need a re-fetch (toggle or
   reinstall through Codex); Codex keeps no pristine copy to restore from.
3. **review-controller packaging.** It is `source_only`, so the installer
   cannot restore or verify it. Promoting it to `optional_skills` would make
   it managed but changes what ships in ready-package exports.
4. **Playwright policy.** `playwright` and `kimi-cu` load user-wide from
   `.claude.json` `mcpServers`, bypassing `enabledPlugins`. Playwright
   contradicts the browser-control ban yet workflow subagents used it on
   09-24; kimi-cu is actively used. Scope both per project or settle the
   policy.
5. **Account-synced plugins.** The claude.ai account sync loads
   `browser-use` and seven other plugins into every session (519 of 560
   startups, 0 invocations) although the official `browser-use` entry is
   disabled. Whether a local `enabledPlugins` entry for the synced id
   disables it is untested.
6. **Merge.** `fix/ai-skills-online-followups-20260825` is still unmerged;
   `main` (`c4d1713`) predates the 09-11 relay gate, so any reinstall from
   `main` regresses both providers.
7. **Shared `~/.agents/skills` root.** No installer owns the 8 hollow
   copies. Codex loads the same skills from `~/.codex/skills`, but Grok
   used the agents-root copies. On 08-22 its sessions listed `deep-audit`,
   `discover`, `manager`, `memory-management`, `planner` and `qa` from
   `.agents`; on 09-24 it listed only `.claude\discover`. Grok now falls
   back to the repaired Claude-flavored copies in `~/.claude/skills`.
   Choose one: restore the Codex-flavored copies (add `skills.config`
   disables so Codex does not list them twice), leave the fallback, or
   delete the hollow directories.

## 6. Upstream / deferred

- Remember (pinned plugin): SessionStart injection and the SessionEnd
  agentic-save path have no session-kind gate; the re-delivery of unchanged
  handoffs is deliberate upstream design.
- 77 Remember session-end save failures across 10 projects (41 outside
  AIUT); a Cygwin fork-exhaustion cause is plausible, not proven.
- About a third of `remember/projects` dirs are junk (~7% of bytes); the
  cross-review ones came from remember-bridge (Grok/Kimi), not Claude
  subagents.
- The relay health file is a single overwritten snapshot; the per-project
  attempt archive (`tmp/handoff-relay/`) is the historical source, but
  orphaned attempts do not record which orphan code applied.
- Codex native `rollout_summaries/` (256 files, 1 MB, oldest 23 days): no
  pruning seen yet; recheck after 30+ days.
- `scripts/Sync-DeepAuditSharing.ps1`, the only owner of the agents-root
  `deep-audit` copy, throws on its dry run. It anchors on a `/manager` row
  in the shared `common_dev/CLAUDE.md`, which has been a 385-byte stub
  since 08-05. Its bare invocation is also a dry run. Retire it or rebase
  it on the current shared-rules layout.

## 7. Refuted or corrected lane claims

- Codex "Stale" skill rows are CRLF-only noise from the 09-21 LF re-clone.
- `measure_hook_cost.py --days` works; the Codex corpus simply starts 09-10.
- "Zero Codex hook errors" was wrong: rollouts do not record hook failures;
  `logs_2.sqlite` does.
- "The 09-11 gate holds for Codex subagents" is vacuous: the gate was not
  deployed on Codex.
- memory-management was one content revision behind, not two.
- The installed handoff edit was the better text, not the stale one.
