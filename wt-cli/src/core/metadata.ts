import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { join, dirname } from 'node:path';
import type { WorktreeMetadata } from '../types/metadata.js';

export function getMetadataPath(worktreePath: string): string {
  return join(worktreePath, '.worktree', 'local.json');
}

export async function readMetadata(worktreePath: string): Promise<WorktreeMetadata | null> {
  const metadataPath = getMetadataPath(worktreePath);
  try {
    const content = await readFile(metadataPath, 'utf8');
    return JSON.parse(content) as WorktreeMetadata;
  } catch (err) {
    if ((err as NodeJS.ErrnoException).code === 'ENOENT') {
      return null;
    }
    throw err;
  }
}

export async function writeMetadata(worktreePath: string, metadata: WorktreeMetadata): Promise<void> {
  const metadataPath = getMetadataPath(worktreePath);
  await mkdir(dirname(metadataPath), { recursive: true });
  await writeFile(metadataPath, JSON.stringify(metadata, null, 2) + '\n', 'utf8');
}
