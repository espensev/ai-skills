# Review - Claude and Codex Skills and Hooks Evaluation

**Date:** 2026-08-30
**Surface:** package review of `claude-skills/` and `codex-skills/` skills and hooks
as they stand in the working tree (`HEAD` = `4feeb37` plus 31 uncommitted files and
12 untracked paths; findings in uncommitted content are labelled "uncommitted").
The remaining ~187 "M" entries in `git status` are CRLF-only and carry no content.
**Spec source:** none found as a file; the user request ("review and evaluate Claude
and Codex skills and hooks") plus the packages' own promises (READMEs, install
manifests, `skills-src/manifest.json`, the `skill-authoring` contract).
**Standards sources:** `AGENTS.md`, `CLAUDE.md`, `claude-skills/CLAUDE.md`,
`codex-skills/AGENTS.md`, `claude-skills/skills/skill-authoring/SKILL.md`,
`skills-src/manifest.json`, both `package/install-manifest.json`,
`scripts/retired-skills.json`, `claude-skills/scripts/hooks/README.md`, both
`tests/test_skill_docs_contract.py`.
**Verdict:** FAIL

Method: the controller ran the repo's own gates and the installed-projection drift
checks, then five bounded read-only lanes (two over the 16 single-source canon
skills, one over the 8 Claude-owned skills and agent definitions, one over the 11
Codex-owned skills, one over hook code and wiring for both providers). Every High
and Medium below was re-verified by the controller against the file, the runtime,
or the live machine before it was accepted; three lane claims were rejected and are
listed at the end so they are not re-raised.

## Findings

### High

- [axis: standards] `claude-skills/package/install-manifest.json` - The release gate
  is red at `HEAD`: seven committed skill directories have no manifest bucket.
  Evidence: `scripts/Test-ReadyPackages.ps1 -StrictSkillManifest` -> `FAIL -
  claude-skills has unexpected skill directories not listed in
  package/install-manifest.json: cc-workflow-builder, chief-operator,
  codebase-design, docs-clean, resolving-merge-conflicts, review-controller,
  verify`; it is the first step of `scripts/Test-ReleaseReadiness.ps1`. The
  directories were added by commit `2d27dd3` ("back up authored Claude skills")
  with no manifest, README, or eval change. `claude-skills/README.md:39-52` lists
  12 of the 24 skill directories; `review-controller` is a declared
  `provider_owned_shared_skill` like `telemetry-live-ops`, yet only the latter has
  a `source_only_skills` entry. Both 2026-08-30 review-controller reviews record
  this as "externally blocked"; it is still unresolved.
  Impact: `Test-ReleaseReadiness.ps1` cannot pass; consumers cannot tell which of
  the seven are portable, machine-local, or backups.
  Recommendation: decide per directory - `optional_skills` for the portable ones
  (`codebase-design`, `docs-clean`, `resolving-merge-conflicts`,
  `review-controller`), `source_only_skills` with a machine-local note for the
  workstation-bound ones (`verify`, `chief-operator`, `cc-workflow-builder`) or
  move those out of the package; add README rows and eval cases for whatever
  ships. Ordinary `/ship` cannot land this branch until it is green.

- [axis: regression] `claude-skills/scripts/hooks/observe_test_output.py:146` - The
  Claude observer hooks are inert as shipped.
  Evidence: line 146 reads `data.get("tool_output", "")` and exits unless it is a
  string; Claude Code's PostToolUse payload carries `tool_response` (an object for
  Bash). Probed with a real-shaped Bash PostToolUse payload: exit 0, nothing
  written; with the key renamed to `tool_output` the observation is recorded.
  `observe_session_briefing.py:85`, `observe_churn.py:115`,
  `observe_test_output.py:197`, `observe_agent_stop.py:100` all emit
  `{"additionalContext": ...}` at the top level; Claude only honours it under
  `hookSpecificOutput` with a `hookEventName`, and SubagentStop has no
  `additionalContext` channel at all. `README.md:42-43,88` says "All scripts use
  `$CLAUDE_PROJECT_DIR`" - `grep CLAUDE_PROJECT_DIR scripts/hooks/*.py` = 0 hits;
  every script uses `os.getcwd()`.
  Impact: the observation log that `manager` and `usage-stats` describe
  (`data/observations.jsonl`) never receives test/build results, and no hook
  injects context. Nothing on this machine registers these hooks
  (`D:\DevHome\state\claude\settings.json` has only the Handoff Relay Stop hook and
  the DevHome `Test-HandoffNote.ps1` SessionStart hook), so nothing is broken
  live, but the shipped feature does not work for any consumer who installs it.
  Recommendation: read `tool_response` (stringify stdout/stderr), wrap
  `additionalContext` in `hookSpecificOutput`, drop the SubagentStop context
  path or switch it to `systemMessage`, resolve paths from `CLAUDE_PROJECT_DIR`
  with cwd fallback, and add stdin-fixture tests for each script.

