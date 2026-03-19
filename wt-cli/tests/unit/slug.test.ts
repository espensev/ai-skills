import { describe, it, expect } from 'vitest';
import { toWorktreeSlug } from '../../src/core/slug.js';

describe('toWorktreeSlug', () => {
  it('lowercases input', () => {
    expect(toWorktreeSlug('Auth')).toBe('auth');
    expect(toWorktreeSlug('MY-FEATURE')).toBe('my-feature');
  });

  it('replaces non-alphanumeric chars with dashes', () => {
    expect(toWorktreeSlug('my feature!')).toBe('my-feature');
    expect(toWorktreeSlug('feat/auth@v2')).toBe('feat-auth-v2');
  });

  it('preserves dots and underscores', () => {
    expect(toWorktreeSlug('v1.2.3')).toBe('v1.2.3');
    expect(toWorktreeSlug('my_feature')).toBe('my_feature');
  });

  it('trims leading and trailing dashes', () => {
    expect(toWorktreeSlug('--auth--')).toBe('auth');
    expect(toWorktreeSlug('!auth!')).toBe('auth');
  });

  it('collapses multiple special chars into single dash', () => {
    expect(toWorktreeSlug('a   b   c')).toBe('a-b-c');
    expect(toWorktreeSlug('a///b')).toBe('a-b');
  });

  it('throws on empty result', () => {
    expect(() => toWorktreeSlug('!!!')).toThrow('Unable to derive');
    expect(() => toWorktreeSlug('---')).toThrow('Unable to derive');
  });

  it('handles simple names unchanged', () => {
    expect(toWorktreeSlug('auth')).toBe('auth');
    expect(toWorktreeSlug('payments')).toBe('payments');
  });
});
