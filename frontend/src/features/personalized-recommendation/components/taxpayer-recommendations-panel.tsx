import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { CheckCircle2, Sparkles, ThumbsDown, ThumbsUp } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

import { submitRecommendationFeedback } from "../api/recommendations";
import { useTaxpayerRecommendations } from "../hooks/use-taxpayer-recommendations";
import { AdoptionChip, RiskChip } from "./metric-chips";
import { recommendationCodeToCatalog, STRATEGY_PLAIN_SUMMARY } from "../constants/strategies";
import { TaxpayerRecommendationImpact } from "./taxpayer-recommendation-impact";
import { TaxpayerRecommendationPreviewRow } from "./taxpayer-recommendation-preview-row";
import { TaxpayerRecommendationsImpactChart } from "./taxpayer-recommendations-impact-chart";

type TaxpayerRecommendationsPanelProps = {
  profileId: string;
};

export function TaxpayerRecommendationsPanel({ profileId }: TaxpayerRecommendationsPanelProps) {
  const [feedbackGiven, setFeedbackGiven] = useState<Record<string, "accepted" | "dismissed">>({});

  const recommendationsQuery = useTaxpayerRecommendations(profileId);

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
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_288px]">
      <Card className="border-[var(--uv-border)] bg-[var(--uv-bg-card)] text-[var(--uv-text)]">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg text-[var(--uv-text)]">
            <Sparkles className="h-5 w-5 text-[var(--uv-accent)]" />
            Your Tax Recommendations
          </CardTitle>
          <CardDescription className="text-[var(--uv-text-muted)]">
            Personalized ways to pay less tax — picked for your situation, in plain terms.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {recommendationsQuery.isLoading && (
            <p className="text-sm text-[var(--uv-text-muted)]">Loading your recommendations…</p>
          )}
          {recommendationsQuery.isError && (
            <div className="rounded-md border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-300">
              {(recommendationsQuery.error as Error).message}
            </div>
          )}
          {!recommendationsQuery.isLoading && recommendations.length === 0 && (
            <p className="text-sm text-[var(--uv-text-muted)]">
              No recommendations are available for your profile yet.
            </p>
          )}
          {recommendations.map((item) => {
            const catalogCode = recommendationCodeToCatalog(item.strategy.code);
            return (
              <div
                key={item.id}
                className="rounded-lg border border-[var(--uv-border)] bg-[var(--uv-bg)]/40 p-4"
              >
                <TaxpayerRecommendationPreviewRow
                  rank={item.rank}
                  title={item.strategy.name}
                  savings={item.estimated_annual_savings}
                />

                <p className="mt-3 ml-10 text-sm leading-relaxed text-[var(--uv-text-muted)]">
                  {STRATEGY_PLAIN_SUMMARY[catalogCode] ?? item.strategy.description}
                </p>

                <div className="mt-3 flex flex-wrap gap-2 pl-10">
                  <AdoptionChip probability={item.adoption_probability} userView />
                  <RiskChip score={item.risk_score} userView />
                </div>

                {item.explanation?.narrative && (
                  <div className="mt-3 ml-10 rounded-md border-l-4 border-l-[var(--uv-accent)]/60 bg-[var(--uv-bg)]/60 p-3 text-sm leading-relaxed text-[var(--uv-text)]">
                    <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-[var(--uv-accent)]">
                      What this means for you
                    </div>
                    <p className="text-[var(--uv-text-muted)]">{item.explanation.narrative}</p>
                  </div>
                )}

                <div className="ml-10">
                  <TaxpayerRecommendationImpact
                    profileId={profileId}
                    strategyCode={catalogCode}
                    strategyName={item.strategy.name}
                  />
                </div>

                <div className="mt-3 ml-10 flex items-center gap-2">
                  {feedbackGiven[item.id] ? (
                    <span className="flex items-center gap-1.5 text-xs text-[var(--uv-text-muted)]">
                      <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
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
                        className="inline-flex items-center gap-1.5 rounded-md border border-emerald-500/40 bg-emerald-500/10 px-2.5 py-1 text-xs font-medium text-emerald-300 transition-colors hover:bg-emerald-500/20 disabled:opacity-50"
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
            );
          })}
        </CardContent>
      </Card>

      {!recommendationsQuery.isLoading && recommendations.length > 0 && (
        <aside className="lg:sticky lg:top-6 lg:self-start">
          <TaxpayerRecommendationsImpactChart
            profileId={profileId}
            recommendations={recommendations}
            compact
          />
        </aside>
      )}
    </div>
  );
}
