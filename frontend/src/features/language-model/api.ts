import { createApiClient } from "@/lib/api-client";

import type { NLUParseRequest, NLUParseResponse, QueryRequest, QueryResponse } from "./types";

/**
 * Language model (Component 4) via API gateway.
 *
 * Browser calls `/api/v1/llm/...` — Vite proxies `/api` to the gateway; the gateway
 * forwards to `COMP_LLM_URL` as `/api/v1/...`.
 */
export const languageModelApi = createApiClient("/api/v1/llm");

export async function postNluParse(body: NLUParseRequest): Promise<NLUParseResponse> {
  const { data } = await languageModelApi.post<NLUParseResponse>("/nlu/parse", body);
  return data;
}

export async function postQuery(body: QueryRequest): Promise<QueryResponse> {
  const { data } = await languageModelApi.post<QueryResponse>("/query", body);
  return data;
}
