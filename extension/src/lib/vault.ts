/**
 * Encrypted profile vault, backed by IndexedDB (`once_vault` database,
 * `entries` object store) and AES-GCM-256 keys derived from a user
 * passphrase via PBKDF2-SHA256 (310k iters). See `CONTRACTS.md` §10.
 *
 * Layout
 * ------
 *   IndexedDB database : `once_vault`            (versioned schema = 1)
 *   Object store       : `entries`               (keyPath = "id")
 *     - id  : string   — profile key (e.g., "default" or a supplier UUID)
 *     - iv  : Uint8Array (12 bytes)
 *     - ct  : Uint8Array (AES-GCM ciphertext + 16-byte tag)
 *     - meta: { kind: "profile" | "verifier"; updated_at: string }
 *
 *   A sentinel entry with id = "__verifier__" stores an encrypted
 *   well-known marker so we can validate a passphrase on `unlock` without
 *   ever persisting key material or hashes.
 *
 *   The vault salt lives in `chrome.storage.local` under
 *   `STORAGE_KEYS.vaultSalt` (base64); the derived AES key never leaves
 *   memory and is held in this module behind `lock()` / configured auto-lock.
 */

import { isSupplierProfile, type SupplierProfile } from "../types/profile";
import { base64ToBytes, bytesToBase64, decrypt, deriveKey, encrypt, randomBytes, SALT_BYTES } from "./crypto";
import { STORAGE_KEYS, storageGet, storageGetOptional, storageRemove, storageSet } from "./storage";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DB_NAME = "once_vault";
const DB_VERSION = 1;
const STORE_NAME = "entries";
const VERIFIER_ID = "__verifier__";
const VERIFIER_PLAINTEXT = "once.vault.v1";
const DEFAULT_AUTO_LOCK_MIN = 15;

// ---------------------------------------------------------------------------
// SessionKey — opaque handle returned by unlock()
// ---------------------------------------------------------------------------

declare const SessionKeyBrand: unique symbol;

export interface SessionKey {
  readonly [SessionKeyBrand]: true;
}

interface SessionKeyImpl extends SessionKey {
  readonly key: CryptoKey;
  readonly createdAt: number;
}

function makeSessionKey(key: CryptoKey): SessionKeyImpl {
  return {
    key,
    createdAt: Date.now(),
  } as SessionKeyImpl;
}

// ---------------------------------------------------------------------------
// Stored record shape
// ---------------------------------------------------------------------------

export type VaultEntryKind = "profile" | "verifier";

interface VaultRecord {
  id: string;
  iv: Uint8Array;
  ct: Uint8Array;
  meta: {
    kind: VaultEntryKind;
    updated_at: string;
  };
}

// ---------------------------------------------------------------------------
// Module-level session state (auto-lock)
// ---------------------------------------------------------------------------

let sessionKey: SessionKeyImpl | null = null;
let autoLockTimer: ReturnType<typeof setTimeout> | null = null;

async function autoLockDelayMs(): Promise<number> {
  const configured = await storageGet<number>(STORAGE_KEYS.autoLockMinutes, DEFAULT_AUTO_LOCK_MIN);
  const minutes =
    typeof configured === "number" && Number.isFinite(configured) && configured > 0
      ? Math.min(240, Math.max(1, Math.floor(configured)))
      : DEFAULT_AUTO_LOCK_MIN;
  return minutes * 60 * 1000;
}

async function armAutoLock(): Promise<void> {
  if (autoLockTimer !== null) {
    clearTimeout(autoLockTimer);
  }
  const delayMs = await autoLockDelayMs();
  autoLockTimer = setTimeout(() => {
    lock();
  }, delayMs);
}

function requireSession(): SessionKeyImpl {
  if (sessionKey === null) {
    throw new VaultLockedError();
  }
  return sessionKey;
}

// ---------------------------------------------------------------------------
// Errors
// ---------------------------------------------------------------------------

export class VaultLockedError extends Error {
  constructor() {
    super("vault is locked");
    this.name = "VaultLockedError";
  }
}

export class VaultNotInitializedError extends Error {
  constructor() {
    super("vault has not been initialized");
    this.name = "VaultNotInitializedError";
  }
}

