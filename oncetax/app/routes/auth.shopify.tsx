/**
 * Shopify install entry point: ``GET /auth/shopify?shop=foo.myshopify.com``.
 *
 * Generates a single-use OAuth ``state`` token, stashes it in KV with a
 * 10-minute TTL, and redirects the merchant into Shopify's
 * ``/admin/oauth/authorize`` flow. The callback (``/oauth/callback``) is
 * required to present the same ``state`` and we delete the KV entry on
 * use \u2014 so a stolen / replayed callback URL is a 401.
 *
 * Without this round-trip an attacker could craft a Shopify callback URL
 * that installs the app against the victim's shop (CSRF).
 */

import type { LoaderFunctionArgs } from "@remix-run/cloudflare";
import { redirect } from "@remix-run/cloudflare";

import { buildInstallUrl, getEnv } from "~/lib/shopify";

const STATE_TTL_SECONDS = 10 * 60;
const STATE_KV_PREFIX = "oauth_state:";

function isValidShopDomain(shop: string): boolean {
  return /^[a-zA-Z0-9][a-zA-Z0-9-]*\.myshopify\.com$/.test(shop);
}

function generateState(): string {
  // 32 bytes of CSPRNG output → 64 hex chars; unguessable.
  const bytes = crypto.getRandomValues(new Uint8Array(32));
  let hex = "";
  for (let i = 0; i < bytes.length; i += 1) {
    hex += bytes[i].toString(16).padStart(2, "0");
  }
  return hex;
}

export async function loader({ request, context }: LoaderFunctionArgs) {
  const env = getEnv(context);
  const url = new URL(request.url);
  const shop = url.searchParams.get("shop");

  if (!shop || !isValidShopDomain(shop)) {
    throw new Response("Invalid or missing shop parameter", { status: 400 });
  }

  const state = generateState();
  // KV value carries the shop so the callback can confirm the state was
  // issued for the same shop it was presented with.
  await env.SESSIONS.put(STATE_KV_PREFIX + state, shop, {
    expirationTtl: STATE_TTL_SECONDS,
  });

  const redirectUri = `${env.APP_URL.replace(/\/$/, "")}/oauth/callback`;
  const installUrl = buildInstallUrl({
    shop,
    apiKey: env.SHOPIFY_API_KEY,
    scopes: env.SCOPES,
    redirectUri,
    state,
  });

  return redirect(installUrl);
}

export const __test__ = { generateState, STATE_KV_PREFIX, STATE_TTL_SECONDS };
