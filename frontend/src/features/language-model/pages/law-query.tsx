import { useMutation } from "@tanstack/react-query";
import { BookOpen, FileText, Loader2 } from "lucide-react";
import { useId, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";

import { DomainNotice } from "../components/domain-notice";
import { GraphContextPanel } from "../components/graph-context-panel";
import { PlainAnswerCard } from "../components/plain-answer-card";
import { anchorsFromCitations } from "../components/graph-source-anchor";
import { RetrievalResultCard } from "../components/retrieval-result-card";
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
  const [synthesizeAnswer, setSynthesizeAnswer] = useState(true);

  const mutation = useMutation({ mutationFn: postQuery });

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    mutation.mutate({
      question: question.trim(),
      top_k: 5,
      synthesize_answer: synthesizeAnswer,
    });
  }

  const res = mutation.data;
  const maxScore = res?.citations[0]?.score ?? 0;
  const graphAnchors = res ? anchorsFromCitations(res.citations) : [];
  const blocked = res?.domain_status != null && res.domain_status !== "in_domain";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Law-grounded query</h1>
        <p className="text-muted-foreground">
          Ask a tax law question and get a cited answer from real IRD law documents. You can also request a plain-language summary.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <BookOpen className="h-5 w-5" />
            Ask a tax law question
          </CardTitle>
          <CardDescription>
            Type your question below. The system will find the most relevant sections from Sri Lankan tax law and show you where the answer comes from.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="space-y-4">
            <div className="space-y-2">
              <label htmlFor={`${idBase}-q`} className="text-sm font-medium">Your question</label>
              <textarea
                id={`${idBase}-q`}
                className={textareaClass}
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                required
              />
            </div>
            <div>
              <label
                htmlFor={`${idBase}-summary`}
                className="flex items-start gap-3 rounded-lg border border-border/70 bg-muted/10 p-3 text-sm"
              >
                <Checkbox
                  id={`${idBase}-summary`}
                  checked={synthesizeAnswer}
                  onChange={(e) => setSynthesizeAnswer(e.target.checked)}
                />
                <span>
                  <span className="font-medium text-foreground">Generate a plain-language answer</span>
                  <span className="mt-1 block text-muted-foreground">
                    When enabled, an AI summary is shown above the law sources.
                  </span>
                </span>
              </label>
            </div>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Retrieving…
                </>
              ) : (
                "Find relevant law"
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

          {!blocked && res.plain_answer ? (
            <PlainAnswerCard
              answer={res.plain_answer}
              provider={res.answer_provider}
              model={res.answer_model}
            />
          ) : null}

          {blocked ? null : (
          <Card className="overflow-hidden rounded-xl border border-border/80 shadow-sm">
            <div className="h-1 w-full bg-gradient-to-r from-primary/70 to-sky-600/60" aria-hidden />
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg">
                <FileText className="h-5 w-5" />
                Law sources used
              </CardTitle>
              <CardDescription>
                These are the actual law sections the answer is based on.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {res.citations.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No law sections were found. The corpus may not be loaded on the server.
                </p>
              ) : (
                <div className="space-y-4">
                  {res.citations.map((citation, index) => (
                    <RetrievalResultCard
                      key={`${citation.chunk_id}-${index}`}
                      rank={index + 1}
                      score={citation.score}
                      maxScore={maxScore || citation.score}
                      fields={citation}
                      chunkId={citation.chunk_id}
                      graphEnriched={Boolean(res.graph_context)}
                      excerpt={citation.text}
                      excerptLabel="Relevant passage"
                    />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
          )}

          {!blocked && res.graph_context ? (
            <GraphContextPanel context={res.graph_context} sourceAnchors={graphAnchors} />
          ) : null}
        </>
      ) : null}
    </div>
  );
}
