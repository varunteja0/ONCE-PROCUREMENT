import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Building2, Loader2 } from 'lucide-react';
import { useSupplier } from '@/hooks/useSuppliers';
import { useSubmissions } from '@/hooks/useSubmissions';
import {
  coisHooks,
  lossRunsHooks,
  producerLicensesHooks,
  eoCertificatesHooks,
  acordFormsHooks,
  riskSchedulesHooks,
} from '@/hooks/useArtifacts';
import { useConsents } from '@/hooks/useConsents';
import {
  Button,
  Card,
  CardHeader,
  DateDisplay,
  EmptyState,
  ErrorState,
  MoneyDisplay,
  Skeleton,
  StatusBadge,
} from '@/components/ui';
import { extractErrorMessage } from '@/services/api';

function ArtifactCount({
  label,
  count,
  isLoading,
}: {
  label: string;
  count: number | undefined;
  isLoading: boolean;
}): JSX.Element {
  return (
    <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-800 dark:bg-slate-900">
      <p className="text-xs text-slate-500 dark:text-slate-400">{label}</p>
      <p className="text-lg font-semibold text-slate-900 dark:text-slate-100">
        {isLoading ? '…' : (count ?? 0)}
      </p>
    </div>
  );
}

export default function SupplierDetail(): JSX.Element {
  const params = useParams<{ id: string }>();
  const navigate = useNavigate();
  const supplierId = params.id;

  const supplier = useSupplier(supplierId);

  const cois = coisHooks.useList({ supplier_id: supplierId, limit: 100 });
  const lossRuns = lossRunsHooks.useList({ supplier_id: supplierId, limit: 100 });
  const licenses = producerLicensesHooks.useList({
    supplier_id: supplierId,
    limit: 100,
  });
  const eos = eoCertificatesHooks.useList({ supplier_id: supplierId, limit: 100 });
  const acords = acordFormsHooks.useList({ supplier_id: supplierId, limit: 100 });
  const schedules = riskSchedulesHooks.useList({
    supplier_id: supplierId,
    limit: 100,
  });
  const submissions = useSubmissions(
    supplierId ? { supplierId, pageSize: 25 } : { pageSize: 0 },
  );
  const consents = useConsents(supplierId ? { supplier_id: supplierId } : {});

  if (supplier.isLoading) {
    return (
      <div className="space-y-3" aria-busy="true">
        <Skeleton className="h-7 w-64" />
        <Skeleton className="h-4 w-1/2" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }

  if (supplier.error || !supplier.data) {
    return (
      <ErrorState
        title="Supplier not found"
        error={supplier.error ?? new Error('Unknown error')}
        onRetry={() => void supplier.refetch()}
      />
    );
  }

  const s = supplier.data;

  return (
    <div className="space-y-6">
      <div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate('/suppliers')}
          leadingIcon={<ArrowLeft className="h-3.5 w-3.5" />}
        >
          Back to suppliers
        </Button>
      </div>

      <header className="flex items-start gap-3">
        <div className="rounded-md bg-slate-100 p-2 dark:bg-slate-800">
          <Building2 className="h-6 w-6 text-slate-700 dark:text-slate-200" aria-hidden="true" />
        </div>
        <div>
          <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
            {s.legal_name}
          </h1>
          {s.dba_name ? (
            <p className="text-sm text-slate-500 dark:text-slate-400">
              DBA: {s.dba_name}
            </p>
          ) : null}
        </div>
      </header>

      <Card>
        <CardHeader title="Supplier details" />
        <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-3">
          <div>
            <dt className="text-xs text-slate-500 dark:text-slate-400">EIN</dt>
            <dd className="font-mono text-slate-900 dark:text-slate-100">
              {s.ein ?? '—'}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500 dark:text-slate-400">NAICS</dt>
            <dd className="text-slate-900 dark:text-slate-100">
              {s.naics_code ?? '—'}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500 dark:text-slate-400">Primary email</dt>
            <dd className="text-slate-900 dark:text-slate-100">
              {s.primary_email ?? '—'}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500 dark:text-slate-400">Primary phone</dt>
            <dd className="text-slate-900 dark:text-slate-100">
              {s.primary_phone ?? '—'}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500 dark:text-slate-400">Website</dt>
            <dd className="text-slate-900 dark:text-slate-100">
              {s.website ? (
                <a
                  href={s.website}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="underline hover:no-underline"
                >
                  {s.website}
                </a>
              ) : (
                '—'
              )}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500 dark:text-slate-400">Created</dt>
            <dd className="text-slate-900 dark:text-slate-100">
              <DateDisplay value={s.created_at} />
            </dd>
          </div>
        </dl>
      </Card>

      <section
        aria-label="Artifact summary"
        className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6"
      >
        <Link to="/cois">
          <ArtifactCount
            label="COIs"
            count={cois.data?.total}
            isLoading={cois.isLoading}
          />
        </Link>
        <Link to="/loss-runs">
          <ArtifactCount
            label="Loss runs"
            count={lossRuns.data?.total}
            isLoading={lossRuns.isLoading}
          />
        </Link>
        <Link to="/producer-licenses">
          <ArtifactCount
            label="Licenses"
            count={licenses.data?.total}
            isLoading={licenses.isLoading}
          />
        </Link>
        <Link to="/eo-certificates">
          <ArtifactCount
            label="E&O certs"
            count={eos.data?.total}
            isLoading={eos.isLoading}
          />
        </Link>
        <Link to="/acord-forms">
          <ArtifactCount
            label="ACORD forms"
            count={acords.data?.total}
            isLoading={acords.isLoading}
          />
        </Link>
        <Link to="/risk-schedules">
          <ArtifactCount
            label="Risk schedules"
            count={schedules.data?.total}
            isLoading={schedules.isLoading}
          />
        </Link>
      </section>

      <Card padded={false}>
        <CardHeader title="Recent COIs" />
        <div className="overflow-x-auto">
          {cois.isLoading ? (
            <div className="flex items-center gap-2 px-4 py-6 text-sm text-slate-500">
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> Loading…
            </div>
          ) : (cois.data?.items.length ?? 0) === 0 ? (
            <div className="p-4">
              <EmptyState
                title="No COIs"
                description="No certificates of insurance recorded for this supplier yet."
              />
            </div>
          ) : (
            <table className="min-w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500 dark:bg-slate-800/50 dark:text-slate-400">
                <tr>
                  <th className="px-5 py-2 font-medium">Carrier</th>
                  <th className="px-5 py-2 font-medium">Policy #</th>
                  <th className="px-5 py-2 font-medium text-right">Limit</th>
                  <th className="px-5 py-2 font-medium">Expires</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {(cois.data?.items ?? []).slice(0, 5).map((c) => (
                  <tr key={c.id}>
                    <td className="px-5 py-2">{c.carrier}</td>
                    <td className="px-5 py-2">{c.policy_number ?? '—'}</td>
                    <td className="px-5 py-2 text-right">
                      <MoneyDisplay value={c.limit_amount} />
                    </td>
                    <td className="px-5 py-2">
                      <DateDisplay value={c.expires_at} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </Card>

      <Card padded={false}>
        <CardHeader title="Recent submissions" />
        <div className="overflow-x-auto">
          {submissions.isLoading ? (
            <div className="flex items-center gap-2 px-4 py-6 text-sm text-slate-500">
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> Loading…
            </div>
          ) : submissions.error ? (
            <div className="p-4 text-sm text-red-700 dark:text-red-300">
              {extractErrorMessage(submissions.error, 'Failed to load submissions')}
            </div>
          ) : (submissions.data?.items.length ?? 0) === 0 ? (
            <div className="p-4">
              <EmptyState
                title="No submissions"
                description="No submissions have been sent for this supplier yet."
              />
            </div>
          ) : (
            <table className="min-w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500 dark:bg-slate-800/50 dark:text-slate-400">
                <tr>
                  <th className="px-5 py-2 font-medium">Submission</th>
                  <th className="px-5 py-2 font-medium">Status</th>
                  <th className="px-5 py-2 font-medium">Updated</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {(submissions.data?.items ?? []).map((row) => (
                  <tr key={row.id}>
                    <td className="px-5 py-2">
                      <Link
                        to={`/submissions/${row.id}`}
                        className="font-mono text-xs underline hover:no-underline"
                      >
                        {row.id.slice(0, 8)}
                      </Link>
                    </td>
                    <td className="px-5 py-2">
                      <StatusBadge status={row.status} />
                    </td>
                    <td className="px-5 py-2 text-slate-500 dark:text-slate-400">
                      <DateDisplay value={row.updated_at} mode="datetime" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </Card>

      <Card padded={false}>
        <CardHeader
          title="Consents"
          description={`${consents.data?.items.length ?? 0} record(s) on file.`}
        />
        <div className="px-4 py-3 text-sm">
          <Link to="/consent-ledger" className="text-slate-700 underline hover:no-underline dark:text-slate-200">
            View consent ledger →
          </Link>
        </div>
      </Card>
    </div>
  );
}
