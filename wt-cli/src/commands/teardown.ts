import { resolve } from 'node:path';
import type { TeardownOptions } from '../types/options.js';
import { getRepoRoot, execGit } from '../core/git.js';
import { getWorktreeRecords } from '../core/worktree.js';
import { readMetadata } from '../core/metadata.js';
import { resolveWorktreeRecord } from '../core/resolve.js';
import { getLifecycle } from '../lifecycle/index.js';
import { outputJson } from '../output/json.js';
import * as log from '../output/logger.js';

export async function teardownWorktree(target: string | undefined, opts: TeardownOptions): Promise<void> {
  const repoRoot = await getRepoRoot();
  const resolvedRoot = resolve(repoRoot);

  let records;
  if (opts.all) {
    const allRecords = await getWorktreeRecords(repoRoot);
    records = allRecords.filter((r) => resolve(r.path) !== resolvedRoot);
    if (records.length === 0) {
      log.info('No worktrees to remove.');
      return;
    }
  } else if (target) {
    records = [await resolveWorktreeRecord(repoRoot, target)];
  } else {
    throw new Error('Specify a worktree name or use --all.');
  }

  const results = [];

  for (const record of records) {
    if (resolve(record.path) === resolvedRoot) {
      log.warn(`Skipping primary worktree: ${record.path}`);
      continue;
    }

    if (record.locked && !opts.force) {
      log.warn(`Worktree '${record.path}' is locked. Use --force to override.`);
      continue;
    }

    // Check for uncommitted changes
    if (!opts.force) {
      const statusResult = await execGit(
        ['status', '--porcelain'],
        { cwd: record.path, allowFailure: true },
      );
      if (statusResult.stdout) {
        log.warn(`Worktree '${record.path}' has uncommitted changes. Use --force to override.`);
        continue;
      }
    }

    const metadata = await readMetadata(record.path);
    const name = metadata?.name ?? record.branchShort ?? record.path;

    log.info(`Removing worktree: ${name}...`);

    const removeArgs = ['worktree', 'remove'];
    if (opts.force) removeArgs.push('--force');
    removeArgs.push(record.path);

    await execGit(removeArgs, { cwd: repoRoot });
    await execGit(['worktree', 'prune'], { cwd: repoRoot });

    let branchDeleted = false;
    if (opts.deleteBranch && record.branchShort) {
      const deleteFlag = opts.force ? '-D' : '-d';
      try {
        await execGit(['branch', deleteFlag, record.branchShort], { cwd: repoRoot });
        branchDeleted = true;
      } catch (err) {
        log.warn(`Could not delete branch '${record.branchShort}': ${(err as Error).message}`);
      }
    }

    await getLifecycle().onTeardown({
      worktreeId: name,
      branchId: record.branchShort,
      branchDeleted,
      timestamp: new Date().toISOString(),
    });

    results.push({ name, path: record.path, branch: record.branchShort, branchDeleted });
    log.success(`Removed: ${name}`);
  }

  if (opts.json) {
    outputJson(results);
  }
}
