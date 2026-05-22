/**
 * Tests for the background "submission.capture" handler — verifies that
 * it queues the submission and surfaces the new pending id.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../src/lib/activity", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    append: vi.fn(async () => undefined),
  };
});

import { __test__ } from "../../src/background/index";
import { getPending } from "../../src/lib/sync";

const { handlers } = __test__;

beforeEach(async () => {
  await chrome.storage.local.clear();
});

describe("background submission.capture handler", () => {
  it("queues the submission and returns the pending id", async () => {
    const resp = await handlers["submission.capture"]!(
      {
        type: "submission.capture",
        payload: {
          supplier_id: "sup1",
          portal_id: "portal-1",
          consent_record_id: "consent-1",
          payload: { url: "https://app.appliedepic.com/intake" },
        },
      },
      { id: "x" } as chrome.runtime.MessageSender,
    );
    expect(resp.ok).toBe(true);
    if (!resp.ok) return;
    expect(typeof resp.id).toBe("string");
    const pending = await getPending();
    expect(pending).toHaveLength(1);
    expect(pending[0]?.id).toBe(resp.id);
    expect(pending[0]?.payload.consent_record_id).toBe("consent-1");
  });
});
