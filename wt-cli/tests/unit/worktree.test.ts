import { describe, it, expect } from 'vitest';
import { parseWorktreePorcelain } from '../../src/core/worktree.js';

const SAMPLE_PORCELAIN = `worktree /home/user/myapp
HEAD abc123def456
branch refs/heads/main

worktree /home/user/wt-myapp-auth
HEAD 789abcdef012
branch refs/heads/agent/auth

worktree /home/user/wt-myapp-review
HEAD deadbeef1234
detached

`;

const LOCKED_PORCELAIN = `worktree /home/user/myapp
HEAD abc123def456
branch refs/heads/main

worktree /home/user/wt-myapp-locked
HEAD 111222333444
branch refs/heads/agent/locked
locked important work in progress

`;

describe('parseWorktreePorcelain', () => {
  it('parses multiple worktree records', () => {
    const records = parseWorktreePorcelain(SAMPLE_PORCELAIN);
    expect(records).toHaveLength(3);
  });

  it('extracts path and HEAD', () => {
    const records = parseWorktreePorcelain(SAMPLE_PORCELAIN);
    expect(records[0].path).toBe('/home/user/myapp');
    expect(records[0].head).toBe('abc123def456');
  });

  it('extracts branch ref and short name', () => {
    const records = parseWorktreePorcelain(SAMPLE_PORCELAIN);
    expect(records[1].branchRef).toBe('refs/heads/agent/auth');
    expect(records[1].branchShort).toBe('agent/auth');
  });

  it('detects detached HEAD', () => {
    const records = parseWorktreePorcelain(SAMPLE_PORCELAIN);
    expect(records[2].detached).toBe(true);
    expect(records[2].branchRef).toBe('');
    expect(records[2].branchShort).toBe('');
  });

  it('detects locked worktree with reason', () => {
    const records = parseWorktreePorcelain(LOCKED_PORCELAIN);
    expect(records[1].locked).toBe(true);
    expect(records[1].lockReason).toBe('important work in progress');
  });

  it('handles empty input', () => {
    expect(parseWorktreePorcelain('')).toEqual([]);
  });

  it('handles Windows-style line endings', () => {
    const windowsOutput = SAMPLE_PORCELAIN.replace(/\n/g, '\r\n');
    const records = parseWorktreePorcelain(windowsOutput);
    expect(records).toHaveLength(3);
  });
});
