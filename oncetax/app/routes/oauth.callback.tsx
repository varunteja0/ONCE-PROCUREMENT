import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/cloudflare";
import { redirect } from "@remix-run/cloudflare";

import { upsertShop } from "~/lib/d1";
import { createShopSessionCookie, isValidShopDomain } from "~/lib/shop_session";
import {
  ShopifyAdminClient,
  exchangeCodeForToken,
  getEnv,
  registerMandatoryWebhooks,
  verifyOAuthHmac,
  type OnceTaxEnv,
} from "~/lib/shopify";

const STATE_KV_PREFIX = "oauth_state:";

export async function loader({ request, context }: LoaderFunctionArgs) {
  const env = getEnv(context);
  const url = new URL(request.url);
  const params = url.searchParams;
  const shop = params.get("shop");
  const code = params.get("code");
  const hmac = params.get("hmac");
  const state = params.get("state");

  if (!shop || !code || !hmac || !state) {
    throw new Response("Missing shop, code, hmac, or state", { status: 400 });
  }
  if (!isValidShopDomain(shop)) {
    throw new Response("Invalid shop domain", { status: 400 });
  }

  // CSRF protection: state must have been issued by /auth/shopify within
  // the last 10 minutes, and must reference the same shop being installed.
  // We delete the KV entry on use so the URL is single-shot \u2014 a leaked
  // callback URL replays as 401.
  const stateKey = STATE_KV_PREFIX + state;
  const issuedForShop = await env.SESSIONS.get(stateKey);
  if (!issuedForShop || issuedForShop !== shop) {
    throw new Response("Invalid or expired OAuth state", { status: 401 });
  }

  if (!env.WORKER_DATA_KEY) {
    // Fail closed if at-rest encryption isn't configured \u2014 we don't want
    // to silently persist a plaintext access token.
    throw new Response("Server misconfigured: missing WORKER_DATA_KEY", {
      status: 500,
    });
  }

  const hmacOk = await verifyOAuthHmac(params, env.SHOPIFY_API_SECRET);
  if (!hmacOk) {
    throw new Response("HMAC verification failed", { status: 401 });
  }

  const token = await exchangeCodeForToken({
    shop,
    code,
    apiKey: env.SHOPIFY_API_KEY,
    apiSecret: env.SHOPIFY_API_SECRET,
  });

  await upsertShop(
    env.DB,
    {
      shop,
      access_token: token.access_token,
      plan: "starter",
    },
    env.WORKER_DATA_KEY
  );

  await registerMandatoryWebhooks(new ShopifyAdminClient(shop, token.access_token), env.APP_URL);

  await env.SESSIONS.delete(stateKey);

  return redirect("/dashboard", {
    headers: {
      "Set-Cookie": await createShopSessionCookie(shop, env),
    },
  });
}

export async function action(_args: ActionFunctionArgs) {
  return new Response("Method Not Allowed", { status: 405 });
}

export type _Env = OnceTaxEnv;
