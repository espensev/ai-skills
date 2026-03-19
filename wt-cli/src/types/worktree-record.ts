export interface GitWorktreeRecord {
  path: string;
  head: string;
  branchRef: string;
  branchShort: string;
  detached: boolean;
  bare: boolean;
  locked: boolean;
  lockReason: string;
  prunable: boolean;
  prunableReason: string;
}
