import { describe, expect, it } from 'vitest';
import {
  formatDate,
  formatDateTime,
  isWithinNextDays,
  isWithinPastDays,
  parseIso,
} from '@/lib/dates';

describe('parseIso', () => {
  it('returns null for empty values', () => {
    expect(parseIso(null)).toBeNull();
    expect(parseIso(undefined)).toBeNull();
    expect(parseIso('')).toBeNull();
  });
  it('parses valid ISO date', () => {
    expect(parseIso('2024-01-02T03:04:05Z')).toBeInstanceOf(Date);
  });
  it('returns null for invalid', () => {
    expect(parseIso('not-a-date')).toBeNull();
  });
});

describe('formatDate/formatDateTime', () => {
  it('returns fallback for empty', () => {
    expect(formatDate(null)).toBe('—');
    expect(formatDateTime(null)).toBe('—');
  });
  it('produces non-empty for valid', () => {
    expect(formatDate('2024-06-15T00:00:00Z')).not.toBe('');
    expect(formatDateTime('2024-06-15T00:00:00Z')).not.toBe('');
  });
});

describe('isWithinNextDays / isWithinPastDays', () => {
  it('returns false for null', () => {
    expect(isWithinNextDays(null, 30)).toBe(false);
    expect(isWithinPastDays(null, 30)).toBe(false);
  });
  it('detects future within window', () => {
    const future = new Date(Date.now() + 5 * 86400000).toISOString();
    expect(isWithinNextDays(future, 10)).toBe(true);
    expect(isWithinNextDays(future, 1)).toBe(false);
  });
  it('detects past within window', () => {
    const past = new Date(Date.now() - 5 * 86400000).toISOString();
    expect(isWithinPastDays(past, 10)).toBe(true);
    expect(isWithinPastDays(past, 1)).toBe(false);
  });
});
