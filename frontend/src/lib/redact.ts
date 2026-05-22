const SENSITIVE_KEYS = new Set([
  'password',
  'access_token',
  'refresh_token',
  'token',
  'authorization',
  'api_key',
  'apikey',
  'ein',
  'ssn',
  'tax_id',
  'signature_b64',
  'signature',
  'private_key',
  'private_key_pem',
]);

const REDACTED = '[REDACTED]';

export function redact(value: unknown, depth = 0): unknown {
  if (depth > 4) return REDACTED;
  if (value === null || value === undefined) return value;
  if (Array.isArray(value)) {
    return value.map((v) => redact(v, depth + 1));
  }
  if (typeof value === 'object') {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      if (SENSITIVE_KEYS.has(k.toLowerCase())) {
        out[k] = REDACTED;
      } else {
        out[k] = redact(v, depth + 1);
      }
    }
    return out;
  }
  return value;
}
