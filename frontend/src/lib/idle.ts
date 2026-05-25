import { useCallback, useEffect, useRef } from "react";

const DEFAULT_TIMEOUT_MIN = 30;
const ACTIVITY_EVENTS: ReadonlyArray<keyof WindowEventMap> = [
  "mousemove",
  "mousedown",
  "keydown",
  "scroll",
  "touchstart",
];

function resolveTimeoutMs(): number {
  try {
    const raw = import.meta.env.VITE_IDLE_TIMEOUT_MIN;
    const n = typeof raw === "string" ? Number(raw) : NaN;
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
export function useIdleTimeout(enabled: boolean, onIdle: () => void, timeoutMs?: number): void {
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

export interface IdleTimerOptions {
  idleMs: number;
  warningMs: number;
  onWarn: () => void;
  onIdle: () => void;
  enabled: boolean;
}

export interface IdleTimerControls {
  reset: () => void;
}

/**
 * Fires `onWarn` at `idleMs - warningMs` and `onIdle` at `idleMs` of user
 * inactivity. Returns a `reset()` helper so callers (e.g. a "Stay signed
 * in" button) can postpone both timers. No-op when `enabled === false`.
 */
export function useIdleTimer(options: IdleTimerOptions): IdleTimerControls {
  const { idleMs, warningMs, onWarn, onIdle, enabled } = options;

  const onWarnRef = useRef(onWarn);
  const onIdleRef = useRef(onIdle);
  onWarnRef.current = onWarn;
  onIdleRef.current = onIdle;

  const warnTimerRef = useRef<number | null>(null);
  const idleTimerRef = useRef<number | null>(null);

  const reset = useCallback((): void => {
    if (warnTimerRef.current !== null) window.clearTimeout(warnTimerRef.current);
    if (idleTimerRef.current !== null) window.clearTimeout(idleTimerRef.current);
    if (!enabled) return;
    const warnDelay = Math.max(0, idleMs - warningMs);
    warnTimerRef.current = window.setTimeout(() => onWarnRef.current(), warnDelay);
    idleTimerRef.current = window.setTimeout(() => onIdleRef.current(), idleMs);
  }, [enabled, idleMs, warningMs]);

  useEffect(() => {
    if (!enabled) {
      if (warnTimerRef.current !== null) window.clearTimeout(warnTimerRef.current);
      if (idleTimerRef.current !== null) window.clearTimeout(idleTimerRef.current);
      return undefined;
    }
    reset();

    function onActivity(): void {
      reset();
    }

    for (const ev of ACTIVITY_EVENTS) {
      window.addEventListener(ev, onActivity, { passive: true });
    }
    return () => {
      if (warnTimerRef.current !== null) window.clearTimeout(warnTimerRef.current);
      if (idleTimerRef.current !== null) window.clearTimeout(idleTimerRef.current);
      for (const ev of ACTIVITY_EVENTS) {
        window.removeEventListener(ev, onActivity);
      }
    };
  }, [enabled, reset]);

  return { reset };
}
