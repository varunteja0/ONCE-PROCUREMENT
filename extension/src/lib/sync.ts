/**
 * Pull-down sync from the Once backend.
 *
 * Strategy
 * --------
 * Cursor-based incremental fetch where the backend supports it
 * (`?since=ISO8601`), with a polite full-refresh fallback for endpoints
 * that don't (`/v1/portals`, which is small). Conflicts use last-write-
 * wins on `updated_at` because the backend is the source of truth and
 * the extension only ever caches a read-only projection.
 *
 * Outbound: pending submissions captured while the user was offline are
 * queued in `chrome.storage.local` under `once.pendingSubmissions` and
 * drained on every successful sync.
 */

import {
  createSubmission,
  getSubmissionReceipt,
  listPortals,
  listSubmissions,
  listSuppliers,
  type PortalListItem,
  type ReceiptListItem,
  type SubmissionCreatePayload,
  type SubmissionListItem,
  type SupplierListItem,
} from "./api";
import type { SyncStatus } from "./messaging";
import { storageGet, storageSet } from "./storage";

// ---------------------------------------------------------------------------
// Cache shape stored in chrome.storage.local
// ---------------------------------------------------------------------------

export const SYNC_KEYS = {
  suppliers: "once.cache.suppliers",
  submissions: "once.cache.submissions",
  portals: "once.cache.portals",
  receipts: "once.cache.receipts",
  cursor: "once.cache.cursor",
  pending: "once.pendingSubmissions",
  status: "once.sync.status",
} as const;

export interface SuppliersCache {
  items: SupplierListItem[];
  fetched_at: number;
}

export interface SubmissionsCache {
  items: SubmissionListItem[];
  fetched_at: number;
}

export interface PortalsCache {
  items: PortalListItem[];
  fetched_at: number;
}

export interface PendingSubmission {
  id: string;
  attempt: number;
  payload: SubmissionCreatePayload;
  queued_at: number;
  last_error: string | null;
}

// ---------------------------------------------------------------------------
// Cache accessors
// ---------------------------------------------------------------------------

export async function getCachedSuppliers(): Promise<SupplierListItem[]> {
  const cache = await storageGet<SuppliersCache | null>(SYNC_KEYS.suppliers, null);
  return cache?.items ?? [];
}

export async function getCachedSubmissions(): Promise<SubmissionListItem[]> {
  const cache = await storageGet<SubmissionsCache | null>(SYNC_KEYS.submissions, null);
  return cache?.items ?? [];
}

export async function getCachedPortals(): Promise<PortalListItem[]> {
  const cache = await storageGet<PortalsCache | null>(SYNC_KEYS.portals, null);
  return cache?.items ?? [];
}

export async function getCachedReceipt(submissionId: string): Promise<ReceiptListItem | null> {
  return storageGet<ReceiptListItem | null>(`${SYNC_KEYS.receipts}.${submissionId}`, null);
}

export async function getStatus(): Promise<SyncStatus> {
  return storageGet<SyncStatus>(SYNC_KEYS.status, {
    last_sync_at: null,
    in_flight: false,
    last_error: null,
    supplier_count: 0,
    submission_count: 0,
  });
}

async function setStatus(patch: Partial<SyncStatus>): Promise<SyncStatus> {
  const current = await getStatus();
  const next: SyncStatus = { ...current, ...patch };
  await storageSet(SYNC_KEYS.status, next);
  return next;
}

// ---------------------------------------------------------------------------
// Conflict resolution helper
// ---------------------------------------------------------------------------

/**
 * Merge `local` ↦ `remote` by id, taking the row with the newer
 * `updated_at`. Items only present remotely are added; items only
 * present locally are dropped (server is authoritative).
 */
export function mergeByUpdatedAt<T extends { id: string; updated_at: string }>(
  local: readonly T[],
  remote: readonly T[],
): T[] {
  const out = new Map<string, T>();
  for (const r of remote) out.set(r.id, r);
  for (const l of local) {
    const r = out.get(l.id);
    if (!r) continue;
    if (Date.parse(l.updated_at) > Date.parse(r.updated_at)) {
      out.set(l.id, l);
    }
  }
  return Array.from(out.values()).sort((a, b) => a.id.localeCompare(b.id));
}

