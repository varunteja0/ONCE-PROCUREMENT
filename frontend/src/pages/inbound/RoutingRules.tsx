// --- L3.9 inbound ---
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Trash2, Plus } from 'lucide-react';
import { Button, ErrorState, Input, Select, Skeleton } from '@/components/ui';
import {
  useCreateInboundRule,
  useDeleteInboundRule,
  useInboundRules,
} from '@/hooks/useInbound';
import type { InboundAction, InboundRuleCreate } from '@/services/inboundApi';
import { extractErrorMessage } from '@/services/api';

const ACTIONS: { value: InboundAction; label: string }[] = [
  { value: 'create_submission', label: 'Create draft submission' },
  { value: 'quarantine', label: 'Quarantine' },
  { value: 'discard', label: 'Discard silently' },
  { value: 'tag_only', label: 'Tag only (no action)' },
];

const EMPTY_FORM: InboundRuleCreate = {
  name: '',
  priority: 100,
  match_from_domain: '',
  match_subject_regex: '',
  match_attachment_kind: '',
  action: 'create_submission',
  active: true,
};

export default function RoutingRules(): JSX.Element {
  const { data: rules, isLoading, error, refetch } = useInboundRules();
  const createRule = useCreateInboundRule();
  const deleteRule = useDeleteInboundRule();
  const [form, setForm] = useState<InboundRuleCreate>(EMPTY_FORM);

  function handleSubmit(e: React.FormEvent): void {
    e.preventDefault();
    if (!form.name.trim()) return;
    createRule.mutate(
      {
        ...form,
        match_from_domain: form.match_from_domain || null,
        match_subject_regex: form.match_subject_regex || null,
        match_attachment_kind: form.match_attachment_kind || null,
      },
      {
        onSuccess: () => setForm(EMPTY_FORM),
      },
    );
  }

  return (
    <div className="space-y-6 p-6">
      <header>
        <Link to="/inbound" className="text-xs text-sky-700 hover:underline dark:text-sky-300">
          ← Back to inbound
        </Link>
        <h1 className="mt-1 text-2xl font-semibold">Inbound routing rules</h1>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Rules are evaluated in ascending priority order; the first match wins.
          A fallback rule (priority 999) always creates a draft submission.
        </p>
      </header>

      {isLoading ? (
        <Skeleton className="h-32 w-full" />
      ) : error ? (
        <ErrorState
          title="Couldn't load rules"
          description={extractErrorMessage(error)}
          onRetry={() => refetch()}
        />
      ) : (
        <div className="overflow-x-auto rounded-md border border-gray-200 dark:border-gray-700">
          <table className="min-w-full divide-y divide-gray-200 text-sm dark:divide-gray-700">
            <thead className="bg-gray-50 text-left text-xs uppercase text-gray-500 dark:bg-gray-900 dark:text-gray-400">
              <tr>
                <th className="px-3 py-2">Priority</th>
                <th className="px-3 py-2">Name</th>
                <th className="px-3 py-2">From domain</th>
                <th className="px-3 py-2">Subject regex</th>
                <th className="px-3 py-2">Action</th>
                <th className="px-3 py-2">Active</th>
                <th className="px-3 py-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
              {(rules ?? []).map((r) => (
                <tr key={r.id}>
                  <td className="px-3 py-2 font-mono">{r.priority}</td>
                  <td className="px-3 py-2 font-medium">{r.name}</td>
                  <td className="px-3 py-2">{r.match_from_domain ?? '—'}</td>
                  <td className="px-3 py-2 font-mono text-xs">
                    {r.match_subject_regex ?? '—'}
                  </td>
                  <td className="px-3 py-2">{r.action}</td>
                  <td className="px-3 py-2">{r.active ? 'Yes' : 'No'}</td>
                  <td className="px-3 py-2 text-right">
                    <button
                      type="button"
                      onClick={() => deleteRule.mutate(r.id)}
                      className="text-rose-600 hover:text-rose-800"
                      aria-label={`Delete rule ${r.name}`}
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <section>
        <h2 className="mb-2 text-lg font-semibold">Add a rule</h2>
        <form onSubmit={handleSubmit} className="grid gap-3 md:grid-cols-2">
          <Input
            label="Name"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            required
          />
          <Input
            label="Priority"
            type="number"
            min={0}
            max={998}
            value={form.priority ?? 100}
            onChange={(e) => setForm({ ...form, priority: Number(e.target.value) })}
          />
          <Input
            label="From domain (optional)"
            placeholder="brokerage.example"
            value={form.match_from_domain ?? ''}
            onChange={(e) => setForm({ ...form, match_from_domain: e.target.value })}
          />
          <Input
            label="Subject regex (optional)"
            placeholder="^(quote|COI)"
            value={form.match_subject_regex ?? ''}
            onChange={(e) => setForm({ ...form, match_subject_regex: e.target.value })}
          />
          <Input
            label="Attachment kind (optional)"
            placeholder="pdf"
            value={form.match_attachment_kind ?? ''}
            onChange={(e) => setForm({ ...form, match_attachment_kind: e.target.value })}
          />
          <Select
            label="Action"
            value={form.action ?? 'create_submission'}
            onChange={(e) =>
              setForm({ ...form, action: e.target.value as InboundAction })
            }
            options={ACTIONS}
          />
          <div className="md:col-span-2">
            <Button type="submit" disabled={createRule.isPending}>
              <Plus className="mr-1 h-4 w-4" />
              Add rule
            </Button>
            {createRule.error ? (
              <p className="mt-2 text-sm text-rose-600">
                {extractErrorMessage(createRule.error)}
              </p>
            ) : null}
          </div>
        </form>
      </section>
    </div>
  );
}
