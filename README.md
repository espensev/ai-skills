# AI Skills

Portable skill packages and supporting runtime code for multiple agent clients.

## Packages

- `codex-skills`: Codex-oriented campaign skills and runtime helpers.
- `claude-skills`: Claude-oriented campaign skills and runtime helpers.
- `gemini-skills`: Gemini-oriented skill set and supporting docs.
- `wt-cli`: TypeScript CLI for worktree orchestration in parallel agent flows.

## Intended Structure

Each package keeps its own installable skill docs, shared contracts, and runtime
scripts so the assets can be vendored into other proof-of-concept repositories
without pulling in the full owner-repo test harness.

## Shipping

The ready-to-ship model packages are tracked in `release-manifest.json`.

To export the currently ready packages into a shared folder:

```powershell
.\scripts\export-ready-skill-packages.ps1 -TargetDir "C:\Users\Sev\OneDrive\Common\ai-skills-ready-packages" -Force
```

Release notes and package readiness are documented in `docs/release-readiness.md`.

## Repo Prep

This root is set up to work as a simple multi-package repository:

- keep provider-specific assets inside their existing package folders
- keep provider runtime/install docs with the owning package
- add shared repo-level docs or automation at the root only when they apply to
  every package