- [axis: regression] `skills-src/planner/SKILL.src.md:237-238` (both generated
  copies) - The default `planner` skill mandates a procedure the Codex contract
  does not contain.
  Evidence: "Follow the canonical conflict zone identification procedure in the
  planning contract (element 8) - do not invent a separate method here."
  `claude-skills/planning-contract.md:120` has "**Identification (canonical
  procedure - use this everywhere):**"; `codex-skills/planning-contract.md:114-124`
  element 8 has the heading and the mitigation table only - no identification
  procedure (grep for "Identification (canonical" = 0 hits).
  Impact: a Codex planner is forbidden from improvising and has nothing to follow;
  the two contract files have drifted although both are shipped `contract_files`.
  Recommendation: port the identification subsection to the Codex contract (or
  single-source `planning-contract.md` the way skills are) and add a contract test
  that both copies contain the section the planner cites.

- [axis: regression] `claude-skills/skills/chief-operator/SKILL.md:140` - Routes to a
  retired skill and asserts it exists.
  Evidence: "Tier 3: the `improvement-analyst` skill EXISTS - invoke it"; also
  lines 92, 112, 132. `scripts/retired-skills.json` retires `improvement-analyst`
  -> `review`; no directory with that name exists in either package, in
  `D:\DevHome\state\claude\skills`, or in `D:\DevHome\state\agents`. The same file
  hard-codes `SND-DESK`, `D:\DevHome\state\claude\agents\`, and
  `C:\Users\Sev\OneDrive\Common\common_development\common_dev` (lines 29-32) and a
  MSYS path to the run log (line 108).
  Impact: the skill's own analytics escalation dead-ends; the file is unusable on
  any other machine or user; committed in `2d27dd3` without manifest entry.
  Recommendation: route Tier 3 to `review` (or delete the tier), replace absolute
  paths with a documented env/config lookup, and bucket the skill as
  machine-local.

- [axis: regression] `claude-skills/skills/telemetry-live-ops/scripts/telemetry-live-start.ps1:80`,
  `telemetry-live-verify.ps1:78`, and the same lines in the Codex copy - The
  default repo path no longer exists, so a bare invocation throws.
  Evidence: fallback `'D:\Development\AI-data-handling\ollama-telemetry'`; `ls`
  -> "No such file or directory". The scripts the skill joins against
  (`native\scripts\verify-live-deployment.ps1`, `start-remote-host-stack.ps1`)
  exist under `D:\Development\web\SevHQ\SevIQ\apps\ollama-telemetry\`. Both
  `SKILL.md` env tables (`claude…:25`, `codex…:21`) document the dead default.
  `telemetry-live-ops` is the only Claude package skill not installed under
  `D:\DevHome\state\claude\skills`.
  Impact: `verify`/`start` fail at `Assert-PathExists` unless
  `OLLAMA_TELEMETRY_REPO` is set; this is a machine-local skill that is wrong on
  its own machine.
  Recommendation: update the default in both packages and both SKILL.md tables,
  or make the env var required with a clear error.

### Medium

- [axis: regression] `codex-skills/local-hooks/devhome-lifecycle/hooks/Invoke-DevHomeHook.ps1:31`
  - The generated-memory write guard is still bypassed by a redirection with no
  whitespace after `>`.
  Evidence: `$mutationPattern` ends `(?:^|\s)>{1,2}(?:\s|$)`; recorded as a Medium
  in `docs/reviews/review-2026-08-16-devhome-lifecycle-feature.md:29-41` with a
  reproduction; the pattern is unchanged in the working tree.
  Impact: `echo x>D:\DevHome\state\codex\memories\MEMORY.md` passes a hook whose
  stated job is to block that write.
  Recommendation: token-aware redirection detection plus the regression cases the
  08-16 review listed.

- [axis: regression] `codex-skills/local-hooks/devhome-lifecycle/hooks.json:58-77` /
  `hooks/Invoke-HandoffRelay.ps1:1163,1312-1322` - Two co-registered Stop handlers
  write into the same project directory and the relay's conflict guard discards
  the loser; abandoned attempts are never quarantined.
  Evidence: Stop registers the Remember adapter then the relay, neither `async`;
  both target `remember/projects/<slug>/`. Pass 1 snapshots `baselineHash`, pass 2
  archives the draft as `.conflict.` on any change. Live residue (read-only
  count): 34 `.conflict.*` artifacts (17 draft/state pairs) under
  `D:\DevHome\state\remember\projects\*\tmp\handoff-relay\`, 15 of them in
  `d--DevHome`, spanning 2026-08-24 to 2026-08-29; 18 bare `.state.json` files
  with no `.conflict/.failed/.orphaned` suffix. `README.md:76-77` and
  `skills/devhome-lifecycle/SKILL.md:47` promise orphan quarantine, but
  `Move-LooseDraftsToArchive` (`:708-748`, uncommitted) only handles the
  state-less case and `Move-AttemptToArchive` (`:1151`) only the current session
  key. Deferral (`background_tasks`/`session_crons`, `:1363-1371`) and re-entrant
  suppression both return `{}` with no health record, and
  `tests/DevHome-Hooks.Tests.ps1:1516,1533` assert the same string for both.
  Impact: handoffs are silently lost at a measurable rate; the temp tree grows;
  a deferred handoff is indistinguishable from a suppressed one in logs and tests.
  Recommendation: serialise the two Stop writers (or have the adapter target a
  different file), quarantine state+draft pairs older than the current session,
  write a health record on deferral and lock timeout, and pin those paths in
  Pester.

- [axis: standards] `codex-skills/local-hooks/devhome-lifecycle/.codex-plugin/plugin.json:3`
  (uncommitted context) - The Codex plugin cache is stale against source at the
  same version.
  Evidence: `Sync-DevHomeLifecyclePlugin.ps1 -Check` -> `Status: STALE`,
  `Version 0.3.0 / InstalledVersion 0.3.0`, drift in exactly the four uncommitted
  hook files (`Invoke-HandoffRelay.ps1`, `Invoke-RememberAdapter.py`,
  `Invoke-RememberClaude.cmd`, `skills/devhome-lifecycle/SKILL.md`); the six-file
  runtime projection and the Claude relay projection are `CURRENT`, so the
  uncommitted source was installed but the plugin was not refreshed.
  `README.md:383-385`: "Re-run it after source changes".
  Impact: the plugin's operator skill and cached scripts disagree with the running
  hooks; hook-behaviour changes shipped without a version bump.
  Recommendation: bump `version`, run `Install-AgentSkills.ps1 -Provider Codex
  -CodexLocalPlugin DevHomeLifecycle` after the change lands, and consider a gate
  that fails when payload drift exists at an unchanged version.

- [axis: standards] `skills-src/discover/SKILL.src.md:98,101`,
  `skills-src/manager/SKILL.src.md:16-17`, `skills-src/usage-stats/SKILL.src.md:132-139,932-939`
  - Provider-specific text leaks into shared canon.
  Evidence: `discover` "Agent (subagent_type: Explore)" / "launch parallel
  Explore agents" is ungated and lands in `codex-skills/skills/discover/SKILL.md:90,93`
  (Codex has no Agent tool or Explore agent type). `manager` opens with "the
  Agent tool for launching parallel work" in both copies while its Codex
  execution steps (`:229-232,258-260`) correctly avoid naming a tool.
  `usage-stats` `{{#codex}}` says "Tool names use Codex canonical names" followed
  by a list byte-identical to the Claude list, and its ungated Setup ladder sends
  Codex to `.codex/hooks/logs/hooks-log.jsonl` - `codex-skills/package/install-manifest.json`
  ships no `scripts/hooks`, and `manager`/`usage-stats` "if present" references
  to `data/observations.jsonl` have no Codex producer either.
  Impact: Codex agents are told to use tools and read logs that cannot exist on
  their side.
  Recommendation: gate the Claude mechanics in `{{#claude}}` blocks with a Codex
  alternative, and either ship a Codex producer or gate the log references.

- [axis: standards] `skills-src/docs-sync/SKILL.src.md:263-272`,
  `skills-src/smart-test/SKILL.src.md:220`, `skills-src/manager/SKILL.src.md:327-330,612-613`
  - Stale or wrong instructions in generated skills.
  Evidence: docs-sync "one of three parallel drift validators… **Run all three
  together**" while `schema-validator` and `truthpack-drift` are retired and the
  table lists one skill. smart-test heading "How Smart Test Relates to QA and
  Build Gate" (`build-gate` retired) over a two-row table. manager
  `python scripts/task_manager.py analyze --json  # to get test command` -
  `analyze --json` output has no `commands` key (checked at runtime); manager
  "`/ship` classifies the tracker file as a 'warn' file" while
  `project.toml.template:45` ships `# warn = []` commented out.
  Impact: agents look for skills that do not exist and run a command that cannot
  yield what the comment promises.
  Recommendation: rewrite the docs-sync section, fix the heading, point manager at
  `project.toml` `[commands].test`, and describe ship's warn list as
  configuration.

- [axis: standards] `codex-skills/planning-contract.md:290-307`,
  `skills-src/browser-control/files-codex/CODEX-INTEGRATION.md:36` (uncommitted)
  and `:74`, `claude-skills/skills/verify/SKILL.md:11,57-58,66`,
  `claude-skills/skills/cc-workflow-builder/references/cc-workflow-studio-reference.md:10`
  - Machine-local content in portable-bucket files.
  Evidence: the Codex contract file (shipped as `contract_files`) names
  `D:\Development\plans\agent-registry.json` and
  `D:\Development\plans\scripts\build-agent-registry.ps1` and a local project
  roster; the Claude contract has no such section. The Codex browser integration
  doc hard-codes `node D:\DevHome\state\codex\skills\browser-control\cdp.mjs`
  while the canon uses `<skill-dir>/cdp.mjs` (`SKILL.src.md:89,138-146`);
  `browser-control` is workstation-bound by documented design (`README.md:96-97`,
  ports 9000/9001, `snd-desk`) yet sits in `optional_skills`, not
  `source_only_skills`. `verify` is entirely `D:\DevHome\shell\...` and a literal
  `C:\Users\Sev` `PSModulePath`. `cc-workflow-builder` names port 6282 and an
  `import-skill` skill that exists only in the gitignored `cc-workflow/` tree.
  Impact: portable exports carry paths that do not exist elsewhere; the package
  boundary in `AGENTS.md` ("machine-local … not a portable package entry") is
  not honoured for these.
  Recommendation: strip the registry section from the Codex contract (or make it
  a `<plans-root>` placeholder), use `<skill-dir>` in the integration doc, and
  bucket `browser-control`, `verify`, `cc-workflow-builder`, `chief-operator` as
  source-only/machine-local.

- [axis: standards] `codex-skills/skills/audit-gated-subagents/SKILL.md:113-115` -
  References an unbundled contract.
  Evidence: "emit JSONL events matching the existing run-observer contract" - no
  such contract in the skill, its `references/`, or either package; the only
  candidate tree `cc-workflow/*` is gitignored (`.gitignore:9`) and untracked.
  The skill ships in `optional_skills`.
  Impact: unsatisfiable instruction for any consumer; violates the
  skill-authoring rule that referenced support files must be bundled.
  Recommendation: bundle the contract under `references/` or drop the sentence.

- [axis: standards] `codex-skills/README.md:59-92`, `claude-skills/README.md:39-52,103-113,145-153`,
  `claude-skills/eval/README.md:11` - README, manifest, and eval surfaces disagree,
  and the contract tests cannot see it.
  Evidence: Codex main table seats `loop-master` (an `optional_skills` alias) in
  the default tier and has no row for `handoff` (a `default_skills` entry);
  `browser-control`, `docs-sync`, `smart-test` have no purpose-table row. Claude
  table lists 12 of 24 directories; the per-project install loop includes
  `skills/browser-control` and the global loop omits it with no note. Claude
  eval README claims "eval cases for all Claude skills" while
  `light-skill-cases.json` covers 11; `smart-test`, `usage-stats`, `handoff`,
  `browser-control`, `docs-sync` have zero cases in both packages and
  `codex-state-cleanup` (new) has none; `claude-skills/eval/README.md:67` requires
  cases before broadening the surface. `test_readme_install_examples_cover_manifest_skills`
  (both packages) only asserts the substring `skills/<name>` appears anywhere,
  which the install code fences satisfy.
  Impact: the human-facing catalogue is wrong in both packages and CI is green.
  Recommendation: generate the purpose tables from the manifest (or test them),
  fix the loop-master/handoff rows, align the two Claude loops, correct the eval
  README, and add the missing routing cases.

- [axis: standards] `skills-src/manifest.json:27` vs
  `claude-skills/skills/review-controller/SKILL.md:74-77,89-91,191-207` and
  `codex-skills/skills/review-controller/SKILL.md:85-109,124-125,238-257` - The
  declared fork reason does not cover the actual divergence.
  Evidence: Claude "Predict - write your 3 expected top findings … Post-wave check:
  all matched -> delegation added little" versus Codex "do not score a review by
  agreement with predictions"; Codex-only SHA-256 evidence manifest and freshness
  gates (0 hits for "freshness" or "external" in the Claude file, 4 each in
  Codex); different report sections; a 25-line Codex routing boundary against
  five siblings versus one Claude sentence. `Compare-ProviderSkillParity.ps1`
  only checks that a declared fork has a reason, never that the diff matches it.
  The 2026-08-30 Claude review deliberately deferred these changes to "its
  concurrent owner", so this is a known interim state - but `README.md:201`
  promises an "equivalent workflow contract".
  Impact: same-named skill, opposite methodology on one axis; parity tooling is
  blind to it.
  Recommendation: either reconcile the Claude copy with the 08-30 spec or widen
  the declared reason to name the methodological differences and the reconvergence
  plan.

- [axis: standards] `codex-skills/skills/verification-loop/SKILL.md:3`,
  `codex-skills/skills/audit-gated-subagents/SKILL.md:3`,
  `claude-skills/skills/chief-operator/SKILL.md`, `claude-skills/skills/verify/SKILL.md:3`
  + `claude-skills/agent-definitions/builder.md:24-25` - Overlapping skills with no
  boundary text.
  Evidence: verification-loop (build/lint/typecheck/test before handoff) never
  mentions `qa` or `smart-test` and neither mentions it; audit-gated-subagents has
  no "Do not use" against `parallel-agents-light`/`manager`/`delegate`;
  chief-operator never mentions `manager` and is outside the trigger-first test
  list. `builder.md` says "invoke the `verify` skill if available (else
  `superpowers:verification-before-completion`)" - the only `verify` is the
  DevHome-profile recipe, and `superpowers@claude-plugins-official` is `false`
  in `settings.json`, so the step silently does nothing for ordinary work; the
  bare name also collides with `manager verify` and telemetry-live-ops `verify`.
  Impact: mis-triggering between siblings; a builder verification step that
  resolves to nothing.
  Recommendation: add "Do not use" clauses on both sides of each pair; rename
  `verify` (e.g. `devhome-verify`) or point `builder.md` at `qa`.

- [axis: regression] `skills-src/memory-management/files-claude/scripts/verify_memory.py:40`
  (uncommitted) - The new gate misses the flat frontmatter form the paired tool
  supports, and ships without tests.
  Evidence: `re.search(r"^\s+type:\s*(\w+)", txt, re.M)` needs leading
  whitespace, so a top-level `type: user` is reported as `type=None`;
  `claude-skills/scripts/memory_audit.py:90-110` accepts both forms;
  `references/compress.md:70-77` makes both tools a joint pass criterion for
  `compress`. `grep -rl verify_memory claude-skills/tests codex-skills/tests` =
  empty; `claude-skills/CLAUDE.md` requires tests in the same change as CLI
  behaviour.
  Impact: false failures block `compress` on legacy-schema stores (fail-closed,
  not destructive); untested script in a pruning workflow.
  Recommendation: accept both forms (or state that only nested `metadata.type` is
  valid, in both tools) and add a fixture test before committing.

- [axis: regression] `claude-skills/agent-definitions/system-fixer.md:15-16` - The
  infrastructure-repair agent holds a false model of the machine layout.
  Evidence: "`~/.claude/skills` and `~/.claude/agents` are symlinks -> OneDrive:
  `C:\Users\Sev\OneDrive\common\common_dev\.claude\{skills,agents}` (synced
  across machines)". `readlink -f /c/Users/Sev/.claude/skills` ->
  `/d/DevHome/state/claude/skills`; the cited OneDrive path does not exist; the
  global `CLAUDE.md` states skills are machine-local. Mitigated only by the
  file's own line 21 ("verify the layout with `ls -la` / `readlink -f`"). Line 22
  uses `MAINDESK` (the SSH alias) as the machine name.
  Impact: a repair agent may believe a local edit propagated everywhere.
  Recommendation: replace with the DevHome junction layout from the global
  `CLAUDE.md`.

- [axis: regression] `claude-skills/scripts/hooks/safety_guard.py:117-123`,
  `claude-skills/scripts/hooks/README.md:10,38-40,49-60`,
  `claude-skills/scripts/hooks/settings-hooks.template.json` - The safety guard
  is neither registered nor a boundary, and the README describes a template that
  does not exist.
  Evidence: the template registers four observer hooks only - no PreToolUse
  block, no `safety_guard.py`, no `log_hook_event.py` (which `usage-stats`
  depends on); README §3 says the template uses `python` (it uses `python3` at
  lines 11/25/36/49). `safety_guard.py` inspects only `tool_name == "Bash"`; this
  machine sets `CLAUDE_CODE_USE_POWERSHELL_TOOL=1`, so commands arrive as
  `PowerShell` and are never checked; probed bypasses: `rm -r -f /`,
  `git checkout .`, `git branch --delete --force`, `Remove-Item -Recurse -Force`,
  `rmdir /s /q`; `git push --force-with-lease` is blocked (the safe variant);
  `MultiEdit`/`NotebookEdit` skip the protected-file check.
  Impact: a consumer following the README believes destructive commands are
  blocked and events are logged; neither is true.
  Recommendation: either register and harden the guard (PowerShell branch,
  normalised flags, allow `--force-with-lease`) or drop the "Safety" claims from
  the README; register `log_hook_event.py` if `usage-stats` is to work.

### Low

- [axis: regression] `claude-skills/scripts/hooks/*.py` - all six crash with a
  traceback and exit 1 on non-dict JSON stdin (`[]`), contrary to the README's
  fail-open principle; template matchers are narrow (`SessionStart: startup`
  only; `PostToolUse: Bash` misses `PowerShell`; `Edit|Write` misses
  `MultiEdit`/`NotebookEdit`); `async` is never set although the README
  recommends it; `safety_guard.py:73` `id_ed25519` alternation lacks the path
  anchor the `id_rsa` branch has.
- [axis: standards] `skills-src/qa/SKILL.src.md` (13 `[qa]` references) - the
  `[qa].*` and extended `[smoke-test].*` keys appear in no `project.toml.template`
  or `docs/config-reference.md` and are read by no runtime module;
  `claude-skills/project.toml.template` lacks the `[models]` section the Codex
  template and both config references have.
- [axis: standards] `skills-src/review/SKILL.src.md:281-283` - empty
  `{{#codex}}…{{/codex}}` block; `extracted-from`/`portable-since` frontmatter
  fields used by smart-test and usage-stats are not in the skill-authoring
  field list.
- [axis: standards] `skills-src/manager/SKILL.src.md` (626 lines),
  `skills-src/usage-stats/SKILL.src.md` (939 lines) - no `references/` or
  `examples/` despite the contract's progressive-disclosure rule;
  `test_manager_uses_progressive_disclosure` is a two-substring proxy.
- [axis: standards] `scripts/retired-skills.json` - lacks `dmux-workflows` and
  `wt-cli` (retired in the 2026-08-09 audit), so `Install-AgentSkills.ps1`
  never prunes them; `D:\DevHome\state\codex\skills\dmux-workflows` is still
  present (`Compare-AgentSkillRoots.ps1` Extra).
- [axis: standards] `README.md:117,127` documents retired `delegation-eval` as
  current; `claude-skills/agent-definitions/builder.md:30-31` and
  `research-scout.md` list retired `deep-research` in do-not-invoke lists.
- [axis: standards] `codex-skills/skills/codex-state-cleanup/SKILL.md` (untracked)
  - safe as written (no machine literals, `$CODEX_HOME` with junction handling,
  refuses broad roots, never VACUUMs an active DB); `tests/test_codex_state_cleanup_skill.py:39-46`
  does not pin "Re-scan each directory before recursive removal" (`:114-115`)
  or "Run `VACUUM` only when the integrity check passes" (`:135`); no eval
  case; the carve-out does not name hook-trust state explicitly.
- [axis: standards] `codex-skills/skills/loop-master/SKILL.md:22-27` - "two to
  four workstreams" contradicts `parallel-agents-light/SKILL.md:41` (2 default,
  3 max) in a skill that presents itself as a pure alias.
