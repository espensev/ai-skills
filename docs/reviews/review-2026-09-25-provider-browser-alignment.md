# Provider evaluation and browser-policy alignment — 2026-09-25

Controller `snd-desk` (v2 verifier VERIFIED 2026-09-25T03:14:50Z). Follow-up
to [the skills-vs-data audit](review-2026-09-25-skills-vs-data-audit.md),
which stays frozen apart from a pointer to §7 here. Method: one read-only
lane per provider family (Claude mechanisms, Claude plugin caches, Codex,
Grok, Kimi, Qwen/Qoder, IDE agents, shared agents root, dormant sweep), each
finding adversarially verified. The fixes were then applied inline, one file
at a time: backup, surgical edit, parse check. Nothing was deleted; the user
removed `E:\dUPEbIN` by hand before this pass.

## 1. Policy

The only agent browser is the DevHome Opera profile set: devbrowser on
`127.0.0.1:9000`/`9001` plus providerbrowser. It is driven by the
`browser-control` skill (`cdp.mjs`) or by `chrome-devtools-mcp` with an
explicit `--browser-url`. Everything else is off: Playwright MCP,
browser-use, browser-harness, claude-in-chrome, provider in-app browsers,
web bridges into the real Chrome, and bare (self-launching)
`chrome-devtools-mcp`. The user's real Chrome is never an agent target, and
that includes its remote-debugging port 9222.

## 2. Provider inventory

| Provider | State | Off-policy browser surfaces found |
|---|---|---|
| Claude Code 2.1.282 | active | `browser-use@synced` (account sync, uvx in every session); bare `chrome-devtools-mcp` 1.9.0 plugin server; `playwright` user MCP on 9001 (4 real calls 09-24); synced skills `chrome-browser`, `built-in-browser` |
| Codex CLI 0.156.1 | active | `playwright` MCP live; `chrome-devtools` config server pointed at dead 9223; `chrome-devtools-mcp@claude-plugins-official` plugin enabled; `node_repl` browser-use host; `browser-harness` skill re-enabled (its disable entry was lost, used 09-21); in-app/browser-use feature flags on by default; desktop import sync pulls Claude plugins in |
| Codex Chrome extension | active | installed and enabled in the real Chrome, native host `com.openai.codexextension` |
| Grok CLI 1.0.41 | active | inherits Claude `mcpServers`, plugins and skills through `[compat.claude]`; it honours Claude's `enabledPlugins` for plugin skills but not `deniedMcpServers` or `skillOverrides`; ran Playwright on 9001 (09-24) and bare chrome-devtools-mcp 1.8.0 (09-11) |
| Kimi Code 2.0.2 / desktop 3.2.14 | active | `kimi-webbridge` plugin plus WebBridge daemon on 10086 plus Chrome extension with `debugger` on all URLs, in the real Chrome; desktop `InAppBrowser` tool; a subagent launched Playwright Edge 09-25 |
| Qwen Code 0.24.2 | dormant | bundled `browser-use` skill not disabled |
| qodercli 1.1.63 | active | none of its own (reads `~/.agents/skills`) |
| Qoder IDE 1.32.0 | active | built-in Browser MCP enabled (UI toggle only) |
| ZCode 3.14.3 | active | 4 browser plugins enabled (`chrome-devtools-mcp`, `playwright`, 2× `browser-use`); Playwright MCP on 9001; `playwright` and `browser-harness` skill junctions |
| VS Code 1.138 Copilot | active | `workbench.browser.enableChatTools` defaults to true |
| Cline 3.0.64 | active | none (`browser_action` off by default) |
| aider, bailian, kilocode, kimi-home, kimi-work, openclaw, qoderwork, qoder-cn, superdesign, serena, ollama, grokbot | dormant / not installed | none active |
| Claude Desktop (MSIX `Claude` 2.9939.2.0) | installed | not evaluated in this pass |
| Real Chrome | user browser | CDP on 9222 user-enabled; Claude, Codex and Kimi extensions installed and enabled |

## 3. Configuration changes applied

Each file was backed up next to itself (suffix `.bak-browseralign-20260925`
unless noted) and parse-validated after the edit.

- **Claude** `D:\DevHome\state\claude\settings.json`:
  `enabledPlugins` `browser-use@synced` and `chrome-devtools-mcp@synced` →
  false; `skillOverrides` `anthropic-skills:chrome-browser` and
  `anthropic-skills:built-in-browser` → off; new `deniedMcpServers` for
  `plugin:chrome-devtools-mcp:chrome-devtools`, `playwright` and
  `claude-in-chrome`. The deny list keeps the definitions and blocks the
  spawn; `syncClaudeAiPlugins:false` was avoided because it trashes synced
  plugins.
- **Claude** `.claude.json`: user MCP `chrome-devtools-opera` =
  `npx chrome-devtools-mcp@1.9.0 --browser-url=http://127.0.0.1:9001`. 1.9.0
  is pinned because the 1.7.0/1.8.0 npx caches lost their lighthouse bundle
  in the wipe. The `playwright` definition stays, denied.
