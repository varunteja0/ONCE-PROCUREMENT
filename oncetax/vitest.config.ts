import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    include: ["*.test.ts", "tests/**/*.test.ts"],
    globals: false,
    testTimeout: 10_000,
  },
});
