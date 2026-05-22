/**
 * Tests for the new lib/api endpoints — `getSubmissionReceipt` and
 * `getConsentForPortal`. Verifies the canonical HTTP method + path is
 * sent via the background `API_CALL` proxy.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getConsentForPortal, getSubmissionReceipt } from "../../src/lib/api";

interface ApiCallMsg {
  type: string;
  method: string;
  path: string;
}

beforeEach(() => {
  // Reset between tests so call counts don't bleed.
  (chrome.runtime.sendMessage as unknown as ReturnType<typeof vi.fn>).mockReset();
});

describe("getSubmissionReceipt", () => {
  it("issues GET /v1/submissions/:id/receipt", async () => {
    chrome.runtime.sendMessage = vi.fn(
      (_msg: unknown, cb: (resp: unknown) => void) => {
        cb({ ok: true, status: 200, json: { id: "rcpt-1" } });
      },
    ) as unknown as typeof chrome.runtime.sendMessage;

    const out = await getSubmissionReceipt("sub-abc");
    expect(out).toEqual({ id: "rcpt-1" });

    const sendMessage = chrome.runtime.sendMessage as unknown as ReturnType<typeof vi.fn>;
    const sent = sendMessage.mock.calls[0]![0] as ApiCallMsg;
    expect(sent.type).toBe("API_CALL");
    expect(sent.method).toBe("GET");
    expect(sent.path).toBe("/v1/submissions/sub-abc/receipt");
  });
});

describe("getConsentForPortal", () => {
  it("queries /v1/consents with supplier_id, portal_id, active=true, limit=1", async () => {
    chrome.runtime.sendMessage = vi.fn(
      (_msg: unknown, cb: (resp: unknown) => void) => {
        cb({
          ok: true,
          status: 200,
          json: {
            items: [{ id: "consent-1" }],
            total: 1,
            limit: 1,
            offset: 0,
          },
        });
      },
    ) as unknown as typeof chrome.runtime.sendMessage;

    const out = await getConsentForPortal("sup-1", "portal-1");
    expect(out).toEqual({ id: "consent-1" });

    const sendMessage = chrome.runtime.sendMessage as unknown as ReturnType<typeof vi.fn>;
    const sent = sendMessage.mock.calls[0]![0] as ApiCallMsg;
    expect(sent.method).toBe("GET");
    expect(sent.path.startsWith("/v1/consents?")).toBe(true);
    const qs = new URLSearchParams(sent.path.split("?")[1] ?? "");
    expect(qs.get("supplier_id")).toBe("sup-1");
    expect(qs.get("portal_id")).toBe("portal-1");
    expect(qs.get("active")).toBe("true");
    expect(qs.get("limit")).toBe("1");
  });

  it("returns null when the API returns no items", async () => {
    chrome.runtime.sendMessage = vi.fn(
      (_msg: unknown, cb: (resp: unknown) => void) => {
        cb({
          ok: true,
          status: 200,
          json: { items: [], total: 0, limit: 1, offset: 0 },
        });
      },
    ) as unknown as typeof chrome.runtime.sendMessage;

    const out = await getConsentForPortal("sup-1", "portal-1");
    expect(out).toBeNull();
  });
});
