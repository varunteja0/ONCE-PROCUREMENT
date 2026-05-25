import react from "@vitejs/plugin-react";
import path from "node:path";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/v1": {
        target: "http://localhost:8000",
        changeOrigin: true,
        secure: false,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
    target: "es2022",
    chunkSizeWarningLimit: 500,
    rollupOptions: {
      output: {
        manualChunks: {
          "vendor-react": ["react", "react-dom", "react-router-dom"],
          "vendor-query": ["@tanstack/react-query"],
          "vendor-forms": ["react-hook-form", "zod", "@hookform/resolvers/zod"],
          "vendor-ui": ["lucide-react", "sonner", "clsx"],
        },
      },
    },
  },
  // To inspect bundle composition, install `rollup-plugin-visualizer` and
  // enable here:
  //   import { visualizer } from 'rollup-plugin-visualizer';
  //   plugins: [react(), visualizer({ filename: 'dist/stats.html', open: true })],
});
