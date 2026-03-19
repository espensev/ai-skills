import type { GitWorktreeRecord } from '../types/worktree-record.js';
import { getRepoRoot, execGit } from '../core/git.js';
import { readMetadata, writeMetadata } from '../core/metadata.js';
import { resolveWorktreeRecord } from '../core/resolve.js';
import { getLifecycle } from '../lifecycle/index.js';
import * as log from '../output/logger.js';

export async function setScope(target: string, scope: string): Promise<void> {
  const repoRoot = await getRepoRoot();
  const record = await resolveWorktreeRecord(repoRoot, target);
  const metadata = await readMetadata(record.path);

  if (!metadata) {
    throw new Error(`No metadata found for worktree '${target}'. Run 'wt bootstrap' first.`);
  }

  const previousScope = metadata.scope;
  metadata.scope = scope;
  await writeMetadata(record.path, metadata);

  await execGit(['config', '--worktree', 'worktree.scope', scope], { cwd: record.path });

  await getLifecycle().onScopeAssigned({
    worktreeId: metadata.name,
    scope,
    previousScope,
    timestamp: new Date().toISOString(),
  });

  log.success(`Scope for '${target}' set to '${scope}'.`);
}
