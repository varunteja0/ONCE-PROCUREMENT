/**
 * Tests for the background `apiCall` — verifies the 401 → refresh →
 * retry round-trip works against a stubbed `fetch`.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

import { __test__ } from "../../src/background/index";
import { STORAGE_KEYS } from "../../src/lib/storage";

const { apiCall } = __test__;

interface FetchResp {
  status: number;
  body: unknown;
}

function mockFetchSequence(responses: FetchResp[]): ReturnType<typeof vi.fn> {
  const fn = vi.fn(async () => {
    const next = responses.shift();
    if (!next) throw new Error("unexpected fetch call");
    return {
      ok: next.status >= 200 && next.status < 300,
      status: next.status,
      text: async () => JSON.stringify(next.body),
      json: async () => next.body,
    } as unknown as Response;
  });
  (globalThis as unknown as { fetch: typeof fetch }).fetch = fn as unknown as typeof fetch;
  return fn;
}

beforeEach(async () => {
  await chrome.storage.local.clear();
  await chrome.storage.local.set({
    [STORAGE_KEYS.apiBase]: "http://localhost:8000",
    [STORAGE_KEYS.access]: "stale-access",
    [STORAGE_KEYS.refresh]: "good-refresh",
  });
});

describe("background apiCall 401 → refresh → retry", () => {
  it("refreshes the access token on 401 and retries successfully", async () => {
    const fn = mockFetchSequence([
      { status: 401, body: { detail: "expired" } },
      {
        status: 200,
        body: { access_token: "fresh-access", refresh_token: "rotated" },
      },
      { status: 200, body: { ok: true } },
    ]);

    const result = await apiCall("GET", "/v1/auth/me", undefined, {});
    expect(result.status).toBe(200);
    expect(result.json).toEqual({ ok: true });

    expect(fn).toHaveBeenCalledTimes(3);
    const refreshCall = fn.mock.calls[1]![0] as string;
    expect(String(refreshCall)).toContain("/v1/auth/refresh");
    const retryHeaders = (fn.mock.calls[2]![1] as RequestInit).headers as Record<string, string>;
    expect(retryHeaders["Authorization"]).toBe("Bearer fresh-access");

    const stored = await chrome.storage.local.get([STORAGE_KEYS.access, STORAGE_KEYS.refresh]);
    expect(stored[STORAGE_KEYS.access]).toBe("fresh-access");
    expect(stored[STORAGE_KEYS.refresh]).toBe("rotated");
  });

  it("returns the original 401 when refresh fails", async () => {
    mockFetchSequence([
      { status: 401, body: { detail: "expired" } },
      { status: 401, body: { detail: "bad refresh" } },
    ]);

    const result = await apiCall("GET", "/v1/auth/me", undefined, {});
    expect(result.status).toBe(401);
  });
});
