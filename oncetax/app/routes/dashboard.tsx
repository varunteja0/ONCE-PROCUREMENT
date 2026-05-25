import type { LoaderFunctionArgs } from "@remix-run/cloudflare";
import { json } from "@remix-run/cloudflare";
import { Form, Link, useLoaderData } from "@remix-run/react";

import { getShop, getStateTotals, type StateTotalsRow } from "~/lib/d1";
import { assertRequestedShopMatchesSession, requireShopFromSession } from "~/lib/shop_session";
import { getEnv } from "~/lib/shopify";
import { SUPPORTED_STATES, type SupportedState } from "~/lib/tax_calc";

interface DashboardData {
  shop: string;
  totalsByState: StateTotalsRow[];
  supportedStates: readonly SupportedState[];
}

export async function loader({ request, context }: LoaderFunctionArgs) {
  const env = getEnv(context);
  const url = new URL(request.url);
  const shop = await requireShopFromSession(request, env);
  assertRequestedShopMatchesSession(url.searchParams.get("shop"), shop);

  const record = await getShop(env.DB, shop);
  if (!record) throw new Response("Shop not installed", { status: 404 });

  const totalsByState = await getStateTotals(env.DB, shop);
  return json<DashboardData>({
    shop,
    totalsByState,
    supportedStates: SUPPORTED_STATES,
  });
}

export default function Dashboard() {
  const data = useLoaderData<typeof loader>();

  return (
    <main className="mx-auto max-w-6xl px-6 py-12">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Dashboard</h1>
          <p className="mt-1 text-sm text-slate-600">{data.shop}</p>
        </div>
        <Link
          to="/billing"
          className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
        >
          Manage billing
        </Link>
      </div>

      <section className="mt-8 rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900">
        <strong>Not tax-of-record — filing-prep worksheets only.</strong> OnceTax is not tax, legal, or accounting
        advice and is not a substitute for a CPA or your state tax authority. Figures use state base rates only — local
        / district / special-purpose rates are not modeled in v0. You must review every figure and file directly with
        your state portal.
      </section>

      <section className="mt-8">
        <h2 className="text-xl font-semibold">Nexus &amp; taxable sales</h2>
        <p className="mt-1 text-sm text-slate-600">Supported states (v0): {data.supportedStates.join(", ")}.</p>

        <div className="mt-4 overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm">
          <table className="min-w-full divide-y divide-slate-200">
            <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wider text-slate-600">
              <tr>
                <th className="px-4 py-3">State</th>
                <th className="px-4 py-3">Orders</th>
                <th className="px-4 py-3">Taxable sales</th>
                <th className="px-4 py-3">Tax collected</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-sm">
              {data.totalsByState.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-slate-500">
                    No orders synced yet.
                  </td>
                </tr>
              ) : (
                data.totalsByState.map((row) => (
                  <tr key={row.state}>
                    <td className="px-4 py-3 font-medium">{row.state}</td>
                    <td className="px-4 py-3">{row.order_count}</td>
                    <td className="px-4 py-3">${(row.taxable_cents / 100).toFixed(2)}</td>
                    <td className="px-4 py-3">${(row.tax_cents / 100).toFixed(2)}</td>
                    <td className="px-4 py-3 text-right">
                      <Form method="post" action={`/api/calc?state=${row.state}`}>
                        <button
                          type="submit"
                          className="rounded-md bg-brand px-3 py-1.5 text-xs font-semibold text-white hover:bg-brand-dark"
                        >
                          Generate filing-prep PDF
                        </button>
                      </Form>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
