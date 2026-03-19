import { resolve } from 'node:path';
import type { BootstrapOptions } from '../types/options.js';
import { getRepoRoot, execGit } from '../core/git.js';
import { readMetadata, writeMetadata } from '../core/metadata.js';
import { ensureRepoExcludePattern } from '../core/exclude.js';
import { copyExampleEnvFile } from '../core/env-copy.js';
import { runBootstrapInstalls } from '../core/bootstrap-runner.js';
import { getPreferredPort } from '../core/port.js';
import { getLifecycle } from '../lifecycle/index.js';
import { outputJson } from '../output/json.js';
import * as log from '../output/logger.js';

export async function bootstrapWorktree(path: string, opts: BootstrapOptions): Promise<void> {
  const worktreePath = resolve(path);
  const repoRoot = await getRepoRoot(worktreePath);

  // Exclude pattern
  await ensureRepoExcludePattern(repoRoot, '.worktree/');

  // Worktree-local git config
  await execGit(['config', 'extensions.worktreeConfig', 'true'], { cwd: worktreePath });

  const port = opts.port ?? await getPreferredPort(repoRoot, worktreePath);
  await execGit(['config', '--worktree', 'worktree.port', String(port)], { cwd: worktreePath });

  if (opts.scope) {
    await execGit(['config', '--worktree', 'worktree.scope', opts.scope], { cwd: worktreePath });
  }

  // Copy .env.example
  let envSource: string | null = null;
  if (!opts.skipEnv) {
    envSource = await copyExampleEnvFile(worktreePath);
    if (envSource) log.info(`Copied ${envSource} to .env`);
  }

  // Install dependencies
  let depsInstalled = false;
  if (!opts.skipInstall) {
    log.info('Installing dependencies...');
    try {
      const result = await runBootstrapInstalls(worktreePath);
      depsInstalled = result.packageManager !== null;
      if (result.packageManager) log.info(`Installed via ${result.packageManager}`);
    } catch (err) {
      log.warn(`Dependency install failed: ${(err as Error).message}`);
    }
  }

  // Update or create metadata
  const existing = await readMetadata(worktreePath);
  const metadata = {
    ...(existing ?? {
      name: '',
      path: worktreePath,
      worktreeRoot: worktreePath,
      sourceRepoRoot: repoRoot,
      branch: '',
      scope: '',
      createdAtUtc: new Date().toISOString(),
    }),
    port,
    envSource,
    ...(opts.scope ? { scope: opts.scope } : {}),
  };
  await writeMetadata(worktreePath, metadata);

  await getLifecycle().onBootstrap({
    worktreeId: metadata.name,
    path: worktreePath,
    envSource,
    depsInstalled,
    timestamp: new Date().toISOString(),
  });

  if (opts.json) {
    outputJson(metadata);
    return;
  }

  log.success('Bootstrap complete.');
}