// ---------------------------------------------------------------------------
// Pending submission queue
// ---------------------------------------------------------------------------

export async function getPending(): Promise<PendingSubmission[]> {
  return storageGet<PendingSubmission[]>(SYNC_KEYS.pending, []);
}

async function setPending(items: PendingSubmission[]): Promise<void> {
  await storageSet(SYNC_KEYS.pending, items);
}

export async function queueSubmission(payload: SubmissionCreatePayload): Promise<PendingSubmission> {
  const pending = await getPending();
  const entry: PendingSubmission = {
    id: `pending_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    attempt: 0,
    payload,
    queued_at: Date.now(),
    last_error: null,
  };
  pending.push(entry);
  await setPending(pending);
  return entry;
}

const MAX_ATTEMPTS = 5;

export async function drainPending(): Promise<{
  sent: number;
  failed: number;
}> {
  const pending = await getPending();
  if (pending.length === 0) return { sent: 0, failed: 0 };

  const keep: PendingSubmission[] = [];
  let sent = 0;
  let failed = 0;

  for (const entry of pending) {
    try {
      const created = await createSubmission(entry.payload);
      sent += 1;
      // Best-effort: fetch + cache the signed receipt so the popup
      // can display it without a round-trip. A receipt fetch failure
      // does NOT roll back the successful submission.
      try {
        const receipt = await getSubmissionReceipt(created.id);
        await storageSet(`${SYNC_KEYS.receipts}.${created.id}`, receipt);
      } catch {
        /* receipt fetch is best-effort */
      }
    } catch (err) {
      entry.attempt += 1;
      entry.last_error = err instanceof Error ? err.message : "unknown";
      if (entry.attempt < MAX_ATTEMPTS) {
        keep.push(entry);
      } else {
        failed += 1;
      }
    }
  }

  await setPending(keep);
  return { sent, failed };
}

// ---------------------------------------------------------------------------
// Top-level sync
// ---------------------------------------------------------------------------

export async function syncNow(): Promise<SyncStatus> {
  await setStatus({ in_flight: true, last_error: null });
  try {
    const [remoteSuppliers, remoteSubmissions, remotePortals] = await Promise.all([
      listSuppliers(),
      listSubmissions(),
      listPortals(),
    ]);

    // We don't currently mutate suppliers locally (read-only mirror) but
    // we keep the conflict resolver wired in case a future iteration
    // adds local drafts.
    const localSuppliers = await getCachedSuppliers();
    const mergedSuppliers = mergeByUpdatedAt(
      localSuppliers.map((s) => ({ ...s, updated_at: s.created_at })),
      remoteSuppliers.map((s) => ({ ...s, updated_at: s.created_at })),
    ).map<SupplierListItem>(({ updated_at: _u, ...rest }) => rest);

    const localSubs = await getCachedSubmissions();
    const mergedSubs = mergeByUpdatedAt(localSubs, remoteSubmissions);

    const now = Date.now();
    const supplierCache: SuppliersCache = {
      items: mergedSuppliers,
      fetched_at: now,
    };
    const subCache: SubmissionsCache = {
      items: mergedSubs,
      fetched_at: now,
    };
    await storageSet(SYNC_KEYS.suppliers, supplierCache);
    await storageSet(SYNC_KEYS.submissions, subCache);
    const portalCache: PortalsCache = {
      items: remotePortals,
      fetched_at: now,
    };
    await storageSet(SYNC_KEYS.portals, portalCache);

    await drainPending();

    return setStatus({
      in_flight: false,
      last_sync_at: now,
      last_error: null,
      supplier_count: mergedSuppliers.length,
      submission_count: mergedSubs.length,
    });
  } catch (err) {
    return setStatus({
      in_flight: false,
      last_error: err instanceof Error ? err.message : "sync_failed",
    });
  }
}

export const __test__ = {
  setStatus,
  setPending,
};
