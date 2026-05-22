// --- L3.7 imports ---
import { useCallback, useRef, useState, type DragEvent } from 'react';
import { UploadCloud } from 'lucide-react';
import { cn } from '@/lib/cn';

export interface FileDropzoneProps {
  /** Comma-separated accept attribute (e.g. ".csv,.xlsx"). */
  accept?: string;
  maxBytes?: number;
  disabled?: boolean;
  onFileSelected: (file: File) => void;
  /** Optional `id` for testing/labelling. */
  id?: string;
}

const DEFAULT_ACCEPT = '.csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';

function extensionAllowed(file: File, accept: string): boolean {
  const parts = accept.split(',').map((s) => s.trim().toLowerCase()).filter(Boolean);
  if (parts.length === 0) return true;
  const name = file.name.toLowerCase();
  const mime = file.type.toLowerCase();
  return parts.some((p) => (p.startsWith('.') ? name.endsWith(p) : mime === p));
}

export function FileDropzone({
  accept = DEFAULT_ACCEPT,
  maxBytes,
  disabled = false,
  onFileSelected,
  id,
}: FileDropzoneProps): JSX.Element {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [isOver, setIsOver] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFile = useCallback(
    (file: File | null | undefined) => {
      if (!file) return;
      if (!extensionAllowed(file, accept)) {
        setError('Unsupported file type. Use CSV or XLSX.');
        return;
      }
      if (typeof maxBytes === 'number' && file.size > maxBytes) {
        setError(`File too large (max ${Math.round(maxBytes / 1024 / 1024)} MB).`);
        return;
      }
      setError(null);
      onFileSelected(file);
    },
    [accept, maxBytes, onFileSelected],
  );

  const onDrop = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setIsOver(false);
      if (disabled) return;
      handleFile(e.dataTransfer.files?.[0]);
    },
    [disabled, handleFile],
  );

  return (
    <div className="space-y-2">
      <div
        id={id}
        role="button"
        tabIndex={disabled ? -1 : 0}
        aria-disabled={disabled}
        aria-label="Upload CSV or XLSX file"
        onClick={() => !disabled && inputRef.current?.click()}
        onKeyDown={(e) => {
          if (disabled) return;
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setIsOver(true);
        }}
        onDragLeave={() => setIsOver(false)}
        onDrop={onDrop}
        className={cn(
          'flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed p-8 text-center transition-colors',
          isOver
            ? 'border-blue-500 bg-blue-50 dark:bg-blue-950/40'
            : 'border-gray-300 bg-gray-50 dark:border-gray-700 dark:bg-gray-900',
          disabled && 'opacity-60 cursor-not-allowed',
          !disabled && 'cursor-pointer hover:border-blue-400',
        )}
      >
        <UploadCloud aria-hidden="true" className="h-8 w-8 text-gray-500" />
        <p className="text-sm font-medium">
          Drag &amp; drop a CSV or XLSX file, or click to browse.
        </p>
        <p className="text-xs text-gray-500">
          Max 25 MB. Headers may include human aliases — we&apos;ll map them in the next step.
        </p>
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          className="sr-only"
          aria-hidden="true"
          tabIndex={-1}
          onChange={(e) => handleFile(e.target.files?.[0])}
        />
      </div>
      {error ? (
        <p role="alert" className="text-sm text-red-600 dark:text-red-400">
          {error}
        </p>
      ) : null}
    </div>
  );
}

export default FileDropzone;
// --- /L3.7 imports ---
