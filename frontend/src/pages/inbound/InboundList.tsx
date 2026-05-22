// --- L3.9 inbound ---
import { Link } from 'react-router-dom';
import { Mail } from 'lucide-react';
import { Button, EmptyState, ErrorState, Skeleton } from '@/components/ui';
import { useInboundList } from '@/hooks/useInbound';
import { RoutingResultBadge } from '@/components/inbound/RoutingResultBadge';
import { extractErrorMessage } from '@/services/api';

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export default function InboundList(): JSX.Element {
  const { data, isLoading, error, refetch } = useInboundList(undefined, {
    refetchInterval: 10_000,
  });

  return (
    <div className="space-y-4 p-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Inbound email</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Emails received at <code>submissions@&lt;your-slug&gt;.in.getonce.com</code>.
          </p>
        </div>
        <Link to="/inbound/rules">
          <Button variant="secondary">Routing rules</Button>
        </Link>
      </header>

      {isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : error ? (
        <ErrorState
          title="Couldn't load inbound emails"
          description={extractErrorMessage(error)}
          onRetry={() => refetch()}
        />
      ) : !data || data.length === 0 ? (
        <EmptyState
          icon={Mail}
          title="No emails yet"
          description="Forward broker submissions to your inbound address to see them here."
        />
      ) : (
        <div className="overflow-x-auto rounded-md border border-gray-200 dark:border-gray-700">
          <table className="min-w-full divide-y divide-gray-200 text-sm dark:divide-gray-700">
            <thead className="bg-gray-50 text-left text-xs uppercase text-gray-500 dark:bg-gray-900 dark:text-gray-400">
              <tr>
                <th className="px-3 py-2">Received</th>
                <th className="px-3 py-2">From</th>
                <th className="px-3 py-2">Subject</th>
                <th className="px-3 py-2">Attachments</th>
                <th className="px-3 py-2">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
              {data.map((item) => (
                <tr key={item.id} className="hover:bg-gray-50 dark:hover:bg-gray-900/40">
                  <td className="whitespace-nowrap px-3 py-2 text-gray-600 dark:text-gray-300">
                    {formatDate(item.received_at)}
                  </td>
                  <td className="px-3 py-2">
                    <div className="font-medium">{item.from_name ?? item.from_address}</div>
                    <div className="text-xs text-gray-500">{item.from_address}</div>
                  </td>
                  <td className="px-3 py-2">
                    <Link to={`/inbound/${item.id}`} className="text-sky-700 hover:underline dark:text-sky-300">
                      {item.subject ?? '(no subject)'}
                    </Link>
                  </td>
                  <td className="px-3 py-2 text-center">{item.attachment_count}</td>
                  <td className="px-3 py-2">
                    <RoutingResultBadge status={item.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
