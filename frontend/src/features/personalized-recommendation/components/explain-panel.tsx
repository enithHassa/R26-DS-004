import { useMutation } from "@tanstack/react-query";
import { Loader2, Microscope } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

import { explainRecommendation } from "../api/explain";
import type { RecommendationExplanation } from "../types";
import { friendlyShapFeature } from "../utils/shap-labels";

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

  const data = explainMutation.data;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <Microscope className="h-5 w-5" />
          Why the model ranked this strategy
        </CardTitle>
        <CardDescription>
          SHAP feature attributions (LambdaMART)
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
              Computing SHAP values…
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

        {data && <ExplanationBody data={data} />}
      </CardContent>
    </Card>
  );
}

function ExplanationBody({ data }: { data: RecommendationExplanation }) {
  return (
    <div className="space-y-4">
      {data.narrative && (
        <p className="rounded-md border bg-muted/30 p-3 text-sm">{data.narrative}</p>
      )}
      <div className="grid gap-4 md:grid-cols-2">
        <AttributionList title="Top positive drivers" items={data.top_reasons} />
        <AttributionList title="Negative drivers" items={data.bottom_reasons} />
      </div>
    </div>
  );
}

function AttributionList({
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
      <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {title}
      </div>
      <ul className="space-y-2">
        {items.map((item) => (
          <li key={item.feature} className="text-sm">
            <div className="flex justify-between gap-2">
              <span className="truncate font-medium" title={friendlyShapFeature(item.feature)}>
                {friendlyShapFeature(item.feature)}
              </span>
              <span className={item.direction === "positive" ? "text-emerald-700" : "text-rose-700"}>
                {item.shap_value > 0 ? "+" : ""}
                {item.shap_value.toFixed(4)}
              </span>
            </div>
            <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-muted">
              <div
                className={`h-full ${item.direction === "positive" ? "bg-emerald-500" : "bg-rose-400"}`}
                style={{ width: `${(Math.abs(item.shap_value) / max) * 100}%` }}
              />
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
