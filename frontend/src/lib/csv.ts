/**
 * Minimal RFC 4180 CSV helpers.
 *
 * `toCsv` serialises an array of rows into a CSV string with proper escaping
 * for embedded commas, double quotes, and newlines. `downloadCsv` triggers a
 * client-side download of the produced CSV via a temporary blob URL.
 *
 * No external dependencies; safe for SSR-less browser environments only
 * (downloadCsv touches `document` + `URL`).
 */

export interface CsvColumn<T> {
  /** Header label as it should appear in the first CSV row. */
  header: string;
  /** Cell value extractor. Return `null`/`undefined` for empty cell. */
  value: (row: T) => string | number | boolean | null | undefined;
}

/** Escape a single CSV field per RFC 4180. */
function escapeField(raw: string | number | boolean | null | undefined): string {
  if (raw === null || raw === undefined) return '';
  const s = String(raw);
  // Quote if the field contains a comma, double quote, CR, or LF.
  if (/[",\r\n]/.test(s)) {
    return `"${s.replace(/"/g, '""')}"`;
  }
  return s;
}

/**
 * Serialise rows into a CSV string. Uses CRLF line endings per RFC 4180.
 */
export function toCsv<T>(rows: readonly T[], columns: ReadonlyArray<CsvColumn<T>>): string {
  const header = columns.map((c) => escapeField(c.header)).join(',');
  const body = rows
    .map((row) => columns.map((c) => escapeField(c.value(row))).join(','))
    .join('\r\n');
  return body.length === 0 ? `${header}\r\n` : `${header}\r\n${body}\r\n`;
}

/**
 * Trigger a browser download of a CSV string under the given filename.
 * Prepends a UTF-8 BOM so Excel opens it correctly.
 */
export function downloadCsv(filename: string, csv: string): void {
  const blob = new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
