import { execGit } from './git.js';

export interface DiffStats {
  filesChanged: number;
  insertions: number;
  deletions: number;
  totalChanges: number;
}

export interface MergePlan {
  worktreeName: string;
  branch: string;
  stats: DiffStats;
  hasConflicts: boolean;
}

export async function getDiffStats(repoRoot: string, targetBranch: string, sourceBranch: string): Promise<DiffStats> {
  // Find merge base
  const baseResult = await execGit(
    ['merge-base', targetBranch, sourceBranch],
    { cwd: repoRoot, allowFailure: true },
  );

  if (baseResult.exitCode !== 0 || !baseResult.stdout) {
    return { filesChanged: 0, insertions: 0, deletions: 0, totalChanges: 0 };
  }

  const mergeBase = baseResult.stdout;
  const result = await execGit(
    ['diff', '--shortstat', `${mergeBase}...${sourceBranch}`],
    { cwd: repoRoot, allowFailure: true },
  );

  return parseShortstat(result.stdout);
}

export function parseShortstat(output: string): DiffStats {
  if (!output.trim()) {
    return { filesChanged: 0, insertions: 0, deletions: 0, totalChanges: 0 };
  }

  const filesMatch = output.match(/(\d+) files? changed/);
  const insertionsMatch = output.match(/(\d+) insertions?\(\+\)/);
  const deletionsMatch = output.match(/(\d+) deletions?\(-\)/);

  const filesChanged = filesMatch ? parseInt(filesMatch[1], 10) : 0;
  const insertions = insertionsMatch ? parseInt(insertionsMatch[1], 10) : 0;
  const deletions = deletionsMatch ? parseInt(deletionsMatch[1], 10) : 0;

  return {
    filesChanged,
    insertions,
    deletions,
    totalChanges: insertions + deletions,
  };
}

export async function predictConflicts(
  repoRoot: string,
  targetBranch: string,
  sourceBranch: string,
): Promise<boolean> {
  // Try git merge-tree --write-tree (Git 2.38+)
  const result = await execGit(
    ['merge-tree', '--write-tree', targetBranch, sourceBranch],
    { cwd: repoRoot, allowFailure: true },
  );

  if (result.exitCode === 0) return false;
  if (result.exitCode === 1) return true;

  // Fallback: merge-tree not supported, try --no-commit merge and abort
  const mergeResult = await execGit(
    ['merge', '--no-commit', '--no-ff', sourceBranch],
    { cwd: repoRoot, allowFailure: true },
  );

  const hasConflicts = mergeResult.exitCode !== 0;

  // Abort the merge attempt
  await execGit(['merge', '--abort'], { cwd: repoRoot, allowFailure: true });

  return hasConflicts;
}

export function sortBySmallestDiff(plans: MergePlan[]): MergePlan[] {
  return [...plans].sort((a, b) => a.stats.totalChanges - b.stats.totalChanges);
}
