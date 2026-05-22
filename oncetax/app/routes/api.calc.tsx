import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/cloudflare";
import { json } from "@remix-run/cloudflare";
import { z } from "zod";

import { getEnv } from "~/lib/shopify";
import {
  getShop,
  insertFiling,
  upsertOrderCache,
  type OrderCacheRow,
} from "~/lib/d1";
import {
  calcForOrder,
  isSupportedState,
  SUPPORTED_STATES,
  type SupportedState,
} from "~/lib/tax_calc";
import { buildFilingPrepPdf } from "~/lib/pdf";

const OrderLineSchema = z.object({
  id: z.string(),
  state: z.string().length(2),
  subtotal_cents: z.number().int().nonnegative(),
  taxable_cents: z.number().int().nonnegative().optional(),
  exempt_cents: z.number().int().nonnegative().optional(),
  captured_at: z.number().int().nonnegative(),
});

const RequestSchema = z.object({
  shop: z.string().min(1),
  period_start: z.string(),
  period_end: z.string(),
  orders: z.array(OrderLineSchema),
});

export async function loader({ request, context }: LoaderFunctionArgs) {
  const env = getEnv(context);
  const url = new URL(request.url);
  const shop = url.searchParams.get("shop");
  const state = url.searchParams.get("state");

  if (!shop || !state) {
    return json({ error: "Missing shop or state" }, { status: 400 });
  }
  if (!isSupportedState(state)) {
    return json(
      { error: `Unsupported state ${state}. v0 supports: ${SUPPORTED_STATES.join(", ")}` },
      { status: 400 },
    );
  }

  const record = await getShop(env.DB, shop);
  if (!record) return json({ error: "Shop not installed" }, { status: 404 });

  return json({ ok: true, shop, state });
}

export async function action({ request, context }: ActionFunctionArgs) {
  const env = getEnv(context);
  const url = new URL(request.url);

  if (url.searchParams.has("state")) {
    return generatePdfAction({ env, url });
  }

  const body = await request.json().catch(() => null);
  const parsed = RequestSchema.safeParse(body);
  if (!parsed.success) {
    return json({ error: parsed.error.flatten() }, { status: 422 });
  }

  const totals = new Map<
    SupportedState,
    { order_count: number; taxable_cents: number; tax_cents: number; exempt_cents: number }
  >();

  for (const order of parsed.data.orders) {
    if (!isSupportedState(order.state)) continue;
    const calc = calcForOrder(
      {
        subtotal_cents: order.subtotal_cents,
        taxable_cents: order.taxable_cents,
        exempt_cents: order.exempt_cents,
      },
      order.state,
    );

    await upsertOrderCache(env.DB, {
      id: `${parsed.data.shop}:${order.id}`,
      shop: parsed.data.shop,
      order_id: order.id,
      state: order.state,
      taxable_cents: calc.taxable_cents,
      tax_cents: calc.tax_due_cents,
      captured_at: order.captured_at,
    });

    const prior =
      totals.get(order.state) ?? {
        order_count: 0,
        taxable_cents: 0,
        tax_cents: 0,
        exempt_cents: 0,
      };
    totals.set(order.state, {
      order_count: prior.order_count + 1,
      taxable_cents: prior.taxable_cents + calc.taxable_cents,
      tax_cents: prior.tax_cents + calc.tax_due_cents,
      exempt_cents: prior.exempt_cents + calc.exempt_cents,
    });
  }

  return json({
    ok: true,
    period_start: parsed.data.period_start,
    period_end: parsed.data.period_end,
    totals: Object.fromEntries(totals),
  });
}

async function generatePdfAction({
  env,
  url,
}: {
  env: ReturnType<typeof getEnv>;
  url: URL;
}): Promise<Response> {
  if (env.ENABLE_PDF_GENERATION !== "true") {
    return json(
      {
        error: "PDF generation disabled in this environment",
        hint: "Set ENABLE_PDF_GENERATION=\"true\" in wrangler.toml [vars] to enable.",
      },
      { status: 503 },
    );
  }

  const shop = url.searchParams.get("shop");
  const state = url.searchParams.get("state");
  if (!shop || !state || !isSupportedState(state)) {
    return json({ error: "Missing or invalid shop/state" }, { status: 400 });
  }
  const record = await getShop(env.DB, shop);
  if (!record) return json({ error: "Shop not installed" }, { status: 404 });

  const periodEnd = new Date();
  const periodStart = new Date(
    Date.UTC(periodEnd.getUTCFullYear(), periodEnd.getUTCMonth(), 1),
  );

  const rows = (await env.DB.prepare(
    `SELECT taxable_cents, tax_cents FROM orders_cache
     WHERE shop = ?1 AND state = ?2
       AND captured_at >= ?3 AND captured_at < ?4`,
  )
    .bind(
      shop,
      state,
      Math.floor(periodStart.getTime() / 1000),
      Math.floor(periodEnd.getTime() / 1000) + 1,
    )
    .all<OrderCacheRow>()).results;

  const totals = rows.reduce(
    (acc, r) => {
      acc.taxable_cents += r.taxable_cents;
      acc.tax_cents += r.tax_cents;
      return acc;
    },
    { taxable_cents: 0, tax_cents: 0 },
  );

  const pdfBytes = await buildFilingPrepPdf({
    shop,
    state,
    period_start: periodStart.toISOString().slice(0, 10),
    period_end: periodEnd.toISOString().slice(0, 10),
    gross_sales_cents: totals.taxable_cents,
    taxable_cents: totals.taxable_cents,
    tax_due_cents: totals.tax_cents,
  });

  const r2Key = `filings/${shop}/${state}/${periodStart
    .toISOString()
    .slice(0, 7)}.pdf`;
  await env.PDF_BUCKET.put(r2Key, pdfBytes, {
    httpMetadata: { contentType: "application/pdf" },
  });

  const filingId = crypto.randomUUID();
  await insertFiling(env.DB, {
    id: filingId,
    shop,
    state,
    period_start: periodStart.toISOString().slice(0, 10),
    period_end: periodEnd.toISOString().slice(0, 10),
    pdf_r2_key: r2Key,
  });

  return json({ ok: true, filing_id: filingId, r2_key: r2Key });
}
