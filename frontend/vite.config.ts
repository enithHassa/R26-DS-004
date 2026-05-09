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
  /** Personalized recommendation service (Component 3). Direct proxy avoids needing the gateway running. */
  const recommendationUrl =
    env.VITE_DEV_RECOMMENDATION_URL?.trim() || "http://127.0.0.1:8003";

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
    server: {
      port: 5173,
      /** Strategy explorer (Component B) — primary dissertation UI for this module. */
      open: "/tax-optimization/explorer",
      proxy: {
        // Longer prefix first: hit Component B directly so new routes work without restarting the gateway.
        // Strips the gateway-only ``/optimization`` segment (upstream app mounts at ``/api/v1/compliance/...``).
        // Hit Component 3 directly — strips /recommendation so upstream sees /api/v1/profiles etc.
        "/api/v1/recommendation": {
          target: recommendationUrl,
          changeOrigin: true,
          rewrite: (p) => p.replace(/^\/api\/v1\/recommendation/, "/api/v1"),
        },
        "/api/v1/optimization": {
          target: optimizationUrl,
          changeOrigin: true,
          /** ML ranking can run >30s; align with axios timeout on `postSearchStrategiesMlRank`. */
          timeout: 180_000,
          proxyTimeout: 180_000,
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
