import { useMemo, useState, type ReactNode } from 'react';
import { Plus } from 'lucide-react';
import {
  Button,
  Card,
  EmptyState,
  ErrorState,
  Modal,
  PaginationControls,
  SkeletonTable,
} from '@/components/ui';
import { toast } from '@/lib/toast';
import type { UseMutationResult, UseQueryResult } from '@tanstack/react-query';
import type { PagedResponse } from '@/types/api';

export interface ResourceColumn<T> {
  key: string;
  header: string;
  cell: (row: T) => ReactNode;
  className?: string;
  align?: 'left' | 'right' | 'center';
}

export interface ResourcePageProps<T, TCreate> {
  title: string;
  description: string;
  pluralNoun: string;
  singularNoun: string;
  columns: ReadonlyArray<ResourceColumn<T>>;
  useList: (params: {
    limit: number;
    offset: number;
  }) => UseQueryResult<PagedResponse<T>, Error>;
  useCreate: () => UseMutationResult<T, Error, TCreate>;
  renderForm: (args: {
    onSubmit: (input: TCreate) => Promise<void>;
    submitting: boolean;
    onCancel: () => void;
  }) => ReactNode;
  emptyIcon?: React.ComponentType<{ className?: string }>;
  pageSize?: number;
  toolbar?: ReactNode;
  rowKey: (row: T) => string;
}

/**
 * Generic list-with-create page used by every "artifact" resource
 * (COIs, loss runs, producer licenses, E&O certs, ACORD forms, risk schedules).
 *
 * Owners can drop in by providing typed columns, hooks, and a form renderer.
 */
export function ResourcePage<T, TCreate>({
  title,
  description,
  pluralNoun,
  singularNoun,
  columns,
  useList,
  useCreate,
  renderForm,
  emptyIcon: EmptyIcon,
  pageSize = 25,
  toolbar,
  rowKey,
}: ResourcePageProps<T, TCreate>): JSX.Element {
  const [page, setPage] = useState(1);
  const [creating, setCreating] = useState(false);

  const params = useMemo(
    () => ({ limit: pageSize, offset: (page - 1) * pageSize }),
    [page, pageSize],
  );

  const query = useList(params);
  const createMutation = useCreate();

  async function onSubmit(input: TCreate): Promise<void> {
    try {
      await createMutation.mutateAsync(input);
      toast.success(`${singularNoun} created.`);
      setCreating(false);
      setPage(1);
    } catch (err) {
      toast.error(err, `Failed to create ${singularNoun.toLowerCase()}`);
    }
  }

  const data = query.data;
  const items = data?.items ?? [];

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
            {title}
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">{description}</p>
        </div>
        <div className="flex items-center gap-2">
          {toolbar}
          <Button
            onClick={() => setCreating(true)}
            leadingIcon={<Plus className="h-3.5 w-3.5" />}
          >
            New {singularNoun.toLowerCase()}
          </Button>
        </div>
      </header>

      <Card padded={false}>
        {query.isLoading ? (
          <SkeletonTable rows={6} columns={columns.length || 4} />
        ) : query.error ? (
          <div className="p-4">
            <ErrorState
              title={`Failed to load ${pluralNoun.toLowerCase()}`}
              error={query.error}
              onRetry={() => void query.refetch()}
            />
          </div>
        ) : items.length === 0 ? (
          <div className="p-6">
            <EmptyState
              title={`No ${pluralNoun.toLowerCase()} yet`}
              description={`Create your first ${singularNoun.toLowerCase()} to get started.`}
              {...(EmptyIcon ? { icon: EmptyIcon } : {})}
              action={{
                label: `New ${singularNoun.toLowerCase()}`,
                onClick: () => setCreating(true),
              }}
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500 dark:bg-slate-800/50 dark:text-slate-400">
                <tr>
                  {columns.map((c) => (
                    <th
                      key={c.key}
                      scope="col"
                      className={[
                        'px-5 py-2 font-medium',
                        c.align === 'right' ? 'text-right' : '',
                        c.align === 'center' ? 'text-center' : '',
                        c.className ?? '',
                      ]
                        .filter(Boolean)
                        .join(' ')}
                    >
                      {c.header}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {items.map((row) => (
                  <tr key={rowKey(row)} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                    {columns.map((c) => (
                      <td
                        key={c.key}
                        className={[
                          'px-5 py-2 text-slate-700 dark:text-slate-300',
                          c.align === 'right' ? 'text-right' : '',
                          c.align === 'center' ? 'text-center' : '',
                        ]
                          .filter(Boolean)
                          .join(' ')}
                      >
                        {c.cell(row)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {data && data.total > 0 ? (
          <PaginationControls
            page={page}
            pageSize={pageSize}
            total={data.total}
            onPageChange={setPage}
            isLoading={query.isFetching}
          />
        ) : null}
      </Card>

      <Modal
        open={creating}
        onClose={() => setCreating(false)}
        title={`New ${singularNoun.toLowerCase()}`}
      >
        {renderForm({
          onSubmit,
          submitting: createMutation.isPending,
          onCancel: () => setCreating(false),
        })}
      </Modal>
    </div>
  );
}
