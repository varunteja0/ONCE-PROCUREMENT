import { consentsApi, type ConsentsListParams } from "@/api/consents";
import { useConsents } from "@/hooks/useConsents";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { type ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/api/consents", () => ({
  consentsApi: {
    list: vi.fn(),
    get: vi.fn(),
  },
}));

function makeWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return function Wrapper({ children }: { children: ReactNode }): JSX.Element {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

describe("useConsents", () => {
  it("does not call the API when disabled", () => {
    const list = vi.mocked(consentsApi.list);
    list.mockReset();

    const { result } = renderHook(() => useConsents({ supplier_id: "supplier-1" }, { enabled: false }), {
      wrapper: makeWrapper(),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(list).not.toHaveBeenCalled();
  });

  it("passes supplier and active filters through to the API client", async () => {
    const list = vi.mocked(consentsApi.list);
    const params: ConsentsListParams = {
      supplier_id: "supplier-1",
      active_only: true,
    };
    list.mockReset();
    list.mockResolvedValueOnce({ items: [], total: 0, limit: 100, offset: 0 });

    const { result } = renderHook(() => useConsents(params), {
      wrapper: makeWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(list).toHaveBeenCalledWith(params);
  });
});
