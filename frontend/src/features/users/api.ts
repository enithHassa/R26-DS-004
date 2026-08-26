import { createApiClient } from "@/lib/api-client";

/** Account auth on the API gateway (`:8000`) — no Comp 3 required. */
export const authApi = createApiClient("/api/v1/auth");
