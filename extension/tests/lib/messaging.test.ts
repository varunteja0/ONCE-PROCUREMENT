/**
 * Tests for lib/messaging — typed message bus.
 */
import { describe, expect, it, vi } from "vitest";

import {
  routeMessages,
  send,
  sendOrThrow,
  __test__,
  type HandlerMap,
} from "../../src/lib/messaging";

describe("messaging.isMessage", () => {
  it("accepts well-formed messages", () => {
    expect(__test__.isMessage({ type: "vault.lock" })).toBe(true);
  });
  it("rejects bare values", () => {
    expect(__test__.isMessage(null)).toBe(false);
    expect(__test__.isMessage({ noType: 1 })).toBe(false);
    expect(__test__.isMessage("vault.lock")).toBe(false);
  });
});

describe("messaging.routeMessages", () => {
  it("dispatches to the matching handler and returns ok", async () => {
    const handler = vi.fn(async () => ({ ok: true as const }));
    const handlers: HandlerMap = { "vault.lock": handler };
    const listener = routeMessages(handlers);

    const send = vi.fn();
    const keep = listener({ type: "vault.lock" }, {}, send);
    expect(keep).toBe(true);

    // Allow the promise microtask to flush.
    await new Promise((r) => setTimeout(r, 0));
    expect(handler).toHaveBeenCalledTimes(1);
    expect(send).toHaveBeenCalledWith({ ok: true });
  });

  it("returns no_handler when no handler is registered", () => {
    const listener = routeMessages({});
    const send = vi.fn();
    const keep = listener({ type: "vault.lock" }, {}, send);
    expect(keep).toBe(false);
    expect(send).toHaveBeenCalledWith(
      expect.objectContaining({ ok: false, error: "no_handler:vault.lock" }),
    );
  });

  it("returns invalid_message for malformed payloads", () => {
    const listener = routeMessages({});
    const send = vi.fn();
    listener({ foo: "bar" }, {}, send);
    expect(send).toHaveBeenCalledWith(
      expect.objectContaining({ ok: false, error: "invalid_message" }),
    );
  });

  it("captures thrown handler errors as ok:false", async () => {
    const handler = vi.fn(async () => {
      throw new Error("boom");
    });
    const listener = routeMessages({ "vault.lock": handler });
    const send = vi.fn();
    listener({ type: "vault.lock" }, {}, send);
    await new Promise((r) => setTimeout(r, 0));
    expect(send).toHaveBeenCalledWith(
      expect.objectContaining({ ok: false, error: "boom" }),
    );
  });
});

describe("messaging.send/sendOrThrow", () => {
  it("send round-trips through chrome.runtime.sendMessage", async () => {
    chrome.runtime.sendMessage = vi.fn(
      (_msg: unknown, cb: (resp: unknown) => void) => {
        cb({ ok: true });
      },
    ) as unknown as typeof chrome.runtime.sendMessage;
    const resp = await send({ type: "vault.lock" });
    expect(resp).toEqual({ ok: true });
  });

  it("send rejects when response is undefined (empty channel)", async () => {
    chrome.runtime.sendMessage = vi.fn(
      (_msg: unknown, cb: (resp: unknown) => void) => {
        cb(undefined);
      },
    ) as unknown as typeof chrome.runtime.sendMessage;
    await expect(send({ type: "vault.lock" })).rejects.toThrow(/empty response/);
  });

  it("sendOrThrow throws on ok:false", async () => {
    chrome.runtime.sendMessage = vi.fn(
      (_msg: unknown, cb: (resp: unknown) => void) => {
        cb({ ok: false, error: "nope" });
      },
    ) as unknown as typeof chrome.runtime.sendMessage;
    await expect(sendOrThrow({ type: "vault.lock" })).rejects.toThrow(/nope/);
  });
});
