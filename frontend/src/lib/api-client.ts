import axios, { type AxiosInstance } from "axios";

const GATEWAY_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

/**
 * Create a typed Axios instance scoped to a component's path prefix on the API gateway.
 *
 * Each component owns its own client under `src/features/<component>/api.ts`
 * so ownership stays clear:
 *
 *   export const api = createApiClient("/api/v1/recommendation");
 */
export function createApiClient(prefix: string): AxiosInstance {
  const baseURL = `${GATEWAY_BASE_URL}${prefix}`;
  const client = axios.create({
    baseURL,
    timeout: 30_000,
    headers: { "Content-Type": "application/json" },
  });

  client.interceptors.response.use(
    (r) => r,
    (error) => {
      const status = error?.response?.status;
      const detail =
        error?.response?.data?.detail ??
        error?.response?.data?.error ??
        error?.message ??
        "Unknown error";
      if (status === 404 && prefix.includes("optimization")) {
        return Promise.reject(
          new Error(
            `${detail} — Tax API route missing. Restart comp-tax-optimization (port 8002) with the latest code. In Vite dev, leave VITE_API_BASE_URL unset so requests proxy to 8002, or ensure the gateway forwards to an updated optimization build.`,
          ),
        );
      }
      return Promise.reject(new Error(detail));
    },
  );

  return client;
}
