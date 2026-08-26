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
  /** Adaptive Tax service (Component 5). Direct proxy avoids needing the gateway running. */
  const adaptiveTaxUrl =
    env.VITE_DEV_ADAPTIVE_TAX_URL?.trim() || "http://127.0.0.1:8005";
  /** Optimization and Explainable. Direct proxy avoids needing the gateway running. */
  const optimizationExplainableUrl =
    env.VITE_DEV_OPTIMIZATION_EXPLAINABLE_URL?.trim() || "http://127.0.0.1:8008";
  /** Transaction semantic service (Component 1). Rewrites /api/v1 → /v1 on the service. */
  const transactionSemanticUrl =
    env.VITE_DEV_TRANSACTION_SEMANTIC_URL?.trim() || "http://127.0.0.1:8001";
  const transactionSemanticProxy = {
    target: transactionSemanticUrl,
    changeOrigin: true,
    timeout: 300_000,
    proxyTimeout: 300_000,
    rewrite: (p: string) => p.replace(/^\/api\/v1/, "/v1"),
  };

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
    server: {
      // Windows often binds Vite to IPv6 ::1 only; the runbook URL is 127.0.0.1.
      host: "127.0.0.1",
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
        // Account auth on the gateway (shared users table) — do not route via Comp 3.
        "/api/v1/auth": {
          target: gatewayUrl,
          changeOrigin: true,
        },
        // Hit Adaptive Tax directly — Catalog Admin must not depend on the gateway (:8000).
        "/api/v1/adaptive-tax": {
          target: adaptiveTaxUrl,
          changeOrigin: true,
          /** GPT-5 extract/approve can take several minutes; keep in sync with axios timeouts. */
          timeout: 300_000,
          proxyTimeout: 300_000,
          rewrite: (p) => p.replace(/^\/api\/v1\/adaptive-tax/, "/api/v1"),
        },
        // Longer than /api/v1/optimization so this is not stolen by Component B.
        "/api/v1/optimization-explainable": {
          target: optimizationExplainableUrl,
          changeOrigin: true,
          rewrite: (p) => p.replace(/^\/api\/v1\/optimization-explainable/, "/api/v1"),
        },
        "/api/v1/optimization": {
          target: optimizationUrl,
          changeOrigin: true,
          /** ML ranking can run >30s; align with axios timeout on `postSearchStrategiesMlRank`. */
          timeout: 180_000,
          proxyTimeout: 180_000,
          rewrite: (p) => p.replace(/^\/api\/v1\/optimization/, "/api/v1"),
        },
        "/api/v1/documents": transactionSemanticProxy,
        "/api/v1/transactions": transactionSemanticProxy,
        "/api/v1/taxonomy": transactionSemanticProxy,
        "/api/v1/taxable-income": transactionSemanticProxy,
        "/api": {
          target: gatewayUrl,
          changeOrigin: true,
        },
      },
    },
  };
});
