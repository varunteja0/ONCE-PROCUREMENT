import ReceiptVerifierWidget from "@/components/ReceiptVerifierWidget";
import { Button, Card, CardHeader, DateDisplay, ErrorState, Skeleton, StatusBadge } from "@/components/ui";
import { usePortals } from "@/hooks/usePortals";
import { useRetrySubmission, useSubmission, useSubmissionReceipt } from "@/hooks/useSubmissions";
import { useSuppliers } from "@/hooks/useSuppliers";
import { toast } from "@/lib/toast";
import { ArrowLeft, RefreshCw } from "lucide-react";
import { useMemo } from "react";
import { useNavigate, useParams } from "react-router-dom";

export default function SubmissionDetail(): JSX.Element {
  const params = useParams<{ id: string }>();
  const navigate = useNavigate();
  const id = params.id;

  const detail = useSubmission(id);

  const receipt = useSubmissionReceipt(detail.data?.status === "completed" ? id : undefined);
  const retry = useRetrySubmission();

  const suppliersQuery = useSuppliers({ pageSize: 200 });
  const portalsQuery = usePortals({ pageSize: 200 });

  const supplierName = useMemo(() => {
    if (!detail.data) return null;
    return (suppliersQuery.data ?? []).find((s) => s.id === detail.data?.supplier_id)?.legal_name ?? null;
  }, [detail.data, suppliersQuery.data]);

  const portalName = useMemo(() => {
    if (!detail.data) return null;
    return (portalsQuery.data?.items ?? []).find((p) => p.id === detail.data?.portal_id)?.display_name ?? null;
  }, [detail.data, portalsQuery.data]);

  async function onRetry(): Promise<void> {
    if (!id) return;
    try {
      await retry.mutateAsync(id);
      toast.success("Submission requeued.");
    } catch (err) {
      toast.error(err, "Retry failed");
    }
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

      {detail.isLoading ? (
        <div className="space-y-3" aria-busy="true">
          <Skeleton className="h-7 w-64" />
          <Skeleton className="h-32 w-full" />
        </div>
      ) : detail.error || !detail.data ? (
        <ErrorState
          title="Submission not found"
          error={detail.error ?? new Error("Unknown")}
          onRetry={() => void detail.refetch()}
        />
      ) : (
        <>
          <header className="flex items-start justify-between gap-3">
            <div>
              <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
                Submission {detail.data.id.slice(0, 8)}
              </h1>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                Supplier{" "}
                <span className="text-slate-700 dark:text-slate-200">
                  {supplierName ?? detail.data.supplier_id.slice(0, 8)}
                </span>{" "}
                · Portal{" "}
                <span className="text-slate-700 dark:text-slate-200">
                  {portalName ?? detail.data.portal_id.slice(0, 8)}
                </span>
              </p>
            </div>
            <div className="flex items-center gap-2">
              <StatusBadge status={detail.data.status} />
              {(detail.data.status === "failed" || detail.data.status === "blocked") && (
                <Button
                  size="sm"
                  variant="outline"
                  loading={retry.isPending}
                  onClick={() => void onRetry()}
                  leadingIcon={<RefreshCw className="h-3.5 w-3.5" />}
                >
                  Retry
                </Button>
              )}
            </div>
          </header>

          <Card>
            <CardHeader title="Run details" />
            <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-3">
              <div>
                <dt className="text-xs text-slate-500 dark:text-slate-400">Attempts</dt>
                <dd className="text-slate-900 dark:text-slate-100">{detail.data.attempt_count}</dd>
              </div>
              <div>
                <dt className="text-xs text-slate-500 dark:text-slate-400">Created</dt>
                <dd>
                  <DateDisplay value={detail.data.created_at} />
                </dd>
              </div>
              <div>
                <dt className="text-xs text-slate-500 dark:text-slate-400">Started</dt>
                <dd>
                  <DateDisplay value={detail.data.started_at} />
                </dd>
              </div>
              <div>
                <dt className="text-xs text-slate-500 dark:text-slate-400">Completed</dt>
                <dd>
                  <DateDisplay value={detail.data.completed_at} />
                </dd>
              </div>
            </dl>
            {detail.data.last_error ? (
              <div className="mt-3 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800 dark:border-rose-800 dark:bg-rose-950/30 dark:text-rose-200">
                <p className="font-medium">Last error</p>
                <p className="font-mono text-xs">{detail.data.last_error}</p>
              </div>
            ) : null}
          </Card>

          <Card padded={false}>
            <CardHeader title="Payload" />
            <pre className="max-h-72 overflow-auto rounded-b-lg bg-slate-900 p-4 text-xs text-slate-100">
              {JSON.stringify(detail.data.payload_json, null, 2)}
            </pre>
          </Card>

          {detail.data.result_json ? (
            <Card padded={false}>
              <CardHeader title="Result" />
              <pre className="max-h-72 overflow-auto rounded-b-lg bg-slate-50 p-4 text-xs text-slate-800 dark:bg-slate-800 dark:text-slate-100">
                {JSON.stringify(detail.data.result_json, null, 2)}
              </pre>
            </Card>
          ) : null}

          {detail.data.status === "completed" && receipt.data ? (
            <Card>
              <CardHeader title="Receipt" />
              <ReceiptVerifierWidget receiptId={receipt.data.id} />
            </Card>
          ) : null}
        </>
      )}
    </div>
  );
}
