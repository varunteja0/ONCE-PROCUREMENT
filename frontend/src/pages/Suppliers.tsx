import { useMemo, useState, type ChangeEvent, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import toast from '@/lib/toast';
import { Loader2, Pencil, Plus, Search, Users, X } from 'lucide-react';
import {
  useCreateSupplier,
  useSuppliers,
  useUpdateSupplier,
} from '@/hooks/useSuppliers';
import { extractErrorMessage } from '@/services/api';
import type {
  Supplier,
  SupplierCreateInput,
  SupplierListItem,
} from '@/services/api';
import EmptyState from '@/components/EmptyState';

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

interface ModalProps {
  initial: Supplier | null;
  onClose: () => void;
}

function SupplierModal({ initial, onClose }: ModalProps): JSX.Element {
  const create = useCreateSupplier();
  const update = useUpdateSupplier();
  const [form, setForm] = useState<FormState>(() =>
    initial
      ? {
          legal_name: initial.legal_name,
          dba_name: initial.dba_name ?? '',
          ein: initial.ein ?? '',
          naics_code: initial.naics_code ?? '',
          primary_email: initial.primary_email ?? '',
          primary_phone: initial.primary_phone ?? '',
          website: initial.website ?? '',
        }
      : emptyForm(),
  );

  const submitting = create.isPending || update.isPending;

  function update_<K extends keyof FormState>(key: K) {
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
      if (initial) {
        await update.mutateAsync({ id: initial.id, patch: toPayload(form) });
        toast.success('Supplier updated.');
      } else {
        await create.mutateAsync(toPayload(form));
        toast.success('Supplier created.');
      }
      onClose();
    } catch (err) {
      toast.error(extractErrorMessage(err, 'Save failed'));
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

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-slate-900/40 px-4"
      role="dialog"
      aria-modal="true"
      aria-label={initial ? 'Edit supplier' : 'New supplier'}
    >
      <div className="w-full max-w-lg rounded-lg bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-3">
          <h2 className="text-base font-semibold text-slate-900">
            {initial ? 'Edit supplier' : 'New supplier'}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-slate-500 hover:bg-slate-100"
            aria-label="Close"
          >
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>
        <form onSubmit={onSubmit} className="space-y-3 px-5 py-4">
          {fields.map((f) => (
            <div key={f.key}>
              <label
                htmlFor={`supplier_${f.key}`}
                className="mb-1 block text-xs font-medium text-slate-700"
              >
                {f.label}
                {f.required && <span className="text-red-600"> *</span>}
              </label>
              <input
                id={`supplier_${f.key}`}
                type={f.type ?? 'text'}
                value={form[f.key]}
                onChange={update_(f.key)}
                required={f.required}
                disabled={submitting}
                className="w-full rounded border border-slate-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-slate-900"
              />
            </div>
          ))}
          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
              className="rounded border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-100"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="inline-flex items-center gap-1 rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-60"
            >
              {submitting && (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              )}
              {initial ? 'Save changes' : 'Create supplier'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function Suppliers(): JSX.Element {
  const [search, setSearch] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Supplier | null>(null);

  const params = useMemo(
    () => ({ search: search.trim() || undefined, pageSize: 100 }),
    [search],
  );
  const query = useSuppliers(params);
  const suppliers: SupplierListItem[] = query.data ?? [];

  function openCreate(): void {
    setEditing(null);
    setModalOpen(true);
  }

  function openEdit(row: SupplierListItem): void {
    // We only have list-item data here; cast minimally into Supplier shape for
    // the form. Missing optional fields will be hydrated as null/empty.
    const partial: Supplier = {
      id: row.id,
      tenant_id: '',
      legal_name: row.legal_name,
      dba_name: row.dba_name,
      ein: null,
      naics_code: null,
      primary_email: row.primary_email,
      primary_phone: null,
      address_json: null,
      website: null,
      created_at: row.created_at,
      updated_at: row.created_at,
    };
    setEditing(partial);
    setModalOpen(true);
  }

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Suppliers</h1>
          <p className="text-sm text-slate-500">
            Producers and MGAs whose submissions you orchestrate.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search
              className="pointer-events-none absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
              aria-hidden="true"
            />
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by legal name…"
              className="w-64 rounded border border-slate-300 bg-white py-1.5 pl-7 pr-3 text-sm focus:outline-none focus:ring-2 focus:ring-slate-900"
              aria-label="Search suppliers by legal name"
            />
          </div>
          <button
            type="button"
            onClick={openCreate}
            className="inline-flex items-center gap-1 rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800"
          >
            <Plus className="h-4 w-4" aria-hidden="true" />
            New supplier
          </button>
        </div>
      </header>

      <div className="rounded-lg border border-slate-200 bg-white shadow-sm">
        {query.isLoading ? (
          <div className="flex items-center justify-center py-12 text-slate-500">
            <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
            <span className="ml-2 text-sm">Loading suppliers…</span>
          </div>
        ) : query.error ? (
          <div className="px-5 py-8 text-sm text-red-700">
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
              <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-5 py-2 font-medium">Legal name</th>
                  <th className="px-5 py-2 font-medium">DBA</th>
                  <th className="px-5 py-2 font-medium">Email</th>
                  <th className="px-5 py-2 font-medium">Created</th>
                  <th className="px-5 py-2 font-medium" aria-label="Actions" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {suppliers.map((row) => (
                  <tr key={row.id} className="hover:bg-slate-50">
                    <td className="px-5 py-2 font-medium text-slate-900">
                      <Link
                        to={`/suppliers/${row.id}`}
                        className="hover:underline"
                      >
                        {row.legal_name}
                      </Link>
                    </td>
                    <td className="px-5 py-2 text-slate-600">
                      {row.dba_name ?? '—'}
                    </td>
                    <td className="px-5 py-2 text-slate-600">
                      {row.primary_email ?? '—'}
                    </td>
                    <td className="px-5 py-2 text-slate-500">
                      {new Date(row.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-5 py-2 text-right">
                      <button
                        type="button"
                        onClick={() => openEdit(row)}
                        className="inline-flex items-center gap-1 rounded border border-slate-300 px-2 py-1 text-xs text-slate-700 hover:bg-slate-100"
                      >
                        <Pencil className="h-3.5 w-3.5" aria-hidden="true" />
                        Edit
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {modalOpen && (
        <SupplierModal initial={editing} onClose={() => setModalOpen(false)} />
      )}
    </div>
  );
}
