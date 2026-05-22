import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { toHaveNoViolations } from 'jest-axe';
import { afterEach, expect, vi } from 'vitest';

expect.extend(toHaveNoViolations);

afterEach(() => {
  cleanup();
});

// JSDom does not implement matchMedia; the theme provider depends on it.
if (typeof window !== 'undefined' && !window.matchMedia) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }),
  });
}

// jsdom lacks ResizeObserver — stub it so Radix-like UI does not crash.
if (typeof window !== 'undefined' && !('ResizeObserver' in window)) {
  class ResizeObserverMock {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  }
  (window as unknown as { ResizeObserver: typeof ResizeObserverMock }).ResizeObserver =
    ResizeObserverMock;
}

// jest-axe types augmentation
declare module 'vitest' {
  // eslint-disable-next-line @typescript-eslint/no-empty-interface
  interface Assertion {
    toHaveNoViolations(): void;
  }
  // eslint-disable-next-line @typescript-eslint/no-empty-interface
  interface AsymmetricMatchersContaining {
    toHaveNoViolations(): void;
  }
}