- **Codex** `D:\DevHome\state\codex\config.toml`: `[features]`
  `in_app_browser`, `browser_use`, `browser_use_external`,
  `browser_use_full_cdp_access` = false; `[mcp_servers.chrome-devtools]` →
  1.9.0 with `--browser-url=http://127.0.0.1:9001`, keeping the name
  because it shadows the plugin servers; `playwright` and `node_repl`
  `enabled = false` (the node_repl path is untouched);
  `chrome-devtools-mcp@claude-plugins-official` plugin off;
  `external-agent-import-sync-enabled = false`; `[[skills.config]]` disables
  for `codex\skills\browser-harness` and the remote
  `build-web-apps/0.1.2/.../frontend-testing-debugging`.
- **Grok** `D:\DevHome\state\grok\config.toml`: `grok mcp disable playwright`
  (`disabled_mcp_servers`); `[plugins] disabled` += `chrome-devtools-mcp`,
  `browser-use`, `playwright`; new `[skills] disabled = ["chrome-browser",
  "built-in-browser", "web-perf"]`.
- **Kimi Code** `D:\DevHome\state\kimi-code\plugins\installed.json`:
  `kimi-webbridge` `enabled: false`. The desktop app re-enables it at launch
  (KIMI-02), so the desktop toggle in §6 is still needed.
- **ZCode** `D:\DevHome\state\zcode\cli\config.json` (backup
  `config.json.bak-20260925-browser-policy`): the 4 browser plugins off;
  `playwright` MCP `enabled: false`; `chrome-devtools` repointed to 1.9.0 on
  9001 and enabled; skill toggles `{"enable": false}` for the `playwright`
  and `browser-harness` SKILL.md paths. ZCode was running only because the
  evaluation's `zcode --version` launched the GUI (10 processes); that tree
  was closed first.
- **Qwen** `D:\DevHome\state\qwen\settings.json`: `skills.disabled =
  ["browser-use"]` (key confirmed in the bundled 0.24.2 settings docs).
- **VS Code** `%APPDATA%\Code\User\settings.json`:
  `"workbench.browser.enableChatTools": false`.

## 4. Restores applied (create-only)

- **Claude orphan backup.** Claude Code's cleanup deletes plugin version
  folders 14 days after they get `.orphaned_at`; the first batch was due
  2026-09-25T14:48Z. All 212 marked folders (30,784 files, 126 MB) were
  copied to `D:\DevHome\state\backups\claude-plugin-orphans-20260925\`, with
  a manifest. File counts match.
- **Claude `cloudflare` 1.0.0** (6 files): 3 from git blobs in the
  `temp_git_1789971483781_7bntg0` clone, 3 from
  `D:\DevHome\state\config\agents\skills`. Every file matches its expected
  blob (`7a4a3ea2`, `a9d05e14`, `06fdbbd4`, `07d4dbbe`, `53c770fb`,
  `2ac2df70`).
- **Claude `frontend-design-audit` 1.0.0** (14 files): extracted with
  `git -c core.autocrlf=false archive 40c9a5f` and `tar -k`. All 14 match
  the tree via `git hash-object --no-filters`.
- **Claude `chrome-devtools-mcp` 1.9.0 `chrome-devtools-cli`**: left absent
  on purpose; that skill drives a self-launched Chrome.
- **Codex `documents` / `presentations` / `spreadsheets` 26.819.11345**:
  4/35/4 missing files copied from the same-version runtime copy in
  `D:\DevHome\state\cache\codex-runtimes\codex-primary-runtime\plugins\openai-primary-runtime\plugins\`.
  All three trees now match it file for file. `template-creator` has no
  copy anywhere and needs a Codex reinstall.
- **Shared `~/.agents/skills`** (`D:\DevHome\state\agents\skills`):
  - The 14 missing runtime files were copied from `codex-skills`:
    `scripts/analysis` ×3, `scripts/task_runtime` ×7, `task_manager.py`,
    `skill_feedback_loop.py`, `planning-contract.md` and `plan-schema.md`.
  - The 8 hollow skills (10 files) were repaired with
    `Install-AgentSkills.ps1 -Provider Codex -SkillNames deep-audit,discover,manager,memory-management,planner,qa,repo-conventions,usage-stats -CodexTargets …`.
    The dry run showed no removals.
  - `browser-control`, `handoff` and `diagnosing-bugs` were refreshed with
    `-SkillNames … -Force` after backups to
    `D:\DevHome\state\backups\agents-skills-{browser-control,drift}-20260925\`.
  - As a result, Grok, Kimi, Copilot CLI, qodercli and ZCode now read the
    current `browser-control` with the providerbrowser lane, and Codex lists
    `discover`, `manager` and `memory-management` again.
  - Grok ranks `~/.agents` above `~/.claude/skills`, so it now uses the
    Codex-flavoured copies of these skills rather than the Claude fallbacks.

## 5. Verification

- Fresh `claude -p "reply ok"` process tree: only
  `chrome-devtools-mcp@1.9.0 --browser-url=http://127.0.0.1:9001` and
  `kimi-cu`, with no uvx browser-use, no `@playwright/mcp` and no bare
  chrome-devtools-mcp. `claude mcp list` shows `chrome-devtools-opera`
  connected and no playwright.
