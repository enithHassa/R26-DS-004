import type { KgJoinFields } from "../types";
import { LawSourceMeta } from "./law-source-meta";
import { PassageExcerpt } from "./passage-excerpt";
import { RelevanceMeter } from "./relevance-meter";

interface RetrievalResultCardProps {
  rank: number;
  score: number;
  maxScore: number;
  fields: KgJoinFields;
  chunkId: string;
  excerpt?: string | null;
  excerptLabel?: string;
  emptyExcerptMessage?: string;
  graphEnriched?: boolean;
}

export function RetrievalResultCard({
  rank,
  score,
  maxScore,
  fields,
  chunkId,
  excerpt,
  excerptLabel = "Excerpt",
  emptyExcerptMessage,
  graphEnriched = false,
}: RetrievalResultCardProps) {
  const hasExcerpt = Boolean(excerpt?.trim());

  return (
    <article className="overflow-hidden rounded-xl border border-border/80 bg-card shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-border/70 bg-muted/20 px-4 py-3">
        <div className="flex items-start gap-3">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary">
            {rank}
          </span>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Match #{rank}
            </p>
            <p className="text-sm text-muted-foreground">
              Ranked by how closely this source matches your question.
            </p>
            {graphEnriched ? (
              <p className="mt-1 text-xs font-medium text-primary">
                Included in the knowledge graph lookup below
              </p>
            ) : null}
          </div>
        </div>
        <RelevanceMeter score={score} maxScore={maxScore} />
      </div>

      <div className="space-y-4 p-4">
        {hasExcerpt ? (
          <PassageExcerpt text={excerpt ?? ""} label={excerptLabel} />
        ) : emptyExcerptMessage ? (
          <p className="rounded-lg border border-dashed border-border/80 bg-muted/10 px-4 py-3 text-sm text-muted-foreground">
            {emptyExcerptMessage}
          </p>
        ) : null}

        <LawSourceMeta fields={fields} fallbackId={chunkId} />
      </div>
    </article>
  );
}
