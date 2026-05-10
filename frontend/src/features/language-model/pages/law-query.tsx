import { useMutation } from "@tanstack/react-query";
import { BookOpen, Loader2 } from "lucide-react";
import { useId, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import { KgJoinDetails } from "../components/kg-join-details";
import { postQuery } from "../api";

const textareaClass =
  "flex min-h-[120px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm " +
  "placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring " +
  "disabled:cursor-not-allowed disabled:opacity-50";

export function LawQueryPage() {
  const idBase = useId();
  const [question, setQuestion] = useState(
    "What are the rules for personal relief in Sri Lanka?",
  );
  const [topK, setTopK] = useState("8");

  const mutation = useMutation({ mutationFn: postQuery });

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    let top_k: number | undefined;
    if (topK.trim()) {
      const parsed = Number.parseInt(topK, 10);
      if (Number.isFinite(parsed) && parsed >= 1 && parsed <= 50) {
        top_k = parsed;
      }
    }
    mutation.mutate({
      question: question.trim(),
      top_k,
    });
  }

  const res = mutation.data;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Law-grounded query</h1>
        <p className="text-muted-foreground">
          Calls <code className="rounded bg-muted px-1 text-xs">POST /api/v1/query</code> —
          ranked citations with excerpted chunk text from the corpus (no generative answer).
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <BookOpen className="h-5 w-5" />
            Request
          </CardTitle>
          <CardDescription>
            Requires the same <strong>COMP_LLM_CORPUS_JSONL</strong> as retrieval; excerpts respect{" "}
            <strong>COMP_LLM_QUERY_CITATION_MAX_CHARS</strong> on the server. When corpus rows
            include document metadata, citations may show <strong>source_doc_id</strong> /{" "}
            <strong>section_uid</strong> for graph alignment.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor={`${idBase}-q`}>Question</Label>
              <textarea
                id={`${idBase}-q`}
                className={textareaClass}
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2 sm:max-w-xs">
              <Label htmlFor={`${idBase}-k`}>Top-k (optional)</Label>
              <Input
                id={`${idBase}-k`}
                type="number"
                min={1}
                max={50}
                value={topK}
                onChange={(e) => setTopK(e.target.value)}
              />
            </div>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Retrieving…
                </>
              ) : (
                "Retrieve citations"
              )}
            </Button>
          </form>

          {mutation.isError ? (
            <p className="mt-4 text-sm text-destructive" role="alert">
              {mutation.error instanceof Error ? mutation.error.message : String(mutation.error)}
            </p>
          ) : null}
        </CardContent>
      </Card>

      {res ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Citations</CardTitle>
            <CardDescription>
              Retrieval: <code className="text-foreground">{res.retrieval_model}</code> — top_k:{" "}
              {res.top_k}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {res.citations.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No citations (corpus/index not loaded on the server).
              </p>
            ) : (
              res.citations.map((c, i) => (
                <article
                  key={`${c.chunk_id}-${i}`}
                  className="rounded-lg border bg-card p-4 text-sm shadow-sm"
                >
                  <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
                    <code className="text-xs font-medium text-foreground">{c.chunk_id}</code>
                    <span className="tabular-nums text-muted-foreground">{c.score.toFixed(4)}</span>
                  </div>
                  <KgJoinDetails fields={c} />
                  <p className="mt-2 whitespace-pre-wrap text-muted-foreground">{c.text || "—"}</p>
                </article>
              ))
            )}
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