- `claude plugin list --json`: `browser-use@synced`, `browser-use`, and
  `playwright` disabled.
- `codex mcp list`: `chrome-devtools` enabled (9001), `node_repl` and
  `playwright` disabled. `codex features list`: the four browser flags are
  false.
- `grok mcp doctor`: playwright "disabled in config". `grok inspect`:
  `chrome-browser`, `built-in-browser` and `web-perf` are `[disabled]`, and
  `browser-control` resolves to the refreshed `~/.agents` copy.
- `Install-AgentSkills.ps1 -Provider Codex -CodexTargets D:\DevHome\state\agents\skills -Check`:
  the only remaining findings are `delegate` (drifted, left alone: the
  installed copy is newer than the source and carries local model routing)
  and `codex-state-cleanup` and `review-controller` (never installed in
  this root; see §6).
- Every edited TOML/JSON file re-parses.

## 6. Left for the user

Real-Chrome and app-UI settings (not changed from here):

1. Chrome remote debugging on 9222: turn it off at
   `chrome://inspect/#remote-debugging`.
2. Kimi: turn off the desktop Work-settings WebBridge toggle and
   Permissions → Browser, and disable (not remove) the Kimi Chrome
   extension.
3. Disable the Codex Chrome extension, and the Claude extension
   `fcoeoabgfenejglbffodgkkbkcdhcgfn` (enabled in Chrome Default, Chrome
   Profile 2 and Edge Default; Claude Code's side is already denied).
4. Qoder IDE: Integrations → Browser Run Mode → Disabled for Editor and
   Quest. `/browser` still bypasses this.

Security:

5. Rotate the Qwen DashScope key and the Z.ai key. Evaluation subagents read
   `qwen\settings.json` and `Code\User\settings.json` unfiltered, so both
   plaintext values are now in local subagent transcripts. The superdesign
   `config.json` also holds a plaintext key.

Decisions:

6. Kimi Remember-bridge hooks have been missing from Kimi Code's
   `config.toml` since 09-17/19. They were wired on Kimi 0.41; the 2.0.2
   format may differ, so re-wire them deliberately rather than restoring the
   old block.
7. `superpowers` is still enabled in Kimi and ZCode while it is parked in
   Claude. kimi-cu is registered twice in Kimi Code.
8. Qoder `product-design@local` cache lost 79 files; an intact copy is in
   `~/.qoderwork`. Restore needs a yes.
9. `review-controller` and `codex-state-cleanup` are absent from the shared
   root: packaging decision §5.3 of the audit is still open.
10. The Remember-bridge `-Check` for Grok fails because the installed bridge
    is ahead of its repo, which is an upstream fix. Separately,
    `grok inspect` lists hooks from the official `remember` 0.33.0 plugin
    (disabled in Claude) and from `superpowers`/`hookify`. Recent session
    logs show only the native `hooks\remember.json` bridge hooks and the
    compat Stop hook firing, so the listing does not look like live double
    capture.
11. EaseUS DupFiles Cleaner is still installed.
12. Merge of `fix/ai-skills-online-followups-20260825` to `main`.

## 7. Corrections to the 09-25 audit

- §1 (line 27) and §5.1 (line 176): the user deleted `E:\dUPEbIN`; drop it
  from the exclusion list.
- §1 table (line 44) and §5.2 (lines 184–185): "no pristine local copy" is
  wrong. The Codex runtime cache holds the same version, and
  documents/presentations/spreadsheets were restored from it. Only
  `template-creator` needs a reinstall. The Codex
  `chrome-devtools-mcp@claude-plugins-official` plugin is now disabled, so
  it needs no re-fetch.
- §5.2 (Claude side): `cloudflare` was restored from local blobs and
  config copies with no reinstall (a reinstall would fetch a different
  commit). `chrome-devtools-mcp`'s missing `chrome-devtools-cli` stays
  absent by policy.
- §3 (lines 111–113): `[[skills.config]] enabled=false` does remove that
  path from the Codex catalog. The heavily used skills kept working because
  they loaded from their un-disabled `~/.agents/skills` copies (catalog
  root r1), which is also why `discover`, `manager` and `memory-management`
  vanished when those copies were hollowed.
- §5.4: settled. Playwright is off in every provider, and `kimi-cu` stays.
- §5.5: the synced plugin id is `browser-use@synced`, and a local
  `enabledPlugins` false disables it (verified in a fresh session).
- §5.7: settled as "restore" (§4 above), including the Grok flavour switch.
