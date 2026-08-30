import type { KgJoinFields } from "../types";
import { LawSourceMeta } from "./law-source-meta";
import { PassageExcerpt } from "./passage-excerpt";
import { RelevanceMeter } from "./relevance-meter";
import { sourceTitle } from "./language-model-display";

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
  const title = sourceTitle(fields, chunkId);

  return (
    <article className="overflow-hidden rounded-xl border border-border/80 bg-card shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border/70 bg-muted/20 px-4 py-3">
        <div className="flex items-center gap-3 min-w-0">
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">
            {rank}
          </span>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-foreground truncate">{title}</p>
            {graphEnriched ? (
              <p className="text-xs text-primary mt-0.5">Verified in knowledge graph</p>
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
