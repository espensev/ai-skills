# AI Skills

Portable multi-agent skill packages for Codex, Claude, and Gemini, plus
supporting tooling for parallel agent development.

## Included Packages

| Package | Status | Purpose |
|---|---|---|
| `codex-skills` | Ready | Portable Codex-oriented skill docs, contracts, and Python runtime helpers |
| `claude-skills` | Ready | Portable Claude-oriented skill docs, contracts, and Python runtime helpers |
| `gemini-skills` | Ready | Gemini adapter package with skills, command wrappers, bootstrap script, and guardrails |
| `wt-cli` | Tooling | TypeScript CLI for worktree orchestration in parallel agent flows |

Package readiness is tracked in `release-manifest.json`, with notes in
`docs/release-readiness.md`.

## Quick Start

Export the currently ready skill packages into a target folder:

```powershell
.\scripts\export-ready-skill-packages.ps1 -TargetDir ".\dist\ai-skills-ready-packages" -Force
```

For Gemini-specific installation into another repo:

```powershell
.\gemini-skills\scripts\bootstrap.ps1 -TargetDir "C:\path\to\target-repo"
```

## Repository Layout

- `codex-skills/`: Codex package source
- `claude-skills/`: Claude package source
- `gemini-skills/`: Gemini package source
- `wt-cli/`: worktree helper CLI
- `scripts/`: repo-level automation
- `docs/`: repo-level release notes

## Notes

- Local runtime state, caches, generated install trees, and build output are
  intentionally ignored from version control.
- The repo stays package-first: provider-specific runtime and install docs live
  with the owning package rather than in a shared root abstraction.
- If `-TargetDir` is omitted, the export script uses the default location from
  `release-manifest.json`.
