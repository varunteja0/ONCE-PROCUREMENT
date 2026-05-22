// --- L3.6 onboarding ---
import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import StepShell from '@/components/onboarding/StepShell';
import { Select } from '@/components/ui/Select';
import { Button } from '@/components/ui/Button';
import { toast } from '@/lib/toast';
import {
  api,
  type Portal,
  type PortalListResponse,
  type SupplierListItem,
} from '@/services/api';
import { onboarding } from '@/services/onboardingApi';
import { useOnboardingStore } from '@/store/onboardingStore';

export default function StepFirstSubmission(): JSX.Element {
  const navigate = useNavigate();
  const setDraft = useOnboardingStore((s) => s.setDraft);
  const draft = useOnboardingStore((s) => s.draft);

  const [portals, setPortals] = useState<Portal[]>([]);
  const [suppliers, setSuppliers] = useState<SupplierListItem[]>([]);
  const [supplierId, setSupplierId] = useState('');
  const [portalId, setPortalId] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [pollStatus, setPollStatus] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const [pRes, sRes] = await Promise.all([
          api.get<PortalListResponse>('/portals', {
            params: { is_supported: true, limit: 50 },
          }),
          api.get<{ items: SupplierListItem[] }>('/suppliers', {
            params: { limit: 50 },
          }),
        ]);
        if (cancelled) return;
        setPortals(pRes.data.items);
        setSuppliers(sRes.data.items);
        if (pRes.data.items[0]) setPortalId(pRes.data.items[0].id);
        if (sRes.data.items[0]) setSupplierId(sRes.data.items[0].id);
      } catch (err) {
        toast.error(err, 'Could not load portals or suppliers');
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const canSubmit = useMemo(
    () => Boolean(supplierId && portalId) && !submitting,
    [supplierId, portalId, submitting],
  );

  async function runSubmission(): Promise<void> {
    setSubmitting(true);
    try {
      const r = await onboarding.runFirstSubmission({
        supplier_id: supplierId,
        portal_id: portalId,
      });
      setDraft({ pendingSubmissionId: r.submission_id });
      setPollStatus(r.status);
      toast.success('First submission queued — sit tight.');
    } catch (err) {
      toast.error(err, 'Could not queue submission');
    } finally {
      setSubmitting(false);
    }
  }

  // Poll submission status until terminal, then advance.
  useEffect(() => {
    const id = draft.pendingSubmissionId;
    if (!id) return;
    let cancelled = false;
    const tick = async (): Promise<void> => {
      try {
        const r = await api.get<{ status: string }>(`/submissions/${id}`);
        if (cancelled) return;
        setPollStatus(r.data.status);
        if (['completed', 'failed', 'blocked', 'platform_unsupported'].includes(r.data.status)) {
          return;
        }
        setTimeout(() => void tick(), 2000);
      } catch {
        /* swallow */
      }
    };
    void tick();
    return () => {
      cancelled = true;
    };
  }, [draft.pendingSubmissionId]);

  async function skip(): Promise<void> {
    try {
      await onboarding.skipStep('submission');
      navigate('/onboarding/done');
    } catch (err) {
      toast.error(err, 'Could not skip this step');
    }
  }

  return (
    <StepShell
      title="Run your first submission"
      description="We’ll queue a real submission. You can cancel from the Submissions list any time."
    >
      <div className="space-y-4">
        <Select
          label="Supplier"
          value={supplierId}
          onChange={(e) => setSupplierId(e.target.value)}
          disabled={submitting || suppliers.length === 0}
          placeholder={suppliers.length === 0 ? 'No suppliers yet — add one first' : undefined}
          options={suppliers.map((s) => ({ value: s.id, label: s.legal_name }))}
        />
        <Select
          label="Portal"
          value={portalId}
          onChange={(e) => setPortalId(e.target.value)}
          disabled={submitting}
          options={portals.map((p) => ({ value: p.id, label: p.display_name }))}
        />
        {pollStatus ? (
          <div
            className="rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-700 dark:bg-slate-800 dark:text-slate-200"
            role="status"
            aria-live="polite"
          >
            Submission status: <strong>{pollStatus}</strong>
          </div>
        ) : null}
        <div className="flex items-center gap-3">
          <Button onClick={runSubmission} disabled={!canSubmit} loading={submitting}>
            {submitting ? 'Queueing…' : 'Queue submission'}
          </Button>
          <Button
            variant="outline"
            onClick={() => navigate('/onboarding/done')}
            disabled={!draft.pendingSubmissionId}
          >
            Continue
          </Button>
          <Button variant="ghost" onClick={skip} disabled={submitting}>
            Skip
          </Button>
        </div>
      </div>
    </StepShell>
  );
}
// --- /L3.6 onboarding ---