- [axis: regression] `claude-skills/plan-schema.md:30` vs `codex-skills/plan-schema.md:30`
  - the `planner_kind` enum differs between the two runtimes
  (`refactor-planner` vs `planner-refactor`); each doc matches its own CLI, so
  this is runtime divergence, not a doc error.
- [axis: standards] `skills-src/handoff/SKILL.src.md:106` routes "correct or
  prune the state store" to `memory-management`, whose Codex text (`:70-73`)
  says the Remember handoff store is outside its queue except for an explicitly
  named target - the boundary works but is not stated on the handoff side.
- [axis: regression] `codex-skills/local-hooks/devhome-lifecycle/hooks/Invoke-HandoffRelay.ps1:1058`
  - `.Replace('--', '- -')` mangles any workspace path containing `--` (the live
  header for this repo is unaffected because the real path has none);
  `Write-HandoffFailureResult` (`:79-85`) declares a mandatory `$Code` it never
  uses; `Complete-HandoffDraft` (`:1221-1233,1296-1323`) mixes 4- and 8-space
  indentation around the conflict branches (parse verified correct).
- [axis: regression] `scripts/tests/AiEnvironment.Tests.ps1:749` - "bounds a hung
  provider command" failed once in the full gate run (PID reuse: the recorded
  child PID matched a concurrent `python` process) and passed in isolation; a
  flake, not a hook or skill defect, but it is in `Test-ReleaseReadiness.ps1`.
