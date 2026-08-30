import { createApiClient } from "@/lib/api-client";

import type {
  ChatRequest,
  ChatResponse,
  NLUParseRequest,
  NLUParseResponse,
  QueryRequest,
  QueryResponse,
} from "./types";

/**
 * Language model (Component 4) via API gateway.
 * Browser calls `/api/v1/llm/...` — Vite proxies `/api` to the gateway.
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

export async function postChat(body: ChatRequest): Promise<ChatResponse> {
  const { data } = await languageModelApi.post<ChatResponse>("/chat", body);
  return data;
}

export async function deleteSession(sessionId: string): Promise<void> {
  await languageModelApi.delete(`/chat/sessions/${sessionId}`);
}

export async function fetchSuggestions(question: string, answer: string): Promise<string[]> {
  try {
    const { data } = await languageModelApi.post<{ suggestions: string[] }>("/chat/suggestions", {
      question,
      answer,
    });
    return data.suggestions ?? [];
  } catch {
    return [];
  }
}
