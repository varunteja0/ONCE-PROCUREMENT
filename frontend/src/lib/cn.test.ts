import { describe, expect, it } from 'vitest';
import { cn } from '@/lib/cn';

describe('cn', () => {
  it('joins string classes', () => {
    expect(cn('a', 'b')).toBe('a b');
  });

  it('skips falsy values', () => {
    expect(cn('a', false, null, undefined, '', 'b')).toBe('a b');
  });

  it('resolves conflicting tailwind utilities (last wins)', () => {
    expect(cn('p-2', 'p-4')).toBe('p-4');
  });

  it('handles arrays and objects', () => {
    expect(cn(['a', { b: true, c: false }], 'd')).toBe('a b d');
  });
});