- [axis: standards] `claude-skills/README.md` and `claude-skills/CLAUDE.md:53-67`
  never mention copying `scripts/hooks/` although the manifest ships it; the
  hooks README has its own install section.

### Rejected after verification (not findings)

- Hooks lane claimed the Codex PreToolUse matcher
  `^(?:Bash|apply_patch|Edit|Write)$` can never match because rollout logs record
  `custom_tool_call.name = exec`. Rejected: the installed `codex.exe` 0.151.0
  string table carries the hook wire vocabulary
  (`hook_event_name … tool_name tool_input tool_use_id PreToolUseDecisionWire`)
  and the literal `Bash` immediately adjacent to `Command blocked by PreToolUse
  hook:`, i.e. the hook layer reports shell execution under the Claude-compatible
  name, independent of the model-facing tool name. Residual: no live payload was
  captured; a one-off live check (run a guarded command in Codex and look for
  "Command blocked by PreToolUse hook") would close it.
- Canon lane claimed `codex-skills/plan-schema.md:30` documents a wrong
  `planner_kind` value. Rejected: `codex-skills/scripts/task_manager.py plan
  create --help` enumerates `{planner,planner-refactor,manager-go}`; recorded as
  the Low runtime-divergence note above.
- Canon lane rated `browser-control`'s machine identity and ports High. Downgraded
  to the Medium machine-local item: the workstation binding is documented design;
  the defects are the hard-coded path in the Codex integration doc and the
  `optional_skills` bucket.

