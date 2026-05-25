/**
 * Mandatory Shopify webhook: ``app/uninstalled``.
 *
 * Fires when a merchant uninstalls OnceTax. We delete the encrypted
 * access token and any session state for the shop. We do NOT immediately
 * purge orders_cache or filings \u2014 those belong to the merchant's
 * historical record and are removed by ``shop/redact`` 48h later.
 */

import type { ActionFunctionArgs } from "@remix-run/cloudflare";

import { verifyShopifyWebhookHmac } from "~/lib/crypto";
import { getEnv } from "~/lib/shopify";

const SHOPIFY_HMAC_HEADER = "x-shopify-hmac-sha256";

interface UninstallPayload {
  domain?: string;
  myshopify_domain?: string;
}

export async function action({ request, context }: ActionFunctionArgs) {
  if (request.method !== "POST") {
    return new Response("Method Not Allowed", { status: 405 });
  }
  const env = getEnv(context);

  // MUST read raw bytes BEFORE parsing JSON \u2014 the HMAC is computed over
  // the wire bytes, not a re-serialised object.
  const raw = await request.arrayBuffer();
  const hmacHeader = request.headers.get(SHOPIFY_HMAC_HEADER);
  const ok = await verifyShopifyWebhookHmac(raw, hmacHeader, env.SHOPIFY_API_SECRET);
  if (!ok) {
    return new Response("Invalid HMAC", { status: 401 });
  }

  let payload: UninstallPayload;
  try {
    payload = JSON.parse(new TextDecoder().decode(raw)) as UninstallPayload;
  } catch {
    return new Response("Invalid JSON", { status: 400 });
  }
  const shop = payload.myshopify_domain ?? payload.domain;
  if (!shop) {
    return new Response("Missing shop in payload", { status: 400 });
  }

  await env.DB.prepare(`DELETE FROM shops WHERE shop = ?1`).bind(shop).run();

  return new Response(null, { status: 204 });
}

export function loader() {
  return new Response("Method Not Allowed", { status: 405 });
}
