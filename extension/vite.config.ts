import { defineConfig } from "vite";
import { fileURLToPath, URL } from "node:url";
import react from "@vitejs/plugin-react";
import { crx } from "@crxjs/vite-plugin";
import manifest from "./manifest.config";
import pkg from "./package.json" with { type: "json" };

export default defineConfig(({ mode }) => ({
  plugins: [react(), crx({ manifest })],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    // Sourcemaps in dev/test only; production zips uploaded to the Web Store
    // must not ship original TypeScript.
    sourcemap: mode !== "production",
    target: "es2022",
    rollupOptions: {
      input: {
        popup: "src/popup/popup.html",
      },
    },
  },
  server: {
    port: 5174,
    strictPort: true,
    hmr: {
      port: 5175,
    },
  },
}));