## Verification

- `scripts/Build-ProviderSkillPackages.ps1 -Check` - pass (47 files across 16 skills)
- `scripts/Compare-ProviderSkillParity.ps1 -FailOnUndeclaredFork` - pass (16 generator-enforced pairs, 2 declared forks)
- `scripts/Test-ReadyPackages.ps1 -StrictSkillManifest -SkipExportSmoke -SkipInstallerSmoke` - **fail** (7 unmanifested claude-skills directories; 26 Codex / 16 Claude counted)
- `scripts/Update-ReadmePackageCounts.ps1 -Check` - pass
- `scripts/Compare-AgentSkillRoots.ps1 -Provider Both -IncludeExtra` - 7 Claude Stale, 8 Claude Extra; 4 Codex Stale, 2 Codex Missing (both uncommitted additions), 18 Codex Extra incl. `dmux-workflows`
- `claude-skills`: `pytest tests/test_skill_docs_contract.py` - 18 passed; `tests/test_memory_audit.py` - 32 passed
- `codex-skills`: `pytest tests/test_skill_docs_contract.py tests/test_codex_state_cleanup_skill.py tests/test_usage_stats_window.py tests/test_review_controller_skill.py tests/test_local_plugin_contract.py` - 40 passed, 5 subtests
- `Invoke-Pester DevHome-Hooks.Tests.ps1 + DevHome-PluginSync.Tests.ps1` - 70 passed
- `python -B -m unittest codex-skills/local-hooks/devhome-lifecycle/tests/test_remember_adapter.py` - 77 passed
- `Invoke-Pester scripts/tests/Install-AgentSkills.Tests.ps1 + AiEnvironment.Tests.ps1` - 38 passed, 1 failed (`bounds a hung provider command`); re-run in isolation - passed
- `Sync-DevHomeCodexHooks.ps1 -Check` - CURRENT (6 files); `Install-DevHomeClaudeHandoffRelay.ps1 -Check` - CURRENT (2 files); `Sync-DevHomeLifecyclePlugin.ps1 -Check` - STALE (4 files differ, version 0.3.0 both sides)
- `git diff --check` - clean (CRLF warnings only)
- Runtime probes (hooks lane, scratchpad only, `CLAUDE_PROJECT_DIR`/`CODEX_HOME` pointed at scratch): all six Claude hook scripts with real-shaped, renamed-key, empty, `[]`, malformed, and missing-`tool_name` stdin; `Invoke-HandoffRelay.ps1` pass 1/pass 2 timing on three transcript sizes (worst 1.53 s against the 5 s budget); `python scripts/task_manager.py analyze --json` key inspection; both `task_manager.py plan create --help` enums
- Not run: full pytest suites (766/694 at the 08-09 audit; out of scope for a skills/hooks review), export/installer smoke, any installer or sync without `-Check`, any live Codex session

