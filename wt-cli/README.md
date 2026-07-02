# wt-cli

Cross-platform worktree orchestrator for parallel AI agent development.

`wt` creates isolated git worktrees with their own branches, deterministic
port allocation, and file-scope metadata; bootstraps them (dependency install,
`.env.example` copy); and coordinates smallest-diff-first merges. It is the
runtime behind the `worktree-manager` skill and is usable standalone in any
git repository.

Per `release-manifest.json` this package is **tooling, source-only** — it is
not part of the model skill export bundle (see `docs/release-readiness.md`).

## Requirements

- Node.js >= 18
- git on PATH

## Install and build

```bash
cd wt-cli
npm install
npm run build     # tsup -> dist/cli.mjs (bin: wt)
npm test          # vitest unit tests
npm run dev       # run from source via tsx
```

Run the built CLI as `wt` (when linked/installed) or directly:

```bash
node wt-cli/dist/cli.mjs <command>
```

## Commands

| Command | Purpose |
|---|---|
| `wt spawn <name>` | Create a worktree with branch, bootstrap, and metadata |
| `wt list` / `wt status` | Show all worktrees with status |
| `wt merge [name]` | Merge worktree branches (smallest-diff-first) |
| `wt teardown [name]` | Remove a worktree safely |
| `wt bootstrap <path>` | Bootstrap an existing worktree |
| `wt scope <name> <path>` | Assign or update file scope for a worktree |
| `wt lock <name>` / `wt unlock <name>` | Protect a worktree from accidental removal |
| `wt ports` | Show the port allocation table |
| `wt diff <name>` | Show diff stats for a worktree branch |

Frequently used options (see `wt <command> --help` for the full list):

- `spawn`: `--branch-prefix <prefix>` (default `agent`), `--base <ref>`,
  `--path <path>`, `--port <number>`, `--scope <path>`, `--detached`,
  `--skip-install`, `--skip-env`, `--skip-bootstrap`
- `merge`: `--target <branch>`, `--all`, `--dry-run`, `--delete-branch`
- `teardown`: `--force`, `--all`, `--delete-branch`
- `list`/`status`: `--all` (include the primary worktree)
- `diff`: `--target <branch>`

Most read/plan commands accept `--json` for machine-readable output, which is
what agent skills consume.

## Layout

| Path | Purpose |
|---|---|
| `src/cli.ts` | Command registration (commander) |
| `src/commands/` | One module per command |
| `src/core/` | Worktree, merge-planner, port, scope, metadata logic |
| `src/platform/` | Platform detection and Windows specifics |
| `src/output/` | Logger, formatter, JSON output |
| `tests/` | Vitest unit and integration tests |
