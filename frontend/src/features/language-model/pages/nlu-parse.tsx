import { useMutation } from "@tanstack/react-query";
import { Loader2, Sparkles } from "lucide-react";
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
import { postNluParse } from "../api";

const textareaClass =
  "flex min-h-[120px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm " +
  "placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring " +
  "disabled:cursor-not-allowed disabled:opacity-50";

export function NluParsePage() {
  const idBase = useId();
  const [utterance, setUtterance] = useState(
    "What is personal relief for the year of assessment?",
  );
  const [topK, setTopK] = useState("8");
  const [intentHint, setIntentHint] = useState("");

  const mutation = useMutation({ mutationFn: postNluParse });

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
      utterance: utterance.trim(),
      top_k,
      intent_hint: intentHint.trim() || null,
    });
  }

  const res = mutation.data;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">NLU parse</h1>
        <p className="text-muted-foreground">
          Calls <code className="rounded bg-muted px-1 text-xs">POST /api/v1/nlu/parse</code> —
          intent (TF-IDF centroid when configured) and retrieval hits over your corpus.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Sparkles className="h-5 w-5" />
            Request
          </CardTitle>
          <CardDescription>
            Set <strong>COMP_LLM_CORPUS_JSONL</strong> and optionally{" "}
            <strong>COMP_LLM_INTENT_BENCHMARK_JSONL</strong> on the language-model process for full
            results. For dense retrieval with a precomputed index, the server may use{" "}
            <strong>COMP_LLM_DENSE_EMBEDDING_BUNDLE_DIR</strong> (optional).
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor={`${idBase}-utt`}>Utterance</Label>
              <textarea
                id={`${idBase}-utt`}
                className={textareaClass}
                value={utterance}
                onChange={(e) => setUtterance(e.target.value)}
                required
              />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
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
              <div className="space-y-2">
                <Label htmlFor={`${idBase}-hint`}>Intent hint (optional)</Label>
                <Input
                  id={`${idBase}-hint`}
                  value={intentHint}
                  onChange={(e) => setIntentHint(e.target.value)}
                  placeholder="Echoed as intent when no classifier"
                />
              </div>
            </div>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Parsing…
                </>
              ) : (
                "Parse"
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
            <CardTitle className="text-lg">Response</CardTitle>
            <CardDescription>
              Model: <code className="text-foreground">{res.model}</code> — corpus loaded:{" "}
              <strong>{res.corpus_loaded ? "yes" : "no"}</strong>
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-2 text-sm sm:grid-cols-2">
              <div>
                <span className="text-muted-foreground">Predicted intent</span>
                <p className="font-medium">{res.predicted_intent ?? "—"}</p>
              </div>
              <div>
                <span className="text-muted-foreground">Intent model</span>
                <p className="font-medium">{res.intent_model ?? "—"}</p>
              </div>
            </div>
            <div>
              <h3 className="mb-2 text-sm font-medium">Retrieval hits</h3>
              {res.retrieval_hits.length === 0 ? (
                <p className="text-sm text-muted-foreground">No hits (stub or empty query).</p>
              ) : (
                <ul className="space-y-3 rounded-md border bg-muted/30 p-3 text-sm">
                  {res.retrieval_hits.map((h) => (
                    <li key={h.chunk_id} className="rounded-md bg-background/50 p-2">
                      <div className="flex justify-between gap-4">
                        <code className="break-all text-xs">{h.chunk_id}</code>
                        <span className="shrink-0 tabular-nums text-muted-foreground">
                          {h.score.toFixed(4)}
                        </span>
                      </div>
                      <KgJoinDetails fields={h} />
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
