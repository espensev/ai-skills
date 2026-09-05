# Remember bridge for Grok and Kimi Code

This directory is the source authority for the machine-local bridge that lets
the Grok CLI and Kimi Code CLI run the upstream Claude Remember plugin
(pinned checkout at `D:\DevHome\state\remember\artifacts\remember-current`,
0.27.0 at `1af50ef`) on verified controller `snd-desk`. The installed copy
lives under `D:\DevHome\state\remember\bridge\bin`; hook commands in both
hosts point at that copy, never at this checkout.

The package is source-only and stays out of `release-manifest.json` and
`codex-skills/package/install-manifest.json`. Claude Code and Codex do not use
it: Claude loads `remember@remember-pinned`, Codex loads
`remember@remember-dev`, both straight from the pinned checkout.

## Why a bridge

Remember at `1af50ef` understands two hook payload shapes and two transcript
envelopes: Claude Code and Codex (`pipeline/host.py`). Grok sends camelCase
payloads and writes `sessions/<url-encoded cwd>/<uuid>/chat_history.jsonl`;
Kimi sends `session_<uuid>` ids and writes `agents/main/wire.jsonl`. Neither
host lets the memory block from `SessionStart` stdout reach the model. The
bridge closes those three gaps without forking Remember.

## What one invocation does

`Invoke-RememberBridge.py` is stdlib-only Python 3, invoked per hook event as

```text
py -3 D:\DevHome\state\remember\bridge\bin\Invoke-RememberBridge.py --host grok|kimi --event <Event>
```

with the host's native payload on stdin. In order it:

1. Normalises the payload (camelCase to snake_case, Kimi `session_` prefix
   stripped, id lower-cased) and resolves the project directory from `cwd`,
   `workspaceRoot` or `CLAUDE_PROJECT_DIR`.
2. Locates the host transcript by session id and appends the new complete
   lines, translated into the Claude Code envelope, to the mirror
   `<bridge_root>\<host>\projects\<slug>\<session_id>.jsonl`. The native byte
   offset is kept in `<bridge_root>\<host>\state\<session_id>.json`; Kimi
   offsets only advance at a step boundary so a half-written assistant turn
   is never split across two runs.
3. Runs `scripts/<event>-hook.sh` from the pinned checkout through Git Bash
   with the environment Claude Code would provide: `CLAUDE_PLUGIN_ROOT` and
   `PLUGIN_ROOT` (the checkout), `CLAUDE_PROJECT_DIR` (the project), `HOME`
   when unset (so `~/.remember/config.json` is read). `CLAUDE_CONFIG_DIR` is
   left alone: the nested `claude` summarizer reads its credentials from it,
   and pointing it at the bridge root made every save fail with "Not logged
   in". Stdin is a flat snake_case payload with `hook_event_name`,
   `session_id`, `transcript_path`, `cwd`, and `source` or `reason` where the
   event carries one. `PostToolUse` and `SessionEnd` always name the mirror
   as `transcript_path`; when no mirror exists they skip upstream entirely,
   because without that path Remember falls back to the newest transcript
   under `~/.claude/projects/<slug>/` and would save a Claude Code session
   under the Grok or Kimi session id. On Grok these two capture hooks are
   launched detached (see "Host process trees" below); everything else runs
   in-tree because the bridge needs its stdout.
4. Handles recall. `SessionStart` stdout is cached at
   `<bridge_root>\<host>\inject\<session_id>.md` and printed nowhere. Grok
   receives it once, on the first `PreToolUse` of the session, as
   `hookSpecificOutput.additionalContext` (clipped at 9,500 characters; Grok
   clips at 10,000). Kimi receives it once, ahead of upstream's own prompt
   line, on the first `UserPromptSubmit`. Later calls exit 0 without work.
5. Writes one `[bridge]` line per event to `<bridge_root>\<host>\logs\bridge.log`
   and, when the Remember user config resolves a store, into that store's
   `logs\memory-YYYY-MM-DD.log` next to upstream's own lines.

Every path exits 0 so the host is never blocked. In-tree, the bridge waits
only for the direct `bash` child (up to 300 s, never killed) and leaves
upstream's disowned `SessionEnd` flush alone; stdout and stderr go through
temporary files so a grandchild holding the pipe cannot stall the hook.
Detached, it waits only for the WMI launcher (about a quarter of a second)
and logs the new process id.

## Host process trees

