import type { WorktreeLifecycle } from '../types/lifecycle.js';
import { noopLifecycle } from './noop.js';

let activeLifecycle: WorktreeLifecycle = noopLifecycle;

export function getLifecycle(): WorktreeLifecycle {
  return activeLifecycle;
}

export function setLifecycle(lifecycle: WorktreeLifecycle): void {
  activeLifecycle = lifecycle;
}
