export interface SpawnContext {
  worktreeId: string;
  branchId: string;
  executionMode: 'worktree';
  path: string;
  port: number;
  scope: string;
  timestamp: string;
}

export interface BootstrapContext {
  worktreeId: string;
  path: string;
  envSource: string | null;
  depsInstalled: boolean;
  timestamp: string;
}

export interface ScopeContext {
  worktreeId: string;
  scope: string;
  previousScope: string;
  timestamp: string;
}

export interface MergeContext {
  worktreeId: string;
  branchId: string;
  targetBranch: string;
  filesChanged: number;
  insertions: number;
  deletions: number;
  hasConflicts: boolean;
  timestamp: string;
}

export interface TeardownContext {
  worktreeId: string;
  branchId: string;
  branchDeleted: boolean;
  timestamp: string;
}

export interface LockContext {
  worktreeId: string;
  lockedBy: string;
  timestamp: string;
}

export interface WorktreeLifecycle {
  onSpawn(ctx: SpawnContext): Promise<void>;
  onBootstrap(ctx: BootstrapContext): Promise<void>;
  onScopeAssigned(ctx: ScopeContext): Promise<void>;
  onMergeStart(ctx: MergeContext): Promise<void>;
  onMergeComplete(ctx: MergeContext): Promise<void>;
  onTeardown(ctx: TeardownContext): Promise<void>;
  onLock(ctx: LockContext): Promise<void>;
  onUnlock(ctx: LockContext): Promise<void>;
}
