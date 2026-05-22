/**
 * Popup entry point. Boots React 18 + TanStack Query and mounts <App /> with
 * a global react-hot-toast Toaster.
 */
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "react-hot-toast";

import { App } from "./App";
import "./popup.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      gcTime: 5 * 60_000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
    mutations: {
      retry: 0,
    },
  },
});

function mount(): void {
  const host = document.getElementById("root");
  if (!host) {
    throw new Error("popup: #root element not found");
  }
  const root = createRoot(host);
  root.render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <App />
        <Toaster
          position="bottom-center"
          toastOptions={{
            duration: 3500,
            style: {
              fontSize: "12px",
              padding: "6px 10px",
              borderRadius: "6px",
            },
          }}
        />
      </QueryClientProvider>
    </StrictMode>,
  );
}

mount();
