import { Command } from 'commander';
import { spawnWorktree } from './commands/spawn.js';
import { listWorktrees } from './commands/list.js';
import { teardownWorktree } from './commands/teardown.js';
import { bootstrapWorktree } from './commands/bootstrap.js';
import { mergeWorktree } from './commands/merge.js';
import { setScope } from './commands/scope.js';
import { lockWorktree, unlockWorktree } from './commands/lock.js';
import { showPorts } from './commands/ports.js';
import { showDiff } from './commands/diff.js';
import * as log from './output/logger.js';

const program = new Command();

program
  .name('wt')
  .description('Cross-platform worktree orchestrator for parallel AI agent development')
  .version('0.1.0');

// wt spawn <name>
program
  .command('spawn')
  .description('Create a new worktree with branch, bootstrap, and metadata')
  .argument('<name>', 'Task name for the worktree')
  .option('--branch-prefix <prefix>', 'Branch prefix', 'agent')
  .option('--base <ref>', 'Base commit or branch', 'HEAD')
  .option('--path <path>', 'Custom worktree path')
  .option('--port <number>', 'Explicit port assignment', parseInt)
  .option('--scope <path>', 'File/directory scope')
  .option('--detached', 'Create with detached HEAD', false)
  .option('--skip-install', 'Skip dependency installation', false)
  .option('--skip-env', 'Skip .env.example copy', false)
  .option('--skip-bootstrap', 'Skip all bootstrap steps', false)
  .option('--json', 'Output as JSON', false)
  .action(async (name, opts) => {
    await spawnWorktree(name, {
      branchPrefix: opts.branchPrefix,
      base: opts.base,
      path: opts.path,
      port: opts.port,
      scope: opts.scope,
      detached: opts.detached,
      skipInstall: opts.skipInstall,
      skipEnv: opts.skipEnv,
      skipBootstrap: opts.skipBootstrap,
      json: opts.json,
    });
  });

// wt list / wt status
for (const cmd of ['list', 'status']) {
  program
    .command(cmd)
    .description('Show all worktrees with status')
    .option('--all', 'Include primary worktree', false)
    .option('--json', 'Output as JSON', false)
    .action(async (opts) => {
      await listWorktrees({ all: opts.all, json: opts.json });
    });
}

// wt merge [name]
program
  .command('merge')
  .description('Merge worktree branches (smallest-diff-first)')
  .argument('[name]', 'Worktree name to merge')
  .option('--target <branch>', 'Target branch for merge')
  .option('--all', 'Merge all worktree branches', false)
  .option('--dry-run', 'Show plan without executing', false)
  .option('--delete-branch', 'Delete source branch after merge', false)
  .option('--json', 'Output as JSON', false)
  .action(async (name, opts) => {
    await mergeWorktree(name, {
      target: opts.target,
      all: opts.all,
      dryRun: opts.dryRun,
      deleteBranch: opts.deleteBranch,
      json: opts.json,
    });
  });

// wt teardown [name]
program
  .command('teardown')
  .description('Remove a worktree safely')
  .argument('[name]', 'Worktree name to remove')
  .option('--force', 'Remove even with uncommitted changes', false)
  .option('--delete-branch', 'Also delete the git branch', false)
  .option('--all', 'Remove all non-primary worktrees', false)
  .option('--json', 'Output as JSON', false)
  .action(async (name, opts) => {
    await teardownWorktree(name, {
      force: opts.force,
      deleteBranch: opts.deleteBranch,
      all: opts.all,
      json: opts.json,
    });
  });

// wt bootstrap <path>
program
  .command('bootstrap')
  .description('Bootstrap an existing worktree')
  .argument('<path>', 'Path to the worktree')
  .option('--port <number>', 'Port assignment', parseInt)
  .option('--scope <path>', 'File/directory scope')
  .option('--skip-install', 'Skip dependency installation', false)
  .option('--skip-env', 'Skip .env.example copy', false)
  .option('--json', 'Output as JSON', false)
  .action(async (path, opts) => {
    await bootstrapWorktree(path, {
      port: opts.port,
      scope: opts.scope,
      skipInstall: opts.skipInstall,
      skipEnv: opts.skipEnv,
      json: opts.json,
    });
  });

// wt scope <name> <path>
program
  .command('scope')
  .description('Assign or update file scope for a worktree')
  .argument('<name>', 'Worktree name')
  .argument('<path>', 'File/directory scope path')
  .action(async (name, path) => {
    await setScope(name, path);
  });

// wt lock <name>
program
  .command('lock')
  .description('Lock a worktree to prevent accidental removal')
  .argument('<name>', 'Worktree name')
  .action(async (name) => {
    await lockWorktree(name);
  });

// wt unlock <name>
program
  .command('unlock')
  .description('Unlock a worktree')
  .argument('<name>', 'Worktree name')
  .action(async (name) => {
    await unlockWorktree(name);
  });

// wt ports
program
  .command('ports')
  .description('Show port allocation table')
  .option('--json', 'Output as JSON', false)
  .action(async (opts) => {
    await showPorts(opts.json);
  });

// wt diff <name>
program
  .command('diff')
  .description('Show diff stats for a worktree branch')
  .argument('<name>', 'Worktree name')
  .option('--target <branch>', 'Target branch for comparison')
  .option('--json', 'Output as JSON', false)
  .action(async (name, opts) => {
    await showDiff(name, { target: opts.target, json: opts.json });
  });

// Error handling
program.exitOverride();

async function main() {
  try {
    await program.parseAsync(process.argv);
  } catch (err) {
    if ((err as Error).message !== '(outputHelp)') {
      log.error((err as Error).message);
      process.exitCode = 1;
    }
  }
}

main();
