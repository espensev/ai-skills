import { resolve } from 'node:path';
import chalk from 'chalk';
import type { ListOptions } from '../types/options.js';
import { getRepoRoot, execGit } from '../core/git.js';
import { getWorktreeRecords } from '../core/worktree.js';
import { readMetadata } from '../core/metadata.js';
import { formatTable } from '../output/formatter.js';
import { outputJson } from '../output/json.js';

export async function listWorktrees(opts: ListOptions): Promise<void> {
  const repoRoot = await getRepoRoot();
  const records = await getWorktreeRecords(repoRoot);
  const resolvedRoot = resolve(repoRoot);

  const rows = [];

  for (const record of records) {
    const isMain = resolve(record.path) === resolvedRoot;
    if (isMain && !opts.all) continue;

    const metadata = await readMetadata(record.path);

    // Check dirty status
    let status = 'clean';
    try {
      const statusResult = await execGit(
        ['status', '--porcelain'],
        { cwd: record.path, allowFailure: true },
      );
      if (statusResult.stdout) {
        const fileCount = statusResult.stdout.split(/\r?\n/).filter(Boolean).length;
        status = `dirty (${fileCount} files)`;
      }
    } catch {
      status = 'unreachable';
    }

    rows.push({
      name: metadata?.name ?? (isMain ? '(primary)' : '(unknown)'),
      branch: record.branchShort || (record.detached ? '(detached)' : ''),
      port: metadata?.port != null ? String(metadata.port) : '-',
      scope: metadata?.scope || (isMain ? '*' : ''),
      locked: record.locked ? 'yes' : '',
      status,
      path: record.path,
      isMain: isMain ? 'true' : 'false',
    });
  }

  if (opts.json) {
    outputJson(rows);
    return;
  }

  if (rows.length === 0) {
    console.log('No worktrees found. Use --all to include the primary worktree.');
    return;
  }

  const table = formatTable(
    [
      { key: 'name', label: 'NAME' },
      { key: 'branch', label: 'BRANCH' },
      { key: 'port', label: 'PORT', align: 'right' },
      { key: 'scope', label: 'SCOPE' },
      { key: 'locked', label: 'LOCKED' },
      {
        key: 'status',
        label: 'STATUS',
        color: (val: string) => {
          if (val.includes('clean')) return chalk.green(val);
          if (val.includes('dirty')) return chalk.yellow(val);
          return chalk.red(val);
        },
      },
    ],
    rows,
  );

  console.log(table);
}