export class VaultAlreadyInitializedError extends Error {
  constructor() {
    super("vault has already been initialized");
    this.name = "VaultAlreadyInitializedError";
  }
}

export class VaultPassphraseError extends Error {
  constructor() {
    super("invalid passphrase");
    this.name = "VaultPassphraseError";
  }
}

// ---------------------------------------------------------------------------
// IndexedDB helpers
// ---------------------------------------------------------------------------

function getIndexedDB(): IDBFactory {
  const f = typeof globalThis !== "undefined" ? (globalThis as { indexedDB?: IDBFactory }).indexedDB : undefined;
  if (!f) {
    throw new Error("indexedDB is unavailable in this environment");
  }
  return f;
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = getIndexedDB().open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = (): void => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: "id" });
      }
    };
    req.onsuccess = (): void => resolve(req.result);
    req.onerror = (): void => reject(req.error ?? new Error("indexedDB open failed"));
    req.onblocked = (): void => reject(new Error("indexedDB open blocked by another connection"));
  });
}

function reqToPromise<T>(req: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    req.onsuccess = (): void => resolve(req.result);
    req.onerror = (): void => reject(req.error ?? new Error("indexedDB request failed"));
  });
}

async function dbPut(record: VaultRecord): Promise<void> {
  const db = await openDb();
  try {
    const tx = db.transaction(STORE_NAME, "readwrite");
    const store = tx.objectStore(STORE_NAME);
    await reqToPromise(store.put(record));
    await new Promise<void>((resolve, reject) => {
      tx.oncomplete = (): void => resolve();
      tx.onerror = (): void => reject(tx.error ?? new Error("indexedDB tx failed"));
      tx.onabort = (): void => reject(tx.error ?? new Error("indexedDB tx aborted"));
    });
  } finally {
    db.close();
  }
}

async function dbGet(id: string): Promise<VaultRecord | null> {
  const db = await openDb();
  try {
    const tx = db.transaction(STORE_NAME, "readonly");
    const store = tx.objectStore(STORE_NAME);
    const got = await reqToPromise(store.get(id));
    return (got as VaultRecord | undefined) ?? null;
  } finally {
    db.close();
  }
}

