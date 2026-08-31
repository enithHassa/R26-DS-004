import { useMutation } from "@tanstack/react-query";
import { Loader2, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

import { explainRecommendation } from "../api/explain";
import { ShapExplanationSection } from "./shap-explanation-section";

type Props = {
  profileId: string;
  strategyCode: string;
  strategyLabel?: string;
};

export function ExplainPanel({ profileId, strategyCode, strategyLabel }: Props) {
  const explainMutation = useMutation({
    mutationFn: () =>
      explainRecommendation({
        profile_id: profileId,
        strategy_code: strategyCode,
        top_k: 5,
      }),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <Sparkles className="h-5 w-5" />
          Why the AI ranked this strategy
        </CardTitle>
        <CardDescription>
          Profile factors that pushed this strategy up or down in the ranker
          {strategyLabel ? ` — ${strategyLabel}` : ""}.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <Button
          variant="outline"
          onClick={() => explainMutation.mutate()}
          disabled={!profileId || !strategyCode || explainMutation.isPending}
        >
          {explainMutation.isPending ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Analysing…
            </>
          ) : (
            "Explain this strategy"
          )}
        </Button>

        {explainMutation.isError && (
          <div className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">
            {(explainMutation.error as Error).message}
          </div>
        )}

        {explainMutation.data && (
          <ShapExplanationSection
            data={explainMutation.data}
            strategyCode={strategyCode}
            strategyLabel={strategyLabel}
          />
        )}
      </CardContent>
    </Card>
  );
}
