import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { CheckCircle2, Sparkles, ThumbsDown, ThumbsUp } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

import { generateRecommendations, submitRecommendationFeedback } from "../api/recommendations";
import { AdoptionChip, RiskChip, SavingsChip } from "./metric-chips";
import { recommendationCodeToCatalog, STRATEGY_PLAIN_SUMMARY } from "../constants/strategies";
import { formatLkr } from "../utils/format-lkr";

type TaxpayerRecommendationsPanelProps = {
  profileId: string;
};

export function TaxpayerRecommendationsPanel({ profileId }: TaxpayerRecommendationsPanelProps) {
  const [feedbackGiven, setFeedbackGiven] = useState<Record<string, "accepted" | "dismissed">>({});

  const recommendationsQuery = useQuery({
    queryKey: ["taxpayer-recommendations", profileId],
    queryFn: () => generateRecommendations({ profile_id: profileId, top_k: 5 }),
    enabled: !!profileId,
    refetchOnMount: "always",
  });

  const feedbackMutation = useMutation({
    mutationFn: submitRecommendationFeedback,
    onSuccess: (_, variables) => {
      setFeedbackGiven((prev) => ({
        ...prev,
        [variables.recommendation_item_id]: variables.accepted ? "accepted" : "dismissed",
      }));
    },
  });

  const recommendations = recommendationsQuery.data?.items ?? [];

  return (
    <Card className="border-[var(--uv-border)] bg-[var(--uv-bg-card)]">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <Sparkles className="h-5 w-5 text-[var(--uv-accent)]" />
          Recommended for you
        </CardTitle>
        <CardDescription className="text-[var(--uv-text-muted)]">
          A few ways to pay less tax, picked for your situation — in plain terms.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {recommendationsQuery.isLoading && (
          <p className="text-sm text-[var(--uv-text-muted)]">Loading your recommendations…</p>
        )}
        {recommendationsQuery.isError && (
          <div className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">
            {(recommendationsQuery.error as Error).message}
          </div>
        )}
        {!recommendationsQuery.isLoading && recommendations.length === 0 && (
          <p className="text-sm text-[var(--uv-text-muted)]">No recommendations are available for your profile yet.</p>
        )}
        {recommendations.map((item) => (
          <div key={item.id} className="rounded-lg border border-[var(--uv-border)] bg-[var(--uv-bg)]/40 p-4">
            <div className="flex flex-wrap items-start gap-2">
              <span className="flex h-6 w-6 flex-none items-center justify-center rounded-full bg-[var(--uv-accent)]/15 text-xs font-semibold text-[var(--uv-accent)]">
                {item.rank}
              </span>
              <div className="min-w-0 flex-1">
                <div className="font-semibold">{item.strategy.name}</div>
                <p className="mt-1 text-sm text-[var(--uv-text-muted)]">
                  {STRATEGY_PLAIN_SUMMARY[recommendationCodeToCatalog(item.strategy.code)] ??
                    item.strategy.description}
                </p>
              </div>
            </div>

            <div className="mt-3 flex flex-wrap gap-2 pl-8">
              <SavingsChip value={formatLkr(item.estimated_annual_savings)} />
              <AdoptionChip probability={item.adoption_probability} />
              <RiskChip score={item.risk_score} />
            </div>

            {item.explanation?.narrative && (
              <div className="mt-3 ml-8 rounded-md border-l-4 border-l-[var(--uv-accent)]/60 bg-[var(--uv-bg)]/60 p-3 text-sm leading-relaxed">
                <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-[var(--uv-text-muted)]">
                  What this means for you
                </div>
                {item.explanation.narrative}
              </div>
            )}

            <div className="mt-3 ml-8 flex items-center gap-2">
              {feedbackGiven[item.id] ? (
                <span className="flex items-center gap-1.5 text-xs text-[var(--uv-text-muted)]">
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                  {feedbackGiven[item.id] === "accepted"
                    ? "Marked as done — thanks, this helps us improve future recommendations."
                    : "Marked as not for you — thanks for the feedback."}
                </span>
              ) : (
                <>
                  <button
                    type="button"
                    disabled={feedbackMutation.isPending}
                    onClick={() =>
                      feedbackMutation.mutate({
                        recommendation_item_id: item.id,
                        accepted: true,
                      })
                    }
                    className="inline-flex items-center gap-1.5 rounded-md border border-emerald-500/40 bg-emerald-500/10 px-2.5 py-1 text-xs font-medium text-emerald-400 transition-colors hover:bg-emerald-500/20 disabled:opacity-50"
                  >
                    <ThumbsUp className="h-3.5 w-3.5" />
                    I&apos;ve done this
                  </button>
                  <button
                    type="button"
                    disabled={feedbackMutation.isPending}
                    onClick={() =>
                      feedbackMutation.mutate({
                        recommendation_item_id: item.id,
                        accepted: false,
                      })
                    }
                    className="inline-flex items-center gap-1.5 rounded-md border border-[var(--uv-border)] px-2.5 py-1 text-xs font-medium text-[var(--uv-text-muted)] transition-colors hover:bg-white/5 disabled:opacity-50"
                  >
                    <ThumbsDown className="h-3.5 w-3.5" />
                    Not for me
                  </button>
                </>
              )}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
