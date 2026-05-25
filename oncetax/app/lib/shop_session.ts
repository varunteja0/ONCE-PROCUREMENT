import type { OnceTaxEnv } from "./shopify";

const COOKIE_NAME = "__oncetax_shop";
const SESSION_TTL_SECONDS = 60 * 60 * 24;

function getSecret(env: OnceTaxEnv): string {
  const secret = env.SESSION_SECRET || env.SHOPIFY_API_SECRET;
  if (!secret) {
    throw new Error("SESSION_SECRET or SHOPIFY_API_SECRET is required");
  }
  return secret;
}

async function hmacHex(message: string, secret: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const signature = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(message));
  return Array.from(new Uint8Array(signature))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

function timingSafeEqual(left: string, right: string): boolean {
  if (left.length !== right.length) return false;
  let diff = 0;
  for (let index = 0; index < left.length; index += 1) {
    diff |= left.charCodeAt(index) ^ right.charCodeAt(index);
  }
  return diff === 0;
}

function cookieValue(request: Request, name: string): string | null {
  const header = request.headers.get("Cookie");
  if (!header) return null;
  for (const part of header.split(";")) {
    const [rawKey, ...rawValue] = part.trim().split("=");
    if (rawKey === name) return rawValue.join("=");
  }
  return null;
}

export function isValidShopDomain(shop: string): boolean {
  return /^[a-zA-Z0-9][a-zA-Z0-9-]*\.myshopify\.com$/.test(shop);
}

export async function createShopSessionCookie(shop: string, env: OnceTaxEnv): Promise<string> {
  if (!isValidShopDomain(shop)) {
    throw new Error("invalid shop domain");
  }
  const issuedAt = Math.floor(Date.now() / 1000);
  const payload = `${shop}.${issuedAt}`;
  const signature = await hmacHex(payload, getSecret(env));
  const secure = env.APP_URL.startsWith("https://") ? "; Secure" : "";
  return `${COOKIE_NAME}=${encodeURIComponent(
    `${payload}.${signature}`
  )}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${SESSION_TTL_SECONDS}${secure}`;
}

export async function requireShopFromSession(request: Request, env: OnceTaxEnv): Promise<string> {
  const raw = cookieValue(request, COOKIE_NAME);
  if (!raw) {
    throw new Response("Missing shop session", { status: 401 });
  }
  const decoded = decodeURIComponent(raw);
  const parts = decoded.split(".");
  if (parts.length < 4) {
    throw new Response("Invalid shop session", { status: 401 });
  }
  const signature = parts.pop() ?? "";
  const issuedAtRaw = parts.pop() ?? "";
  const shop = parts.join(".");
  if (!isValidShopDomain(shop)) {
    throw new Response("Invalid shop session", { status: 401 });
  }
  const issuedAt = Number(issuedAtRaw);
  if (!Number.isFinite(issuedAt)) {
    throw new Response("Invalid shop session", { status: 401 });
  }
  const ageSeconds = Math.floor(Date.now() / 1000) - issuedAt;
  if (ageSeconds < 0 || ageSeconds > SESSION_TTL_SECONDS) {
    throw new Response("Expired shop session", { status: 401 });
  }
  const payload = `${shop}.${issuedAtRaw}`;
  const expected = await hmacHex(payload, getSecret(env));
  if (!timingSafeEqual(expected, signature)) {
    throw new Response("Invalid shop session", { status: 401 });
  }
  return shop;
}

export function assertRequestedShopMatchesSession(requestedShop: string | null, sessionShop: string): void {
  if (requestedShop && requestedShop !== sessionShop) {
    throw new Response("Shop session mismatch", { status: 403 });
  }
}
