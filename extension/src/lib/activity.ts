/**
 * Local activity log — a thin IndexedDB-backed ring buffer of fill /
 * capture / sync events, used by the popup's "Activity" tab.
 *
 * Stored UNENCRYPTED on purpose: these are *events* (timestamps + portal
 * names), not PII. The actual filled fields never enter this store —
 * those go to the backend via the submissions API after explicit user
 * action.
 *
 * Cap: most recent 200 entries are kept; older entries are trimmed on
 * `append`. Reads are newest-first.
 */

import type { ActivityEntry } from "./messaging";

const DB_NAME = "once_activity";
const DB_VERSION = 1;
const STORE = "events";
const MAX_ENTRIES = 200;

function idb(): IDBFactory {
  const f =
    typeof globalThis !== "undefined"
      ? (globalThis as { indexedDB?: IDBFactory }).indexedDB
      : undefined;
  if (!f) throw new Error("indexedDB unavailable");
  return f;
}

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = idb().open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = (): void => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) {
        const store = db.createObjectStore(STORE, { keyPath: "id" });
        store.createIndex("ts", "ts", { unique: false });
      }
    };
    req.onsuccess = (): void => resolve(req.result);
    req.onerror = (): void =>
      reject(req.error ?? new Error("indexedDB open failed"));
  });
}

function toPromise<T>(req: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    req.onsuccess = (): void => resolve(req.result);
    req.onerror = (): void =>
      reject(req.error ?? new Error("indexedDB request failed"));
  });
}

export async function append(entry: ActivityEntry): Promise<void> {
  const db = await open();
  try {
    const tx = db.transaction(STORE, "readwrite");
    const store = tx.objectStore(STORE);
    await toPromise(store.put(entry));

    // Trim — fetch all keys (cheap; capped), drop oldest if over cap.
    const allKeys = (await toPromise(store.getAllKeys())) as IDBValidKey[];
    if (allKeys.length > MAX_ENTRIES) {
      const all = (await toPromise(store.getAll())) as ActivityEntry[];
      const sorted = [...all].sort((a, b) => a.ts - b.ts);
      const drop = sorted.slice(0, sorted.length - MAX_ENTRIES);
      for (const e of drop) {
        await toPromise(store.delete(e.id));
      }
    }
    await new Promise<void>((resolve, reject) => {
      tx.oncomplete = (): void => resolve();
      tx.onerror = (): void =>
        reject(tx.error ?? new Error("activity tx failed"));
    });
  } finally {
    db.close();
  }
}

export async function list(limit = 20): Promise<ActivityEntry[]> {
  const db = await open();
  try {
    const tx = db.transaction(STORE, "readonly");
    const store = tx.objectStore(STORE);
    const all = (await toPromise(store.getAll())) as ActivityEntry[];
    return [...all].sort((a, b) => b.ts - a.ts).slice(0, limit);
  } finally {
    db.close();
  }
}

export async function clear(): Promise<void> {
  const db = await open();
  try {
    const tx = db.transaction(STORE, "readwrite");
    await toPromise(tx.objectStore(STORE).clear());
    await new Promise<void>((resolve, reject) => {
      tx.oncomplete = (): void => resolve();
      tx.onerror = (): void =>
        reject(tx.error ?? new Error("activity clear failed"));
    });
  } finally {
    db.close();
  }
}

/** Cryptographically-random id without external deps. */
export function newId(): string {
  const buf = new Uint8Array(16);
  globalThis.crypto.getRandomValues(buf);
  return Array.from(buf, (b) => b.toString(16).padStart(2, "0")).join("");
}

export const __test__ = { DB_NAME, STORE, MAX_ENTRIES };
