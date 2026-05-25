import { usePublicPortals, type PortalHealthStatus } from "@/hooks/usePublicPortals";

const STATUS_STYLES: Record<PortalHealthStatus, string> = {
  healthy: "bg-emerald-100 text-emerald-800 ring-1 ring-emerald-200",
  degraded: "bg-amber-100 text-amber-800 ring-1 ring-amber-200",
  down: "bg-rose-100 text-rose-800 ring-1 ring-rose-200",
  unknown: "bg-slate-100 text-slate-700 ring-1 ring-slate-200",
};

const STATUS_LABEL: Record<PortalHealthStatus, string> = {
  healthy: "Healthy",
  degraded: "Degraded",
  down: "Down",
  unknown: "Unknown",
};

function StatusBadge({ status }: { status: PortalHealthStatus }): JSX.Element {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_STYLES[status]}`}
      aria-label={`Status: ${STATUS_LABEL[status]}`}
    >
      <span className="mr-1.5 inline-block h-1.5 w-1.5 rounded-full bg-current" aria-hidden />
      {STATUS_LABEL[status]}
    </span>
  );
}

function formatTimestamp(value: string | null): string {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

export default function Coverage(): JSX.Element {
  const { data, isLoading, isError, error, refetch } = usePublicPortals();

  return (
    <main className="min-h-screen bg-slate-50 px-4 py-12">
      <div className="mx-auto max-w-5xl">
        <header className="text-center">
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">Carrier &amp; portal coverage</h1>
          <p className="mx-auto mt-3 max-w-2xl text-sm text-slate-600">
            Live status of every carrier portal and agency-management system Once submits into. Numbers are derived from
            automated smoke tests that run continuously against the real portals. Anything you see here is something you
            can use today &mdash; or that we&rsquo;ll deliver under the{" "}
            <a className="font-medium text-slate-900 underline" href="/trust">
              14-day new-carrier SLA
            </a>
            .
          </p>
        </header>

        {data ? (
          <dl className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-3">
            <Stat label="Supported portals" value={data.supported_count} total={data.total_count} />
            <Stat label="Healthy now" value={data.healthy_count} total={data.supported_count} />
            <Stat label="Declared roadmap" value={data.total_count} />
          </dl>
        ) : null}

        <section className="mt-10 rounded-lg border border-slate-200 bg-white shadow-sm">
          {isLoading ? (
            <p className="p-6 text-center text-sm text-slate-500" role="status" aria-live="polite">
              Loading coverage…
            </p>
          ) : null}
          {isError ? (
            <div role="alert" className="m-4 rounded-md border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
              <p>Failed to load coverage: {error?.message ?? "unknown error"}</p>
              <button
                type="button"
                onClick={() => void refetch()}
                className="mt-2 text-sm font-medium text-rose-700 underline"
              >
                Retry
              </button>
            </div>
          ) : null}
          {data ? (
            <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th scope="col" className="px-4 py-3 font-semibold">
                    Portal / AMS
                  </th>
                  <th scope="col" className="px-4 py-3 font-semibold">
                    Shipping
                  </th>
                  <th scope="col" className="px-4 py-3 font-semibold">
                    Status
                  </th>
                  <th scope="col" className="px-4 py-3 font-semibold">
                    Last change
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.portals.map((row) => (
                  <tr key={row.platform}>
                    <td className="px-4 py-3 font-medium text-slate-900">
                      {row.display_name}
                      <div className="text-xs text-slate-500">{row.platform}</div>
                    </td>
                    <td className="px-4 py-3 text-slate-700">
                      {row.supported ? (
                        <span className="rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700">
                          Live
                        </span>
                      ) : (
                        <span className="rounded bg-slate-50 px-2 py-0.5 text-xs font-medium text-slate-500 ring-1 ring-slate-200">
                          Roadmap
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={row.status} />
                    </td>
                    <td className="px-4 py-3 text-slate-500">{formatTimestamp(row.last_status_change_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}
        </section>

        <p className="mt-6 text-center text-xs text-slate-500">
          Need a carrier we don&rsquo;t list? Email{" "}
          <a className="underline" href="mailto:carriers@getonce.com">
            carriers@getonce.com
          </a>{" "}
          and we&rsquo;ll ship the integration in 14 days.
        </p>
      </div>
    </main>
  );
}

function Stat({ label, value, total }: { label: string; value: number; total?: number }): JSX.Element {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="mt-1 text-3xl font-semibold tracking-tight text-slate-900">
        {value}
        {total != null ? <span className="text-base font-normal text-slate-400"> / {total}</span> : null}
      </dd>
    </div>
  );
}
