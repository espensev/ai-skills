import { getRepoRoot, execGit } from '../core/git.js';
import { readMetadata, writeMetadata } from '../core/metadata.js';
import { resolveWorktreeRecord } from '../core/resolve.js';
import { getLifecycle } from '../lifecycle/index.js';
import * as log from '../output/logger.js';

export async function lockWorktree(target: string): Promise<void> {
  const repoRoot = await getRepoRoot();
  const record = await resolveWorktreeRecord(repoRoot, target);

  await execGit(['worktree', 'lock', record.path], { cwd: repoRoot });

  const metadata = await readMetadata(record.path);
  if (metadata) {
    metadata.locked = true;
    metadata.lockedAt = new Date().toISOString();
    metadata.lockedBy = 'manual';
    await writeMetadata(record.path, metadata);
  }

  await getLifecycle().onLock({
    worktreeId: metadata?.name ?? target,
    lockedBy: 'manual',
    timestamp: new Date().toISOString(),
  });

  log.success(`Locked: ${target}`);
}

export async function unlockWorktree(target: string): Promise<void> {
  const repoRoot = await getRepoRoot();
  const record = await resolveWorktreeRecord(repoRoot, target);

  await execGit(['worktree', 'unlock', record.path], { cwd: repoRoot });

  const metadata = await readMetadata(record.path);
  if (metadata) {
    metadata.locked = false;
    metadata.lockedAt = undefined;
    metadata.lockedBy = undefined;
    await writeMetadata(record.path, metadata);
  }

  await getLifecycle().onUnlock({
    worktreeId: metadata?.name ?? target,
    lockedBy: 'manual',
    timestamp: new Date().toISOString(),
  });

  log.success(`Unlocked: ${target}`);
}
