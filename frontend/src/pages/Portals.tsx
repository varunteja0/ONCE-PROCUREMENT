import { useState, type ChangeEvent } from 'react';
import { Loader2, PlugZap, Search } from 'lucide-react';
import { usePortals } from '@/hooks/usePortals';
import { extractErrorMessage } from '@/services/api';
import EmptyState from '@/components/EmptyState';
import PortalCard from '@/components/PortalCard';

export default function Portals(): JSX.Element {
  const [search, setSearch] = useState('');
  const [supportedOnly, setSupportedOnly] = useState(false);

  const query = usePortals({ search: search.trim() || undefined, supportedOnly });
  const portals = query.data?.items ?? [];

  function onSearchChange(e: ChangeEvent<HTMLInputElement>): void {
    setSearch(e.target.value);
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Portals</h1>
          <p className="text-sm text-slate-500">
            Carrier and agency-management portals that Once can submit to.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative">
            <Search
              className="pointer-events-none absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
              aria-hidden="true"
            />
            <input
              type="search"
              value={search}
              onChange={onSearchChange}
              placeholder="Search portals…"
              className="w-64 rounded border border-slate-300 bg-white py-1.5 pl-7 pr-3 text-sm focus:outline-none focus:ring-2 focus:ring-slate-900"
              aria-label="Search portals"
            />
          </div>
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={supportedOnly}
              onChange={(e) => setSupportedOnly(e.target.checked)}
              className="rounded border-slate-300"
            />
            Supported only
          </label>
        </div>
      </header>

      {query.isLoading ? (
        <div className="flex items-center justify-center py-12 text-slate-500">
          <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
          <span className="ml-2 text-sm">Loading portals…</span>
        </div>
      ) : query.error ? (
        <div className="rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {extractErrorMessage(query.error, 'Failed to load portals')}
        </div>
      ) : portals.length === 0 ? (
        <EmptyState
          title="No portals match your search"
          description="Try clearing the filter or searching for a different carrier."
          icon={PlugZap}
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {portals.map((portal) => (
            <PortalCard key={portal.id} portal={portal} />
          ))}
        </div>
      )}
    </div>
  );
}
