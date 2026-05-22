// --- L3.7 imports ---
import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, ErrorState, Select, Skeleton } from '@/components/ui';
import { extractErrorMessage } from '@/services/api';
import {
  importsApi,
  type ImportEntityType,
  type ImportJob,
  type OnDuplicateMode,
} from '@/services/importsApi';
import {
  useImportColumns,
  useUploadImport,
  useImport,
  useCommitImport,
} from '@/hooks/useImports';
import { FileDropzone } from '@/components/imports/FileDropzone';
import {
  ColumnMapper,
  suggestMapping,
} from '@/components/imports/ColumnMapper';
import { ImportProgress } from '@/components/imports/ImportProgress';
import { PreviewTable } from '@/components/imports/PreviewTable';

type Step = 'pick' | 'mapping' | 'review';

const ENTITY_OPTIONS = [
  { value: 'supplier', label: 'Suppliers' },
  { value: 'coi', label: 'COIs' },
  { value: 'loss_run', label: 'Loss Runs' },
  { value: 'producer_license', label: 'Producer Licenses' },
] as const;

const DUP_OPTIONS = [
  { value: 'error', label: 'Error on duplicate' },
  { value: 'update', label: 'Update on duplicate' },
  { value: 'skip', label: 'Skip on duplicate' },
] as const;

/** Read header row from a CSV file (first line, naive split). */
async function readCsvHeaders(file: File): Promise<string[]> {
  // Read up to 64KB to keep memory bounded
  const blob = file.slice(0, 64 * 1024);
  const text = await blob.text();
  const firstLine = text.split(/\r?\n/, 1)[0] ?? '';
  // Tiny CSV parser for header line (handles double-quoted commas).
  const out: string[] = [];
  let cur = '';
  let inQuote = false;
  for (let i = 0; i < firstLine.length; i++) {
    const c = firstLine[i];
    if (inQuote) {
      if (c === '"' && firstLine[i + 1] === '"') {
        cur += '"';
        i++;
      } else if (c === '"') {
        inQuote = false;
      } else {
        cur += c;
      }
    } else if (c === '"') {
      inQuote = true;
    } else if (c === ',') {
      out.push(cur.trim());
      cur = '';
    } else {
      cur += c;
    }
  }
  out.push(cur.trim());
  // Strip BOM from first header
  if (out.length > 0) out[0] = out[0].replace(/^\uFEFF/, '');
  return out.filter((h) => h.length > 0);
}

