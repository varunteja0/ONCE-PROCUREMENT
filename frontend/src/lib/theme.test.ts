import { afterEach, describe, expect, it } from 'vitest';
import { applyTheme, readTheme, writeTheme } from '@/lib/theme';

afterEach(() => {
  window.localStorage.clear();
  document.documentElement.classList.remove('dark');
});

describe('theme', () => {
  it('defaults to system', () => {
    expect(readTheme()).toBe('system');
  });

  it('writes and reads a theme', () => {
    writeTheme('dark');
    expect(readTheme()).toBe('dark');
  });

  it('applyTheme(dark) toggles .dark on documentElement', () => {
    applyTheme('dark');
    expect(document.documentElement.classList.contains('dark')).toBe(true);
  });

  it('applyTheme(light) removes .dark', () => {
    document.documentElement.classList.add('dark');
    applyTheme('light');
    expect(document.documentElement.classList.contains('dark')).toBe(false);
  });
});
