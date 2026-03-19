import type { GitWorktreeRecord } from '../types/worktree-record.js';
import { execGit } from './git.js';

export async function getWorktreeRecords(repoRoot: string): Promise<GitWorktreeRecord[]> {
  const result = await execGit(['worktree', 'list', '--porcelain'], { cwd: repoRoot });
  if (!result.stdout) {
    return [];
  }

  return parseWorktreePorcelain(result.stdout);
}

export function parseWorktreePorcelain(output: string): GitWorktreeRecord[] {
  const records: GitWorktreeRecord[] = [];
  let current: GitWorktreeRecord | null = null;

  for (const line of output.split(/\r?\n/)) {
    if (!line.trim()) {
      if (current) {
        records.push(current);
        current = null;
      }
      continue;
    }

    const spaceIndex = line.indexOf(' ');
    const key = spaceIndex === -1 ? line : line.slice(0, spaceIndex);
    const value = spaceIndex === -1 ? '' : line.slice(spaceIndex + 1);

    if (key === 'worktree') {
      if (current) {
        records.push(current);
      }
      current = {
        path: value,
        head: '',
        branchRef: '',
        branchShort: '',
        detached: false,
        bare: false,
        locked: false,
        lockReason: '',
        prunable: false,
        prunableReason: '',
      };
      continue;
    }

    if (!current) continue;

    switch (key) {
      case 'HEAD':
        current.head = value;
        break;
      case 'branch':
        current.branchRef = value;
        if (value.startsWith('refs/heads/')) {
          current.branchShort = value.slice(11);
        }
        break;
      case 'detached':
        current.detached = true;
        break;
      case 'bare':
        current.bare = true;
        break;
      case 'locked':
        current.locked = true;
        current.lockReason = value;
        break;
      case 'prunable':
        current.prunable = true;
        current.prunableReason = value;
        break;
    }
  }

  if (current) {
    records.push(current);
  }

  return records;
}
