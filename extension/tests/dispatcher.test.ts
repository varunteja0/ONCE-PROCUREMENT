/**
 * @vitest-environment jsdom
 *
 * Tests for the content-script dispatcher. The dispatcher runs an async
 * IIFE on module load, so each test:
 *   1. Resets the module cache (so the IIFE re-runs against fresh state).
 *   2. Overrides `window.location` to a known carrier hostname.
 *   3. Stubs `chrome.runtime.sendMessage` to return a valid profile for
 *      the `GET_ACTIVE_PROFILE` round-trip.
 *   4. Mocks every filler with `vi.fn` spies via `vi.mock` so we can
 *      assert that exactly one filler runs for the detected portal.
 *   5. Dynamically imports the dispatcher and waits for spies to settle.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { SupplierProfile } from "../src/types/profile";

// ---- Filler mocks (hoisted by vitest) ------------------------------------
const amtrustFill = vi.fn(async (_profile: unknown, _ctx?: unknown) => ({ filled: ["x"], skipped: [] }));
const appliedEpicFill = vi.fn(async (_profile: unknown, _ctx?: unknown) => ({ filled: ["x"], skipped: [] }));
const markelFill = vi.fn(async (_profile: unknown, _ctx?: unknown) => ({ filled: ["x"], skipped: [] }));

vi.mock("../src/content/fillers/amtrust", () => ({ fill: amtrustFill }));
vi.mock("../src/content/fillers/applied_epic", () => ({
  fill: appliedEpicFill,
}));
vi.mock("../src/content/fillers/markel", () => ({ fill: markelFill }));

// ---- Helpers --------------------------------------------------------------

function setLocation(hostname: string, href?: string): void {
  const fakeUrl = href ?? `https://${hostname}/intake`;
  const fakeLocation = {
    hostname,
    href: fakeUrl,
    protocol: "https:",
    host: hostname,
    pathname: "/intake",
    search: "",
    hash: "",
    origin: `https://${hostname}`,
    port: "",
    assign: vi.fn(),
    replace: vi.fn(),
    reload: vi.fn(),
    toString: () => fakeUrl,
  } satisfies Partial<Location> & { toString: () => string };

  Object.defineProperty(window, "location", {
    configurable: true,
    writable: true,
    value: fakeLocation as unknown as Location,
  });
}

function sampleProfile(): SupplierProfile {
  return {
    legal_name: "Acme Insurance Brokers LLC",
    primary_email: "ops@acme.example",
  };
}

interface SendMessageRequest {
  type?: string;
}

function stubProfileFetch(profile: SupplierProfile | null): void {
  chrome.runtime.sendMessage = vi.fn((msg: unknown, cb?: (resp: unknown) => void) => {
    const req = (msg ?? {}) as SendMessageRequest;
    let response: unknown;
    if (req.type === "profile.active") {
      response = profile === null ? { ok: false, error: "locked" } : { ok: true, profile, locked: false };
    } else {
      response = undefined;
    }
    if (typeof cb === "function") cb(response);
    return Promise.resolve(response);
  }) as unknown as typeof chrome.runtime.sendMessage;
}

async function loadDispatcher(): Promise<void> {
  vi.resetModules();
  await import("../src/content/dispatcher");
  // Yield to allow the dispatcher's async IIFE to progress past the
  // initial sendMessage + filler invocation.
  for (let i = 0; i < 10; i++) {
    await Promise.resolve();
    await new Promise<void>((r) => setTimeout(r, 0));
  }
}

// ---- Setup / teardown -----------------------------------------------------

beforeEach(() => {
  document.body.innerHTML = "";
  // Reset the dispatcher's idempotency flag so each test re-runs the IIFE.
  delete (window as unknown as Record<string, unknown>).__once_dispatcher_ran__;
  amtrustFill.mockClear();
  appliedEpicFill.mockClear();
  markelFill.mockClear();
});

afterEach(() => {
  document.body.innerHTML = "";
});

// ---- Tests ----------------------------------------------------------------

describe("dispatcher", () => {
  it("routes amtrust hostnames to the amtrust filler exactly once", async () => {
    setLocation("producers.amtrustfinancial.com");
    stubProfileFetch(sampleProfile());

    await loadDispatcher();

    expect(amtrustFill).toHaveBeenCalledTimes(1);
    expect(appliedEpicFill).not.toHaveBeenCalled();
    expect(markelFill).not.toHaveBeenCalled();

    const [profileArg, ctxArg] = amtrustFill.mock.calls[0]!;
    expect(profileArg).toMatchObject({
      legal_name: "Acme Insurance Brokers LLC",
      primary_email: "ops@acme.example",
    });
    expect(ctxArg).toMatchObject({
      hostname: "producers.amtrustfinancial.com",
      portal: "amtrust",
    });
  });

  it("routes appliedepic hostnames to the applied_epic filler exactly once", async () => {
    setLocation("agency.appliedepic.com");
    stubProfileFetch(sampleProfile());

    await loadDispatcher();

    expect(appliedEpicFill).toHaveBeenCalledTimes(1);
    expect(amtrustFill).not.toHaveBeenCalled();
    expect(markelFill).not.toHaveBeenCalled();
  });

  it("calls chrome.runtime.sendMessage to fetch the active profile", async () => {
    setLocation("producers.amtrustfinancial.com");
    stubProfileFetch(sampleProfile());

    await loadDispatcher();

    const sendMessage = chrome.runtime.sendMessage as unknown as ReturnType<typeof vi.fn>;
    const calls = sendMessage.mock.calls;
    expect(calls.length).toBeGreaterThanOrEqual(1);
    expect(calls[0]![0]).toEqual({ type: "profile.active" });

    // Find the FILL_REPORT message (sent after the filler resolves).
    const reportCall = calls.find((c) => {
      const arg = c[0] as { type?: string } | null;
      return arg !== null && arg?.type === "FILL_REPORT";
    });
    expect(reportCall).toBeDefined();
    expect(reportCall![0]).toMatchObject({
      type: "FILL_REPORT",
      portal: "amtrust",
      hostname: "producers.amtrustfinancial.com",
    });
  });

  it("does nothing when hostname does not match any known portal", async () => {
    setLocation("example.com");
    stubProfileFetch(sampleProfile());

    await loadDispatcher();

    expect(amtrustFill).not.toHaveBeenCalled();
    expect(appliedEpicFill).not.toHaveBeenCalled();
    expect(markelFill).not.toHaveBeenCalled();

    // Also: no GET_ACTIVE_PROFILE message is sent because detection returns
    // early before the profile fetch.
    const sendMessage = chrome.runtime.sendMessage as unknown as ReturnType<typeof vi.fn>;
    expect(sendMessage).not.toHaveBeenCalled();
  });

  it("skips filler invocation when the vault has no active profile", async () => {
    setLocation("producers.amtrustfinancial.com");
    stubProfileFetch(null);

    await loadDispatcher();

    expect(amtrustFill).not.toHaveBeenCalled();
  });
});
