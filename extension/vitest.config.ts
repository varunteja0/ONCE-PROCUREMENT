import { defineConfig } from "vitest/config";
import { fileURLToPath, URL } from "node:url";

export default defineConfig({
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  define: {
    __APP_VERSION__: JSON.stringify("0.1.0-test"),
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    include: ["tests/**/*.test.ts", "tests/**/*.test.tsx", "src/**/*.test.ts", "src/**/*.test.tsx"],
    css: false,
    clearMocks: true,
    restoreMocks: true,
    coverage: {
      reporter: ["text", "html"],
    },
  },
});