## Coverage Notes

- Files reviewed deeply: all 16 `skills-src/*/SKILL.src.md` and their `files*/`
  support files (incl. `cdp.mjs`, `CODEX-INTEGRATION.md`, `verify_memory.py`,
  `compress.md`, `audit-tool.md`, `codex_usage_window.py`, deep-audit references);
  all 8 Claude-owned skills with support files and all 6 `agent-definitions`; all
  11 Codex-owned skills with support files and `agents/openai.yaml`; the generated
  `SKILL.md` copies at every provider-block site; all six
  `claude-skills/scripts/hooks/*.py`, the hooks README and template;
  `codex-skills/local-hooks/devhome-lifecycle/` `hooks.json`, `hooks/hooks.json`,
  `plugin.json`, `Invoke-DevHomeHook.ps1`, `Invoke-HandoffRelay.ps1` (1412
  lines), `Invoke-RememberClaude.cmd`, both installers, both Sync scripts,
  `README.md`, `skills/devhome-lifecycle/SKILL.md`; both install manifests,
  `skills-src/manifest.json`, `release-manifest.json`, `retired-skills.json`, both
  contract tests, `test_codex_state_cleanup_skill.py`,
  `test_review_controller_skill.py`, `test_usage_stats_window.py`; both package
  READMEs, root README count section, both `planning-contract.md`,
  `plan-schema.md`, `project.toml.template`; `D:\DevHome\state\claude\settings.json`
  and `D:\DevHome\state\codex\hooks.json` (read-only).
