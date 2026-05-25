import { useMemo, useState, type ChangeEvent, type FormEvent } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Download, Pencil, Plus, Users } from 'lucide-react';
import {
  useCreateSupplier,
  useSupplier,
  useSuppliers,
  useUpdateSupplier,
} from '@/hooks/useSuppliers';
import { extractErrorMessage } from '@/services/api';
import type { SupplierCreateInput, SupplierListItem } from '@/services/api';
import {
  Button,
  EmptyState,
  Modal,
  PaginationControls,
  SearchInput,
  Skeleton,
} from '@/components/ui';
import { downloadCsv, toCsv } from '@/lib/csv';
import { toast } from '@/lib/toast';

const PAGE_SIZE = 25;

interface FormState {
  legal_name: string;
  dba_name: string;
  ein: string;
  naics_code: string;
  primary_email: string;
  primary_phone: string;
  website: string;
}

function emptyForm(): FormState {
  return {
    legal_name: '',
    dba_name: '',
    ein: '',
    naics_code: '',
    primary_email: '',
    primary_phone: '',
    website: '',
  };
}

function toPayload(form: FormState): SupplierCreateInput {
  const trim = (s: string): string | null => (s.trim() === '' ? null : s.trim());
  return {
    legal_name: form.legal_name.trim(),
    dba_name: trim(form.dba_name),
    ein: trim(form.ein),
    naics_code: trim(form.naics_code),
    primary_email: trim(form.primary_email),
    primary_phone: trim(form.primary_phone),
    website: trim(form.website),
  };
}

interface ModalContentProps {
  editingId: string | null;
  onClose: () => void;
}

function SupplierForm({ editingId, onClose }: ModalContentProps): JSX.Element {
  const detail = useSupplier(editingId ?? undefined);
  const create = useCreateSupplier();
  const update = useUpdateSupplier();
  const submitting = create.isPending || update.isPending;

  const [form, setForm] = useState<FormState>(emptyForm);
  const [hydrated, setHydrated] = useState(false);

  if (editingId && detail.data && !hydrated) {
    const d = detail.data;
    setForm({
      legal_name: d.legal_name,
      dba_name: d.dba_name ?? '',
      ein: d.ein ?? '',
      naics_code: d.naics_code ?? '',
      primary_email: d.primary_email ?? '',
      primary_phone: d.primary_phone ?? '',
      website: d.website ?? '',
    });
    setHydrated(true);
  }

  function field<K extends keyof FormState>(key: K) {
    return (e: ChangeEvent<HTMLInputElement>): void => {
      setForm((prev) => ({ ...prev, [key]: e.target.value }));
    };
  }

  async function onSubmit(e: FormEvent<HTMLFormElement>): Promise<void> {
    e.preventDefault();
    if (submitting) return;
    if (form.legal_name.trim() === '') {
      toast.error('Legal name is required.');
      return;
    }
    try {
      if (editingId) {
        await update.mutateAsync({ id: editingId, patch: toPayload(form) });
        toast.success('Supplier updated.');
      } else {
        await create.mutateAsync(toPayload(form));
        toast.success('Supplier created.');
      }
      onClose();
    } catch (err) {
      toast.error(err, 'Save failed');
    }
  }

  const fields: ReadonlyArray<{
    key: keyof FormState;
    label: string;
    type?: string;
    required?: boolean;
  }> = [
    { key: 'legal_name', label: 'Legal name', required: true },
    { key: 'dba_name', label: 'DBA name' },
    { key: 'ein', label: 'EIN' },
    { key: 'naics_code', label: 'NAICS code' },
    { key: 'primary_email', label: 'Primary email', type: 'email' },
    { key: 'primary_phone', label: 'Primary phone', type: 'tel' },
    { key: 'website', label: 'Website', type: 'url' },
  ];

  if (editingId && detail.isLoading) {
    return (
      <div className="space-y-2" aria-busy="true">
        <Skeleton className="h-9 w-full" />
        <Skeleton className="h-9 w-full" />
        <Skeleton className="h-9 w-full" />
      </div>
    );
  }

  return (
    <form
      id="supplier-form"
      onSubmit={(e) => void onSubmit(e)}
      className="space-y-3"
    >
      {fields.map((f) => (
        <div key={f.key}>
          <label
            htmlFor={`supplier_${f.key}`}
            className="mb-1 block text-xs font-medium text-slate-700 dark:text-slate-300"
          >
            {f.label}
            {f.required && <span className="text-rose-600"> *</span>}
          </label>
          <input
            id={`supplier_${f.key}`}
            type={f.type ?? 'text'}
            value={form[f.key]}
            onChange={field(f.key)}
            required={f.required}
            disabled={submitting}
            className="w-full rounded border border-slate-300 bg-white px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          />
        </div>
      ))}
    </form>
  );
}

