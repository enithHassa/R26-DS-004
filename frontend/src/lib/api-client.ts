import axios, { type AxiosInstance, isAxiosError } from "axios";

const GATEWAY_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

function formatAxiosError(error: unknown, apiPrefix: string): string {
  if (!isAxiosError(error)) {
    return error instanceof Error ? error.message : String(error);
  }

  const status = error.response?.status;
  const data = error.response?.data as unknown;

  if (data && typeof data === "object" && "detail" in data) {
    const raw = (data as { detail: unknown }).detail;
    let message: string;
    if (typeof raw === "string") {
      message = raw;
    } else if (Array.isArray(raw)) {
      message = raw
        .map((item) =>
          typeof item === "object" && item !== null && "msg" in item
            ? String((item as { msg: unknown }).msg)
            : JSON.stringify(item),
        )
        .join("; ");
    } else {
      try {
        message = JSON.stringify(raw);
      } catch {
        message = String(raw);
      }
    }
    if (status === 404 && apiPrefix.includes("optimization")) {
      return `${message} — Tax API route missing. Restart comp-tax-optimization (port 8002) with the latest code. In Vite dev, leave VITE_API_BASE_URL unset so requests proxy to 8002, or ensure the gateway forwards to an updated optimization build.`;
    }
    return status ? `${message} (HTTP ${status})` : message;
  }

  if (typeof data === "string" && data.length > 0) {
    const clipped = data.length > 800 ? `${data.slice(0, 800)}…` : data;
    return status ? `${clipped} (HTTP ${status})` : clipped;
  }

  if (data !== undefined && data !== null && typeof data === "object") {
    try {
      const s = JSON.stringify(data);
      const clipped = s.length > 800 ? `${s.slice(0, 800)}…` : s;
      return status ? `${clipped} (HTTP ${status})` : clipped;
    } catch {
      /* fall through */
    }
  }

  const base = error.message || "Request failed";
  return status ? `${base} (HTTP ${status})` : base;
}

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
    (error) => Promise.reject(new Error(formatAxiosError(error, prefix))),
  );

  return client;
}
