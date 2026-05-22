import { SupplierPicker } from "@/components/SupplierPicker";
import { Button, Card, CardHeader, ErrorState, MultiSelect, Select, Skeleton, Textarea } from "@/components/ui";
import { useConsents } from "@/hooks/useConsents";
import { usePortals } from "@/hooks/usePortals";
import { useCreateSubmission } from "@/hooks/useSubmissions";
import { toast } from "@/lib/toast";
import { ArrowLeft, Send } from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

type Step = 1 | 2 | 3;

export default function SubmissionNew(): JSX.Element {
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>(1);
  const [supplierId, setSupplierId] = useState("");
  const [consentId, setConsentId] = useState("");
  const [portalIds, setPortalIds] = useState<string[]>([]);
  const [payload, setPayload] = useState("{\n  \n}");
  const [payloadError, setPayloadError] = useState<string | null>(null);

  const portals = usePortals({ supportedOnly: true, pageSize: 200 });
  const consents = useConsents(supplierId ? { supplier_id: supplierId, active_only: true } : {}, {
    enabled: Boolean(supplierId),
  });
  const create = useCreateSubmission();

  const portalOptions = useMemo(
    () =>
      (portals.data?.items ?? []).map((p) => ({
        value: p.id,
        label: p.display_name,
        description: p.platform,
      })),
    [portals.data],
  );

  const consentOptions = useMemo(
    () =>
      (consents.data?.items ?? []).map((c) => ({
        value: c.id,
        label: `${c.scope} · ${new Date(c.granted_at).toLocaleDateString()}`,
      })),
    [consents.data],
  );

  function tryParsePayload(): Record<string, unknown> | null {
    try {
      const v: unknown = JSON.parse(payload);
      if (typeof v !== "object" || v === null || Array.isArray(v)) {
        setPayloadError("Payload must be a JSON object.");
        return null;
      }
      setPayloadError(null);
      return v as Record<string, unknown>;
    } catch (e) {
      setPayloadError((e as Error).message);
      return null;
    }
  }

  async function onSubmit(): Promise<void> {
    const parsed = tryParsePayload();
    if (!parsed) return;
    if (!supplierId || !consentId || portalIds.length === 0) {
      toast.error("Pick a supplier, a consent record, and at least one portal.");
      return;
    }
    try {
      await Promise.all(
        portalIds.map((portalId) =>
          create.mutateAsync({
            supplier_id: supplierId,
            portal_id: portalId,
            payload: parsed,
            consent_record_id: consentId,
          }),
        ),
      );
      toast.success(`${portalIds.length} submission(s) queued.`);
      navigate("/submissions");
    } catch (err) {
      toast.error(err, "Failed to create submission(s)");
    }
  }

  function canAdvance(): boolean {
    if (step === 1) return Boolean(supplierId) && Boolean(consentId);
    if (step === 2) return portalIds.length > 0;
    return true;
  }

  return (
    <div className="space-y-4">
      <Button
        variant="ghost"
        size="sm"
        onClick={() => navigate("/submissions")}
        leadingIcon={<ArrowLeft className="h-3.5 w-3.5" />}
      >
        Back to submissions
      </Button>

      <header>
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">New submission</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Submit once. Fan out to every selected carrier portal.
        </p>
      </header>

      <ol className="flex items-center gap-3 text-xs">
        {([1, 2, 3] as const).map((s) => (
          <li
            key={s}
            className={
              s === step
                ? "rounded-full bg-slate-900 px-3 py-1 font-medium text-white dark:bg-slate-100 dark:text-slate-900"
                : "rounded-full bg-slate-100 px-3 py-1 text-slate-600 dark:bg-slate-800 dark:text-slate-300"
            }
          >
            {s}. {s === 1 ? "Supplier" : s === 2 ? "Portals" : "Payload & review"}
          </li>
        ))}
      </ol>

      <Card>
        {step === 1 && (
          <div className="space-y-3">
            <CardHeader title="Step 1 — Supplier & consent" />
            <SupplierPicker
              label="Supplier"
              required
              value={supplierId}
              onChange={(e) => {
                setSupplierId(e.target.value);
                setConsentId("");
              }}
            />
            {supplierId ? (
              consents.isLoading ? (
                <Skeleton className="h-9 w-full" />
              ) : consents.error ? (
                <ErrorState
                  title="Could not load consents"
                  error={consents.error}
                  onRetry={() => void consents.refetch()}
                />
              ) : consentOptions.length === 0 ? (
                <p className="text-sm text-amber-700 dark:text-amber-300">
                  This supplier has no active consent records. Add one in the consent ledger before submitting.
                </p>
              ) : (
                <Select
                  label="Consent record"
                  required
                  options={consentOptions}
                  placeholder="Pick an active consent"
                  value={consentId}
                  onChange={(e) => setConsentId(e.target.value)}
                />
              )
            ) : null}
          </div>
        )}

        {step === 2 && (
          <div className="space-y-3">
            <CardHeader title="Step 2 — Portals" />
            {portals.isLoading ? (
              <Skeleton className="h-40 w-full" />
            ) : portals.error ? (
              <ErrorState title="Could not load portals" error={portals.error} onRetry={() => void portals.refetch()} />
            ) : (
              <MultiSelect<string>
                label="Carrier portals"
                hint="Pick one or more portals; we will create one submission per portal."
                options={portalOptions}
                value={portalIds}
                onChange={setPortalIds}
              />
            )}
          </div>
        )}

        {step === 3 && (
          <div className="space-y-3">
            <CardHeader title="Step 3 — Payload & review" />
            <Textarea
              label="Submission payload (JSON object)"
              rows={10}
              className="font-mono text-xs"
              required
              value={payload}
              onChange={(e) => setPayload(e.target.value)}
              error={payloadError ?? undefined}
            />
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1 rounded-md border border-slate-200 bg-slate-50 p-3 text-xs dark:border-slate-700 dark:bg-slate-800/40">
              <dt className="text-slate-500">Supplier</dt>
              <dd className="font-mono">{supplierId.slice(0, 8)}</dd>
              <dt className="text-slate-500">Consent</dt>
              <dd className="font-mono">{consentId.slice(0, 8)}</dd>
              <dt className="text-slate-500">Portals</dt>
              <dd>{portalIds.length}</dd>
            </dl>
          </div>
        )}

        <div className="mt-4 flex items-center justify-between">
          <Button
            variant="outline"
            disabled={step === 1}
            onClick={() => setStep((s) => (s > 1 ? ((s - 1) as Step) : s))}
          >
            Back
          </Button>
          {step < 3 ? (
            <Button disabled={!canAdvance()} onClick={() => setStep((s) => (s + 1) as Step)}>
              Next
            </Button>
          ) : (
            <Button
              loading={create.isPending}
              onClick={() => void onSubmit()}
              leadingIcon={<Send className="h-3.5 w-3.5" />}
            >
              Submit to {portalIds.length} portal(s)
            </Button>
          )}
        </div>
      </Card>
    </div>
  );
}
