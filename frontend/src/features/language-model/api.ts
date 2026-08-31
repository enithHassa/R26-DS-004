import { createApiClient } from "@/lib/api-client";

import type {
  ChatRequest,
  ChatResponse,
  ChatSessionDetail,
  ChatSessionSummary,
  NLUParseRequest,
  NLUParseResponse,
  QueryRequest,
  QueryResponse,
} from "./types";

/**
 * Language model (Component 4) via API gateway.
 * Browser calls `/api/v1/llm/...` — Vite proxies `/api` to the gateway.
 */
// Chat turns run retrieval + KG enrichment + Gemini synthesis (with one retry)
// server-side, which can take well over the 30s default. Give this client more room.
export const languageModelApi = createApiClient("/api/v1/llm", { timeoutMs: 90_000 });

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

export async function deleteSession(sessionId: string, userId?: string | null): Promise<void> {
  await languageModelApi.delete(`/chat/sessions/${sessionId}`, {
    params: userId ? { user_id: userId } : undefined,
  });
}

/** List the signed-in user's saved chat sessions (most recent first). */
export async function listChatSessions(
  userId: string,
  includeArchived = false,
): Promise<ChatSessionSummary[]> {
  const { data } = await languageModelApi.get<{ sessions: ChatSessionSummary[] }>(
    "/chat/sessions",
    { params: { user_id: userId, include_archived: includeArchived } },
  );
  return data.sessions ?? [];
}

/** Fetch one saved session's full message history so the user can resume it. */
export async function getChatSession(
  sessionId: string,
  userId: string,
): Promise<ChatSessionDetail> {
  const { data } = await languageModelApi.get<ChatSessionDetail>(
    `/chat/sessions/${sessionId}`,
    { params: { user_id: userId } },
  );
  return data;
}

export async function renameChatSession(
  sessionId: string,
  userId: string,
  title: string,
): Promise<void> {
  await languageModelApi.patch(`/chat/sessions/${sessionId}`, { user_id: userId, title });
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
