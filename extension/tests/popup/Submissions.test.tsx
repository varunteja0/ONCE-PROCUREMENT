/**
 * Tests for popup/screens/Submissions.
 */
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { Submissions } from "../../src/popup/screens/Submissions";
import type { SubmissionListItem } from "../../src/lib/api";

function mk(id: string, status: SubmissionListItem["status"]): SubmissionListItem {
  return {
    id,
    supplier_id: "sup-abc12345",
    portal_id: "applied_epic",
    status,
    attempt_count: 0,
    last_error: null,
    completed_at: null,
    updated_at: new Date().toISOString(),
    created_at: new Date().toISOString(),
  };
}

describe("Submissions screen", () => {
  it("renders empty state when there are no submissions", () => {
    render(<Submissions submissions={[]} />);
    expect(screen.getByText(/No submissions yet/)).toBeInTheDocument();
  });

  it("caps the list at 10 entries", () => {
    const items: SubmissionListItem[] = Array.from({ length: 25 }, (_, i) =>
      mk(`sub${i.toString().padStart(8, "0")}`, "completed"),
    );
    const { container } = render(<Submissions submissions={items} />);
    const rows = container.querySelectorAll("ul li");
    expect(rows.length).toBe(10);
  });

  it("applies the matching status pill class", () => {
    render(<Submissions submissions={[mk("aabbccddeeff", "failed")]} />);
    const pill = screen.getByText("failed");
    expect(pill.className).toContain("pill-failed");
  });
});
