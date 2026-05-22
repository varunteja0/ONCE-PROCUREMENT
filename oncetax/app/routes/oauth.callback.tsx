import type {
  ActionFunctionArgs,
  LoaderFunctionArgs,
} from "@remix-run/cloudflare";
import { redirect } from "@remix-run/cloudflare";

import { getEnv, type OnceTaxEnv } from "~/lib/shopify";
import { exchangeCodeForToken, verifyOAuthHmac } from "~/lib/shopify";
import { upsertShop } from "~/lib/d1";

export async function loader({ request, context }: LoaderFunctionArgs) {
  const env = getEnv(context);
  const url = new URL(request.url);
  const params = url.searchParams;
  const shop = params.get("shop");
  const code = params.get("code");
  const hmac = params.get("hmac");

  if (!shop || !code || !hmac) {
    throw new Response("Missing shop, code, or hmac", { status: 400 });
  }
  if (!isValidShopDomain(shop)) {
    throw new Response("Invalid shop domain", { status: 400 });
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

  await upsertShop(env.DB, {
    shop,
    access_token: token.access_token,
    plan: "starter",
  });

  return redirect(`/dashboard?shop=${encodeURIComponent(shop)}`);
}

export async function action(_args: ActionFunctionArgs) {
  return new Response("Method Not Allowed", { status: 405 });
}

function isValidShopDomain(shop: string): boolean {
  return /^[a-zA-Z0-9][a-zA-Z0-9-]*\.myshopify\.com$/.test(shop);
}

export type _Env = OnceTaxEnv;
