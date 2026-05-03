import { createApiClient } from "@/lib/api-client";

/**
 * Axios client for Component 3 endpoints.
 *
 * Base URL = `<gateway>/api/v1/recommendation`. The gateway strips this
 * prefix and forwards `/<path>` to the component's own `/api/v1/<path>`
 * route, so here you just call `recommendationApi.post("/profiles", ...)`.
 */
export const recommendationApi = createApiClient("/api/v1/recommendation");

export type UUID = string;
