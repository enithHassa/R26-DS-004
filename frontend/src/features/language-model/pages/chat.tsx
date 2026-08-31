import { useMutation } from "@tanstack/react-query";
import { Bot, Clock, Loader2, MessageSquare, Plus, Send, Trash2, User } from "lucide-react";
import { useCallback, useRef, useState, useEffect } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import { useUserSessionStore } from "@/features/personalized-recommendation/store/user-session-store";

import {
  deleteSession,
  fetchSuggestions,
  getChatSession,
  listChatSessions,
  postChat,
} from "../api";
import { DomainNotice } from "../components/domain-notice";
import { MarkdownLite } from "../components/markdown-lite";
import { ProofMapPanel } from "../components/proof-map-panel";
import type { ChatResponse, ChatSessionSummary } from "../types";

// ── Types ────────────────────────────────────────────────────────────────────

interface TurnEntry {
  userMessage: string;
  response: ChatResponse;
}

interface HistorySession {
  id: string;
  title: string;
  turns: TurnEntry[];
  timestamp: number;
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function ChatPage() {
  const userId = useUserSessionStore((s) => s.userId);
  const profileId = useUserSessionStore((s) => s.profileId);

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [synthesize, setSynthesize] = useState(true);
  const [yearHint, setYearHint] = useState("");
  const [showProofMap, setShowProofMap] = useState(false);
  const [turns, setTurns] = useState<TurnEntry[]>([]);
  const [history, setHistory] = useState<HistorySession[]>([]);
  const [savedSessions, setSavedSessions] = useState<ChatSessionSummary[]>([]);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const refreshSavedSessions = useCallback(() => {
    if (!userId) {
      setSavedSessions([]);
      return;
    }
    listChatSessions(userId)
      .then(setSavedSessions)
      .catch(() => setSavedSessions([]));
  }, [userId]);

  useEffect(() => {
    refreshSavedSessions();
  }, [refreshSavedSessions]);

  const mutation = useMutation({
    mutationFn: postChat,
    onSuccess(data) {
      setSessionId(data.session_id);
      if (data.persisted) refreshSavedSessions();
      setTurns((prev) => [...prev, { userMessage: data.user_message, response: data }]);
      const inDomain = data.query_result?.domain_status === "in_domain";
      if (inDomain) {
        const answer =
          data.query_result?.plain_answer ||
          data.query_result?.citations?.slice(0, 2).map((c) => c.text).join(" ") ||
          "";
        setSuggestions([]);
        setLoadingSuggestions(true);
        fetchSuggestions(data.user_message, answer).then((s) => {
          setSuggestions(s);
          setLoadingSuggestions(false);
        });
      } else {
        setSuggestions([]);
        setLoadingSuggestions(false);
      }
    },
  });

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, mutation.isPending]);

  const sendMessage = useCallback(
    (msg: string) => {
      if (!msg.trim()) return;
      setInput("");
      mutation.mutate({
        message: msg.trim(),
        session_id: sessionId,
        synthesize_answer: synthesize,
        assessment_year_hint: yearHint.trim() || undefined,
        user_id: userId ?? undefined,
        profile_id: profileId ?? undefined,
      });
    },
    [sessionId, synthesize, yearHint, mutation, userId, profileId],
  );

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      sendMessage(input);
    },
    [input, sendMessage],
  );

  // Start a fresh conversation. Persisted sessions stay in the DB; anonymous
  // sessions are stashed in the local sidebar (and dropped server-side).
  const handleNewSession = useCallback(async () => {
    if (turns.length > 0 && sessionId && !userId) {
      setHistory((prev) => [
        {
          id: sessionId,
          title: turns[0].userMessage.slice(0, 60),
          turns,
          timestamp: Date.now(),
        },
        ...prev.filter((h) => h.id !== sessionId),
      ]);
      try { await deleteSession(sessionId); } catch { /* ignore */ }
    }
    setSessionId(null);
    setTurns([]);
    setSuggestions([]);
    mutation.reset();
    refreshSavedSessions();
  }, [sessionId, turns, mutation, userId, refreshSavedSessions]);

  // Restore a local (anonymous) history session — read-only view.
  const loadHistory = useCallback((session: HistorySession) => {
    setTurns(session.turns);
    setSessionId(session.id);
    mutation.reset();
  }, [mutation]);

  // Resume a DB-saved session for the signed-in user — continue where they left off.
  const resumeSavedSession = useCallback(
    async (summary: ChatSessionSummary) => {
      if (!userId) return;
      try {
        const detail = await getChatSession(summary.session_id, userId);
        const rebuilt: TurnEntry[] = [];
        for (let i = 0; i < detail.messages.length; i++) {
          const m = detail.messages[i];
          if (m.role !== "user") continue;
          const next = detail.messages[i + 1];
          const qr =
            next && next.role === "assistant" && next.query_result ? next.query_result : null;
          rebuilt.push({
            userMessage: m.content,
            response: {
              session_id: detail.session_id,
              turn_index: rebuilt.length,
              user_message: m.content,
              assistant_message: next?.role === "assistant" ? next.content : "",
              query_result: (qr ?? {
                question: m.content,
                top_k: 0,
                citations: [],
                retrieval_model: "restored",
                plain_answer: next?.role === "assistant" ? next.content : null,
              }) as ChatResponse["query_result"],
              proof_map: next?.proof_map ?? null,
              history_length: detail.messages.length,
              taxpayer_context: next?.taxpayer_context ?? null,
              persisted: true,
            },
          });
        }
        setTurns(rebuilt);
        setSessionId(detail.session_id);
        setSuggestions([]);
        mutation.reset();
      } catch {
        /* ignore — session may have been deleted */
      }
    },
    [userId, mutation],
  );

  const removeSavedSession = useCallback(
    async (id: string) => {
      if (!userId) return;
      try { await deleteSession(id, userId); } catch { /* ignore */ }
      if (id === sessionId) {
        setSessionId(null);
        setTurns([]);
      }
      refreshSavedSessions();
    },
    [userId, sessionId, refreshSavedSessions],
  );

  const isEmpty = turns.length === 0 && !mutation.isPending;

  return (
    <div className="flex gap-4 h-full">
      {/* ── Sidebar: chat history ── */}
      <aside className="w-56 shrink-0 flex flex-col gap-2">
        <Button
          variant="outline"
          size="sm"
          className="w-full justify-start gap-2"
          onClick={handleNewSession}
        >
          <Plus className="h-3.5 w-3.5" />
          New session
        </Button>

        <p className="text-xs font-medium text-muted-foreground px-1 pt-1">
          {userId ? "Your saved chats" : "History (this device)"}
        </p>

        {userId ? (
          savedSessions.length === 0 ? (
            <p className="text-xs text-muted-foreground px-1">No saved chats yet</p>
          ) : (
            <ul className="flex flex-col gap-1">
              {savedSessions.map((s) => (
                <li key={s.session_id} className="group relative">
                  <button
                    onClick={() => resumeSavedSession(s)}
                    className={`w-full text-left rounded-md px-2 py-1.5 text-xs hover:bg-muted transition-colors ${
                      s.session_id === sessionId ? "bg-muted" : ""
                    }`}
                  >
                    <div className="flex items-start gap-1.5">
                      <Clock className="h-3 w-3 mt-0.5 shrink-0 text-muted-foreground" />
                      <span className="line-clamp-2 text-muted-foreground leading-snug">
                        {s.title || "Untitled chat"}
                      </span>
                    </div>
                    <p className="text-[10px] text-muted-foreground/60 mt-0.5 pl-4">
                      {s.message_count} message{s.message_count !== 1 ? "s" : ""} ·{" "}
                      {new Date(s.last_message_at).toLocaleDateString()}
                    </p>
                  </button>
                  <button
                    aria-label="Delete chat"
                    onClick={() => removeSavedSession(s.session_id)}
                    className="absolute right-1 top-1 hidden group-hover:block rounded p-1 text-muted-foreground hover:text-destructive"
                  >
                    <Trash2 className="h-3 w-3" />
                  </button>
                </li>
              ))}
            </ul>
          )
        ) : history.length === 0 ? (
          <p className="text-xs text-muted-foreground px-1">
            Sign in to save chats across devices
          </p>
        ) : (
          <ul className="flex flex-col gap-1">
            {history.map((h) => (
              <li key={h.id}>
                <button
                  onClick={() => loadHistory(h)}
                  className="w-full text-left rounded-md px-2 py-1.5 text-xs hover:bg-muted transition-colors"
                >
                  <div className="flex items-start gap-1.5">
                    <Clock className="h-3 w-3 mt-0.5 shrink-0 text-muted-foreground" />
                    <span className="line-clamp-2 text-muted-foreground leading-snug">{h.title}</span>
                  </div>
                  <p className="text-[10px] text-muted-foreground/60 mt-0.5 pl-4">
                    {h.turns.length} turn{h.turns.length !== 1 ? "s" : ""}
                  </p>
                </button>
              </li>
            ))}
          </ul>
        )}
      </aside>

      {/* ── Main chat area ── */}
      <div className="flex flex-col flex-1 gap-4 min-w-0">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Tax advisory chat</h1>
            <p className="text-muted-foreground text-sm">
              Multi-turn conversation grounded in Sri Lankan income-tax law.
            </p>
          </div>
          {sessionId && (
            <p className="text-xs text-muted-foreground shrink-0">
              Session: <span className="font-mono">{sessionId.slice(0, 8)}…</span> · {turns.length} turn
              {turns.length !== 1 ? "s" : ""}
            </p>
          )}
        </div>

        {/* Conversation */}
        <div className="flex flex-col gap-6 min-h-[200px]">
          {isEmpty ? (
            <Card className="flex flex-col items-center justify-center gap-3 py-12 text-center border-dashed">
              <MessageSquare className="h-8 w-8 text-muted-foreground/50" />
              <div>
                <p className="font-medium text-muted-foreground">Ask a tax question to start</p>
                <p className="text-sm text-muted-foreground/70">
                  E.g. "What is personal relief for 2025/26?"
                </p>
              </div>
              {/* Default starter chips */}
              <div className="flex flex-wrap justify-center gap-2 pt-2">
                {[
                  "What is personal relief for 2025/26?",
                  "When is the tax return deadline?",
                  "What is withholding tax on dividends?",
                ].map((s) => (
                  <button
                    key={s}
                    onClick={() => sendMessage(s)}
                    className="rounded-full border border-border px-3 py-1 text-xs text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </Card>
          ) : (
            turns.map((turn, idx) => (
              <TurnBlock
                key={turn.response.session_id + idx}
                turn={turn}
                showProofMap={showProofMap}
                isLast={idx === turns.length - 1}
                suggestions={idx === turns.length - 1 && !mutation.isPending ? suggestions : []}
                loadingSuggestions={idx === turns.length - 1 && !mutation.isPending && loadingSuggestions}
                onSuggestion={sendMessage}
              />
            ))
          )}

          {mutation.isPending && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground pl-1">
              <Loader2 className="h-4 w-4 animate-spin" />
              Thinking…
            </div>
          )}

          {mutation.isError && (
            <p className="text-sm text-destructive" role="alert">
              {mutation.error instanceof Error ? mutation.error.message : "Request failed"}
            </p>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <Card className="sticky bottom-0 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 shadow-md">
          <CardContent className="pt-4">
            <form onSubmit={handleSubmit} className="space-y-3">
              <div className="flex gap-2">
                <Input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Ask a tax question…"
                  disabled={mutation.isPending}
                  className="flex-1"
                  autoFocus
                />
                <Button type="submit" disabled={mutation.isPending || !input.trim()}>
                  {mutation.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Send className="h-4 w-4" />
                  )}
                  <span className="sr-only">Send</span>
                </Button>
              </div>

              <div className="flex flex-wrap items-center gap-4 text-sm">
                <label className="flex items-center gap-2 cursor-pointer">
                  <Checkbox
                    checked={synthesize}
                    onChange={(e) => setSynthesize(e.target.checked)}
                  />
                  <span className="text-muted-foreground">AI plain answer (Gemini)</span>
                </label>

                <label className="flex items-center gap-2 cursor-pointer">
                  <Checkbox
                    checked={showProofMap}
                    onChange={(e) => setShowProofMap(e.target.checked)}
                  />
                  <span className="text-muted-foreground">Show Proof Maps</span>
                </label>

                <div className="flex items-center gap-1.5">
                  <Label htmlFor="year-hint" className="text-muted-foreground whitespace-nowrap">
                    Year hint:
                  </Label>
                  <Input
                    id="year-hint"
                    value={yearHint}
                    onChange={(e) => setYearHint(e.target.value)}
                    placeholder="e.g. 2025_26"
                    className="h-7 w-28 text-xs"
                  />
                </div>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

// ── Individual turn ───────────────────────────────────────────────────────────

function TurnBlock({
  turn,
  showProofMap,
  isLast,
  suggestions,
  loadingSuggestions,
  onSuggestion,
}: {
  turn: TurnEntry;
  showProofMap: boolean;
  isLast: boolean;
  suggestions: string[];
  loadingSuggestions?: boolean;
  onSuggestion: (msg: string) => void;
}) {
  const res = turn.response;
  const qr = res.query_result;
  const blocked = qr.domain_status != null && qr.domain_status !== "in_domain";

  return (
    <div className="space-y-3">
      {/* User bubble */}
      <div className="flex items-start gap-2 justify-end">
        <div className="max-w-[80%] rounded-xl rounded-tr-sm bg-primary px-4 py-2.5 text-sm text-primary-foreground shadow-sm">
          {turn.userMessage}
        </div>
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/20 text-primary">
          <User className="h-4 w-4" />
        </div>
      </div>

      {/* Domain notice */}
      <DomainNotice status={qr.domain_status} message={qr.domain_message} />

      {/* Assistant bubble */}
      <div className="flex items-start gap-2">
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300">
          <Bot className="h-4 w-4" />
        </div>
        <div className="max-w-[85%] space-y-3">
          <div className="rounded-xl rounded-tl-sm border border-border/70 bg-card px-4 py-3 text-sm shadow-sm">
            {!blocked && qr.plain_answer ? (
              <div className="space-y-2">
                <MarkdownLite content={qr.plain_answer} />
                {qr.validation_status && (
                  <p className="text-xs text-muted-foreground">
                    Validation:{" "}
                    <span
                      className={
                        qr.validation_status === "passed"
                          ? "text-emerald-600"
                          : qr.validation_status === "corrected"
                            ? "text-amber-600"
                            : "text-muted-foreground"
                      }
                    >
                      {qr.validation_status}
                    </span>
                  </p>
                )}
              </div>
            ) : blocked ? (
              <p className="text-muted-foreground italic">
                {qr.domain_message ?? "This question appears to be outside the tax domain."}
              </p>
            ) : (
              <CitationSummary citations={qr.citations} />
            )}
          </div>

          {/* Cited sources */}
          {!blocked && qr.citations.length > 0 && (
            <details className="group text-xs">
              <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
                {qr.citations.length} law source{qr.citations.length !== 1 ? "s" : ""} cited — click to view
              </summary>
              <ul className="mt-2 space-y-1.5 pl-2">
                {qr.citations.map((c, i) => (
                  <li key={`${c.chunk_id}-${i}`} className="text-muted-foreground">
                    <span className="font-medium text-foreground">
                      {c.section_label ?? c.source_doc_id ?? c.chunk_id}
                    </span>
                    {c.tier ? (
                      <span className="ml-1 rounded bg-muted px-1 font-mono text-[10px]">
                        Tier {c.tier}
                      </span>
                    ) : null}
                    {c.text && (
                      <p className="mt-0.5 line-clamp-2 leading-relaxed">{c.text}</p>
                    )}
                  </li>
                ))}
              </ul>
            </details>
          )}

          {/* AI-generated suggested next questions — only on last turn */}
          {isLast && !blocked && loadingSuggestions && (
            <div className="flex items-center gap-2 pt-1 text-xs text-muted-foreground">
              <Loader2 className="h-3 w-3 animate-spin" />
              Generating suggested questions…
            </div>
          )}
          {isLast && !blocked && !loadingSuggestions && suggestions.length > 0 && (
            <div className="space-y-1 pt-1">
              <p className="text-xs text-muted-foreground">Suggested follow-up questions:</p>
              <div className="flex flex-wrap gap-2">
                {suggestions.map((s) => (
                  <button
                    key={s}
                    onClick={() => onSuggestion(s)}
                    className="rounded-full border border-border px-3 py-1 text-xs text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Proof Map */}
      {showProofMap && res.proof_map && (
        <div className="pl-9">
          <ProofMapPanel proofMap={res.proof_map} />
        </div>
      )}
    </div>
  );
}

function CitationSummary({
  citations,
}: {
  citations: {
    chunk_id: string;
    score: number;
    text?: string;
    section_label?: string | null;
    source_doc_id?: string | null;
  }[];
}) {
  if (citations.length === 0) {
    return (
      <p className="text-muted-foreground">
        No relevant law excerpts found. The corpus may not be loaded on the server.
      </p>
    );
  }
  const top = citations[0];
  return (
    <div className="space-y-1">
      <p className="text-muted-foreground text-xs">
        Top match:{" "}
        <span className="font-medium text-foreground">
          {top.section_label ?? top.source_doc_id ?? top.chunk_id}
        </span>
      </p>
      {top.text && <p className="leading-relaxed line-clamp-4">{top.text}</p>}
      {citations.length > 1 && (
        <p className="text-xs text-muted-foreground">
          +{citations.length - 1} more source{citations.length > 2 ? "s" : ""}
        </p>
      )}
    </div>
  );
}
