/**
 * Mandatory Shopify GDPR webhook: ``customers/data_request``.
 *
 * OnceTax does NOT store any customer PII \u2014 we only persist per-state
 * aggregate totals in ``orders_cache`` (state code + cents amounts; no
 * names, emails, addresses). Therefore we have no customer-scoped data
 * to return.
 *
 * We still validate HMAC and respond 200 OK so Shopify marks the
 * webhook delivery successful. Failing to acknowledge results in app
 * rejection during review.
 */

import type { ActionFunctionArgs } from "@remix-run/cloudflare";

import { verifyShopifyWebhookHmac } from "~/lib/crypto";
import { getEnv } from "~/lib/shopify";

const SHOPIFY_HMAC_HEADER = "x-shopify-hmac-sha256";

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
  // No customer data stored \u2014 acknowledge.
  return new Response(null, { status: 200 });
}

export function loader() {
  return new Response("Method Not Allowed", { status: 405 });
}