Probed on 2026-09-05 with a hook that spawns sleepers of every kind and
records its own job-object state:

- **Grok 1.0.13** runs each hook through `pwsh.exe` inside a Windows Job
  Object and terminates that job the moment the hook returns. Plain
  children, `CREATE_BREAKAWAY_FROM_JOB | DETACHED_PROCESS` children and
  double-forked grandchildren all died within a second, mid-session as well
  as at exit; the store's `logs\autonomous\save-*.log` files held only the
  `[post-tool] save triggered` header. Only a process created through WMI
  `Win32_Process.Create` (parent `WmiPrvSE.exe`, outside the tree and the
  job) survived. The bridge therefore launches `post-tool-hook.sh` and
  `session-end-hook.sh` that way on Grok: it writes the payload, a
  three-line launcher and a `.ps1` under `<bridge_root>\grok\tmp\detached\`
  (pruned after two days), passes the full environment block explicitly
  (WMI replaces the block rather than extending it), hides the console with
  `ShowWindow=0`, and appends upstream's stdout/stderr to
  `<bridge_root>\grok\logs\detached.log` (rotated at 2 MB). `SessionStart`
  still runs in-tree because its stdout is the memory block, so the
  background work that hook starts itself (the `features.recovery` force
  save, `run-consolidation.sh`) does not survive under Grok; recovery is off
  in this store's config and consolidation also runs from Claude sessions.
- **Kimi Code 0.41.0** runs hooks through `cmd.exe` and lets every child
  outlive both the hook and the session, so Kimi stays in-tree. Kimi's `-p`
  mode never fires `SessionEnd`; only an interactive session flushes at exit.

`REMEMBER_BRIDGE_DETACH=always|never` overrides the per-host default for
both capture events. A failed detached launch falls back to the in-tree run
and records `detach_error=` in the bridge log.

A bare invocation prints the resolved configuration (plugin root, bridge
root, bash, host homes, Remember config, data directory, hook script
presence) and exits 0.

## Install

```powershell
.\codex-skills\local-hooks\remember-bridge\Install-RememberBridge.ps1
.\codex-skills\local-hooks\remember-bridge\Install-RememberBridge.ps1 -Check
```

The installer verifies `snd-desk` through the installed v2 machine verifier
before writing, refuses filesystem roots and any target other than
`D:\DevHome\state\remember\bridge` unless `-AllowTestOnlyTargetRootOverride`
is set, copies `Invoke-RememberBridge.py` to `<TargetRoot>\bin`, keeps a
timestamped copy of a drifted installed file under `<TargetRoot>\bin-backups`,
and reports `INSTALLED`, `UNCHANGED` or (with `-Check`) `CURRENT` as a
`[pscustomobject]` that includes the bare-invocation probe of the installed
copy. `-Check` never verifies the machine and never writes; drift throws.

## Host wiring

Grok, global hooks file `D:\DevHome\state\grok\hooks\remember.json` (global
hooks are always trusted):

```json
{
  "hooks": {
    "SessionStart": [{ "hooks": [{ "type": "command", "command": "py -3 D:/DevHome/state/remember/bridge/bin/Invoke-RememberBridge.py --host grok --event SessionStart", "timeout": 20 }] }],
    "UserPromptSubmit": [{ "hooks": [{ "type": "command", "command": "py -3 D:/DevHome/state/remember/bridge/bin/Invoke-RememberBridge.py --host grok --event UserPromptSubmit", "timeout": 10 }] }],
    "PreToolUse": [{ "matcher": ".*", "hooks": [{ "type": "command", "command": "py -3 D:/DevHome/state/remember/bridge/bin/Invoke-RememberBridge.py --host grok --event PreToolUse", "timeout": 5 }] }],
    "PostToolUse": [{ "matcher": ".*", "hooks": [{ "type": "command", "command": "py -3 D:/DevHome/state/remember/bridge/bin/Invoke-RememberBridge.py --host grok --event PostToolUse", "timeout": 10 }] }],
    "SessionEnd": [{ "hooks": [{ "type": "command", "command": "py -3 D:/DevHome/state/remember/bridge/bin/Invoke-RememberBridge.py --host grok --event SessionEnd", "timeout": 15 }] }]
  }
}
```

Add `[plugins] disabled = ["remember"]` to Grok's `config.toml` so none of the
Remember copies Grok discovers in the Claude plugin cache can be enabled next
to the bridge. Do not wire `Stop`: the Handoff Relay owns it.

Kimi, `[[hooks]]` tables appended to `D:\DevHome\state\kimi-code\config.toml`
(the file also holds a provider API key: append tables only, keep a dated
`.bak`, never print or copy it):

```toml
[[hooks]]
event = "SessionStart"
command = "py -3 D:/DevHome/state/remember/bridge/bin/Invoke-RememberBridge.py --host kimi --event SessionStart"
timeout = 30
```

and the same for `UserPromptSubmit` (15), `PostToolUse` (15) and `SessionEnd`
(30). Kimi accepts exactly `event`, `matcher`, `command` and `timeout`; any
other key stops the whole config from loading, which is why the bridge
carries its own environment instead of relying on hook `env` fields.

## Environment knobs (all optional)

| Variable | Default | Meaning |
|---|---|---|
| `REMEMBER_BRIDGE_PLUGIN_ROOT` | `D:/DevHome/state/remember/artifacts/remember-current` | Pinned Remember checkout whose `scripts/*-hook.sh` run. |
| `REMEMBER_BRIDGE_ROOT` | `D:/DevHome/state/remember/bridge` | Mirrors, offsets, inject cache and bridge logs, per host. |
| `REMEMBER_BRIDGE_BASH` | `C:/Program Files/Git/bin/bash.exe`, then `bash` on PATH | Shell that runs the upstream scripts. |
| `GROK_HOME`, `KIMI_CODE_HOME` | `~/.grok`, `~/.kimi-code` | Where the native transcripts are looked up. |
| `REMEMBER_BRIDGE_DETACH` | `auto` (Grok detached, Kimi in-tree) | `always` or `never` forces how `PostToolUse` and `SessionEnd` reach upstream. |

Remember's own knobs still apply to the upstream scripts (`~/.remember/config.json`
with `data_dir`, `REMEMBER_SUMMARIZER`, `REMEMBER_SUMMARIZER_FALLBACK`). The
bridge sets none of them.

## Tests

```powershell
python -B -m unittest .\codex-skills\local-hooks\remember-bridge\tests\test_remember_bridge.py
Invoke-Pester -Path .\codex-skills\local-hooks\remember-bridge\tests\RememberBridge-Install.Tests.ps1
```

The Python suite covers payload normalisation, the slug port (parity with
`pipeline/slug.py`), both translators on sanitised captures, incremental
mirroring, transcript lookup, config resolution, the per-event flows with a
fake upstream, the detached-launch policy with a fake launcher, the
grandchild-never-blocks contract with real Git Bash, one real WMI launch of
a fixture script (skipped without Windows PowerShell), and one end-to-end
run of the pinned `save-session.sh --dry` over a bridge-built mirror
(skipped when the checkout or Git Bash is absent). The Pester suite
exercises the installer against disposable targets with fake verifiers.

## Known limitations

- Grok delivers recall only through `PreToolUse`, after the tool call it
  rides on. A chat-only Grok session gets no memory block; the first tool
  result carries it.
- Kimi's `context.append_message` records (system reminders, plugin
  scaffolding) are not mirrored; human prompts come from `turn.prompt` and
  `turn.steer`. Only `agents/main` is mirrored; swarm sub-agents are ignored,
  matching Claude's handling of subagent transcripts.
- Grok `reasoning`, `tool_result` and Kimi `think` parts are dropped. Tool
  calls are kept as `tool_use` blocks, so the pinned extractor reports the
  usual `[TOOL: name]` markers.
- The store log says `claude-code` for the envelope because the mirror is
  Claude-shaped. Upstream issues proposing native `grok` and `kimi` hosts
  would remove the mirror step at a later pin bump.
- Kimi `-p` (headless) sessions never fire `SessionEnd`, so their tail is
  captured only by a mid-session save or by the next session's recovery
  (off in this store's config). Grok bounds its `SessionEnd` hooks with a
  ten-second exit budget; the detached launch needs well under a second,
  and the flush itself then runs unattended.
- Under Grok the in-tree `SessionStart` hook loses its own background
  children (recovery force save, consolidation) to the job-object kill; see
  "Host process trees".

## Rollback

Delete `D:\DevHome\state\grok\hooks\remember.json`; restore Kimi's
`config.toml` from its dated `.bak` (or remove the four tables). Bridge state
under `D:\DevHome\state\remember\bridge` and the stores themselves are never
deleted by the bridge or the installer.
