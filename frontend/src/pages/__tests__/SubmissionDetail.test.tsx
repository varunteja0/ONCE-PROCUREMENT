import { renderWithProviders } from "@/test/utils";
import type { Submission } from "@/types/api";
import type * as ReactRouter from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

const COMPLETED_SUBMISSION: Submission = {
  id: "sub_00000000000000000000000000000001",
  tenant_id: "ten_00000000000000000000000000000001",
  supplier_id: "sup_00000000000000000000000000000001",
  portal_id: "por_00000000000000000000000000000001",
  status: "completed",
  payload_json: {},
  result_json: null,
  attempt_count: 1,
  last_error: null,
  claimed_at: null,
  started_at: "2026-01-01T00:00:00Z",
  completed_at: "2026-01-01T00:00:05Z",
  consent_record_id: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:05Z",
};

vi.mock("@/hooks/useSubmissions", () => ({
  useSubmission: () => ({
    data: COMPLETED_SUBMISSION,
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
  useSubmissionReceipt: () => ({
    data: undefined,
    isLoading: false,
    error: null,
  }),
  useRetrySubmission: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof ReactRouter>("react-router-dom");
  return {
    ...actual,
    useParams: () => ({ id: COMPLETED_SUBMISSION.id }),
    useNavigate: () => vi.fn(),
  };
});

vi.mock("@/components/ReceiptVerifierWidget", () => ({
  default: () => null,
}));

vi.mock("@/lib/toast", () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
  default: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}));

import SubmissionDetail from "@/pages/SubmissionDetail";

describe("SubmissionDetail page", () => {
  it("renders the status badge for a completed submission", () => {
    renderWithProviders(<SubmissionDetail />);

    // The StatusBadge component renders `data-status="<status>"`.
    const badge = document.querySelector('[data-status="completed"]');
    expect(badge).not.toBeNull();
    expect(badge?.textContent ?? "").toMatch(/completed/i);
  });
});
