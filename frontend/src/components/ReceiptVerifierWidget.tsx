import { useCallback, useEffect, useMemo, useState } from 'react';
import { Check, Copy, Loader2, ShieldAlert, ShieldCheck } from 'lucide-react';
import { api, isApiCancel, isApiError } from '@/services/api';

export interface VerifyResponse {
  payload: Record<string, unknown>;
  signature: string;
  public_key: string;
  signing_key_id: string;
  public_key_fingerprint: string;
  verified: boolean;
  error?: string;
}

export interface ReceiptVerifierWidgetProps {
  receiptId: string;
  /** Optional explicit verifier base URL. Falls back to VITE_VERIFIER_BASE then '/verify'. */
  verifierBase?: string;
  className?: string;
}

function resolveVerifierBase(explicit?: string): string {
  if (explicit && explicit.length > 0) return explicit.replace(/\/$/, '');
  const raw: unknown = import.meta.env.VITE_VERIFIER_BASE;
  if (typeof raw === 'string' && raw.length > 0) return raw.replace(/\/$/, '');
  return '/verify';
}

function renderValue(value: unknown): string {
  if (value === null) return 'null';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

export default function ReceiptVerifierWidget({
  receiptId,
  verifierBase,
  className,
}: ReceiptVerifierWidgetProps): JSX.Element {
  const [data, setData] = useState<VerifyResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [copied, setCopied] = useState<boolean>(false);

  const base = useMemo(() => resolveVerifierBase(verifierBase), [verifierBase]);

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();

    async function run(): Promise<void> {
      setLoading(true);
      setError(null);
      setData(null);
      try {
        const resp = await api.get<VerifyResponse>(
          `${base}/${encodeURIComponent(receiptId)}`,
          {
            signal: controller.signal,
            headers: { Accept: 'application/json' },
            _onceSkipAuth: true,
          },
        );
        if (!cancelled) setData(resp.data);
      } catch (e) {
        if (cancelled) return;
        if (isApiCancel(e)) return;
        if (e instanceof DOMException && e.name === 'AbortError') return;
        const msg =
          isApiError(e) && e.response
            ? `Verifier returned HTTP ${e.response.status}`
            : e instanceof Error
              ? e.message
              : 'Verification request failed';
        setError(msg);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void run();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [base, receiptId]);

  const handleCopy = useCallback(async () => {
    if (!data) return;
    try {
      const text = JSON.stringify(data, null, 2);
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setError('Copy to clipboard failed');
    }
  }, [data]);

  const containerClass = [
    'rounded-lg border bg-white p-4 shadow-sm dark:bg-slate-900',
    className ?? '',
  ]
    .filter(Boolean)
    .join(' ');

  if (loading) {
    return (
      <div
        className={`${containerClass} border-slate-200 dark:border-slate-800`}
        role="status"
        aria-live="polite"
        aria-busy="true"
      >
        <div className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
          <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
          Verifying receipt…
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div
        className={`${containerClass} border-rose-200 dark:border-rose-900`}
        role="alert"
        aria-live="assertive"
      >
        <div className="flex items-center gap-2 text-sm font-semibold text-rose-800 dark:text-rose-200">
          <ShieldAlert aria-hidden="true" className="h-5 w-5" />
          Verification failed
        </div>
        <p className="mt-2 text-sm text-rose-700 dark:text-rose-300">
          {error ?? 'No verification payload returned.'}
        </p>
      </div>
    );
  }

  const verified = data.verified === true;
  const payloadEntries = Object.entries(data.payload ?? {});

  return (
    <div
      className={`${containerClass} ${
        verified
          ? 'border-emerald-200 dark:border-emerald-900'
          : 'border-rose-200 dark:border-rose-900'
      }`}
      aria-live="polite"
    >
      <div className="flex items-start justify-between gap-3">
        <div
          className={`flex items-center gap-2 text-sm font-semibold ${
            verified
              ? 'text-emerald-800 dark:text-emerald-200'
              : 'text-rose-800 dark:text-rose-200'
          }`}
          role="status"
        >
          {verified ? (
            <ShieldCheck aria-hidden="true" className="h-5 w-5" />
          ) : (
            <ShieldAlert aria-hidden="true" className="h-5 w-5" />
          )}
          {verified
            ? 'Signature verified · Ed25519'
            : 'Signature did not verify'}
        </div>
        <button
          type="button"
          onClick={handleCopy}
          aria-label="Copy receipt JSON to clipboard"
          className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-900 focus-visible:ring-offset-2 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800 dark:focus-visible:ring-slate-100"
        >
          {copied ? (
            <Check aria-hidden="true" className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" />
          ) : (
            <Copy aria-hidden="true" className="h-3.5 w-3.5" />
          )}
          {copied ? 'Copied' : 'Copy JSON'}
        </button>
      </div>

      <dl className="mt-4 grid grid-cols-1 gap-x-6 gap-y-2 text-xs sm:grid-cols-[max-content_1fr]">
        <dt className="font-medium text-slate-600 dark:text-slate-400">Signing key ID</dt>
        <dd className="break-all font-mono text-slate-900 dark:text-slate-100">
          {data.signing_key_id}
        </dd>
        <dt className="font-medium text-slate-600 dark:text-slate-400">Public key fingerprint</dt>
        <dd className="break-all font-mono text-slate-900 dark:text-slate-100">
          {data.public_key_fingerprint}
        </dd>
      </dl>

      <div className="mt-4">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-400">
          Receipt payload
        </h4>
        <div className="mt-2 overflow-x-auto rounded-md border border-slate-200 dark:border-slate-800">
          <table className="min-w-full divide-y divide-slate-200 text-xs dark:divide-slate-800">
            <caption className="sr-only">Receipt payload fields</caption>
            <thead className="bg-slate-50 text-left font-medium uppercase tracking-wide text-slate-600 dark:bg-slate-950/40 dark:text-slate-400">
              <tr>
                <th scope="col" className="px-3 py-2">
                  Field
                </th>
                <th scope="col" className="px-3 py-2">
                  Value
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white dark:divide-slate-800 dark:bg-slate-900">
              {payloadEntries.length === 0 ? (
                <tr>
                  <td
                    colSpan={2}
                    className="px-3 py-3 text-center text-slate-500 dark:text-slate-400"
                  >
                    Empty payload
                  </td>
                </tr>
              ) : (
                payloadEntries.map(([key, value]) => (
                  <tr key={key}>
                    <th
                      scope="row"
                      className="whitespace-nowrap px-3 py-2 text-left font-medium text-slate-700 dark:text-slate-300"
                    >
                      {key}
                    </th>
                    <td className="break-all px-3 py-2 font-mono text-slate-900 dark:text-slate-100">
                      {renderValue(value)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
