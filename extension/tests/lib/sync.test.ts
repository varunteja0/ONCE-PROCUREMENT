/**
 * Tests for lib/sync — merge, queue, drain, syncNow happy path.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

const listSuppliers = vi.fn();
const listSubmissions = vi.fn();
const listPortals = vi.fn();
const createSubmission = vi.fn();
const getSubmissionReceipt = vi.fn();
vi.mock("../../src/lib/api", () => ({
  listSuppliers: (...a: unknown[]) => listSuppliers(...a),
  listSubmissions: (...a: unknown[]) => listSubmissions(...a),
  listPortals: (...a: unknown[]) => listPortals(...a),
  createSubmission: (...a: unknown[]) => createSubmission(...a),
  getSubmissionReceipt: (...a: unknown[]) => getSubmissionReceipt(...a),
}));

import {
  drainPending,
  getCachedSubmissions,
  getCachedSuppliers,
  getPending,
  mergeByUpdatedAt,
  queueSubmission,
  syncNow,
} from "../../src/lib/sync";

beforeEach(() => {
  listSuppliers.mockReset();
  listSubmissions.mockReset();
  listPortals.mockReset();
  createSubmission.mockReset();
  getSubmissionReceipt.mockReset();
  listPortals.mockResolvedValue([]);
  getSubmissionReceipt.mockResolvedValue({ id: "r1" });
});

describe("sync.mergeByUpdatedAt", () => {
  it("takes the newer row by updated_at", () => {
    const local = [{ id: "a", updated_at: "2024-02-01T00:00:00Z", n: 2 }];
    const remote = [{ id: "a", updated_at: "2024-01-01T00:00:00Z", n: 1 }];
    const merged = mergeByUpdatedAt(local, remote);
    expect(merged).toEqual([{ id: "a", updated_at: "2024-02-01T00:00:00Z", n: 2 }]);
  });

  it("drops local-only rows (server is authoritative)", () => {
    const local = [{ id: "x", updated_at: "2024-01-01T00:00:00Z" }];
    const remote = [{ id: "y", updated_at: "2024-01-01T00:00:00Z" }];
    const merged = mergeByUpdatedAt(local, remote);
    expect(merged.map((r) => r.id)).toEqual(["y"]);
  });
});

describe("sync.queue + drain", () => {
  const payload = {
    supplier_id: "sup1",
    portal_id: "applied_epic" as const,
    consent_record_id: "consent-x",
    payload: {},
  };

  it("queues a submission and lists it back", async () => {
    const entry = await queueSubmission(payload);
    expect(entry.attempt).toBe(0);
    const pending = await getPending();
    expect(pending).toHaveLength(1);
    expect(pending[0]?.id).toBe(entry.id);
  });

  it("drainPending removes successful entries", async () => {
    await queueSubmission(payload);
    createSubmission.mockResolvedValueOnce({ id: "s1" });
    const res = await drainPending();
    expect(res.sent).toBe(1);
    expect(await getPending()).toEqual([]);
  });

  it("drainPending increments attempt on failure", async () => {
    await queueSubmission(payload);
    createSubmission.mockRejectedValue(new Error("nope"));
    await drainPending();
    const pending = await getPending();
    expect(pending[0]?.attempt).toBe(1);
    expect(pending[0]?.last_error).toBe("nope");
  });
});

describe("sync.syncNow", () => {
  it("caches lists on success", async () => {
    listSuppliers.mockResolvedValue([
      {
        id: "sup1",
        legal_name: "Acme",
        dba_name: null,
        domicile_state: "DE",
        primary_email: null,
        created_at: "2024-01-01T00:00:00Z",
      },
    ]);
    listSubmissions.mockResolvedValue([]);
    const status = await syncNow();
    expect(status.last_error).toBeNull();
    expect(status.supplier_count).toBe(1);
    expect(await getCachedSuppliers()).toHaveLength(1);
    expect(await getCachedSubmissions()).toHaveLength(0);
  });

  it("records last_error on failure", async () => {
    listSuppliers.mockRejectedValue(new Error("net"));
    listSubmissions.mockResolvedValue([]);
    const status = await syncNow();
    expect(status.last_error).toBe("net");
  });
});
