/**
 * Tests for popup/screens/Receipts — rendering + verify link.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

const listReceipts = vi.fn();
vi.mock("../../src/lib/api", () => ({
  listReceipts: (...a: unknown[]) => listReceipts(...a),
}));

import { Receipts } from "../../src/popup/screens/Receipts";
import type { ReceiptListItem } from "../../src/lib/api";

function mk(id: string, overrides: Partial<ReceiptListItem> = {}): ReceiptListItem {
  return {
    id,
    tenant_id: "t1",
    supplier_id: "sup-1",
    submission_id: `sub-${id}`,
    portal_platform: "applied_epic",
    payload_hash: "hash",
    tos_version_hash: "abc123",
    consent_record_id: "consent-1",
    signing_key_id: "key-1",
    signature_b64: "sig",
    submitted_at: "2024-05-01T12:00:00Z",
    public_payload_json: {},
    verify_url: `https://verify.example.com/${id}`,
    created_at: "2024-05-01T12:00:00Z",
    updated_at: "2024-05-01T12:00:00Z",
    ...overrides,
  };
}

beforeEach(() => {
  listReceipts.mockReset();
});

describe("Receipts screen", () => {
  it("renders the empty state when there are no receipts", async () => {
    listReceipts.mockResolvedValue([]);
    render(<Receipts />);
    await waitFor(() => {
      expect(screen.getByText(/No receipts yet/i)).toBeInTheDocument();
    });
  });

  it("renders receipt rows and a Verify button", async () => {
    listReceipts.mockResolvedValue([mk("rcpt-aaaaaaaa")]);
    render(<Receipts />);
    await waitFor(() => {
      expect(screen.getByText(/applied_epic/)).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: /Verify receipt/i })).toBeInTheDocument();
  });

  it("caps the list at 10 entries", async () => {
    listReceipts.mockResolvedValue(
      Array.from({ length: 25 }, (_, i) => mk(`r${i.toString().padStart(8, "0")}`)),
    );
    const { container } = render(<Receipts />);
    await waitFor(() => {
      expect(container.querySelectorAll("ul li").length).toBe(10);
    });
  });
});
