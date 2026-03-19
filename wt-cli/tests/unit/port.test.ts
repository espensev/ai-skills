import { describe, it, expect } from 'vitest';
import { getStableHashNumber } from '../../src/core/port.js';

describe('getStableHashNumber', () => {
  it('returns a consistent number for the same input', () => {
    const a = getStableHashNumber('test');
    const b = getStableHashNumber('test');
    expect(a).toBe(b);
  });

  it('returns different numbers for different inputs', () => {
    const a = getStableHashNumber('auth');
    const b = getStableHashNumber('payments');
    expect(a).not.toBe(b);
  });

  it('returns a positive number', () => {
    expect(getStableHashNumber('anything')).toBeGreaterThanOrEqual(0);
  });

  it('returns a 32-bit unsigned integer', () => {
    const result = getStableHashNumber('test-value');
    expect(result).toBeLessThanOrEqual(0xFFFFFFFF);
  });
});
