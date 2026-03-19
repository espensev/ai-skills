import { access } from 'node:fs/promises';
import { join } from 'node:path';
import { execFile } from 'node:child_process';
import { detectPlatform } from '../platform/detect.js';

async function fileExists(path: string): Promise<boolean> {
  try {
    await access(path);
    return true;
  } catch {
    return false;
  }
}

function commandExists(name: string): Promise<boolean> {
  const cmd = detectPlatform() === 'win32' ? 'where' : 'which';
  return new Promise((resolve) => {
    execFile(cmd, [name], (error) => resolve(!error));
  });
}

function run(command: string, args: string[], cwd: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const child = execFile(command, args, { cwd, encoding: 'utf8', maxBuffer: 10 * 1024 * 1024 }, (error) => {
      if (error) reject(new Error(`${command} ${args.join(' ')} failed: ${error.message}`));
      else resolve();
    });
    child.stdout?.pipe(process.stdout);
    child.stderr?.pipe(process.stderr);
  });
}

export interface BootstrapResult {
  packageManager: string | null;
  command: string | null;
}

export async function runBootstrapInstalls(worktreePath: string): Promise<BootstrapResult> {
  // JavaScript/TypeScript projects
  if (await fileExists(join(worktreePath, 'pnpm-lock.yaml'))) {
    await run('pnpm', ['install', '--prefer-offline'], worktreePath);
    return { packageManager: 'pnpm', command: 'pnpm install --prefer-offline' };
  }

  if (await fileExists(join(worktreePath, 'yarn.lock'))) {
    await run('yarn', ['install'], worktreePath);
    return { packageManager: 'yarn', command: 'yarn install' };
  }

  if (await fileExists(join(worktreePath, 'package.json'))) {
    await run('npm', ['install', '--prefer-offline'], worktreePath);
    return { packageManager: 'npm', command: 'npm install --prefer-offline' };
  }

  // Python projects
  if (await fileExists(join(worktreePath, 'uv.lock'))) {
    await run('uv', ['sync'], worktreePath);
    return { packageManager: 'uv', command: 'uv sync' };
  }

  if (await fileExists(join(worktreePath, 'pyproject.toml')) && await commandExists('uv')) {
    await run('uv', ['sync'], worktreePath);
    return { packageManager: 'uv', command: 'uv sync' };
  }

  if (await fileExists(join(worktreePath, 'requirements.txt'))) {
    const platform = detectPlatform();
    const pythonBin = platform === 'win32' ? 'Scripts\\python.exe' : 'bin/python';
    const venvPath = join(worktreePath, '.venv');

    await run('python', ['-m', 'venv', venvPath], worktreePath);
    await run(join(venvPath, pythonBin), ['-m', 'pip', 'install', '-r', 'requirements.txt'], worktreePath);
    return { packageManager: 'pip', command: 'pip install -r requirements.txt' };
  }

  return { packageManager: null, command: null };
}
