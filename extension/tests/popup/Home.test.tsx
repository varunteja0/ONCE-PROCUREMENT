/**
 * Tests for popup/screens/Home.
 *
 * Covers: detected portal rendering + clicking Fill calls sendToTab
 * with the content.fill payload built from the unlocked vault profile.
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

const sendToTab = vi.fn();
const sendBg = vi.fn();
vi.mock("../../src/lib/messaging", () => ({
  send: (...a: unknown[]) => sendBg(...a),
  sendToTab: (...a: unknown[]) => sendToTab(...a),
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
  id: "sup1",
  legal_name: "Acme Insurance Co",
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
  sendToTab.mockReset();
  sendBg.mockReset();
  getProfile.mockReset();
});

describe("Home screen", () => {
  it("renders the detected portal and confidence", () => {
    render(<Home suppliers={[supplier]} detection={detection} />);
    expect(screen.getByText(/applied_epic/)).toBeInTheDocument();
    expect(screen.getByTestId("confidence")).toHaveTextContent("95%");
  });

  it("clicking Fill loads the profile and sends content.fill to the tab", async () => {
    getProfile.mockResolvedValue({ legal_name: "Acme Insurance Co" });
    sendToTab.mockResolvedValue({ ok: true, filled: 3, skipped: 1 });
    sendBg.mockResolvedValue({ ok: true, filled: 3, skipped: 1 });

    render(<Home suppliers={[supplier]} detection={detection} />);
    // default-select effect runs; click Fill.
    fireEvent.click(screen.getByRole("button", { name: /Fill from supplier/i }));

    await waitFor(() => {
      expect(sendToTab).toHaveBeenCalledTimes(1);
    });
    const [tabId, msg] = sendToTab.mock.calls[0] as [number, { type: string; portal: string }];
    expect(tabId).toBe(11);
    expect(msg.type).toBe("content.fill");
    expect(msg.portal).toBe("applied_epic");
  });
});
