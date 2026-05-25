/**
 * OnceTax cryptographic primitives (Workers runtime).
 *
 * IMPORTANT: This module is the **only** place AES-GCM and HMAC operations
 * live in OnceTax. Per `extension/AGENTS.md` rule #4 (mirrored here), routes
 * MUST NOT call ``crypto.subtle`` directly so we can audit one file.
 *
 * Bindings consumed:
 *   - ``WORKER_DATA_KEY`` — base64url-encoded 32-byte (256-bit) AES-GCM
 *     key. Set with ``wrangler secret put WORKER_DATA_KEY`` for each env.
 *     A fresh key is generated with:
 *         openssl rand -base64 32 | tr -d '=' | tr '/+' '_-'
 *   - ``SHOPIFY_API_SECRET`` — used by ``verifyShopifyWebhookHmac`` to
 *     validate ``X-Shopify-Hmac-Sha256`` on webhook requests.
 */

const ENC = new TextEncoder();
const DEC = new TextDecoder();

const AES_KEY_USAGES: KeyUsage[] = ["encrypt", "decrypt"];
const HMAC_KEY_USAGES: KeyUsage[] = ["sign"];

const IV_BYTES = 12; // 96 bits — the GCM recommended/standard size.

function base64UrlToBytes(b64url: string): Uint8Array {
  const padded = b64url
    .replace(/-/g, "+")
    .replace(/_/g, "/")
    .padEnd(Math.ceil(b64url.length / 4) * 4, "=");
  const binary = atob(padded);
  const out = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) out[i] = binary.charCodeAt(i);
  return out;
}

function bytesToBase64(bytes: Uint8Array): string {
  let binary = "";
  for (let i = 0; i < bytes.length; i += 1) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

function base64ToBytes(b64: string): Uint8Array {
  const binary = atob(b64);
  const out = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) out[i] = binary.charCodeAt(i);
  return out;
}

async function importAesKey(rawB64Url: string): Promise<CryptoKey> {
  const raw = base64UrlToBytes(rawB64Url);
  if (raw.length !== 32) {
    throw new Error("WORKER_DATA_KEY must decode to exactly 32 bytes (AES-256-GCM)");
  }
  return crypto.subtle.importKey("raw", raw as BufferSource, { name: "AES-GCM" }, false, AES_KEY_USAGES);
}

export interface SealedToken {
  /** base64 ciphertext (includes the GCM auth tag at the end). */
  ciphertext: string;
  /** base64 12-byte random IV. */
  iv: string;
}

/**
 * Encrypt a string (e.g. a Shopify access token) with AES-256-GCM.
 *
 * Returns base64-encoded ciphertext + IV so the pair can be stored as
 * two TEXT columns in D1.
 */
export async function sealString(plaintext: string, keyB64Url: string): Promise<SealedToken> {
  const key = await importAesKey(keyB64Url);
  const iv = crypto.getRandomValues(new Uint8Array(IV_BYTES));
  const ct = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, ENC.encode(plaintext));
  return {
    ciphertext: bytesToBase64(new Uint8Array(ct)),
    iv: bytesToBase64(iv),
  };
}

export async function openString(sealed: SealedToken, keyB64Url: string): Promise<string> {
  const key = await importAesKey(keyB64Url);
  const iv = base64ToBytes(sealed.iv);
  const ct = base64ToBytes(sealed.ciphertext);
  const pt = await crypto.subtle.decrypt({ name: "AES-GCM", iv: iv as BufferSource }, key, ct as BufferSource);
  return DEC.decode(pt);
}

/**
 * Constant-time string compare. Operates on UTF-16 code units, which is
 * safe for hex / base64 inputs (single-byte char set).
 */
function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i += 1) {
    diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return diff === 0;
}

/**
 * Verify a Shopify webhook ``X-Shopify-Hmac-Sha256`` header against the
 * **raw** request body. Shopify documents the algorithm at
 * https://shopify.dev/docs/apps/webhooks/configuration/https#step-5-verify-the-webhook.
 *
 * @param rawBody  The exact bytes as received; ``await request.arrayBuffer()``.
 *                 DO NOT JSON-roundtrip the body before calling — the
 *                 signature is computed over the raw bytes.
 * @param headerB64  Value of the ``X-Shopify-Hmac-Sha256`` header (base64).
 * @param secret    ``SHOPIFY_API_SECRET``.
 */
export async function verifyShopifyWebhookHmac(
  rawBody: ArrayBuffer | Uint8Array,
  headerB64: string | null,
  secret: string
): Promise<boolean> {
  if (!headerB64) return false;
  const key = await crypto.subtle.importKey(
    "raw",
    ENC.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    HMAC_KEY_USAGES
  );
  const bodyBytes = rawBody instanceof Uint8Array ? rawBody : new Uint8Array(rawBody);
  const sig = await crypto.subtle.sign("HMAC", key, bodyBytes as BufferSource);
  const expected = bytesToBase64(new Uint8Array(sig));
  return timingSafeEqual(expected, headerB64);
}

export const __test__ = {
  base64UrlToBytes,
  bytesToBase64,
  timingSafeEqual,
};
