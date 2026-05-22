/**
 * Verifier API keys management page (Phase L6.1).
 *
 * Tenant-admin surface for issuing, listing, and revoking API keys that
 * authenticate calls to the public Verifier (`verify.once.io`). The
 * plaintext key is shown ONCE in a modal immediately after creation \u2014
 * after that the server only stores a SHA-256 hash.
 */

import type {
    VerifierKey,
    VerifierKeyIssued,
} from '@/api/verifierKeys';
import {
    Button,
    Card,
    CardHeader,
    DateDisplay,
    EmptyState,
    ErrorState,
    Input,
    Modal,
    Skeleton,
} from '@/components/ui';
import {
    useIssueVerifierKey,
    useRevokeVerifierKey,
    useVerifierKeys,
} from '@/hooks/useVerifierKeys';
import toast from '@/lib/toast';
import { extractErrorMessage } from '@/services/api';
import { AlertTriangle, Copy, KeyRound, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { useForm } from 'react-hook-form';

interface IssueFormValues {
  name: string;
  cap: string; // string from input; parsed below
}

export default function VerifierKeys(): JSX.Element {
  const list = useVerifierKeys();
  const issue = useIssueVerifierKey();
  const revoke = useRevokeVerifierKey();

  const [issueOpen, setIssueOpen] = useState(false);
  const [issued, setIssued] = useState<VerifierKeyIssued | null>(null);

  const form = useForm<IssueFormValues>({
    defaultValues: { name: '', cap: '' },
  });

  async function handleIssue(values: IssueFormValues): Promise<void> {
    const trimmedCap = values.cap.trim();
    let cap: number | null;
    if (trimmedCap === '') {
      cap = null;
    } else {
      const parsed = Number(trimmedCap);
      if (!Number.isFinite(parsed) || parsed < 0 || !Number.isInteger(parsed)) {
        form.setError('cap', {
          message: 'Must be a non-negative integer (0 = uncapped, blank = free-tier default).',
        });
        return;
      }
      cap = parsed;
    }
    try {
      const result = await issue.mutateAsync({
        name: values.name.trim(),
        monthly_call_cap: cap,
      });
      setIssued(result);
      setIssueOpen(false);
      form.reset();
    } catch (err) {
      toast.error(extractErrorMessage(err, 'Failed to issue verifier key'));
    }
  }

  async function handleRevoke(key: VerifierKey): Promise<void> {
    const confirmed = window.confirm(
      `Revoke "${key.name}" (${key.key_prefix}\u2026)? Existing calls using it will start failing with 401 within ~1 minute.`,
    );
    if (!confirmed) return;
    try {
      await revoke.mutateAsync(key.id);
      toast.success('Verifier key revoked');
    } catch (err) {
      toast.error(extractErrorMessage(err, 'Failed to revoke verifier key'));
    }
  }

  async function copyPlaintext(): Promise<void> {
    if (!issued) return;
    try {
      await navigator.clipboard.writeText(issued.plaintext);
      toast.success('Copied to clipboard');
    } catch {
      toast.error('Could not access clipboard; copy manually.');
    }
  }

  return (
    <div className="space-y-4" data-testid="verifier-keys-page">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-amber-900 dark:text-amber-100">
            Verifier API keys
          </h1>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
            Issue API keys for programmatic calls to the public receipt
            verifier. Unauthenticated callers are rate-limited per IP; an
            API key raises that limit and is subject to a monthly call cap.
          </p>
        </div>
        <Button
          onClick={() => {
            form.reset();
            setIssueOpen(true);
          }}
        >
          Issue key
        </Button>
      </div>

      <Card>
        <CardHeader title="Active keys" />
        {list.isLoading ? (
          <div className="space-y-2 p-4">
            <Skeleton className="h-6 w-full" />
            <Skeleton className="h-6 w-full" />
            <Skeleton className="h-6 w-2/3" />
          </div>
        ) : list.isError ? (
          <div className="p-4">
            <ErrorState
              title="Could not load verifier keys"
              description={extractErrorMessage(list.error, 'Try again.')}
              onRetry={() => void list.refetch()}
            />
          </div>
        ) : list.data && list.data.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-amber-100 dark:divide-amber-900">
              <thead className="bg-amber-50 text-left text-xs uppercase tracking-wide text-amber-900 dark:bg-slate-900 dark:text-amber-200">
                <tr>
                  <th className="px-3 py-2">Name</th>
                  <th className="px-3 py-2">Prefix</th>
                  <th className="px-3 py-2">Monthly cap</th>
                  <th className="px-3 py-2">Last used</th>
                  <th className="px-3 py-2">Created</th>
                  <th className="px-3 py-2" aria-label="Actions" />
                </tr>
              </thead>
              <tbody className="divide-y divide-amber-50 text-sm dark:divide-amber-900/60">
                {list.data.map((k) => (
                  <tr key={k.id} data-testid={`vk-row-${k.id}`}>
                    <td className="px-3 py-2 font-medium">{k.name}</td>
                    <td className="px-3 py-2 font-mono text-xs">
                      {k.key_prefix}{'\u2026'}
                    </td>
                    <td className="px-3 py-2">
                      {k.monthly_call_cap === null
                        ? <span className="text-slate-500">uncapped</span>
                        : k.monthly_call_cap.toLocaleString()}
                    </td>
                    <td className="px-3 py-2">
                      {k.last_used_at
                        ? <DateDisplay value={k.last_used_at} />
                        : <span className="text-slate-500">never</span>}
                    </td>
                    <td className="px-3 py-2">
                      <DateDisplay value={k.created_at} />
                    </td>
                    <td className="px-3 py-2 text-right">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => void handleRevoke(k)}
                        loading={revoke.isPending && revoke.variables === k.id}
                        leadingIcon={<Trash2 className="h-3.5 w-3.5" />}
                      >
                        Revoke
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState
            icon={KeyRound}
            title="No verifier keys yet"
            description="Issue your first key to authenticate calls to verify.once.io."
          />
        )}
      </Card>

      <Modal
        open={issueOpen}
        onClose={() => setIssueOpen(false)}
        title="Issue verifier API key"
        description="Give the key a descriptive name (e.g. the consumer system). You will see the secret value once."
      >
        <form
          onSubmit={form.handleSubmit(handleIssue)}
          className="space-y-3"
          noValidate
        >
          <Input
            label="Name"
            required
            placeholder="e.g. ACME Carrier Portal"
            error={form.formState.errors.name?.message}
            {...form.register('name', { required: 'Name is required' })}
          />
          <Input
            label="Monthly call cap"
            type="number"
            min={0}
            placeholder="(blank = free-tier default)"
            hint="Leave blank for the free-tier default. Enter 0 to disable the cap (paid metered tier). Otherwise the integer is a hard limit; the 10,001st call returns 402."
            error={form.formState.errors.cap?.message}
            {...form.register('cap')}
          />
          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => setIssueOpen(false)}
            >
              Cancel
            </Button>
            <Button type="submit" loading={issue.isPending}>
              Issue key
            </Button>
          </div>
        </form>
      </Modal>

      <Modal
        open={issued !== null}
        onClose={() => setIssued(null)}
        title="Copy your new verifier key"
        description={'This is the only time the full key will be shown. Once you close this dialog it cannot be retrieved \u2014 the server only stores a hash.'}
        size="lg"
      >
        {issued ? (
          <div className="space-y-3" data-testid="vk-issued-modal">
            <div className="flex items-start gap-2 rounded border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-100">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <p>
                Store this somewhere safe (a secrets manager). If you lose it,
                revoke the key and issue a new one.
              </p>
            </div>
            <label
              htmlFor="vk-plaintext"
              className="block text-xs uppercase tracking-wide text-slate-500"
            >
              API key
            </label>
            <div className="flex items-center gap-2">
              <code
                id="vk-plaintext"
                className="block w-full overflow-x-auto rounded border border-amber-200 bg-white px-3 py-2 font-mono text-xs text-amber-900 dark:border-amber-900 dark:bg-slate-900 dark:text-amber-100"
                data-testid="vk-plaintext"
              >
                {issued.plaintext}
              </code>
              <Button
                type="button"
                variant="outline"
                onClick={() => void copyPlaintext()}
                leadingIcon={<Copy className="h-3.5 w-3.5" />}
              >
                Copy
              </Button>
            </div>
            <dl className="grid grid-cols-2 gap-2 text-xs">
              <div>
                <dt className="text-slate-500">Prefix</dt>
                <dd className="font-mono">{issued.key_prefix}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Monthly cap</dt>
                <dd>
                  {issued.monthly_call_cap === null
                    ? 'uncapped'
                    : issued.monthly_call_cap.toLocaleString()}
                </dd>
              </div>
            </dl>
            <div className="flex justify-end pt-2">
              <Button onClick={() => setIssued(null)}>I have copied it</Button>
            </div>
          </div>
        ) : null}
      </Modal>
    </div>
  );
}
