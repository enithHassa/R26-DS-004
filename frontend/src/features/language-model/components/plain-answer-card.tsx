import { Sparkles } from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

import { AnswerConfidenceBadge } from "./answer-confidence-badge";
import { MarkdownLite } from "./markdown-lite";

interface PlainAnswerCardProps {
  answer: string;
  provider?: string | null;
  model?: string | null;
  confidenceScore?: number | null;
  confidenceLabel?: string | null;
}

export function PlainAnswerCard({
  answer,
  provider,
  model,
  confidenceScore,
  confidenceLabel,
}: PlainAnswerCardProps) {
  return (
    <Card className="overflow-hidden rounded-xl border border-emerald-200/80 bg-emerald-50/40 shadow-sm dark:border-emerald-900/50 dark:bg-emerald-950/20">
      <div className="h-1 w-full bg-gradient-to-r from-emerald-600/80 to-primary/70" aria-hidden />
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0 space-y-1.5">
            <CardTitle className="flex items-center gap-2 text-lg">
              <Sparkles className="h-5 w-5 text-emerald-700 dark:text-emerald-300" />
              Plain-language answer
            </CardTitle>
            <CardDescription>
              Written for easy reading from the law passages below
              {provider || model ? (
                <>
                  {" "}
                  · Generated with {provider ?? "AI"}
                  {model ? ` (${model})` : ""}
                </>
              ) : null}
              . Tags like <span className="font-medium text-foreground">[Match 1]</span> point to
              the numbered sources in the next section.
            </CardDescription>
          </div>
          <AnswerConfidenceBadge score={confidenceScore} label={confidenceLabel} />
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <MarkdownLite content={answer} className="text-sm leading-relaxed text-foreground" />
        <p className="rounded-lg border border-emerald-200/70 bg-background/60 px-3 py-2 text-xs text-muted-foreground dark:border-emerald-900/40">
          Decision-support only — not legally binding advice. Confirm figures against the{" "}
          <span className="font-medium text-foreground">Law sources used</span> section below.
        </p>
      </CardContent>
    </Card>
  );
}
