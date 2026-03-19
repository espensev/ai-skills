import { copyFile, access } from 'node:fs/promises';
import { join } from 'node:path';

const ENV_CANDIDATES = ['.env.example', '.env.sample'] as const;

async function fileExists(path: string): Promise<boolean> {
  try {
    await access(path);
    return true;
  } catch {
    return false;
  }
}

export async function copyExampleEnvFile(worktreePath: string): Promise<string | null> {
  const targetPath = join(worktreePath, '.env');
  if (await fileExists(targetPath)) {
    return null; // .env already exists, don't overwrite
  }

  for (const candidate of ENV_CANDIDATES) {
    const sourcePath = join(worktreePath, candidate);
    if (await fileExists(sourcePath)) {
      await copyFile(sourcePath, targetPath);
      return candidate;
    }
  }

  return null;
}
