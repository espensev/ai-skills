import { execGit } from '../core/git.js';
import { isWindows } from './detect.js';
import { execFile } from 'node:child_process';

export interface WindowsChecks {
  longPathsEnabled: boolean;
  gitLongPathsEnabled: boolean;
}

export async function checkWindowsLongPaths(repoRoot: string): Promise<WindowsChecks> {
  if (!isWindows()) {
    return { longPathsEnabled: true, gitLongPathsEnabled: true };
  }

  let gitLongPathsEnabled = false;
  try {
    const result = await execGit(['config', '--get', 'core.longpaths'], { cwd: repoRoot, allowFailure: true });
    gitLongPathsEnabled = result.stdout.toLowerCase() === 'true';
  } catch {
    // ignore
  }

  let longPathsEnabled = false;
  try {
    longPathsEnabled = await checkRegistryLongPaths();
  } catch {
    // ignore — registry access may be restricted
  }

  return { longPathsEnabled, gitLongPathsEnabled };
}

function checkRegistryLongPaths(): Promise<boolean> {
  return new Promise((resolve) => {
    execFile(
      'reg',
      ['query', 'HKLM\\SYSTEM\\CurrentControlSet\\Control\\FileSystem', '/v', 'LongPathsEnabled'],
      { encoding: 'utf8' },
      (error, stdout) => {
        if (error) {
          resolve(false);
          return;
        }
        // Output contains "REG_DWORD    0x1" if enabled
        resolve(/0x1/.test(stdout));
      },
    );
  });
}

export function checkPathLength(path: string, maxLength = 200): string | null {
  if (path.length > maxLength) {
    return `Path length (${path.length}) exceeds recommended maximum of ${maxLength} characters: ${path}`;
  }
  return null;
}
