import ReceiptVerifierWidget from "@/components/ReceiptVerifierWidget";
import { Button, Card, CardHeader, DateDisplay, ErrorState, Skeleton } from "@/components/ui";
import { useReceipt } from "@/hooks/useReceipts";
import { toast } from "@/lib/toast";
import { ArrowLeft, Copy, Download, Mail, Send } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";

export default function ReceiptDetail(): JSX.Element {
  const params = useParams<{ id: string }>();
  const navigate = useNavigate();
  const id = params.id;

  const query = useReceipt(id);

  function copyVerifyUrl(): void {
    if (!query.data) return;
    void navigator.clipboard.writeText(query.data.verify_url).then(
      () => toast.success("Verify URL copied."),
      (err) => toast.error(err, "Failed to copy"),
    );
  }

  function downloadJson(): void {
    if (!query.data) return;
    const blob = new Blob([JSON.stringify(query.data, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `receipt-${query.data.id}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  function emailVerifyUrl(): void {
    if (!query.data) return;
    const subject = encodeURIComponent(`Verify submission receipt ${query.data.id.slice(0, 8)}`);
    const body = encodeURIComponent(
      `Hi,\n\nPlease verify the attached submission receipt at:\n${query.data.verify_url}\n\nReceipt ID: ${query.data.id}\nSubmitted: ${query.data.submitted_at}\nPortal: ${query.data.portal_platform}\n`,
    );
    window.location.href = `mailto:?subject=${subject}&body=${body}`;
  }

  function sendToUnderwriter(): void {
    if (!query.data) return;
    const subject = encodeURIComponent(
      `Submission receipt ${query.data.id.slice(0, 8)} — ${query.data.portal_platform}`,
    );
    const body = encodeURIComponent(
      `Hello underwriter,\n\nAttached is the cryptographically-signed receipt for our recent submission.\n\nVerify online: ${query.data.verify_url}\nReceipt ID: ${query.data.id}\nSubmission ID: ${query.data.submission_id}\nSubmitted at: ${query.data.submitted_at}\nSigning key: ${query.data.signing_key_id}\n\nThanks,\n`,
    );
    window.location.href = `mailto:?subject=${subject}&body=${body}`;
  }

  return (
    <div className="space-y-4">
      <Button
        variant="ghost"
        size="sm"
        onClick={() => navigate("/receipts")}
        leadingIcon={<ArrowLeft className="h-3.5 w-3.5" />}
      >
        Back to receipts
      </Button>

      {query.isLoading ? (
        <div className="space-y-3" aria-busy="true">
          <Skeleton className="h-7 w-64" />
          <Skeleton className="h-32 w-full" />
        </div>
      ) : query.error || !query.data ? (
        <ErrorState
          title="Receipt not found"
          error={query.error ?? new Error("Unknown")}
          onRetry={() => void query.refetch()}
        />
      ) : (
        <>
          <header className="flex items-start justify-between gap-3">
            <div>
              <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
                Receipt {query.data.id.slice(0, 8)}
              </h1>
              <p className="text-sm text-slate-500 dark:text-slate-400">Platform {query.data.portal_platform}</p>
            </div>
            <Button
              variant="primary"
              size="sm"
              onClick={sendToUnderwriter}
              leadingIcon={<Send className="h-3.5 w-3.5" />}
            >
              Send to underwriter
            </Button>
          </header>

          <Card>
            <CardHeader title="Envelope" />
            <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-3">
              <div>
                <dt className="text-xs text-slate-500 dark:text-slate-400">Submitted</dt>
                <dd>
                  <DateDisplay value={query.data.submitted_at} />
                </dd>
              </div>
              <div>
                <dt className="text-xs text-slate-500 dark:text-slate-400">Signing key</dt>
                <dd className="font-mono text-xs">{query.data.signing_key_id}</dd>
              </div>
              <div>
                <dt className="text-xs text-slate-500 dark:text-slate-400">Payload hash</dt>
                <dd className="break-all font-mono text-xs">{query.data.payload_hash}</dd>
              </div>
              <div>
                <dt className="text-xs text-slate-500 dark:text-slate-400">ToS hash</dt>
                <dd className="break-all font-mono text-xs">{query.data.tos_version_hash}</dd>
              </div>
              <div>
                <dt className="text-xs text-slate-500 dark:text-slate-400">Consent record</dt>
                <dd className="font-mono text-xs">{query.data.consent_record_id}</dd>
              </div>
            </dl>
          </Card>

          <Card>
            <CardHeader title="Share" description="Distribute the verifier link or download the signed envelope." />
            <div className="flex flex-wrap items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={copyVerifyUrl}
                leadingIcon={<Copy className="h-3.5 w-3.5" />}
              >
                Copy URL
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={emailVerifyUrl}
                leadingIcon={<Mail className="h-3.5 w-3.5" />}
              >
                Email
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={downloadJson}
                leadingIcon={<Download className="h-3.5 w-3.5" />}
              >
                Download JSON
              </Button>
              {/* TODO(qr): once `qrcode` (or a tree-shakable canvas alternative)
                  is added to the bundle, render a QR for `query.data.verify_url`
                  alongside these share actions. */}
            </div>
            <p className="mt-3 break-all rounded-md border border-slate-200 bg-slate-50 px-3 py-2 font-mono text-xs text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200">
              {query.data.verify_url}
            </p>
          </Card>

          <Card>
            <CardHeader title="Verification" />
            <ReceiptVerifierWidget receiptId={query.data.id} />
          </Card>
        </>
      )}
    </div>
  );
}
