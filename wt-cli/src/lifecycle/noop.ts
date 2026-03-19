import type { WorktreeLifecycle } from '../types/lifecycle.js';

export const noopLifecycle: WorktreeLifecycle = {
  onSpawn: async () => {},
  onBootstrap: async () => {},
  onScopeAssigned: async () => {},
  onMergeStart: async () => {},
  onMergeComplete: async () => {},
  onTeardown: async () => {},
  onLock: async () => {},
  onUnlock: async () => {},
};
