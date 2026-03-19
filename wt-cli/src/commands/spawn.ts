import { resolve, basename, dirname, join } from 'node:path';
import { access } from 'node:fs/promises';
import type { SpawnOptions } from '../types/options.js';
import { execGit, getRepoRoot } from '../core/git.js';
import { toWorktreeSlug } from '../core/slug.js';
import { getPreferredPort } from '../core/port.js';
import { writeMetadata } from '../core/metadata.js';
import { ensureRepoExcludePattern } from '../core/exclude.js';
import { copyExampleEnvFile } from '../core/env-copy.js';
import { runBootstrapInstalls } from '../core/bootstrap-runner.js';
import { checkWindowsLongPaths, checkPathLength } from '../platform/windows.js';
import { isWindows } from '../platform/detect.js';
import { getLifecycle } from '../lifecycle/index.js';
import { formatTable } from '../output/formatter.js';
import { outputJson } from '../output/json.js';
import * as log from '../output/logger.js';

export async function spawnWorktree(name: string, opts: SpawnOptions): Promise<void> {
  const repoRoot = await getRepoRoot();
  const slug = toWorktreeSlug(name);
  const repoLeaf = basename(repoRoot);
  const parentDir = dirname(repoRoot);
  const worktreePath = opts.path ?? join(parentDir, `wt-${repoLeaf}-${slug}`);
  const branch = `${opts.branchPrefix}/${slug}`;

  // Check worktree path doesn't already exist
  try {
    await access(worktreePath);
    throw new Error(`Path already exists: ${worktreePath}`);
  } catch (err) {
    if ((err as NodeJS.ErrnoException).code !== 'ENOENT') throw err;
  }

  // Windows checks
  if (isWindows()) {
    const pathWarning = checkPathLength(worktreePath);
    if (pathWarning) log.warn(pathWarning);

    const checks = await checkWindowsLongPaths(repoRoot);
    if (!checks.gitLongPathsEnabled) {
      log.warn('git core.longpaths is not enabled. Run: git config core.longpaths true');
    }
  }

  // Check branch doesn't already exist
  if (!opts.detached) {
    const branchCheck = await execGit(
      ['rev-parse', '--verify', `refs/heads/${branch}`],
      { cwd: repoRoot, allowFailure: true },
    );
    if (branchCheck.exitCode === 0) {
      throw new Error(`Branch '${branch}' already exists.`);
    }
  }

  // Create worktree
  const worktreeArgs = ['worktree', 'add'];
  if (opts.detached) {
    worktreeArgs.push('--detach');
  } else {
    worktreeArgs.push('-b', branch);
  }
  worktreeArgs.push(worktreePath, opts.base);

  log.info(`Creating worktree at ${worktreePath}...`);
  await execGit(worktreeArgs, { cwd: repoRoot });

  // Allocate port
  const port = opts.port ?? await getPreferredPort(repoRoot, worktreePath);

  // Bootstrap
  let envSource: string | null = null;
  if (!opts.skipBootstrap) {
    // Exclude pattern
    await ensureRepoExcludePattern(repoRoot, '.worktree/');

    // Worktree-local git config
    await execGit(['config', 'extensions.worktreeConfig', 'true'], { cwd: worktreePath });
    await execGit(['config', '--worktree', 'worktree.port', String(port)], { cwd: worktreePath });
    if (opts.scope) {
      await execGit(['config', '--worktree', 'worktree.scope', opts.scope], { cwd: worktreePath });
    }

    // Copy .env.example
    if (!opts.skipEnv) {
      envSource = await copyExampleEnvFile(worktreePath);
      if (envSource) log.info(`Copied ${envSource} to .env`);
    }

    // Install dependencies
    if (!opts.skipInstall) {
      log.info('Installing dependencies...');
      try {
        const result = await runBootstrapInstalls(worktreePath);
        if (result.packageManager) {
          log.info(`Installed via ${result.packageManager}`);
        }
      } catch (err) {
        log.warn(`Dependency install failed: ${(err as Error).message}`);
        log.warn('You can retry manually or use --skip-install');
      }
    }
  }

  // Write metadata
  const metadata = {
    name,
    path: worktreePath,
    worktreeRoot: worktreePath,
    sourceRepoRoot: repoRoot,
    branch: opts.detached ? '(detached)' : branch,
    port,
    scope: opts.scope ?? '',
    envSource,
    createdAtUtc: new Date().toISOString(),
  };
  await writeMetadata(worktreePath, metadata);

  // Lifecycle hook
  await getLifecycle().onSpawn({
    worktreeId: name,
    branchId: branch,
    executionMode: 'worktree',
    path: worktreePath,
    port,
    scope: opts.scope ?? '',
    timestamp: metadata.createdAtUtc,
  });

  // Output
  if (opts.json) {
    outputJson(metadata);
    return;
  }

  log.success(`\nWorktree '${name}' created successfully.`);
  const table = formatTable(
    [
      { key: 'field', label: 'Field' },
      { key: 'value', label: 'Value' },
    ],
    [
      { field: 'Name', value: name },
      { field: 'Path', value: worktreePath },
      { field: 'Branch', value: metadata.branch },
      { field: 'Port', value: String(port) },
      { field: 'Scope', value: opts.scope ?? '(none)' },
      { field: 'Env', value: envSource ?? '(none)' },
    ],
  );
  console.log(table);
}
