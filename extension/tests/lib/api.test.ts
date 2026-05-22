/**
 * Tests for lib/api — extractErrorCode + transport behavior via sendMessage mock.
 */
import { describe, expect, it, vi } from "vitest";

import { ApiError, ApiTransportError, __test__ } from "../../src/lib/api";

const { call, extractErrorCode } = __test__;

describe("api.extractErrorCode", () => {
  it("prefers detail then code then error", () => {
    expect(extractErrorCode({ detail: "d" }, "fb")).toBe("d");
    expect(extractErrorCode({ code: "c" }, "fb")).toBe("c");
    expect(extractErrorCode({ error: "e" }, "fb")).toBe("e");
    expect(extractErrorCode({}, "fb")).toBe("fb");
    expect(extractErrorCode(null, "fb")).toBe("fb");
  });
});

describe("api.call", () => {
  it("resolves on ok response", async () => {
    chrome.runtime.sendMessage = vi.fn(
      (_msg: unknown, cb: (resp: unknown) => void) => {
        cb({ ok: true, status: 200, json: { hello: "world" } });
      },
    ) as unknown as typeof chrome.runtime.sendMessage;
    const data = await call<{ hello: string }>("GET", "/v1/x");
    expect(data).toEqual({ hello: "world" });
  });

  it("throws ApiError on non-ok response", async () => {
    chrome.runtime.sendMessage = vi.fn(
      (_msg: unknown, cb: (resp: unknown) => void) => {
        cb({ ok: false, status: 403, json: { detail: "forbidden" } });
      },
    ) as unknown as typeof chrome.runtime.sendMessage;
    await expect(call("GET", "/v1/x")).rejects.toBeInstanceOf(ApiError);
  });

  it("throws ApiTransportError on missing response", async () => {
    chrome.runtime.sendMessage = vi.fn(
      (_msg: unknown, cb: (resp: unknown) => void) => {
        cb(null);
      },
    ) as unknown as typeof chrome.runtime.sendMessage;
    await expect(call("GET", "/v1/x")).rejects.toBeInstanceOf(
      ApiTransportError,
    );
  });
});
