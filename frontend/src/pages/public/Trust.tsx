import { usePublicKeys } from "@/hooks/usePublicKeys";

export default function Trust(): JSX.Element {
  const { data, isLoading, isError, error, refetch } = usePublicKeys(true);

  return (
    <main className="min-h-screen bg-slate-50 px-4 py-12">
      <div className="mx-auto max-w-3xl">
        <header className="text-center">
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">Trust &amp; transparency</h1>
          <p className="mx-auto mt-3 max-w-2xl text-sm text-slate-600">
            Every submission Once makes is sealed with an Ed25519 signature over a deterministic, canonical JSON payload
            (RFC 8785). The public keys, the verifier source code, and the smoke-test results are all open &mdash; so
            customers, regulators, and E&amp;O insurers can audit Once without trusting Once.
          </p>
        </header>

        <Section title="1. Cryptographic receipts">
          <p>
            Each submission emits a <code className="rounded bg-slate-100 px-1 py-0.5">SubmissionReceipt</code>{" "}
            containing the payload hash, portal, timestamps, and a signature from one of our registered keys. Receipts
            are immutable — once signed, they cannot be mutated without invalidating the signature.
          </p>
          <p className="mt-2">
            Verify any receipt right now at{" "}
            <a href="/verify" className="font-medium text-slate-900 underline">
              /verify
            </a>
            , or call the public API directly:
          </p>
          <CodeBlock>{`curl https://getonce.com/v1/verify/<receipt_id>`}</CodeBlock>
        </Section>

        <Section title="2. Standalone verifier microservice">
          <p>
            The <code className="rounded bg-slate-100 px-1 py-0.5">verifier/</code> service is{" "}
            <a className="font-medium text-slate-900 underline" href="https://www.apache.org/licenses/LICENSE-2.0">
              Apache 2.0
            </a>
            -licensed and ships independently of the main Once codebase. It performs the same byte-for-byte Ed25519
            verification using only the published public keys — no database, no shared secrets. You can self-host it or
            run it from a regulator&rsquo;s network for fully independent audit.
          </p>
        </Section>

        <Section title="3. Published signing keys">
          <p>
            Our active signing keys are published below, on this site, and via{" "}
            <a className="underline" href="/v1/public/keys">
              <code className="rounded bg-slate-100 px-1 py-0.5">/v1/public/keys</code>
            </a>{" "}
            (JSON) and{" "}
            <a className="underline" href="/v1/public/keys.txt">
              <code className="rounded bg-slate-100 px-1 py-0.5">.txt</code>
            </a>{" "}
            (PEM blocks). The same fingerprints are also published in DNS as{" "}
            <code className="rounded bg-slate-100 px-1 py-0.5">_once-keys.getonce.com</code> TXT records, so attackers
            cannot silently swap a key without also compromising DNS.
          </p>

          <div className="mt-4">
            {isLoading ? <p className="text-sm text-slate-500">Loading keys…</p> : null}
            {isError ? (
              <div role="alert" className="rounded-md border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
                <p>Failed to load keys: {error?.message ?? "unknown error"}</p>
                <button
                  type="button"
                  onClick={() => void refetch()}
                  className="mt-2 text-sm font-medium text-rose-700 underline"
                >
                  Retry
                </button>
              </div>
            ) : null}
            {data ? (
              <ul className="space-y-3">
                {data.keys.map((key) => (
                  <li key={key.key_id} className="rounded-md border border-slate-200 bg-white p-4 shadow-sm">
                    <div className="flex items-center justify-between">
                      <code className="text-xs text-slate-700">{key.key_id}</code>
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                          key.status === "active" ? "bg-emerald-100 text-emerald-800" : "bg-slate-200 text-slate-700"
                        }`}
                      >
                        {key.status}
                      </span>
                    </div>
                    <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-all rounded bg-slate-50 p-3 text-xs text-slate-700">
                      {key.public_key_pem.trim()}
                    </pre>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        </Section>

        <Section title="4. Live coverage scorecard">
          <p>
            Carrier-portal coverage and uptime are published on the public{" "}
            <a className="font-medium text-slate-900 underline" href="/coverage">
              coverage scorecard
            </a>
            . Numbers are produced by automated smoke tests against the real portals — no marketing math.
          </p>
        </Section>

        <Section title="5. Verification links">
          <p>For one-click receipt verification from your own systems, link directly to the hosted verifier route:</p>
          <CodeBlock>{`https://getonce.com/verify/<receipt_id>`}</CodeBlock>
          <p className="mt-2 text-xs text-slate-500">
            The verifier runs as a normal HTTPS page and API endpoint. We do not ask customers to install bookmarklets
            or run injected script.
          </p>
        </Section>
      </div>
    </main>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }): JSX.Element {
  return (
    <section className="mt-10">
      <h2 className="text-xl font-semibold tracking-tight text-slate-900">{title}</h2>
      <div className="mt-3 space-y-2 text-sm leading-6 text-slate-700">{children}</div>
    </section>
  );
}

function CodeBlock({ children }: { children: React.ReactNode }): JSX.Element {
  return <pre className="mt-3 overflow-x-auto rounded-md bg-slate-900 p-3 text-xs text-slate-100">{children}</pre>;
}
