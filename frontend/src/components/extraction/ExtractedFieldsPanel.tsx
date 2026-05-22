// --- L3.8 pdf extraction ---
/**
 * Editable preview of an extractor's output.
 *
 * Each row shows: field key (human-formatted), the current value, an
 * optional confidence badge, and a text input for the operator to
 * override the value. Overrides are accumulated in local state and
 * surfaced via the `onAccept` / `onReject` callbacks - persistence is
 * the caller's responsibility (typically `useAcceptExtraction` /
 * `useRejectExtraction`).
 *
 * The component is intentionally framework-light: no form library, no
 * controlled-vs-uncontrolled tricks. It renders editable strings for
 * primitive values and a read-only JSON preview for nested objects /
 * arrays so the user can at least *see* policy arrays etc.
 */

import { useMemo, useState } from 'react';

import type { ExtractionRead } from '@/services/extractionsApi';

import { ConfidenceBadge } from './ConfidenceBadge';

export interface ExtractedFieldsPanelProps {
  extraction: ExtractionRead;
  onAccept?: (overrides: Record<string, unknown>) => void;
  onReject?: (reason: string) => void;
  /** When true, the form is read-only (e.g. already accepted/rejected). */
  readOnly?: boolean;
}

function formatKey(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .replace(/\bCents\b/, '(cents)');
}

function isPrimitive(v: unknown): v is string | number | boolean | null {
  return (
    v === null ||
    typeof v === 'string' ||
    typeof v === 'number' ||
    typeof v === 'boolean'
  );
}

function stringify(v: unknown): string {
  if (v === null || v === undefined) return '';
  if (typeof v === 'object') return JSON.stringify(v);
  return String(v);
}

export function ExtractedFieldsPanel({
  extraction,
  onAccept,
  onReject,
  readOnly = false,
}: ExtractedFieldsPanelProps): JSX.Element {
  const fields = useMemo(
    () => extraction.extracted_fields ?? {},
    [extraction.extracted_fields],
  );
  const confidences = extraction.field_confidences ?? {};
  const warnings = extraction.warnings ?? [];

  const fieldKeys = useMemo(() => Object.keys(fields).sort(), [fields]);
  const [overrides, setOverrides] = useState<Record<string, string>>({});
  const [reason, setReason] = useState<string>('');

  function handleChange(key: string, value: string) {
    setOverrides((prev) => ({ ...prev, [key]: value }));
  }

  function handleAccept() {
    if (!onAccept) return;
    const final: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(overrides)) {
      // Empty string ⇒ user wants to delete this override - skip.
      if (v === '') continue;
      const original = fields[k];
      if (typeof original === 'number' && /^-?\d+(\.\d+)?$/.test(v)) {
        final[k] = Number(v);
      } else if (typeof original === 'boolean') {
        final[k] = v.toLowerCase() === 'true';
      } else {
        final[k] = v;
      }
    }
    onAccept(final);
  }

  function handleReject() {
    if (!onReject) return;
    onReject(reason.trim());
  }

  return (
    <section
      data-testid="extracted-fields-panel"
      className="rounded border border-gray-200 bg-white p-4"
    >
      <header className="mb-3 flex items-center justify-between">
        <div>
          <h3 className="text-base font-semibold text-gray-900">
            Extracted fields
          </h3>
          <p className="text-xs text-gray-500">
            status: <span data-testid="status">{extraction.status}</span> ·
            extractor v{extraction.extractor_version}
          </p>
        </div>
      </header>

      {warnings.length > 0 && (
        <ul
          data-testid="warnings"
          className="mb-3 list-disc rounded bg-yellow-50 p-2 pl-6 text-xs text-yellow-800"
        >
          {warnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      )}

      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs uppercase tracking-wide text-gray-500">
            <th className="py-1">Field</th>
            <th className="py-1">Extracted</th>
            <th className="py-1">Confidence</th>
            <th className="py-1">Override</th>
          </tr>
        </thead>
        <tbody>
          {fieldKeys.length === 0 && (
            <tr>
              <td colSpan={4} className="py-3 text-gray-500">
                No fields extracted.
              </td>
            </tr>
          )}
          {fieldKeys.map((key) => {
            const value = fields[key];
            const conf = confidences[key];
            return (
              <tr key={key} className="border-t border-gray-100">
                <td className="py-2 font-medium text-gray-700">
                  {formatKey(key)}
                </td>
                <td className="py-2 font-mono text-xs text-gray-900">
                  {isPrimitive(value) ? (
                    stringify(value)
                  ) : (
                    <pre className="whitespace-pre-wrap">{stringify(value)}</pre>
                  )}
                </td>
                <td className="py-2">
                  {typeof conf === 'number' ? (
                    <ConfidenceBadge value={conf} />
                  ) : (
                    <span className="text-xs text-gray-400">—</span>
                  )}
                </td>
                <td className="py-2">
                  {isPrimitive(value) && !readOnly ? (
                    <input
                      type="text"
                      aria-label={`override ${key}`}
                      data-testid={`override-${key}`}
                      defaultValue=""
                      placeholder={stringify(value)}
                      onChange={(e) => handleChange(key, e.target.value)}
                      className="w-full rounded border border-gray-300 px-2 py-1 text-xs"
                    />
                  ) : (
                    <span className="text-xs text-gray-400">read-only</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {!readOnly && (onAccept || onReject) && (
        <footer className="mt-4 flex items-center gap-2">
          {onAccept && (
            <button
              type="button"
              data-testid="accept-button"
              onClick={handleAccept}
              className="rounded bg-green-600 px-3 py-1 text-sm font-medium text-white hover:bg-green-700"
            >
              Accept
            </button>
          )}
          {onReject && (
            <>
              <input
                type="text"
                aria-label="reject reason"
                data-testid="reject-reason"
                placeholder="reason (optional)"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                className="flex-1 rounded border border-gray-300 px-2 py-1 text-xs"
              />
              <button
                type="button"
                data-testid="reject-button"
                onClick={handleReject}
                className="rounded bg-red-600 px-3 py-1 text-sm font-medium text-white hover:bg-red-700"
              >
                Reject
              </button>
            </>
          )}
        </footer>
      )}
    </section>
  );
}

export default ExtractedFieldsPanel;
// --- /L3.8 pdf extraction ---
