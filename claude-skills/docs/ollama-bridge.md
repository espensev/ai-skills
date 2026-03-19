# Ollama Bridge Example

This package's runtime does not call any model API directly. The orchestration
surface stays in `scripts/task_manager.py`, and model-specific execution should
sit outside that backend.

`examples/ollama-bridge.ps1` is the base bridge script for consumer repos that
already have the installed runtime.

To avoid mode/argument parsing mistakes, use these wrappers:

- `examples/ollama-bridge-tasks.ps1` (runs existing task state via `run ready`)
- `examples/ollama-bridge-campaign.ps1` (runs full lifecycle via `go`)

Default mode is `tasks`, which means:

1. It calls `python scripts/task_manager.py run ready --json`.
2. It works against the current task/spec state without creating or resuming a
   campaign plan.
3. After no more ready tasks remain, it can merge completed worktrees back into
   the main tree.

Optional `campaign` mode is the original end-to-end lifecycle:

1. It calls `python scripts/task_manager.py go --json`.
2. When the backend returns launch payloads, it creates worktrees under
   `.claude/worktrees/`.
3. It sends each agent prompt plus the current owned-file contents to the local
   Ollama server.
4. It expects Ollama to return an `<agent_result>` JSON block and a `<patch>`
   block.
5. It applies the patch with `git apply`, runs the spec's `## Verification`
   commands, and records the result back through:
   `attach` and `result`.
6. It loops until the backend reaches `verified`,
   `verification_failed`, or `merge_conflicts`.

Recommended first run (existing tasks, no campaign kickoff):

```powershell
pwsh -File .\examples\ollama-bridge-tasks.ps1 `
  -RepoRoot D:\Development\MyRepo `
  -DefaultModel qwen3-coder:30b `
  -SkipMerge
```

Base script invocation from a consumer repo:

```powershell
pwsh -File .\examples\ollama-bridge.ps1 `
  -RepoRoot D:\Development\MyRepo `
  -DefaultModel qwen3-coder:30b
```

Optional tier overrides keep the backend's abstract `haiku` / `sonnet` /
`opus` contract intact while mapping them to actual Ollama models:

```powershell
pwsh -File .\examples\ollama-bridge.ps1 `
  -RepoRoot D:\Development\MyRepo `
  -HaikuModel gemma3:latest `
  -SonnetModel qwen3-coder:30b `
  -OpusModel gpt-oss:120b
```

Full plan-driven lifecycle with wrapper:

```powershell
pwsh -File .\examples\ollama-bridge-campaign.ps1 `
  -RepoRoot D:\Development\MyRepo `
  -DefaultModel qwen3-coder:30b
```

Equivalent base-script form:

```powershell
pwsh -File .\examples\ollama-bridge.ps1 `
  -RepoRoot D:\Development\MyRepo `
  -LaunchMode campaign `
  -DefaultModel qwen3-coder:30b
```

Important limits:

- Ollama is still text inference only. The bridge works by packaging file
  contents into the prompt and then applying the returned diff.
- Keep agent ownership tight. Large owned-file sets will degrade patch quality
  and can exceed local context limits.
- The bridge runs agents sequentially on purpose. That avoids oversubscribing a
  local GPU or CPU while the backend still preserves worktree isolation and
  task state.
- Raw responses, generated patches, verification logs, and result payloads are
  written to `.claude/ollama/` in the consumer repo for inspection.

Treat this as an example integration layer, not a core runtime contract.
