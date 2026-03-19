import { resolve, basename } from 'node:path';
import type { GitWorktreeRecord } from '../types/worktree-record.js';
import { getWorktreeRecords } from './worktree.js';
import { toWorktreeSlug } from './slug.js';

export async function resolveWorktreeRecord(
  repoRoot: string,
  target: string,
): Promise<GitWorktreeRecord> {
  const records = await getWorktreeRecords(repoRoot);
  const slug = toWorktreeSlug(target);
  const candidates = [target, slug, `wt-${slug}`, `agent/${slug}`];

  // Try path match first if target looks like a path
  if (target.includes('/') || target.includes('\\') || resolve(target) === target) {
    const resolvedTarget = resolve(target);
    const pathMatches = records.filter(
      (r) => resolve(r.path) === resolvedTarget,
    );
    if (pathMatches.length === 1) {
      return pathMatches[0];
    }
  }

  // Match by directory leaf name or branch short name
  const matches = records.filter((r) => {
    const leaf = basename(r.path);
    return candidates.includes(leaf) || candidates.includes(r.branchShort);
  });

  if (matches.length === 1) {
    return matches[0];
  }

  if (matches.length > 1) {
    throw new Error(`Multiple worktrees matched '${target}'. Use an absolute path instead.`);
  }

  throw new Error(`No worktree matched '${target}'.`);
}
