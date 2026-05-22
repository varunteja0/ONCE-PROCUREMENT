/**
 * WebCrypto wrappers — PBKDF2(SHA-256, 310k iters) → AES-GCM-256.
 *
 * All operations go through `window.crypto.subtle`. The 310k iteration
 * count matches OWASP's 2023 PBKDF2-SHA256 recommendation and the value
 * recorded in `CONTRACTS.md` §10.
 */

export const PBKDF2_ITERATIONS = 310_000 as const;
export const PBKDF2_HASH = "SHA-256" as const;
export const AES_KEY_BITS = 256 as const;
export const AES_IV_BYTES = 12 as const;
export const SALT_BYTES = 16 as const;

export interface AesGcmCiphertext {
  iv: Uint8Array;
  ct: Uint8Array;
}

function subtle(): SubtleCrypto {
  const c =
    typeof globalThis !== "undefined" ? globalThis.crypto : undefined;
  if (!c || !c.subtle) {
    throw new Error("crypto.subtle is unavailable in this environment");
  }
  return c.subtle;
}

/**
 * Fill `n` cryptographically-random bytes.
 */
export function randomBytes(n: number): Uint8Array {
  if (!Number.isInteger(n) || n <= 0) {
    throw new RangeError("randomBytes: n must be a positive integer");
  }
  const out = new Uint8Array(n);
  const c = typeof globalThis !== "undefined" ? globalThis.crypto : undefined;
  if (!c) {
    throw new Error("crypto is unavailable in this environment");
  }
  c.getRandomValues(out);
  return out;
}

/**
 * Derive a non-extractable AES-GCM-256 key from `passphrase` and `salt`.
 *
 * @param passphrase UTF-8 passphrase entered by the user.
 * @param salt       Per-vault random salt (≥ 16 bytes, persisted alongside
 *                   the vault metadata).
 */
export async function deriveKey(
  passphrase: string,
  salt: Uint8Array,
): Promise<CryptoKey> {
  if (typeof passphrase !== "string" || passphrase.length === 0) {
    throw new Error("deriveKey: passphrase must be a non-empty string");
  }
  if (!(salt instanceof Uint8Array) || salt.byteLength < 8) {
    throw new Error("deriveKey: salt must be a Uint8Array of ≥ 8 bytes");
  }

  const s = subtle();
  const enc = new TextEncoder();
  const baseKey = await s.importKey(
    "raw",
    enc.encode(passphrase),
    { name: "PBKDF2" },
    false,
    ["deriveKey"],
  );

  return s.deriveKey(
    {
      name: "PBKDF2",
      salt: salt as BufferSource,
      iterations: PBKDF2_ITERATIONS,
      hash: PBKDF2_HASH,
    },
    baseKey,
    { name: "AES-GCM", length: AES_KEY_BITS },
    false,
    ["encrypt", "decrypt"],
  );
}

/**
 * Encrypt `plaintext` under `key`. Generates a fresh 12-byte IV per call.
 */
export async function encrypt(
  key: CryptoKey,
  plaintext: Uint8Array,
): Promise<AesGcmCiphertext> {
  if (!(plaintext instanceof Uint8Array)) {
    throw new TypeError("encrypt: plaintext must be a Uint8Array");
  }
  const iv = randomBytes(AES_IV_BYTES);
  const ctBuf = await subtle().encrypt(
    { name: "AES-GCM", iv: iv as BufferSource },
    key,
    plaintext as BufferSource,
  );
  return { iv, ct: new Uint8Array(ctBuf) };
}

/**
 * Decrypt `ct` under `key` using the supplied `iv`. Throws on tag mismatch.
 */
export async function decrypt(
  key: CryptoKey,
  iv: Uint8Array,
  ct: Uint8Array,
): Promise<Uint8Array> {
  if (!(iv instanceof Uint8Array) || iv.byteLength !== AES_IV_BYTES) {
    throw new TypeError(
      `decrypt: iv must be a Uint8Array of exactly ${AES_IV_BYTES} bytes`,
    );
  }
  if (!(ct instanceof Uint8Array)) {
    throw new TypeError("decrypt: ct must be a Uint8Array");
  }
  const ptBuf = await subtle().decrypt(
    { name: "AES-GCM", iv: iv as BufferSource },
    key,
    ct as BufferSource,
  );
  return new Uint8Array(ptBuf);
}

// ---------------------------------------------------------------------------
// Encoding helpers (base64 for IndexedDB storage of binary blobs).
// ---------------------------------------------------------------------------

export function bytesToBase64(bytes: Uint8Array): string {
  let bin = "";
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    bin += String.fromCharCode(
      ...bytes.subarray(i, Math.min(i + chunk, bytes.length)),
    );
  }
  if (typeof btoa === "function") return btoa(bin);
  // Node fallback (used only in vitest under jsdom — Buffer is global there).
  return Buffer.from(bin, "binary").toString("base64");
}

export function base64ToBytes(b64: string): Uint8Array {
  const bin =
    typeof atob === "function"
      ? atob(b64)
      : Buffer.from(b64, "base64").toString("binary");
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i += 1) out[i] = bin.charCodeAt(i);
  return out;
}
