import { getRepoRoot } from '../core/git.js';
import { getWorktreeRecords } from '../core/worktree.js';
import { readMetadata } from '../core/metadata.js';
import { formatTable } from '../output/formatter.js';
import { outputJson } from '../output/json.js';

export async function showPorts(json: boolean): Promise<void> {
  const repoRoot = await getRepoRoot();
  const records = await getWorktreeRecords(repoRoot);

  const rows = [];
  for (const record of records) {
    const metadata = await readMetadata(record.path);
    if (metadata?.port != null) {
      rows.push({
        name: metadata.name || record.branchShort || '(unknown)',
        port: String(metadata.port),
        branch: record.branchShort || '(detached)',
        scope: metadata.scope || '',
      });
    }
  }

  rows.sort((a, b) => parseInt(a.port) - parseInt(b.port));

  if (json) {
    outputJson(rows);
    return;
  }

  if (rows.length === 0) {
    console.log('No port allocations found.');
    return;
  }

  const table = formatTable(
    [
      { key: 'port', label: 'PORT', align: 'right' },
      { key: 'name', label: 'NAME' },
      { key: 'branch', label: 'BRANCH' },
      { key: 'scope', label: 'SCOPE' },
    ],
    rows,
  );

  console.log(table);
}