async function dbKeys(): Promise<string[]> {
  const db = await openDb();
  try {
    const tx = db.transaction(STORE_NAME, "readonly");
    const store = tx.objectStore(STORE_NAME);
    const keys = (await reqToPromise(store.getAllKeys())) as IDBValidKey[];
    return keys.filter((k): k is string => typeof k === "string");
  } finally {
    db.close();
  }
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Returns true if a vault has been initialised (i.e. a salt + verifier
 * record exist).
 */
export async function isInitialized(): Promise<boolean> {
  const salt = await storageGetOptional<string>(STORAGE_KEYS.vaultSalt);
  if (!salt) return false;
  const verifier = await dbGet(VERIFIER_ID);
  return verifier !== null;
}

/**
 * Initialise a new vault under the given passphrase. Generates a fresh
 * salt, derives the AES key, stores an encrypted verifier marker and
 * leaves the vault **unlocked** (returns a `SessionKey`).
 */
export async function init(passphrase: string): Promise<SessionKey> {
  if (await isInitialized()) {
    throw new VaultAlreadyInitializedError();
  }

  const salt = randomBytes(SALT_BYTES);
  const key = await deriveKey(passphrase, salt);

  const enc = new TextEncoder();
  const { iv, ct } = await encrypt(key, enc.encode(VERIFIER_PLAINTEXT));

  await dbPut({
    id: VERIFIER_ID,
    iv,
    ct,
    meta: { kind: "verifier", updated_at: new Date().toISOString() },
  });
  await storageSet(STORAGE_KEYS.vaultSalt, bytesToBase64(salt));
  await storageSet(STORAGE_KEYS.vaultInitialized, true);

  sessionKey = makeSessionKey(key);
  await armAutoLock();
  return sessionKey;
}

/**
 * Unlock the vault and return a `SessionKey` handle. The derived AES key
 * is held in module state and auto-locked after the configured timeout from the most
 * recent `unlock` / `putProfile` / `getProfile` call.
 *
 * @throws `VaultNotInitializedError` if `init` has not been called.
 * @throws `VaultPassphraseError`     if the passphrase does not decrypt
 *                                    the verifier blob.
 */
export async function unlock(passphrase: string): Promise<SessionKey> {
  const saltB64 = await storageGetOptional<string>(STORAGE_KEYS.vaultSalt);
  if (!saltB64) throw new VaultNotInitializedError();
  const verifier = await dbGet(VERIFIER_ID);
  if (!verifier) throw new VaultNotInitializedError();

  const salt = base64ToBytes(saltB64);
  const key = await deriveKey(passphrase, salt);

  let plaintext: Uint8Array;
  try {
    plaintext = await decrypt(key, verifier.iv, verifier.ct);
  } catch {
    throw new VaultPassphraseError();
  }

  const dec = new TextDecoder();
  if (dec.decode(plaintext) !== VERIFIER_PLAINTEXT) {
    throw new VaultPassphraseError();
  }

  sessionKey = makeSessionKey(key);
  await armAutoLock();
  return sessionKey;
}

/**
 * Forget the in-memory session key and cancel the auto-lock timer. Safe
 * to call when already locked.
 */
export function lock(): void {
  sessionKey = null;
  if (autoLockTimer !== null) {
    clearTimeout(autoLockTimer);
    autoLockTimer = null;
  }
}

/**
 * Encrypt and persist `profile` under `key`. Requires an unlocked vault.
 */
export async function putProfile(key: string, profile: SupplierProfile): Promise<void> {
  if (typeof key !== "string" || key.length === 0) {
    throw new Error("putProfile: key must be a non-empty string");
  }
  if (key === VERIFIER_ID) {
    throw new Error(`putProfile: key '${VERIFIER_ID}' is reserved`);
  }
  if (!isSupplierProfile(profile)) {
    throw new Error("putProfile: profile is not a valid SupplierProfile");
  }
  const session = requireSession();

  const enc = new TextEncoder();
  const plaintext = enc.encode(JSON.stringify(profile));
  const { iv, ct } = await encrypt(session.key, plaintext);

  await dbPut({
    id: key,
    iv,
    ct,
    meta: { kind: "profile", updated_at: new Date().toISOString() },
  });
  await armAutoLock();
}

/**
 * Load and decrypt a profile by `key`. Returns `null` if no entry exists.
 * Requires an unlocked vault.
 */
export async function getProfile(key: string): Promise<SupplierProfile | null> {
  if (typeof key !== "string" || key.length === 0) {
    throw new Error("getProfile: key must be a non-empty string");
  }
  if (key === VERIFIER_ID) return null;
  const session = requireSession();

  const record = await dbGet(key);
  if (!record) return null;
  if (record.meta.kind !== "profile") return null;

  const plaintext = await decrypt(session.key, record.iv, record.ct);
  const dec = new TextDecoder();
  const parsed: unknown = JSON.parse(dec.decode(plaintext));
  await armAutoLock();
  if (!isSupplierProfile(parsed)) return null;
  return parsed;
}

/**
 * List all stored profile ids (excluding internal sentinels).
 */
export async function listProfileIds(): Promise<string[]> {
  const keys = await dbKeys();
  return keys.filter((k) => k !== VERIFIER_ID);
}

// ---------------------------------------------------------------------------
// Test/debug helpers — NOT part of the public API.
// ---------------------------------------------------------------------------

export const __test__ = {
  DEFAULT_AUTO_LOCK_MIN,
  DB_NAME,
  STORE_NAME,
  VERIFIER_ID,
  VERIFIER_PLAINTEXT,
  getSessionKey: (): SessionKey | null => sessionKey,
  /** Force-destroy local vault state. Intended for tests only. */
  async _wipe(): Promise<void> {
    lock();
    await storageRemove(STORAGE_KEYS.vaultSalt);
    await storageRemove(STORAGE_KEYS.vaultInitialized);
    await new Promise<void>((resolve, reject) => {
      const req = getIndexedDB().deleteDatabase(DB_NAME);
      req.onsuccess = (): void => resolve();
      req.onerror = (): void => reject(req.error ?? new Error("indexedDB delete failed"));
      req.onblocked = (): void => resolve();
    });
  },
};
