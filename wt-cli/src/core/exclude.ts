import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { dirname, isAbsolute, join } from 'node:path';
import { execGit } from './git.js';

export async function ensureRepoExcludePattern(repoRoot: string, pattern: string): Promise<void> {
  const result = await execGit(['rev-parse', '--git-path', 'info/exclude'], { cwd: repoRoot });
  let excludePath = result.stdout;

  if (!isAbsolute(excludePath)) {
    excludePath = join(repoRoot, excludePath);
  }

  await mkdir(dirname(excludePath), { recursive: true });

  let existing = '';
  try {
    existing = await readFile(excludePath, 'utf8');
  } catch (err) {
    if ((err as NodeJS.ErrnoException).code !== 'ENOENT') throw err;
  }

  const lines = existing.split(/\r?\n/);
  if (!lines.includes(pattern)) {
    const suffix = existing.endsWith('\n') || existing === '' ? '' : '\n';
    await writeFile(excludePath, existing + suffix + pattern + '\n', 'utf8');
  }
}
