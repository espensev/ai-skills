import { createHash } from 'node:crypto';
import { getWorktreeRecords } from './worktree.js';
import { readMetadata } from './metadata.js';

const DEFAULT_BASE_PORT = 3000;
const DEFAULT_SPAN = 1000;

export function getStableHashNumber(text: string): number {
  const hash = createHash('sha256').update(text, 'utf8').digest();
  return hash.readUInt32LE(0);
}

export async function getUsedWorktreePorts(repoRoot: string): Promise<Set<number>> {
  const ports = new Set<number>();
  const records = await getWorktreeRecords(repoRoot);

  for (const record of records) {
    const metadata = await readMetadata(record.path);
    if (metadata?.port != null) {
      ports.add(metadata.port);
    }
  }

  return ports;
}

export async function getPreferredPort(
  repoRoot: string,
  seed: string,
  basePort: number = DEFAULT_BASE_PORT,
  span: number = DEFAULT_SPAN,
): Promise<number> {
  const usedPorts = await getUsedWorktreePorts(repoRoot);
  const offset = getStableHashNumber(seed);
  const candidate = basePort + (offset % span);

  for (let i = 0; i < span; i++) {
    const port = basePort + ((candidate - basePort + i) % span);
    if (!usedPorts.has(port)) {
      return port;
    }
  }

  throw new Error(`Unable to allocate a free port in the range ${basePort}-${basePort + span - 1}.`);
}
