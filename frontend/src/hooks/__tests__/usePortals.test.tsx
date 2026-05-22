import { usePortals } from "@/hooks/usePortals";
import { api } from "@/services/api";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { type ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/services/api", () => ({
  api: {
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

describe("usePortals", () => {
  it("uses the backend is_supported query parameter for supportedOnly", async () => {
    const get = vi.mocked(api.get);
    get.mockReset();
    get.mockResolvedValueOnce({ data: { items: [], total: 0 } });

    const { result } = renderHook(() => usePortals({ supportedOnly: true }), {
      wrapper: makeWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(get).toHaveBeenCalledWith("/portals", {
      params: {
        is_supported: true,
        search: undefined,
        limit: 100,
        offset: 0,
      },
    });
  });
});
