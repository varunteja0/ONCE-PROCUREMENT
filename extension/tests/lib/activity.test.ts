/**
 * Tests for lib/activity — IndexedDB-backed ring buffer.
 */
import "fake-indexeddb/auto";
import { beforeEach, describe, expect, it } from "vitest";

import { append, clear, list, newId, __test__ } from "../../src/lib/activity";
import type { ActivityEntry } from "../../src/lib/messaging";

function mk(id: string, ts: number): ActivityEntry {
  return {
    id,
    ts,
    kind: "fill",
    portal: null,
    supplier_id: null,
    detail: "",
  };
}

beforeEach(async () => {
  await clear();
});

describe("activity log", () => {
  it("append + list returns newest-first", async () => {
    await append(mk("a", 1));
    await append(mk("b", 5));
    await append(mk("c", 3));
    const items = await list(10);
    expect(items.map((i) => i.id)).toEqual(["b", "c", "a"]);
  });

  it("clear empties the store", async () => {
    await append(mk("a", 1));
    await clear();
    expect(await list()).toEqual([]);
  });

  it("trims to MAX_ENTRIES", async () => {
    const N = __test__.MAX_ENTRIES;
    for (let i = 0; i < N + 5; i += 1) {
      await append(mk(`x${i}`, i));
    }
    const items = await list(N + 10);
    expect(items).toHaveLength(N);
    // newest first → highest ts.
    expect(items[0]?.ts).toBe(N + 4);
  });

  it("newId is unique on rapid calls", () => {
    const ids = new Set(Array.from({ length: 50 }, () => newId()));
    expect(ids.size).toBe(50);
  });
});