export default function ImportNew(): JSX.Element {
  const navigate = useNavigate();
  const [entity, setEntity] = useState<ImportEntityType>('supplier');
  const [onDup, setOnDup] = useState<OnDuplicateMode>('error');
  const [file, setFile] = useState<File | null>(null);
  const [headers, setHeaders] = useState<string[]>([]);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [step, setStep] = useState<Step>('pick');
  const [uploadedJob, setUploadedJob] = useState<ImportJob | null>(null);

  const columnsQ = useImportColumns(entity);
  const upload = useUploadImport();
  const commit = useCommitImport();
  const jobDetailQ = useImport(uploadedJob?.id, {
    refetchInterval:
      uploadedJob && (uploadedJob.status === 'validating' || uploadedJob.status === 'importing')
        ? 1500
        : false,
  });
  const detail = jobDetailQ.data ?? null;

  const schemaColumns = useMemo(
    () => columnsQ.data?.columns ?? [],
    [columnsQ.data],
  );

  const missingRequired = useMemo(
    () =>
      schemaColumns
        .filter((c) => c.required && !mapping[c.field])
        .map((c) => c.field),
    [schemaColumns, mapping],
  );

  async function handleFileSelected(f: File): Promise<void> {
    setFile(f);
    try {
      const hs = await readCsvHeaders(f);
      setHeaders(hs);
      setMapping(suggestMapping(schemaColumns, hs));
    } catch {
      setHeaders([]);
      setMapping({});
    }
    setStep('mapping');
  }

  async function handleUpload(): Promise<void> {
    if (!file) return;
    const job = await upload.mutateAsync({
      file,
      entity_type: entity,
      mapping,
      on_duplicate: onDup,
    });
    setUploadedJob(job);
    setStep('review');
  }

  async function handleCommit(): Promise<void> {
    if (!uploadedJob) return;
    await commit.mutateAsync(uploadedJob.id);
    navigate(`/imports/${uploadedJob.id}`);
  }

  return (
    <div className="space-y-6 p-6">
      <header>
        <h1 className="text-2xl font-semibold">New Bulk Import</h1>
        <p className="text-sm text-gray-600 dark:text-gray-400">
          Upload a CSV or XLSX, map columns, review validation, then commit.
        </p>
      </header>

      {/* Step 1 — pick entity + file */}
      <section className="space-y-3 rounded border border-gray-200 p-4 dark:border-gray-800">
        <h2 className="text-lg font-medium">1 · Choose what to import</h2>
        <div className="grid gap-3 sm:grid-cols-3">
          <Select
            label="Entity"
            value={entity}
            options={[...ENTITY_OPTIONS]}
            onChange={(e) => {
              const next = e.target.value as ImportEntityType;
              setEntity(next);
              setStep('pick');
              setFile(null);
              setHeaders([]);
              setMapping({});
              setUploadedJob(null);
            }}
          />
          <Select
            label="On duplicate"
            value={onDup}
            options={[...DUP_OPTIONS]}
            onChange={(e) => setOnDup(e.target.value as OnDuplicateMode)}
          />
          <div className="flex items-end">
            <a
              className="text-sm text-blue-600 hover:underline dark:text-blue-400"
              href={importsApi.templateUrl(entity)}
              download
            >
              Download {entity} template (CSV)
            </a>
          </div>
        </div>
        <FileDropzone
          maxBytes={25 * 1024 * 1024}
          disabled={upload.isPending}
          onFileSelected={(f) => void handleFileSelected(f)}
        />
        {file ? (
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Selected: <span className="font-mono">{file.name}</span> (
            {(file.size / 1024).toFixed(1)} KB)
          </p>
        ) : null}
      </section>

      {/* Step 2 — column mapping */}
      {step !== 'pick' ? (
        <section className="space-y-3 rounded border border-gray-200 p-4 dark:border-gray-800">
          <h2 className="text-lg font-medium">2 · Map columns</h2>
          {columnsQ.isLoading ? (
            <Skeleton className="h-32 w-full" />
          ) : columnsQ.error ? (
            <ErrorState
              title="Could not load column schema"
              description={extractErrorMessage(columnsQ.error)}
              onRetry={() => columnsQ.refetch()}
            />
          ) : headers.length === 0 ? (
            <p className="text-sm text-amber-700 dark:text-amber-300">
              We couldn&apos;t read headers from the file. XLSX header preview is
              not available in the browser — proceed and the server will
              auto-detect.
            </p>
          ) : (
            <ColumnMapper
              fileHeaders={headers}
              schemaColumns={schemaColumns}
              value={mapping}
              onChange={setMapping}
            />
          )}
          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              onClick={() => {
                setStep('pick');
              }}
            >
              Back
            </Button>
            <Button
              loading={upload.isPending}
              disabled={!file || (headers.length > 0 && missingRequired.length > 0)}
              onClick={() => void handleUpload()}
            >
              Validate
            </Button>
          </div>
          {upload.error ? (
            <p role="alert" className="text-sm text-red-700 dark:text-red-300">
              {extractErrorMessage(upload.error)}
            </p>
          ) : null}
        </section>
      ) : null}

      {/* Step 3 — review */}
      {step === 'review' && uploadedJob ? (
        <section className="space-y-3 rounded border border-gray-200 p-4 dark:border-gray-800">
          <h2 className="text-lg font-medium">3 · Review &amp; commit</h2>
          {jobDetailQ.isLoading && !detail ? (
            <Skeleton className="h-32 w-full" />
          ) : null}
          {detail ? (
            <>
              <ImportProgress job={detail} />
              <PreviewTable
                errors={detail.errors_preview}
                totalErrors={detail.error_count}
                errorsCsvUrl={
                  detail.error_count > 0 ? importsApi.errorsUrl(detail.id) : undefined
                }
              />
              <div className="flex justify-end gap-2">
                <Button
                  variant="outline"
                  onClick={() => navigate(`/imports/${detail.id}`)}
                >
                  Open job
                </Button>
                <Button
                  loading={commit.isPending}
                  disabled={
                    detail.status !== 'dry_run_ready' || detail.valid_rows === 0
                  }
                  onClick={() => void handleCommit()}
                >
                  Commit {detail.valid_rows.toLocaleString()} rows
                </Button>
              </div>
              {commit.error ? (
                <p role="alert" className="text-sm text-red-700 dark:text-red-300">
                  {extractErrorMessage(commit.error)}
                </p>
              ) : null}
            </>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
// --- /L3.7 imports ---