export default function Suppliers(): JSX.Element {
  const [params, setParams] = useSearchParams();
  const search = params.get('q') ?? '';
  const page = Math.max(1, Number(params.get('page') ?? '1'));
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);

  const query = useSuppliers(
    useMemo(
      () => ({
        search: search.trim() || undefined,
        page,
        pageSize: PAGE_SIZE,
      }),
      [search, page],
    ),
  );
  const suppliers: SupplierListItem[] = query.data ?? [];

  function setSearch(next: string): void {
    setParams((prev) => {
      const out = new URLSearchParams(prev);
      if (next.trim() === '') out.delete('q');
      else out.set('q', next);
      out.set('page', '1');
      return out;
    });
  }

  function setPage(next: number): void {
    setParams((prev) => {
      const out = new URLSearchParams(prev);
      out.set('page', String(next));
      return out;
    });
  }

  function openCreate(): void {
    setEditingId(null);
    setModalOpen(true);
  }

  function openEdit(id: string): void {
    setEditingId(id);
    setModalOpen(true);
  }

  function closeModal(): void {
    setModalOpen(false);
    setEditingId(null);
  }

  function exportCsv(): void {
    if (suppliers.length === 0) {
      toast.error('Nothing to export.');
      return;
    }
    const csv = toCsv(suppliers, [
      { header: 'ID', value: (r) => r.id },
      { header: 'Legal name', value: (r) => r.legal_name },
      { header: 'DBA name', value: (r) => r.dba_name ?? '' },
      { header: 'Primary email', value: (r) => r.primary_email ?? '' },
      { header: 'Created', value: (r) => r.created_at },
    ]);
    downloadCsv(`suppliers-${new Date().toISOString().slice(0, 10)}.csv`, csv);
  }

  // BACKEND-COUPLED: `/suppliers` returns a bare array (no `total`); page
  // navigation relies on result-count fallback in PaginationControls.
  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
            Suppliers
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Producers and MGAs whose submissions you orchestrate.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <SearchInput
            value={search}
            onChange={setSearch}
            placeholder="Search by legal name…"
            ariaLabel="Search suppliers by legal name"
            className="w-64"
          />
          <Button
            variant="outline"
            size="sm"
            onClick={exportCsv}
            disabled={suppliers.length === 0}
            leadingIcon={<Download className="h-3.5 w-3.5" />}
          >
            Export CSV
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={openCreate}
            leadingIcon={<Plus className="h-3.5 w-3.5" />}
          >
            New supplier
          </Button>
        </div>
      </header>

      <div className="rounded-lg border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
        {query.isLoading ? (
          <div className="space-y-2 p-5" aria-busy="true">
            <Skeleton className="h-6 w-full" />
            <Skeleton className="h-6 w-full" />
            <Skeleton className="h-6 w-full" />
            <Skeleton className="h-6 w-full" />
          </div>
        ) : query.error ? (
          <div className="px-5 py-8 text-sm text-red-700 dark:text-red-400">
            {extractErrorMessage(query.error, 'Failed to load suppliers')}
          </div>
        ) : suppliers.length === 0 ? (
          <div className="px-5 py-12">
            <EmptyState
              title="No suppliers yet"
              description={
                search.trim()
                  ? 'No suppliers match your search.'
                  : 'Create your first supplier to start submitting on their behalf.'
              }
              icon={Users}
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500 dark:bg-slate-800/60 dark:text-slate-400">
                <tr>
                  <th className="px-5 py-2 font-medium">Legal name</th>
                  <th className="px-5 py-2 font-medium">DBA</th>
                  <th className="px-5 py-2 font-medium">Email</th>
                  <th className="px-5 py-2 font-medium">Created</th>
                  <th className="px-5 py-2 font-medium" aria-label="Actions" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {suppliers.map((row) => (
                  <tr
                    key={row.id}
                    className="hover:bg-slate-50 dark:hover:bg-slate-800/50"
                  >
                    <td className="px-5 py-2 font-medium text-slate-900 dark:text-slate-100">
                      <Link
                        to={`/suppliers/${row.id}`}
                        className="hover:underline"
                      >
                        {row.legal_name}
                      </Link>
                    </td>
                    <td className="px-5 py-2 text-slate-600 dark:text-slate-300">
                      {row.dba_name ?? '—'}
                    </td>
                    <td className="px-5 py-2 text-slate-600 dark:text-slate-300">
                      {row.primary_email ?? '—'}
                    </td>
                    <td className="px-5 py-2 text-slate-500 dark:text-slate-400">
                      {new Date(row.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-5 py-2 text-right">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => openEdit(row.id)}
                        leadingIcon={<Pencil className="h-3.5 w-3.5" />}
                      >
                        Edit
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <PaginationControls
          page={page}
          pageSize={PAGE_SIZE}
          total={null}
          onPageChange={setPage}
          isLoading={query.isLoading}
        />
      </div>

      <Modal
        open={modalOpen}
        onClose={closeModal}
        title={editingId ? 'Edit supplier' : 'New supplier'}
        size="md"
        footer={
          <>
            <Button variant="outline" size="sm" onClick={closeModal}>
              Cancel
            </Button>
            <Button
              type="submit"
              form="supplier-form"
              variant="primary"
              size="sm"
            >
              {editingId ? 'Save changes' : 'Create supplier'}
            </Button>
          </>
        }
      >
        <SupplierForm editingId={editingId} onClose={closeModal} />
      </Modal>
    </div>
  );
}
