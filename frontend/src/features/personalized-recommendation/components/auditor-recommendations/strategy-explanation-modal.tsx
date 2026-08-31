import { useEffect } from "react";
import { useMutation } from "@tanstack/react-query";
import { Loader2, Sparkles, X } from "lucide-react";

import { Button } from "@/components/ui/button";

import type { HybridResultItem } from "../../api/hybrid";
import type { RagDetailedExplanation } from "../../api/rag";
import { explainRecommendation } from "../../api/explain";
import { recommendationCodeToCatalog } from "../../constants/strategies";
import { ShapExplanationSection } from "../shap-explanation-section";

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
    // eslint-disable-next-line react-hooks/exhaustive-deps -- load ranking explanation once when modal opens
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
            <h3 className="text-sm font-semibold">Guidance</h3>
            {buildPlainSections(detail).map((s) => (
              <PlainSection key={s.title} title={s.title} body={s.body} />
            ))}
          </div>

          <div className="space-y-3 border-t pt-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="flex items-center gap-2 text-sm font-semibold">
                <Sparkles className="h-4 w-4 text-primary" />
                Why the AI ranked this strategy
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
                    Analysing…
                  </>
                ) : explainMutation.data ? (
                  "Refresh analysis"
                ) : (
                  "Load analysis"
                )}
              </Button>
            </div>

            {explainMutation.isError && (
              <p className="text-sm text-destructive">{(explainMutation.error as Error).message}</p>
            )}

            {explainMutation.isPending && !explainMutation.data && (
              <div className="flex items-center gap-2 rounded-lg border bg-muted/20 p-4 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Identifying the profile factors that influenced this rank…
              </div>
            )}

            {explainMutation.data && (
              <ShapExplanationSection
                data={explainMutation.data}
                strategyCode={strategyCode}
                strategyLabel={item.name}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
