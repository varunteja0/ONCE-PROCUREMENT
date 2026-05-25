import type { AppLoadContext } from "@remix-run/cloudflare";

export interface OnceTaxEnv {
  DB: D1Database;
  PDF_BUCKET: R2Bucket;
  SESSIONS: KVNamespace;
  SHOPIFY_API_KEY: string;
  SHOPIFY_API_SECRET: string;
  APP_URL: string;
  SCOPES: string;
  RESEND_API_KEY: string;
  /** AES-256-GCM key for at-rest encryption of Shopify access tokens.
   *  base64url-encoded 32 bytes. Set with `wrangler secret put WORKER_DATA_KEY`.
   *  Optional at boot so dev/test environments without the secret still
   *  start; routes that touch ciphertext fail-closed if it's missing. */
  WORKER_DATA_KEY?: string;
  // Phase 1 feature flags — string "true"/"false" because Workers env vars
  // are always strings.
  ENABLE_PDF_GENERATION?: string;
  WEDGE_MODE?: string;
  // Optional secrets — declared so TS allows reading them; not required at boot.
  SESSION_SECRET?: string;
  TAXJAR_API_KEY?: string;
}

export function getEnv(context: AppLoadContext): OnceTaxEnv {
  const env =
    (context as { cloudflare?: { env?: unknown }; env?: unknown }).cloudflare?.env ??
    (context as { env?: unknown }).env;
  if (!env || typeof env !== "object") {
    throw new Error("Cloudflare bindings not present on load context");
  }
  return env as OnceTaxEnv;
}

export function buildInstallUrl({
  shop,
  apiKey,
  scopes,
  redirectUri,
  state,
}: {
  shop: string;
  apiKey: string;
  scopes: string;
  redirectUri: string;
  state: string;
}): string {
  const params = new URLSearchParams({
    client_id: apiKey,
    scope: scopes,
    redirect_uri: redirectUri,
    state,
  });
  return `https://${shop}/admin/oauth/authorize?${params.toString()}`;
}

export async function verifyOAuthHmac(params: URLSearchParams, secret: string): Promise<boolean> {
  const incoming = params.get("hmac");
  if (!incoming) return false;

  const entries: [string, string][] = [];
  params.forEach((value, key) => {
    if (key === "hmac" || key === "signature") return;
    entries.push([key, value]);
  });
  entries.sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0));
  const message = entries.map(([k, v]) => `${k}=${v}`).join("&");

  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(message));
  const expected = Array.from(new Uint8Array(sig))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");

  return timingSafeEqual(expected, incoming.toLowerCase());
}

function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i += 1) {
    diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return diff === 0;
}

export interface TokenExchangeResult {
  access_token: string;
  scope: string;
}

export async function exchangeCodeForToken({
  shop,
  code,
  apiKey,
  apiSecret,
}: {
  shop: string;
  code: string;
  apiKey: string;
  apiSecret: string;
}): Promise<TokenExchangeResult> {
  const resp = await fetch(`https://${shop}/admin/oauth/access_token`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      client_id: apiKey,
      client_secret: apiSecret,
      code,
    }),
  });
  if (!resp.ok) {
    throw new Error(`Token exchange failed: ${resp.status}`);
  }
  const data = (await resp.json()) as Partial<TokenExchangeResult>;
  if (!data.access_token) {
    throw new Error("Token exchange response missing access_token");
  }
  return { access_token: data.access_token, scope: data.scope ?? "" };
}

export class ShopifyAdminClient {
  constructor(
    private readonly shop: string,
    private readonly accessToken: string,
    private readonly apiVersion = "2024-10"
  ) {}

  async graphql<T>(query: string, variables?: Record<string, unknown>): Promise<T> {
    const resp = await fetch(`https://${this.shop}/admin/api/${this.apiVersion}/graphql.json`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": this.accessToken,
      },
      body: JSON.stringify({ query, variables }),
    });
    if (!resp.ok) {
      throw new Error(`Shopify Admin GraphQL failed: ${resp.status}`);
    }
    const body = (await resp.json()) as { data?: T; errors?: unknown };
    if (body.errors) {
      throw new Error(`Shopify GraphQL errors: ${JSON.stringify(body.errors)}`);
    }
    if (!body.data) {
      throw new Error("Shopify GraphQL: empty data");
    }
    return body.data;
  }
}

interface WebhookSubscriptionCreateResult {
  webhookSubscriptionCreate?: {
    userErrors: { field: string[] | null; message: string }[];
    webhookSubscription: { id: string } | null;
  };
}

const MANDATORY_WEBHOOKS: readonly { topic: string; path: string }[] = [
  { topic: "APP_UNINSTALLED", path: "/webhooks/shopify/app-uninstalled" },
  { topic: "CUSTOMERS_DATA_REQUEST", path: "/webhooks/shopify/customers-data-request" },
  { topic: "CUSTOMERS_REDACT", path: "/webhooks/shopify/customers-redact" },
  { topic: "SHOP_REDACT", path: "/webhooks/shopify/shop-redact" },
];

export async function registerMandatoryWebhooks(client: ShopifyAdminClient, appUrl: string): Promise<void> {
  const mutation = `
    mutation webhookSubscriptionCreate(
      $topic: WebhookSubscriptionTopic!
      $callbackUrl: URL!
    ) {
      webhookSubscriptionCreate(
        topic: $topic
        webhookSubscription: { callbackUrl: $callbackUrl, format: JSON }
      ) {
        userErrors { field message }
        webhookSubscription { id }
      }
    }
  `;

  for (const webhook of MANDATORY_WEBHOOKS) {
    const data = await client.graphql<WebhookSubscriptionCreateResult>(mutation, {
      topic: webhook.topic,
      callbackUrl: `${appUrl.replace(/\/+$/, "")}${webhook.path}`,
    });
    const result = data.webhookSubscriptionCreate;
    if (!result || result.userErrors.length > 0) {
      throw new Error(
        `Webhook registration failed for ${webhook.topic}: ${JSON.stringify(result?.userErrors ?? "empty response")}`
      );
    }
  }
}
