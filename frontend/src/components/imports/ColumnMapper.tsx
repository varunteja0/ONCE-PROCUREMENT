// --- L3.7 imports ---
import { useMemo } from 'react';
import { Select } from '@/components/ui';
import type { ImportColumnSpec } from '@/services/importsApi';

export interface ColumnMapperProps {
  /** Header row from the uploaded file. */
  fileHeaders: string[];
  /** Target schema columns from `/imports/columns/{entity}`. */
  schemaColumns: readonly ImportColumnSpec[];
  /** Current mapping: target field -> source header. */
  value: Record<string, string>;
  onChange: (next: Record<string, string>) => void;
}

const UNMAPPED = '__unmapped__';

function autoMatch(
  schemaColumns: readonly ImportColumnSpec[],
  fileHeaders: string[],
): Record<string, string> {
  const normalised = new Map<string, string>();
  for (const h of fileHeaders) {
    normalised.set(h.trim().toLowerCase().replace(/[\s_-]+/g, ''), h);
  }
  const out: Record<string, string> = {};
  for (const col of schemaColumns) {
    const candidates = [col.field, ...col.aliases];
    for (const c of candidates) {
      const key = c.toLowerCase().replace(/[\s_-]+/g, '');
      const match = normalised.get(key);
      if (match) {
        out[col.field] = match;
        break;
      }
    }
  }
  return out;
}

export function suggestMapping(
  schemaColumns: readonly ImportColumnSpec[],
  fileHeaders: string[],
): Record<string, string> {
  return autoMatch(schemaColumns, fileHeaders);
}

export function ColumnMapper({
  fileHeaders,
  schemaColumns,
  value,
  onChange,
}: ColumnMapperProps): JSX.Element {
  const headerOptions = useMemo(
    () => [
      { value: UNMAPPED, label: '— Not mapped —' },
      ...fileHeaders.map((h) => ({ value: h, label: h })),
    ],
    [fileHeaders],
  );

  const missingRequired = schemaColumns
    .filter((c) => c.required && !value[c.field])
    .map((c) => c.field);

  return (
    <div className="space-y-3" role="group" aria-label="Column mapping">
      {missingRequired.length > 0 ? (
        <p
          role="alert"
          className="rounded border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-200"
        >
          Map required columns: {missingRequired.join(', ')}
        </p>
      ) : null}
      <table className="w-full text-sm">
        <thead className="text-left text-xs uppercase text-gray-500">
          <tr>
            <th className="py-2 pr-4">Target field</th>
            <th className="py-2 pr-4">Source header</th>
            <th className="py-2">Description</th>
          </tr>
        </thead>
        <tbody>
          {schemaColumns.map((col) => {
            const current = value[col.field] ?? UNMAPPED;
            return (
              <tr key={col.field} className="border-t border-gray-200 dark:border-gray-800">
                <td className="py-2 pr-4 align-top">
                  <div className="font-mono text-sm">{col.field}</div>
                  {col.required ? (
                    <span className="text-xs font-semibold text-red-600 dark:text-red-400">
                      required
                    </span>
                  ) : (
                    <span className="text-xs text-gray-500">optional</span>
                  )}
                </td>
                <td className="py-2 pr-4 align-top">
                  <Select
                    aria-label={`Source header for ${col.field}`}
                    value={current}
                    options={headerOptions}
                    onChange={(e) => {
                      const next = { ...value };
                      const v = e.target.value;
                      if (v === UNMAPPED) {
                        delete next[col.field];
                      } else {
                        next[col.field] = v;
                      }
                      onChange(next);
                    }}
                  />
                </td>
                <td className="py-2 align-top text-xs text-gray-600 dark:text-gray-400">
                  {col.description}
                  {col.example ? (
                    <span className="ml-1 text-gray-400">e.g. {col.example}</span>
                  ) : null}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default ColumnMapper;
// --- /L3.7 imports ---
