export interface WorktreeMetadata {
  name: string;
  path: string;
  worktreeRoot: string;
  sourceRepoRoot: string | null;
  branch: string;
  port: number;
  scope: string;
  envSource: string | null;
  createdAtUtc: string;
  locked?: boolean;
  lockedAt?: string;
  lockedBy?: string;
}
