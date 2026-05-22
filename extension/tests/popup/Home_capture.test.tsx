/**
 * Tests for popup/screens/Home — onCapture round-trip:
 *  - resolves portal_id from the cached portals list
 *  - resolves the active consent_record_id from the backend
 *  - sends `submission.capture` with the canonical payload shape
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const send = vi.fn();
const sendToTab = vi.fn();
vi.mock("../../src/lib/messaging", () => ({
  send: (...a: unknown[]) => send(...a),
  sendToTab: (...a: unknown[]) => sendToTab(...a),
}));

const getCachedPortals = vi.fn();
vi.mock("../../src/lib/sync", () => ({
  getCachedPortals: (...a: unknown[]) => getCachedPortals(...a),
}));

const getConsentForPortal = vi.fn();
vi.mock("../../src/lib/api", () => ({
  getConsentForPortal: (...a: unknown[]) => getConsentForPortal(...a),
}));

const getProfile = vi.fn();
vi.mock("../../src/lib/vault", () => ({
  getProfile: (...a: unknown[]) => getProfile(...a),
}));

import { Home } from "../../src/popup/screens/Home";
import { usePopupStore, __test__ } from "../../src/lib/store";
import type { SupplierListItem } from "../../src/lib/api";
import type { PortalDetection } from "../../src/lib/messaging";

const supplier: SupplierListItem = {
  id: "sup-1",
  legal_name: "Acme",
  dba_name: null,
  primary_email: null,
  created_at: "2024-01-01T00:00:00Z",
};

const detection: PortalDetection = {
  portal: "applied_epic",
  hostname: "app.appliedepic.com",
  url: "https://app.appliedepic.com/intake",
  confidence: 0.95,
  html_hash: "abcd1234",
};

beforeEach(() => {
  usePopupStore.setState({ ...__test__.initialState, tabId: 11 });
  send.mockReset();
  sendToTab.mockReset();
  getCachedPortals.mockReset();
  getConsentForPortal.mockReset();
  getProfile.mockReset();
});

describe("Home onCapture", () => {
  it("resolves portal + consent and sends submission.capture", async () => {
    getCachedPortals.mockResolvedValue([
      { id: "p-applied", platform: "applied_epic", display_name: "AE" },
    ]);
    getConsentForPortal.mockResolvedValue({ id: "c-123" });
    send.mockResolvedValue({ ok: true, id: "sub-12345678" });

    render(<Home suppliers={[supplier]} detection={detection} />);
    fireEvent.click(
      screen.getByRole("button", { name: /Capture this submission/i }),
    );

    await waitFor(() => {
      expect(send).toHaveBeenCalledTimes(1);
    });
    expect(getConsentForPortal).toHaveBeenCalledWith("sup-1", "p-applied");

    const [msg] = send.mock.calls[0] as [
      { type: string; payload: Record<string, unknown> },
    ];
    expect(msg.type).toBe("submission.capture");
    expect(msg.payload.supplier_id).toBe("sup-1");
    expect(msg.payload.portal_id).toBe("p-applied");
    expect(msg.payload.consent_record_id).toBe("c-123");
    expect((msg.payload.payload as { url: string }).url).toBe(detection.url);
  });

  it("blocks capture when no consent exists", async () => {
    getCachedPortals.mockResolvedValue([
      { id: "p-applied", platform: "applied_epic", display_name: "AE" },
    ]);
    getConsentForPortal.mockResolvedValue(null);

    render(<Home suppliers={[supplier]} detection={detection} />);
    fireEvent.click(
      screen.getByRole("button", { name: /Capture this submission/i }),
    );

    await waitFor(() => {
      expect(getConsentForPortal).toHaveBeenCalled();
    });
    expect(send).not.toHaveBeenCalled();
  });

  it("blocks capture when the portal is missing from the cache", async () => {
    getCachedPortals.mockResolvedValue([]);

    render(<Home suppliers={[supplier]} detection={detection} />);
    fireEvent.click(
      screen.getByRole("button", { name: /Capture this submission/i }),
    );

    await waitFor(() => {
      expect(getCachedPortals).toHaveBeenCalled();
    });
    expect(getConsentForPortal).not.toHaveBeenCalled();
    expect(send).not.toHaveBeenCalled();
  });
});
