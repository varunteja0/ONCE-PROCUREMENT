/**
 * Structured logger. Console output is suppressed in production except for
 * errors. Use this in committed code in place of `console.log`.
 *
 * When @sentry/react is installed, wire `Sentry.captureException` inside
 * `captureException` below, gated by `import.meta.env.VITE_SENTRY_DSN`.
 */

type Level = 'debug' | 'info' | 'warn' | 'error';

interface LogContext {
  readonly [key: string]: unknown;
}

function isProduction(): boolean {
  try {
    return import.meta.env.PROD === true;
  } catch {
    return false;
  }
}

function isDebugEnabled(): boolean {
  try {
    return Boolean(import.meta.env.VITE_LOG_DEBUG);
  } catch {
    return false;
  }
}

function emit(level: Level, message: string, ctx?: LogContext): void {
  if (isProduction() && level !== 'error') return;
  if (level === 'debug' && !isDebugEnabled()) return;

  const payload = ctx ? { msg: message, ...ctx } : { msg: message };
  /* eslint-disable no-console */
  switch (level) {
    case 'debug':
      console.debug(payload);
      return;
    case 'info':
      console.info(payload);
      return;
    case 'warn':
      console.warn(payload);
      return;
    case 'error':
      console.error(payload);
      return;
  }
  /* eslint-enable no-console */
}

function captureException(
  err: unknown,
  context?: Record<string, unknown>,
): void {
  if (isProduction()) {
    // No-op in production until @sentry/react is installed and wired:
    //   if (import.meta.env.VITE_SENTRY_DSN) {
    //     Sentry.captureException(err, { extra: context });
    //   }
    return;
  }
  /* eslint-disable-next-line no-console */
  console.error(err, context);
}

export const logger = {
  debug: (msg: string, ctx?: LogContext): void => emit('debug', msg, ctx),
  info: (msg: string, ctx?: LogContext): void => emit('info', msg, ctx),
  warn: (msg: string, ctx?: LogContext): void => emit('warn', msg, ctx),
  error: (msg: string, ctx?: LogContext): void => emit('error', msg, ctx),
  captureException,
};
