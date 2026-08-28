import { useEffect } from "react";
import { useMutation } from "@tanstack/react-query";
import { Loader2, Microscope, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import type { HybridResultItem } from "../../api/hybrid";
import type { RagDetailedExplanation } from "../../api/rag";
import { explainRecommendation } from "../../api/explain";
import { recommendationCodeToCatalog } from "../../constants/strategies";
import type { RecommendationExplanation } from "../../types";
import { friendlyShapFeature } from "../../utils/shap-labels";

type Props = {
  item: HybridResultItem;
  profileId: string;
  onClose: () => void;
};

function PlainSection({ title, body }: { title: string; body: string }) {
  if (!body?.trim()) return null;
  return (
    <div className="rounded-lg border bg-muted/30 p-3">
      <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</h4>
      <p className="mt-2 whitespace-pre-line text-sm leading-relaxed">{body}</p>
    </div>
  );
}

function ShapSection({ data }: { data: RecommendationExplanation }) {
  return (
    <div className="space-y-3">
      {data.narrative && (
        <p className="rounded-lg border border-primary/20 bg-primary/5 p-3 text-sm leading-relaxed">
          {data.narrative}
        </p>
      )}
      <div className="grid gap-4 md:grid-cols-2">
        <ShapList title="Top positive drivers (SHAP)" items={data.top_reasons} />
        <ShapList title="Negative drivers (SHAP)" items={data.bottom_reasons} />
      </div>
    </div>
  );
}

function ShapList({
  title,
  items,
}: {
  title: string;
  items: RecommendationExplanation["top_reasons"];
}) {
  if (items.length === 0) return null;
  const max = Math.max(...items.map((i) => Math.abs(i.shap_value)), 0.001);
  return (
    <div>
      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {title}
      </h4>
      <ul className="space-y-2">
        {items.map((item) => (
          <li key={item.feature} className="text-sm">
            <div className="flex justify-between gap-2">
              <span className="truncate font-medium">{friendlyShapFeature(item.feature)}</span>
              <span className={item.direction === "positive" ? "text-emerald-700" : "text-rose-700"}>
                {item.shap_value > 0 ? "+" : ""}
                {item.shap_value.toFixed(4)}
              </span>
            </div>
            <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-muted">
              <div
                className={cn(
                  "h-full",
                  item.direction === "positive" ? "bg-emerald-500" : "bg-rose-400",
                )}
                style={{ width: `${(Math.abs(item.shap_value) / max) * 100}%` }}
              />
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function buildPlainSections(detail: RagDetailedExplanation) {
  return [
    { title: "What it means", body: detail.what_it_means },
    { title: "Why this taxpayer qualifies", body: detail.why_you_qualify },
    { title: "What to do", body: detail.what_to_do },
    { title: "Potential benefit", body: detail.potential_benefit },
    { title: "Risk level", body: detail.risk_level },
  ];
}

export function StrategyExplanationModal({ item, profileId, onClose }: Props) {
  const strategyCode = recommendationCodeToCatalog(item.strategy_id);
  const detail = item.detailed_explanation;

  const explainMutation = useMutation({
    mutationFn: () =>
      explainRecommendation({
        profile_id: profileId,
        strategy_code: strategyCode,
        top_k: 5,
      }),
  });

  useEffect(() => {
    explainMutation.mutate();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- load SHAP once when modal opens
  }, [profileId, strategyCode]);

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/50 p-4 pt-[max(1rem,5vh)]">
      <div className="relative w-full max-w-2xl rounded-xl border bg-card shadow-xl">
        <div className="flex items-start justify-between gap-3 border-b px-5 py-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Strategy explanation
            </p>
            <h2 className="text-lg font-bold">{item.name}</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-muted-foreground hover:bg-muted"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="max-h-[70vh] space-y-4 overflow-y-auto px-5 py-4">
          <p className="text-sm text-muted-foreground">{item.why_relevant || item.description}</p>

          <div className="space-y-3">
            <h3 className="text-sm font-semibold">Plain-language guidance</h3>
            {buildPlainSections(detail).map((s) => (
              <PlainSection key={s.title} title={s.title} body={s.body} />
            ))}
          </div>

          <div className="space-y-3 border-t pt-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="flex items-center gap-2 text-sm font-semibold">
                <Microscope className="h-4 w-4 text-primary" />
                SHAP ranking drivers (LambdaMART)
              </h3>
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={explainMutation.isPending}
                onClick={() => explainMutation.mutate()}
              >
                {explainMutation.isPending ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    Computing…
                  </>
                ) : explainMutation.data ? (
                  "Refresh SHAP"
                ) : (
                  "Load SHAP explanation"
                )}
              </Button>
            </div>

            {explainMutation.isError && (
              <p className="text-sm text-destructive">{(explainMutation.error as Error).message}</p>
            )}

            {explainMutation.data && <ShapSection data={explainMutation.data} />}
          </div>
        </div>
      </div>
    </div>
  );
}
