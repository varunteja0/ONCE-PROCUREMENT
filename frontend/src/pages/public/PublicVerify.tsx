import { api, extractErrorMessage } from "@/services/api";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

interface VerifyResponse {
  receipt: {
    receipt_id: string;
    submission_id: string;
    tenant_id: string;
    portal_platform: string | null;
    submitted_at: string;
    payload_hash: string;
    signing_key_id: string;
    signature_b64: string;
  };
  verified: boolean;
  public_key_b64: string;
  reason: string | null;
}

export default function PublicVerify(): JSX.Element {
  const [receiptId, setReceiptId] = useState("");
  const verify = useMutation<VerifyResponse, Error, string>({
    mutationFn: async (id: string) => {
      const resp = await api.get<VerifyResponse>(`/verify/${encodeURIComponent(id)}`);
      return resp.data;
    },
  });

  function onSubmit(event: React.FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    const trimmed = receiptId.trim();
    if (!trimmed) return;
    verify.mutate(trimmed);
  }

  return (
    <main className="min-h-screen bg-slate-50 px-4 py-12">
      <div className="mx-auto max-w-2xl">
        <header className="text-center">
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">Verify a receipt</h1>
          <p className="mt-3 text-sm text-slate-600">
            Paste a Once receipt ID below. We&rsquo;ll re-fetch the signed payload from the canonical key registry and
            verify the Ed25519 signature byte-for-byte. No login required — anyone, anywhere, can do this.
          </p>
        </header>

        <form onSubmit={onSubmit} className="mt-8 rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
          <label htmlFor="receipt-id" className="block text-sm font-medium text-slate-700">
            Receipt ID
          </label>
          <input
            id="receipt-id"
            type="text"
            value={receiptId}
            onChange={(e) => setReceiptId(e.target.value)}
            placeholder="rcpt_..."
            spellCheck={false}
            autoComplete="off"
            className="mt-2 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 font-mono text-sm shadow-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
          />
          <button
            type="submit"
            disabled={verify.isPending || !receiptId.trim()}
            className="mt-4 inline-flex w-full justify-center rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {verify.isPending ? "Verifying…" : "Verify signature"}
          </button>
        </form>

        {verify.isError ? (
          <div role="alert" className="mt-6 rounded-md border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
            {extractErrorMessage(verify.error, "Unable to verify receipt")}
          </div>
        ) : null}

        {verify.data ? <VerifyResult data={verify.data} /> : null}

        <p className="mt-8 text-center text-xs text-slate-500">
          Prefer the API? <code className="rounded bg-slate-100 px-1.5 py-0.5">GET /v1/verify/{"{receipt_id}"}</code>{" "}
          returns the same JSON. The standalone{" "}
          <a className="underline" href="/trust">
            verifier microservice
          </a>{" "}
          (Apache-licensed) runs the math without trusting our backend.
        </p>
      </div>
    </main>
  );
}

function VerifyResult({ data }: { data: VerifyResponse }): JSX.Element {
  return (
    <section
      className={`mt-6 rounded-lg border p-6 shadow-sm ${
        data.verified ? "border-emerald-300 bg-emerald-50" : "border-rose-300 bg-rose-50"
      }`}
      aria-live="polite"
    >
      <div className="flex items-center gap-3">
        <span
          className={`inline-flex h-8 w-8 items-center justify-center rounded-full text-white ${
            data.verified ? "bg-emerald-600" : "bg-rose-600"
          }`}
          aria-hidden
        >
          {data.verified ? "✓" : "✗"}
        </span>
        <div>
          <h2 className="text-lg font-semibold text-slate-900">
            {data.verified ? "Signature valid" : "Signature invalid"}
          </h2>
          {data.reason ? <p className="text-sm text-slate-700">{data.reason}</p> : null}
        </div>
      </div>

      <dl className="mt-6 grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
        <Field label="Receipt ID" value={data.receipt.receipt_id} mono />
        <Field label="Submission ID" value={data.receipt.submission_id} mono />
        <Field label="Submitted at" value={new Date(data.receipt.submitted_at).toLocaleString()} />
        <Field label="Portal" value={data.receipt.portal_platform ?? "—"} />
        <Field label="Signing key" value={data.receipt.signing_key_id} mono />
        <Field label="Payload hash" value={data.receipt.payload_hash} mono />
      </dl>
    </section>
  );
}

function Field({ label, value, mono }: { label: string; value: string; mono?: boolean }): JSX.Element {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className={`mt-0.5 break-all text-slate-900 ${mono ? "font-mono text-xs" : ""}`}>{value}</dd>
    </div>
  );
}
