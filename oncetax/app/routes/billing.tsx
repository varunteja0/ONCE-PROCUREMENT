import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/cloudflare";
import { json, redirect } from "@remix-run/cloudflare";
import { Form, useLoaderData } from "@remix-run/react";

import { getEnv } from "~/lib/shopify";
import { getShop } from "~/lib/d1";

const BASE_PRICE_USD = 79;
const PER_STATE_PRICE_USD = 19;

interface BillingLoaderData {
  shop: string;
  basePriceUsd: number;
  perStatePriceUsd: number;
  currentPlan: string | null;
}

export async function loader({ request, context }: LoaderFunctionArgs) {
  const env = getEnv(context);
  const url = new URL(request.url);
  const shop = url.searchParams.get("shop");
  if (!shop) throw new Response("Missing shop", { status: 400 });

  const record = await getShop(env.DB, shop);
  if (!record) throw new Response("Shop not installed", { status: 404 });

  return json<BillingLoaderData>({
    shop,
    basePriceUsd: BASE_PRICE_USD,
    perStatePriceUsd: PER_STATE_PRICE_USD,
    currentPlan: record.plan,
  });
}

export async function action({ request, context }: ActionFunctionArgs) {
  const env = getEnv(context);
  const form = await request.formData();
  const shop = String(form.get("shop") ?? "");
  const states = Number(form.get("states") ?? 1);
  if (!shop) throw new Response("Missing shop", { status: 400 });

  const record = await getShop(env.DB, shop);
  if (!record) throw new Response("Shop not installed", { status: 404 });

  const extraStates = Math.max(0, states - 1);
  const totalUsd = BASE_PRICE_USD + extraStates * PER_STATE_PRICE_USD;

  const mutation = `
    mutation appSubscriptionCreate(
      $name: String!
      $returnUrl: URL!
      $lineItems: [AppSubscriptionLineItemInput!]!
      $test: Boolean
    ) {
      appSubscriptionCreate(
        name: $name
        returnUrl: $returnUrl
        lineItems: $lineItems
        test: $test
      ) {
        userErrors { field message }
        confirmationUrl
        appSubscription { id status }
      }
    }
  `;

  const variables = {
    name: `OnceTax — ${states} state${states === 1 ? "" : "s"}`,
    returnUrl: `${env.APP_URL}/dashboard?shop=${encodeURIComponent(shop)}`,
    test: env.APP_URL.includes("localhost") || env.APP_URL.includes("ngrok"),
    lineItems: [
      {
        plan: {
          appRecurringPricingDetails: {
            price: { amount: totalUsd.toFixed(2), currencyCode: "USD" },
            interval: "EVERY_30_DAYS",
          },
        },
      },
    ],
  };

  const resp = await fetch(
    `https://${shop}/admin/api/2024-10/graphql.json`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": record.access_token,
      },
      body: JSON.stringify({ query: mutation, variables }),
    },
  );

  if (!resp.ok) {
    throw new Response(`Shopify billing API failed: ${resp.status}`, {
      status: 502,
    });
  }

  const body = (await resp.json()) as {
    data?: {
      appSubscriptionCreate?: {
        userErrors: { field: string[]; message: string }[];
        confirmationUrl: string | null;
      };
    };
  };

  const result = body.data?.appSubscriptionCreate;
  if (!result || result.userErrors.length > 0) {
    throw new Response(
      JSON.stringify(result?.userErrors ?? "Unknown billing error"),
      { status: 502 },
    );
  }
  if (!result.confirmationUrl) {
    throw new Response("Missing confirmationUrl", { status: 502 });
  }
  return redirect(result.confirmationUrl);
}

export default function Billing() {
  const data = useLoaderData<typeof loader>();
  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <h1 className="text-3xl font-bold">Billing</h1>
      <p className="mt-2 text-slate-600">
        ${data.basePriceUsd}/mo base + ${data.perStatePriceUsd} per additional
        state. Billed via Shopify Subscription Billing.
      </p>

      <Form method="post" className="mt-8 space-y-6 rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <input type="hidden" name="shop" value={data.shop} />
        <label className="block">
          <span className="text-sm font-medium text-slate-700">
            Number of states
          </span>
          <input
            type="number"
            name="states"
            min={1}
            max={5}
            defaultValue={1}
            className="mt-2 block w-32 rounded-md border-slate-300 shadow-sm focus:border-brand focus:ring-brand"
          />
        </label>
        <button
          type="submit"
          className="rounded-md bg-brand px-5 py-3 text-base font-semibold text-white shadow-sm hover:bg-brand-dark"
        >
          Subscribe via Shopify
        </button>
      </Form>

      <p className="mt-6 text-xs text-slate-500">
        Reminder: OnceTax v0 does not auto-file to state portals. We generate
        filing-prep PDFs you submit yourself.
      </p>
    </main>
  );
}
