import { describe, expect, it } from 'vitest';
import { redact } from '@/lib/redact';

describe('redact', () => {
  it('redacts top-level sensitive keys', () => {
    const out = redact({ password: 'abc', email: 'x@y.z' }) as Record<string, unknown>;
    expect(out.password).toBe('[REDACTED]');
    expect(out.email).toBe('x@y.z');
  });
  it('redacts nested sensitive keys', () => {
    const out = redact({
      user: { access_token: 't', name: 'n' },
    }) as Record<string, Record<string, unknown>>;
    expect(out.user.access_token).toBe('[REDACTED]');
    expect(out.user.name).toBe('n');
  });
  it('redacts inside arrays', () => {
    const out = redact([{ ssn: '111' }]) as Array<Record<string, unknown>>;
    expect(out[0].ssn).toBe('[REDACTED]');
  });
  it('passes through primitives', () => {
    expect(redact(42)).toBe(42);
    expect(redact('s')).toBe('s');
    expect(redact(null)).toBeNull();
  });
  it('handles signature key', () => {
    const out = redact({ signature_b64: 'xx' }) as Record<string, unknown>;
    expect(out.signature_b64).toBe('[REDACTED]');
  });
});
