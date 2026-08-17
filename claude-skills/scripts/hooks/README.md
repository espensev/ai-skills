# Campaign Skills — Hook Scripts

Hook scripts that integrate with Claude Code's hook system to provide
observability, analytics, and safety features.

## Scripts

| Script | Hook Event | Purpose | Required By |
|--------|-----------|---------|-------------|
| `log_hook_event.py` | Any | Universal JSONL event logger | `/usage-stats` |
| `safety_guard.py` | PreToolUse | Block destructive commands and protected file edits | Standalone |
| `observe_session_briefing.py` | SessionStart | Inject project health context at session start | `/observer`, `/campaign-health` |
| `observe_test_output.py` | PostToolUse (Bash) | Record test/build results as observations | `/observer` |
| `observe_churn.py` | PostToolUse (Edit\|Write) | Track file edit frequency, flag churn | `/observer` |
| `observe_agent_stop.py` | SubagentStop | Summarize worktree observations for parent | `/manager`, `/observer` |

## Data Files

| File | Created By | Read By |
|------|-----------|---------|
| `.claude/hooks/logs/hooks-log.jsonl` | `log_hook_event.py` | `/usage-stats` |
| `data/observations.jsonl` | `observe_test_output.py`, `observe_churn.py` | `/observer`, `/campaign-health`, `observe_session_briefing.py` |

## Installation

### 1. Copy scripts

Copy `scripts/hooks/` into your project's `scripts/hooks/` directory.

### 2. Configure hooks

Copy the `hooks` block from `settings-hooks.template.json` into your
project's `.claude/settings.json` (shared) or `.claude/settings.local.json`
(personal).

### 3. Python command

The template uses `python` which works on Windows. On macOS/Linux where
only `python3` is available, find-and-replace `"python "` with `"python3 "`
in the settings block. Both work if your system has the command on PATH.

All scripts use `$CLAUDE_PROJECT_DIR` for path resolution — this environment
variable is set by Claude Code automatically.

### 4. Selective installation

You don't need all hooks. Pick by category:

**Analytics only** (for `/usage-stats`):
- `log_hook_event.py` on: SessionStart, PreToolUse, PostToolUse,
  PostToolUseFailure, SubagentStart, SubagentStop, Stop, StopFailure

**Observer only** (for `/observer`, `/campaign-health`):
- `observe_session_briefing.py` on: SessionStart
- `observe_test_output.py` on: PostToolUse (Bash)
- `observe_churn.py` on: PostToolUse (Edit|Write)
- `observe_agent_stop.py` on: SubagentStop

**Safety only** (standalone):
- `safety_guard.py` on: PreToolUse (Bash, Edit, Write)

## Skill ↔ Hook Dependency Map

```
/usage-stats    ──── reads ── .claude/hooks/logs/hooks-log.jsonl ◄── log_hook_event.py

/observer       ──┐
/campaign-health──┼── reads ── data/observations.jsonl ◄── observe_test_output.py
                  │                                     ◄── observe_churn.py
                  └── reads via session briefing        ◄── observe_session_briefing.py

/manager        ──── reads agent observations via       ◄── observe_agent_stop.py

(standalone)    ──── blocks destructive actions via     ◄── safety_guard.py
```

## Design Principles

- **Standalone**: No hook imports `task_manager.py` or any skill script.
  All hooks are self-contained Python with stdlib only.
- **Graceful degradation**: If data files don't exist, hooks exit silently.
  Missing observer initialization = hooks do nothing.
- **Non-blocking**: Logger and observer hooks use `async: true` or short
  timeouts. Safety guard runs synchronously (must block before execution).
- **Deduplication**: Observer hooks check for existing identical observations
  before recording.
- **Portable**: Works on Windows (`python`) and Unix (`python3`).
  Uses `$CLAUDE_PROJECT_DIR` for path resolution.
