/**
 * Tests for popup/screens/Suppliers.
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

vi.mock("../../src/lib/messaging", () => ({
  send: vi.fn(async () => ({ ok: true, supplier_count: 0 })),
}));

import { Suppliers } from "../../src/popup/screens/Suppliers";
import { usePopupStore, __test__ } from "../../src/lib/store";
import type { SupplierListItem } from "../../src/lib/api";

const suppliers: SupplierListItem[] = [
  {
    id: "sup1",
    legal_name: "Acme",
    dba_name: null,
    primary_email: null,
    created_at: "2024-01-01T00:00:00Z",
  },
  {
    id: "sup2",
    legal_name: "Globex",
    dba_name: "Globex Inc",
    primary_email: null,
    created_at: "2024-01-02T00:00:00Z",
  },
];

beforeEach(() => {
  usePopupStore.setState({ ...__test__.initialState, tabId: 7 });
});

describe("Suppliers screen", () => {
  it("renders empty state when no suppliers", () => {
    render(<Suppliers suppliers={[]} onRefreshed={() => undefined} />);
    expect(screen.getByText(/No suppliers yet/)).toBeInTheDocument();
  });

  it("renders supplier names and marks one active on click", () => {
    render(<Suppliers suppliers={suppliers} onRefreshed={() => undefined} />);
    expect(screen.getByText("Acme")).toBeInTheDocument();
    expect(screen.getByText("Globex")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Acme/i }));
    expect(usePopupStore.getState().activeSupplierByTab[7]).toBe("sup1");
  });
});
