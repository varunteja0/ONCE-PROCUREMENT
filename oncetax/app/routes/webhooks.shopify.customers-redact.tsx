/**
 * Mandatory Shopify GDPR webhook: ``customers/redact``.
 *
 * OnceTax stores no customer PII (see customers-data-request route).
 * We still acknowledge the request so Shopify marks delivery successful.
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
  return new Response(null, { status: 200 });
}

export function loader() {
  return new Response("Method Not Allowed", { status: 405 });
}
