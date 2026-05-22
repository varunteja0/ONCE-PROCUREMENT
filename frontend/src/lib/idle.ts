import { useEffect, useRef } from 'react';

const DEFAULT_TIMEOUT_MIN = 30;
const ACTIVITY_EVENTS: ReadonlyArray<keyof WindowEventMap> = [
  'mousemove',
  'mousedown',
  'keydown',
  'scroll',
  'touchstart',
];

function resolveTimeoutMs(): number {
  try {
    const raw = import.meta.env.VITE_IDLE_TIMEOUT_MIN;
    const n = typeof raw === 'string' ? Number(raw) : NaN;
    if (Number.isFinite(n) && n > 0) return n * 60_000;
  } catch {
    /* ignore */
  }
  return DEFAULT_TIMEOUT_MIN * 60_000;
}

/**
 * Fires `onIdle` after the configured period of user inactivity.
 * Listener is a no-op when `enabled === false`.
 */
export function useIdleTimeout(
  enabled: boolean,
  onIdle: () => void,
  timeoutMs?: number,
): void {
  const onIdleRef = useRef(onIdle);
  onIdleRef.current = onIdle;

  useEffect(() => {
    if (!enabled) return undefined;
    const limit = timeoutMs ?? resolveTimeoutMs();
    let timer = window.setTimeout(() => onIdleRef.current(), limit);

    function reset(): void {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => onIdleRef.current(), limit);
    }

    for (const ev of ACTIVITY_EVENTS) {
      window.addEventListener(ev, reset, { passive: true });
    }
    return () => {
      window.clearTimeout(timer);
      for (const ev of ACTIVITY_EVENTS) {
        window.removeEventListener(ev, reset);
      }
    };
  }, [enabled, timeoutMs]);
}
