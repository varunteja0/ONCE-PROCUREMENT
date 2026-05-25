import ReceiptVerifierWidget from "@/components/ReceiptVerifierWidget";
import { Button, EmptyState, PaginationControls, Skeleton } from "@/components/ui";
import { useReceipts } from "@/hooks/useReceipts";
import { useSuppliers } from "@/hooks/useSuppliers";
import { downloadCsv, toCsv } from "@/lib/csv";
import { toast } from "@/lib/toast";
import type { Receipt } from "@/services/api";
import { extractErrorMessage } from "@/services/api";
import { Download, FileCheck2, ShieldCheck, X } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

const PAGE_SIZE = 25;

export default function Receipts(): JSX.Element {
  const [params, setParams] = useSearchParams();
  const page = Math.max(1, Number(params.get("page") ?? "1"));
  const query = useReceipts({ page, pageSize: PAGE_SIZE });
  const suppliersQuery = useSuppliers({ pageSize: 200 });
  const [active, setActive] = useState<Receipt | null>(null);

  const receipts = query.data ?? [];

  const supplierNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const s of suppliersQuery.data ?? []) {
      map.set(s.id, s.legal_name);
    }
    return map;
  }, [suppliersQuery.data]);

  function setPage(next: number): void {
    setParams((prev) => {
      const out = new URLSearchParams(prev);
      out.set("page", String(next));
      return out;
    });
  }

  function exportCsv(): void {
    if (receipts.length === 0) {
      toast.error("Nothing to export.");
      return;
    }
    const csv = toCsv(receipts, [
      { header: "Receipt ID", value: (r) => r.id },
      { header: "Submission ID", value: (r) => r.submission_id },
      {
        header: "Supplier",
        value: (r) => supplierNameById.get(r.supplier_id) ?? r.supplier_id,
      },
      { header: "Portal platform", value: (r) => r.portal_platform },
      { header: "Submitted", value: (r) => r.submitted_at },
      { header: "Signing key", value: (r) => r.signing_key_id },
      { header: "Payload hash", value: (r) => r.payload_hash },
      { header: "Verify URL", value: (r) => r.verify_url },
    ]);
    downloadCsv(`receipts-${new Date().toISOString().slice(0, 10)}.csv`, csv);
  }

  // BACKEND-COUPLED: `/receipts` returns a bare array (no `total`), so
  // PaginationControls is given `total={null}` and shows "Page N".
  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">Receipts</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Ed25519-signed proof of every successful submission. Click a receipt to verify.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={exportCsv}
          disabled={receipts.length === 0}
          leadingIcon={<Download className="h-3.5 w-3.5" />}
        >
          Export CSV
        </Button>
      </header>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2 rounded-lg border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
          {query.isLoading ? (
            <div className="space-y-2 p-5" aria-busy="true">
              <Skeleton className="h-6 w-full" />
              <Skeleton className="h-6 w-full" />
              <Skeleton className="h-6 w-full" />
            </div>
          ) : query.error ? (
            <div className="px-5 py-8 text-sm text-red-700 dark:text-red-400">
              {extractErrorMessage(query.error, "Failed to load receipts")}
            </div>
          ) : receipts.length === 0 ? (
            <div className="px-5 py-12">
              <EmptyState
                title="No receipts yet"
                description="Receipts will appear here once a submission completes successfully."
                icon={FileCheck2}
              />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500 dark:bg-slate-800/60 dark:text-slate-400">
                  <tr>
                    <th className="px-5 py-2 font-medium">Receipt</th>
                    <th className="px-5 py-2 font-medium">Supplier</th>
                    <th className="px-5 py-2 font-medium">Portal</th>
                    <th className="px-5 py-2 font-medium">Submitted</th>
                    <th className="px-5 py-2 font-medium">Key</th>
                    <th className="px-5 py-2 font-medium" aria-label="Actions" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {receipts.map((r) => {
                    const isActive = active?.id === r.id;
                    return (
                      <tr
                        key={r.id}
                        className={
                          isActive
                            ? "bg-slate-100 dark:bg-slate-800/60"
                            : "hover:bg-slate-50 dark:hover:bg-slate-800/50"
                        }
                      >
                        <td className="px-5 py-2">
                          <Link
                            to={`/receipts/${r.id}`}
                            className="font-mono text-xs text-slate-700 underline hover:no-underline dark:text-slate-200"
                          >
                            {r.id.slice(0, 8)}
                          </Link>
                        </td>
                        <td className="px-5 py-2 text-slate-700 dark:text-slate-200">
                          {supplierNameById.get(r.supplier_id) ?? (
                            <span className="font-mono text-xs text-slate-500 dark:text-slate-400">
                              {r.supplier_id.slice(0, 8)}
                            </span>
                          )}
                        </td>
                        <td className="px-5 py-2 text-slate-700 dark:text-slate-200">{r.portal_platform}</td>
                        <td className="px-5 py-2 text-slate-500 dark:text-slate-400">
                          {new Date(r.submitted_at).toLocaleString()}
                        </td>
                        <td className="px-5 py-2 font-mono text-xs text-slate-500 dark:text-slate-400">
                          {r.signing_key_id}
                        </td>
                        <td className="px-5 py-2 text-right">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setActive(r)}
                            leadingIcon={<ShieldCheck className="h-3.5 w-3.5" />}
                          >
                            Verify
                          </Button>
                        </td>
                      </tr>
                    );
                  })}
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

        <aside className="rounded-lg border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
          <div className="flex items-center justify-between border-b border-slate-200 px-4 py-2 dark:border-slate-800">
            <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Verification</h2>
            {active && (
              <button
                type="button"
                onClick={() => setActive(null)}
                className="rounded p-1 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800"
                aria-label="Close verifier"
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </button>
            )}
          </div>
          <div className="p-4">
            {active ? (
              <ReceiptVerifierWidget receiptId={active.id} />
            ) : (
              <p className="text-sm text-slate-500 dark:text-slate-400">
                Select a receipt to view its cryptographic verification.
              </p>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