- Files sampled: `Invoke-RememberAdapter.py` (layout, routing, containment,
  `main()`, and the full uncommitted diff); `Sync-DevHomeLifecyclePlugin.ps1`
  (`-Check` gate, `Get-PayloadDrift`); `DevHome-Hooks.Tests.ps1`,
  `DevHome-PluginSync.Tests.ps1`, `test_remember_adapter.py` (test-title
  enumeration and spot reads); `task_manager.py` (help surfaces only);
  `docs/config-reference.md`, `docs/file-map.md`, `skill-portability-notes.md`,
  eval case JSON (parsed for coverage, not read as prose); root README beyond
  the count section.
- Excluded: runtime Python under `scripts/analysis` and `scripts/task_runtime`
  (not skills or hooks); `scripts/AiEnvironment` module body (its tests ran);
  the imported reference tree `skills/`, `Deep-Audit/`, `cc-workflow/`,
  `claude-memory-manager/`; Claude plugin-contributed hooks
  (`wt-agent-hooks@wt-local`, `remember`) outside this repo.

## Skill Scorecard

Purpose clarity / trigger quality / operational quality / portability, 1-5.
Machine-local-by-design skills are scored on their declared scope.

| Skill | Owner | P | T | O | Port | Note |
|---|---|---|---|---|---|---|
| deep-audit | canon | 5 | 5 | 5 | 5 | clean |
| diagnosing-bugs | canon | 5 | 5 | 5 | 4 | clean; new hook-failure section solid |
| handoff | canon | 5 | 5 | 4 | 5 | state-store routing boundary (Low) |
| ship | canon | 5 | 4 | 5 | 5 | clean |
| review | canon | 5 | 4 | 5 | 4 | dead empty codex block (Low) |
| skill-authoring | canon | 5 | 4 | 4 | 5 | field list incomplete (Low) |
| qa | canon | 5 | 4 | 4 | 4 | undocumented `[qa]` config (Low) |
| delegate | canon | 4 | 4 | 4 | 4 | clean; README still lists `delegation-eval` |
| memory-management | canon | 5 | 4 | 3 | 5 | untested `verify_memory.py` gate (Medium, uncommitted) |
| docs-sync | canon | 4 | 4 | 3 | 4 | stale "three validators" (Medium) |
| smart-test | canon | 5 | 4 | 3 | 4 | "Build Gate" heading; no eval case |
| planner | canon | 5 | 4 | 3 | 3 | dangling conflict-zone procedure on Codex (High) |
| discover | canon | 4 | 4 | 3 | 2 | Agent/Explore leak into Codex (Medium) |
| manager | canon | 5 | 4 | 4 | 2 | Agent-tool leak, wrong `analyze` comment, 626 lines flat |
| usage-stats | canon | 4 | 4 | 4 | 2 | Codex tool-name/log claims, 939 lines flat, no eval |
| browser-control | canon | 4 | 4 | 4 | 2 | hard path in Codex doc; wrong bucket |
| review-controller (Claude) | Claude | 5 | 5 | 4 | 5 | unmanifested; undeclared fork divergence |
| codebase-design | Claude | 5 | 4 | 4 | 5 | unmanifested; clean |
| docs-clean | Claude | 5 | 5 | 4 | 5 | unmanifested; clean |
| resolving-merge-conflicts | Claude | 5 | 4 | 4 | 5 | unmanifested; clean |
| cc-workflow-builder | Claude | 5 | 4 | 5 | 2 | port + gitignored dependency |
| verify | Claude | 3 | 2 | 4 | 1 | machine-local; name collision |
| chief-operator | Claude | 4 | 3 | 3 | 1 | retired route; hard-coded paths |
| telemetry-live-ops (both) | fork | 5 | 4 | 2 | n/a | dead default repo path (High) |
| review-controller (Codex) | Codex | 5 | 5 | 5 | 4 | most rigorous skill in the repo |
| codex-state-cleanup | Codex | 5 | 5 | 5 | 5 | new; safe; thin test pins |
| repo-conventions | Codex | 4 | 4 | 4 | 5 | has route-out text |
| verification-loop | Codex | 5 | 4 | 5 | 5 | no boundary vs qa/smart-test |
| audit-gated-subagents | Codex | 5 | 4 | 4 | 3 | unbundled run-observer contract |
| parallel-agents-light | Codex | 5 | 4 | 4 | 5 | clean; no eval case |
| documentation-lookup | Codex | 5 | 4 | 4 | 5 | clean |
| exa-search | Codex | 5 | 4 | 4 | 5 | clean |
| mcp-server-patterns | Codex | 5 | 4 | 4 | 5 | clean |
| loop-master | Codex | 4 | 3 | 3 | 5 | alias with stray guidance; misfiled in README |
| devhome-lifecycle (plugin skill) | local | 5 | 4 | 4 | n/a | honest about adapter blockers; repeats orphan claim |

Hooks: the Codex/Handoff Relay stack is well-engineered (verified read-only
`-Check` paths, machine-identity gating before mutation, Job Object containment,
5 s budget with 1.5 s worst case, 70 Pester + 77 unittest green) but has the
write-contention and quarantine gaps above; the Claude portable hook set does
not function as shipped.

## Open Questions

- Which of the seven unmanifested Claude skills are meant to ship, and which are
  backups of machine-local state that belong outside the package?
- Is `browser-control` intended to stay in `optional_skills` given its
  documented workstation binding, or should it join `telemetry-live-ops` in
  `source_only_skills`?
- Should the Claude `review-controller` be reconciled with the 2026-08-30 Codex
  spec now, or should the declared fork reason be widened to describe the interim
  divergence?
- Do the observation-log hooks still have a consumer worth fixing, or should
  `manager`/`usage-stats` drop the `observations.jsonl` and `hooks-log.jsonl`
  paths and the hook directory be retired?

Recommended next command: fix the High items directly (they are small, targeted
edits), then `/qa` for the hook fixtures and `Test-ReleaseReadiness.ps1` before
`/ship`. The uncommitted work on this branch should not be committed until the
`verify_memory.py` test gap and the plugin cache/version drift are addressed.
