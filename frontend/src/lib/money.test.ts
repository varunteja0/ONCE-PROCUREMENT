import { describe, expect, it } from 'vitest';
import { formatMoney } from '@/lib/money';

describe('formatMoney', () => {
  it('returns fallback for null/undefined/empty', () => {
    expect(formatMoney(null)).toBe('—');
    expect(formatMoney(undefined)).toBe('—');
    expect(formatMoney('')).toBe('—');
  });

  it('returns fallback for non-numeric strings', () => {
    expect(formatMoney('abc')).toBe('—');
    expect(formatMoney(Number.NaN)).toBe('—');
  });

  it('formats numbers as USD by default', () => {
    expect(formatMoney(1234.5)).toMatch(/1,234\.5/);
    expect(formatMoney(1234.5)).toMatch(/\$/);
  });

  it('formats numeric strings', () => {
    expect(formatMoney('1000')).toMatch(/1,000/);
  });

  it('honors custom currency', () => {
    const out = formatMoney(100, 'EUR');
    expect(out).toMatch(/100/);
  });

  it('honors custom fallback', () => {
    expect(formatMoney(null, 'USD', 'n/a')).toBe('n/a');
  });
});
