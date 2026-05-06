import path from "node:path";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  // Empty string in .env would bypass ?? and break the proxy target.
  const gatewayUrl =
    env.VITE_API_BASE_URL?.trim() || "http://127.0.0.1:8000";
  /** Tax optimization service (Component B). Used when the browser hits relative `/api/v1/optimization/...` through Vite. */
  const optimizationUrl =
    env.VITE_DEV_OPTIMIZATION_URL?.trim() || "http://127.0.0.1:8002";

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
    server: {
      port: 5173,
      proxy: {
        // Longer prefix first: hit Component B directly so new routes work without restarting the gateway.
        // Strips the gateway-only ``/optimization`` segment (upstream app mounts at ``/api/v1/compliance/...``).
        "/api/v1/optimization": {
          target: optimizationUrl,
          changeOrigin: true,
          rewrite: (p) => p.replace(/^\/api\/v1\/optimization/, "/api/v1"),
        },
        "/api": {
          target: gatewayUrl,
          changeOrigin: true,
        },
      },
    },
  };
});
