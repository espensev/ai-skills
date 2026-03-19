import { describe, it, expect } from 'vitest';
import { parseShortstat, sortBySmallestDiff, type MergePlan } from '../../src/core/merge-planner.js';

describe('parseShortstat', () => {
  it('parses full stat line', () => {
    const result = parseShortstat(' 3 files changed, 42 insertions(+), 10 deletions(-)');
    expect(result).toEqual({
      filesChanged: 3,
      insertions: 42,
      deletions: 10,
      totalChanges: 52,
    });
  });

  it('parses insertions only', () => {
    const result = parseShortstat(' 1 file changed, 5 insertions(+)');
    expect(result).toEqual({
      filesChanged: 1,
      insertions: 5,
      deletions: 0,
      totalChanges: 5,
    });
  });

  it('parses deletions only', () => {
    const result = parseShortstat(' 2 files changed, 3 deletions(-)');
    expect(result).toEqual({
      filesChanged: 2,
      insertions: 0,
      deletions: 3,
      totalChanges: 3,
    });
  });

  it('handles empty input', () => {
    const result = parseShortstat('');
    expect(result).toEqual({
      filesChanged: 0,
      insertions: 0,
      deletions: 0,
      totalChanges: 0,
    });
  });
});

describe('sortBySmallestDiff', () => {
  it('sorts plans by total changes ascending', () => {
    const plans: MergePlan[] = [
      { worktreeName: 'big', branch: 'agent/big', stats: { filesChanged: 10, insertions: 200, deletions: 100, totalChanges: 300 }, hasConflicts: false },
      { worktreeName: 'small', branch: 'agent/small', stats: { filesChanged: 1, insertions: 5, deletions: 2, totalChanges: 7 }, hasConflicts: false },
      { worktreeName: 'medium', branch: 'agent/medium', stats: { filesChanged: 5, insertions: 50, deletions: 20, totalChanges: 70 }, hasConflicts: false },
    ];

    const sorted = sortBySmallestDiff(plans);
    expect(sorted.map((p) => p.worktreeName)).toEqual(['small', 'medium', 'big']);
  });

  it('does not mutate original array', () => {
    const plans: MergePlan[] = [
      { worktreeName: 'b', branch: 'b', stats: { filesChanged: 2, insertions: 20, deletions: 10, totalChanges: 30 }, hasConflicts: false },
      { worktreeName: 'a', branch: 'a', stats: { filesChanged: 1, insertions: 5, deletions: 2, totalChanges: 7 }, hasConflicts: false },
    ];

    sortBySmallestDiff(plans);
    expect(plans[0].worktreeName).toBe('b');
  });
});
