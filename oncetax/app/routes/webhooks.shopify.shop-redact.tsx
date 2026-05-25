/**
 * Mandatory Shopify GDPR webhook: ``shop/redact``.
 *
 * Fires 48h after app uninstall. We delete every row tied to the shop:
 *   - shops          (already gone via app/uninstalled, but defensive)
 *   - orders_cache
 *   - filings
 *
 * R2 PDF artefacts referenced by ``filings.pdf_r2_key`` must be deleted
 * before DB rows are removed. If R2 is unavailable we return 500 so Shopify
 * retries instead of orphaning objects with their DB pointers gone.
 */

import type { ActionFunctionArgs } from "@remix-run/cloudflare";

import { verifyShopifyWebhookHmac } from "~/lib/crypto";
import { getEnv } from "~/lib/shopify";

const SHOPIFY_HMAC_HEADER = "x-shopify-hmac-sha256";

interface ShopRedactPayload {
  shop_domain?: string;
  myshopify_domain?: string;
}

export async function action({ request, context }: ActionFunctionArgs) {
  if (request.method !== "POST") {
    return new Response("Method Not Allowed", { status: 405 });
  }
  const env = getEnv(context);
  const raw = await request.arrayBuffer();
  const ok = await verifyShopifyWebhookHmac(raw, request.headers.get(SHOPIFY_HMAC_HEADER), env.SHOPIFY_API_SECRET);
  if (!ok) {
    return new Response("Invalid HMAC", { status: 401 });
  }

  let payload: ShopRedactPayload;
  try {
    payload = JSON.parse(new TextDecoder().decode(raw)) as ShopRedactPayload;
  } catch {
    return new Response("Invalid JSON", { status: 400 });
  }
  const shop = payload.myshopify_domain ?? payload.shop_domain;
  if (!shop) {
    return new Response("Missing shop in payload", { status: 400 });
  }

  // Collect R2 keys for best-effort delete BEFORE we drop the rows.
  const filings = await env.DB.prepare(`SELECT pdf_r2_key FROM filings WHERE shop = ?1`)
    .bind(shop)
    .all<{ pdf_r2_key: string }>();
  for (const row of filings.results ?? []) {
    if (row.pdf_r2_key) {
      try {
        await env.PDF_BUCKET.delete(row.pdf_r2_key);
      } catch {
        return new Response("R2 deletion failed; retry required", { status: 500 });
      }
    }
  }

  await env.DB.batch([
    env.DB.prepare(`DELETE FROM filings WHERE shop = ?1`).bind(shop),
    env.DB.prepare(`DELETE FROM orders_cache WHERE shop = ?1`).bind(shop),
    env.DB.prepare(`DELETE FROM shops WHERE shop = ?1`).bind(shop),
  ]);

  return new Response(null, { status: 200 });
}

export function loader() {
  return new Response("Method Not Allowed", { status: 405 });
}
