/**
 * Anti open-redirect helpers.
 *
 * `sanitizeRedirect` returns the input only when it is a safe, same-origin
 * root-relative path (e.g. "/dashboard"). Anything else collapses to "/".
 */

const FALLBACK = '/';

export function sanitizeRedirect(url: string): string {
  if (typeof url !== 'string' || url.length === 0) return FALLBACK;
  // Protocol-relative ("//evil.com") - browser resolves to external origin.
  if (url.startsWith('//')) return FALLBACK;
  // Backslash confusion: some browsers normalise "\" -> "/", so "/\\evil.com"
  // can become "//evil.com". Reject any backslash defensively.
  if (url.includes('\\')) return FALLBACK;
  // Must be a root-relative path.
  if (!url.startsWith('/')) return FALLBACK;
  // Defence in depth: reject anything that looks like a scheme.
  if (/^[a-z][a-z0-9+\-.]*:/i.test(url)) return FALLBACK;
  return url;
}
