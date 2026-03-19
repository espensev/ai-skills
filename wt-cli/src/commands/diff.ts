import chalk from 'chalk';
import type { DiffOptions } from '../types/options.js';
import { getRepoRoot, execGit } from '../core/git.js';
import { resolveWorktreeRecord } from '../core/resolve.js';
import { getDiffStats } from '../core/merge-planner.js';
import { formatTable } from '../output/formatter.js';
import { outputJson } from '../output/json.js';
import * as log from '../output/logger.js';

export async function showDiff(target: string, opts: DiffOptions): Promise<void> {
  const repoRoot = await getRepoRoot();
  const record = await resolveWorktreeRecord(repoRoot, target);

  if (!record.branchShort) {
    throw new Error(`Worktree '${target}' has no branch (detached HEAD).`);
  }

  // Determine target branch for comparison
  const targetBranch = opts.target ?? (await execGit(['symbolic-ref', '--short', 'HEAD'], { cwd: repoRoot })).stdout;

  // Summary stats
  const stats = await getDiffStats(repoRoot, targetBranch, record.branchShort);

  // Detailed per-file stats
  const baseResult = await execGit(
    ['merge-base', targetBranch, record.branchShort],
    { cwd: repoRoot, allowFailure: true },
  );

  let fileDetails: { file: string; changes: string }[] = [];
  if (baseResult.exitCode === 0 && baseResult.stdout) {
    const statResult = await execGit(
      ['diff', '--stat', `${baseResult.stdout}...${record.branchShort}`],
      { cwd: repoRoot, allowFailure: true },
    );

    if (statResult.stdout) {
      // Parse per-file lines (skip the summary line)
      const lines = statResult.stdout.split(/\r?\n/).filter(Boolean);
      for (const line of lines.slice(0, -1)) {
        const match = line.match(/^\s*(.+?)\s+\|\s+(.+)$/);
        if (match) {
          fileDetails.push({ file: match[1].trim(), changes: match[2].trim() });
        }
      }
    }
  }

  if (opts.json) {
    outputJson({ branch: record.branchShort, target: targetBranch, stats, files: fileDetails });
    return;
  }

  log.info(`${chalk.bold(record.branchShort)} vs ${targetBranch}:\n`);

  if (fileDetails.length > 0) {
    const table = formatTable(
      [
        { key: 'file', label: 'FILE' },
        { key: 'changes', label: 'CHANGES' },
      ],
      fileDetails,
    );
    console.log(table);
  }

  console.log(
    `\n${stats.filesChanged} files changed, ` +
    `${chalk.green(`+${stats.insertions}`)} insertions, ` +
    `${chalk.red(`-${stats.deletions}`)} deletions`,
  );
}
