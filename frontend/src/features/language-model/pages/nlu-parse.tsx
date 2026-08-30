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

import { DomainNotice } from "../components/domain-notice";
import { GraphContextPanel } from "../components/graph-context-panel";
import { anchorsFromRetrievalHits } from "../components/graph-source-anchor";
import { intentLabel, retrievalModelLabel } from "../components/language-model-display";
import { RetrievalResultCard } from "../components/retrieval-result-card";
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
  const graphAnchors = res ? anchorsFromRetrievalHits(res.retrieval_hits) : [];
  const blocked = res?.domain_status != null && res.domain_status !== "in_domain";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">NLU parse</h1>
        <p className="text-muted-foreground">
          Understand the likely topic behind a question and see which legal sources the system would
          retrieve before reading full excerpts.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Sparkles className="h-5 w-5" />
            Ask a question
          </CardTitle>
          <CardDescription>
            Enter a tax question in everyday language. Optional fields let you limit how many sources
            are returned or provide an intent hint for routing.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor={`${idBase}-utt`}>Your question</Label>
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
                <Label htmlFor={`${idBase}-k`}>Number of sources (optional)</Label>
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
                  placeholder="Used when no classifier is configured"
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
                "Parse question"
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
        <>
          <DomainNotice status={res.domain_status} message={res.domain_message} />

          {blocked ? null : (
          <Card className="overflow-hidden rounded-xl border border-border/80 shadow-sm">
            <div className="h-1 w-full bg-gradient-to-r from-primary/70 to-emerald-600/60" aria-hidden />
            <CardHeader>
              <CardTitle className="text-lg">What we understood</CardTitle>
              <CardDescription>
                Plain-language summary of how the system interpreted your question and which sources
                it matched.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="rounded-xl border border-border/70 bg-muted/15 p-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Your question
                </p>
                <p className="mt-2 text-sm leading-relaxed text-foreground">{res.utterance}</p>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="rounded-xl border border-border/70 bg-card p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    Likely topic
                  </p>
                  <p className="mt-2 text-base font-semibold text-foreground">
                    {intentLabel(res.predicted_intent ?? res.intent)}
                  </p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {res.predicted_intent || res.intent
                      ? "This is the closest intent label from the configured classifier."
                      : "No intent classifier result was available for this request."}
                  </p>
                </div>
                <div className="rounded-xl border border-border/70 bg-card p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    Search method
                  </p>
                  <p className="mt-2 text-base font-semibold text-foreground">
                    {retrievalModelLabel(res.model)}
                  </p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Corpus loaded: {res.corpus_loaded ? "yes" : "no"}
                    {res.intent_model ? ` · Intent model: ${res.intent_model}` : ""}
                  </p>
                </div>
              </div>

              <div className="space-y-3">
                <div>
                  <h3 className="text-base font-semibold">Matched sources</h3>
                  <p className="text-sm text-muted-foreground">
                    Ranked document sections that best match your question.
                  </p>
                </div>
                {res.retrieval_hits.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    No matching sources were returned. The corpus may be empty or the server is
                    running in stub mode.
                  </p>
                ) : (
                  <div className="space-y-4">
                    {res.retrieval_hits.map((hit, index) => (
                      <RetrievalResultCard
                        key={hit.chunk_id}
                        rank={index + 1}
                        score={hit.score}
                        maxScore={res.retrieval_hits[0]?.score ?? hit.score}
                        fields={hit}
                        chunkId={hit.chunk_id}
                        graphEnriched={Boolean(res.graph_context)}
                        emptyExcerptMessage="This NLU view returns source metadata only. Open Law query to read the excerpted legal text for the same question."
                      />
                    ))}
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
          )}

          {!blocked && res.graph_context ? (
            <GraphContextPanel
              context={res.graph_context}
              sourceAnchors={graphAnchors}
              intentLabel={res.predicted_intent ?? res.intent}
            />
          ) : null}
        </>
      ) : null}
    </div>
  );
}
