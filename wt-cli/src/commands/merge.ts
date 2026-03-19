import { resolve } from 'node:path';
import chalk from 'chalk';
import type { MergeOptions } from '../types/options.js';
import { getRepoRoot, execGit } from '../core/git.js';
import { getWorktreeRecords } from '../core/worktree.js';
import { readMetadata } from '../core/metadata.js';
import { resolveWorktreeRecord } from '../core/resolve.js';
import { getDiffStats, predictConflicts, sortBySmallestDiff, type MergePlan } from '../core/merge-planner.js';
import { getLifecycle } from '../lifecycle/index.js';
import { formatTable } from '../output/formatter.js';
import { outputJson } from '../output/json.js';
import * as log from '../output/logger.js';

export async function mergeWorktree(target: string | undefined, opts: MergeOptions): Promise<void> {
  const repoRoot = await getRepoRoot();
  const resolvedRoot = resolve(repoRoot);

  // Determine target branch
  const targetBranch = opts.target ?? (await execGit(['symbolic-ref', '--short', 'HEAD'], { cwd: repoRoot })).stdout;

  // Gather worktree branches to merge
  let worktrees;
  if (opts.all) {
    const allRecords = await getWorktreeRecords(repoRoot);
    worktrees = allRecords.filter((r) => resolve(r.path) !== resolvedRoot && r.branchShort);
  } else if (target) {
    worktrees = [await resolveWorktreeRecord(repoRoot, target)];
  } else {
    throw new Error('Specify a worktree name or use --all.');
  }

  if (worktrees.length === 0) {
    log.info('No worktree branches to merge.');
    return;
  }

  // Build merge plans
  log.info('Calculating diff sizes...');
  const plans: MergePlan[] = [];

  for (const wt of worktrees) {
    const metadata = await readMetadata(wt.path);
    const stats = await getDiffStats(repoRoot, targetBranch, wt.branchShort);
    const hasConflicts = await predictConflicts(repoRoot, targetBranch, wt.branchShort);

    plans.push({
      worktreeName: metadata?.name ?? wt.branchShort,
      branch: wt.branchShort,
      stats,
      hasConflicts,
    });
  }

  const sorted = sortBySmallestDiff(plans);

  // Display plan
  const table = formatTable(
    [
      { key: 'order', label: '#', align: 'right' },
      { key: 'name', label: 'NAME' },
      { key: 'branch', label: 'BRANCH' },
      { key: 'files', label: 'FILES', align: 'right' },
      { key: 'changes', label: 'CHANGES', align: 'right' },
      {
        key: 'conflicts',
        label: 'CONFLICTS',
        color: (val: string) => val === 'yes' ? chalk.red(val) : chalk.green(val),
      },
    ],
    sorted.map((p, i) => ({
      order: String(i + 1),
      name: p.worktreeName,
      branch: p.branch,
      files: String(p.stats.filesChanged),
      changes: `+${p.stats.insertions} -${p.stats.deletions}`,
      conflicts: p.hasConflicts ? 'yes' : 'no',
    })),
  );
  console.log(table);

  if (opts.dryRun) {
    log.info('\nDry run — no merges executed.');
    if (opts.json) outputJson(sorted);
    return;
  }

  // Execute merges
  for (const plan of sorted) {
    const ctx = {
      worktreeId: plan.worktreeName,
      branchId: plan.branch,
      targetBranch,
      filesChanged: plan.stats.filesChanged,
      insertions: plan.stats.insertions,
      deletions: plan.stats.deletions,
      hasConflicts: plan.hasConflicts,
      timestamp: new Date().toISOString(),
    };

    if (plan.hasConflicts) {
      log.warn(`Skipping '${plan.branch}' — conflicts detected. Resolve manually.`);
      continue;
    }

    await getLifecycle().onMergeStart(ctx);
    log.info(`Merging ${plan.branch} into ${targetBranch}...`);

    await execGit(
      ['merge', '--no-ff', plan.branch, '-m', `Merge ${plan.branch} into ${targetBranch}`],
      { cwd: repoRoot },
    );

    if (opts.deleteBranch) {
      await execGit(['branch', '-d', plan.branch], { cwd: repoRoot, allowFailure: true });
    }

    await getLifecycle().onMergeComplete(ctx);
    log.success(`Merged: ${plan.branch}`);
  }

  if (opts.json) outputJson(sorted);
}
