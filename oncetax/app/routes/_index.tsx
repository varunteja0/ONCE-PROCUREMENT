import type { MetaFunction } from "@remix-run/cloudflare";
import { Link } from "@remix-run/react";

export const meta: MetaFunction = () => [
  { title: "OnceTax — Sales tax filing prep for Shopify" },
  {
    name: "description",
    content:
      "Generate filing-prep PDFs per state from your Shopify orders. $79/mo + $19/state.",
  },
];

export default function Index() {
  return (
    <main className="mx-auto max-w-5xl px-6 py-16">
      <header className="mb-12">
        <p className="text-sm font-semibold uppercase tracking-widest text-brand">
          OnceTax
        </p>
        <h1 className="mt-2 text-4xl font-bold tracking-tight sm:text-5xl">
          Sales tax filing prep for Shopify
        </h1>
        <p className="mt-4 max-w-2xl text-lg text-slate-600">
          We turn your Shopify orders into clean, state-by-state filing-prep
          PDFs. You stay in control — review, then file with your state portal
          yourself.
        </p>

        <div className="mt-8 flex flex-wrap items-center gap-4">
          <Link
            to="/auth/shopify"
            className="inline-flex items-center rounded-md bg-brand px-5 py-3 text-base font-semibold text-white shadow-sm hover:bg-brand-dark"
          >
            Install on Shopify
          </Link>
          <Link
            to="/dashboard"
            className="inline-flex items-center rounded-md border border-slate-300 bg-white px-5 py-3 text-base font-semibold text-slate-700 hover:bg-slate-100"
          >
            Open dashboard
          </Link>
        </div>
      </header>

      <section className="grid gap-8 sm:grid-cols-3">
        <Card title="$79/mo base">
          Includes nexus map, orders sync, and filing-prep PDFs for your first
          state.
        </Card>
        <Card title="$19 per extra state">
          Add states as your nexus grows. CA, TX, NY, FL, WA supported in v0.
        </Card>
        <Card title="No auto-filing — yet">
          We generate the numbers and the PDF. You file with your state. We
          never submit on your behalf in v0.
        </Card>
      </section>

      <section className="mt-16 rounded-lg border border-amber-300 bg-amber-50 p-6 text-sm text-amber-900">
        <p className="font-semibold">v0 limitation</p>
        <p className="mt-1">
          OnceTax v0 supports state-level base rates only (CA, TX, NY, FL, WA).
          Local / district rates are not modeled yet. PDFs are filing-prep
          worksheets — not state-portal submissions.
        </p>
      </section>
    </main>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
      <h3 className="text-lg font-semibold text-slate-900">{title}</h3>
      <p className="mt-2 text-sm text-slate-600">{children}</p>
    </div>
  );
}
