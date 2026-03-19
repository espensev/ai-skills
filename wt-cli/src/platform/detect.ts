export type Platform = 'win32' | 'darwin' | 'linux';

export function detectPlatform(): Platform {
  const p = process.platform;
  if (p === 'win32') return 'win32';
  if (p === 'darwin') return 'darwin';
  return 'linux';
}

export function isWindows(): boolean {
  return process.platform === 'win32';
}

export function getTerminalWidth(): number {
  return process.stdout.columns ?? 80;
}
