import { execFile } from 'node:child_process';

export interface GitResult {
  exitCode: number;
  stdout: string;
  stderr: string;
}

export async function execGit(
  args: string[],
  options?: { cwd?: string; allowFailure?: boolean },
): Promise<GitResult> {
  const cwd = options?.cwd ?? process.cwd();
  const allowFailure = options?.allowFailure ?? false;

  return new Promise((resolve, reject) => {
    execFile('git', args, { cwd, encoding: 'utf8', maxBuffer: 10 * 1024 * 1024 }, (error, stdout, stderr) => {
      const exitCode = error?.code === 'ENOENT'
        ? -1
        : (error as NodeJS.ErrnoException & { status?: number })?.status ?? 0;

      if (error?.code === 'ENOENT') {
        reject(new Error('Required command \'git\' was not found. Install Git and make sure it is available on PATH.'));
        return;
      }

      const result: GitResult = {
        exitCode,
        stdout: (stdout ?? '').trim(),
        stderr: (stderr ?? '').trim(),
      };

      if (!allowFailure && result.exitCode !== 0) {
        const message = result.stderr || result.stdout || 'git command failed.';
        reject(new Error(`git ${args.join(' ')} failed: ${message}`));
        return;
      }

      resolve(result);
    });
  });
}

export async function getRepoRoot(cwd?: string): Promise<string> {
  const result = await execGit(['rev-parse', '--show-toplevel'], { cwd, allowFailure: true });
  if (result.exitCode !== 0 || !result.stdout) {
    throw new Error('This command must be run inside a Git repository.');
  }
  return result.stdout;
}
