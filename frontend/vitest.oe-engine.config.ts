import path from "node:path";
import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const root = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(root, "./src"),
    },
  },
  test: {
    environment: "jsdom",
    pool: "forks",
    fileParallelism: false,
    isolate: true,
    include: ["src/features/optimization-explainable-engine/**/*.test.{ts,tsx}"],
    setupFiles: ["src/features/optimization-explainable-engine/test-setup.ts"],
  },
});
