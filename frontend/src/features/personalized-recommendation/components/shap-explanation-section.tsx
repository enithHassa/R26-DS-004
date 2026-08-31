import { cn } from "@/lib/utils";

import type { RecommendationExplanation } from "../types";
import {
  prepareShapExplanation,
  shapImpactLabel,
  strategyLabelFromCode,
} from "../utils/shap-explanation";
import { describeShapFeature, friendlyShapFeature } from "../utils/shap-labels";

type Props = {
  data: RecommendationExplanation;
  strategyCode: string;
  strategyLabel?: string;
};

export function ShapExplanationSection({ data, strategyCode, strategyLabel }: Props) {
  const label = strategyLabel ?? strategyLabelFromCode(strategyCode);
  const { positive, negative, narrative } = prepareShapExplanation(data, strategyCode, label);

  return (
    <div className="space-y-4">
      <p className="rounded-lg border border-primary/20 bg-primary/5 p-3 text-sm leading-relaxed">
        {narrative}
      </p>

      <p className="text-xs text-muted-foreground">
        These factors come from the AI ranker (LambdaMART). Each bar shows how much a profile
        feature pushed this strategy up or down compared with other strategies for the same taxpayer.
      </p>

      <div className="grid gap-4 md:grid-cols-2">
        <ShapDriverList
          title="What helped this rank"
          emptyMessage="No strong positive drivers after filtering cross-strategy noise."
          items={positive}
          tone="positive"
        />
        <ShapDriverList
          title="What held it back"
          emptyMessage="Nothing significant reduced the rank for this strategy."
          items={negative}
          tone="negative"
        />
      </div>
    </div>
  );
}

function ShapDriverList({
  title,
  emptyMessage,
  items,
  tone,
}: {
  title: string;
  emptyMessage: string;
  items: RecommendationExplanation["top_reasons"];
  tone: "positive" | "negative";
}) {
  if (items.length === 0) {
    return (
      <div className="rounded-lg border bg-muted/20 p-3">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</h4>
        <p className="mt-2 text-sm text-muted-foreground">{emptyMessage}</p>
      </div>
    );
  }

  const max = Math.max(...items.map((i) => Math.abs(i.shap_value)), 0.001);

  return (
    <div className="rounded-lg border bg-muted/10 p-3">
      <h4 className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</h4>
      <ul className="space-y-3">
        {items.map((item) => {
          const featureLabel = friendlyShapFeature(item.feature);
          const hint = describeShapFeature(item.feature);
          const impact = shapImpactLabel(Math.abs(item.shap_value), max);
          const barPct = (Math.abs(item.shap_value) / max) * 100;

          return (
            <li key={item.feature} className="text-sm">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0 flex-1">
                  <p className="font-medium leading-snug">{featureLabel}</p>
                  {hint && <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">{hint}</p>}
                </div>
                <span
                  className={cn(
                    "shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                    tone === "positive"
                      ? "bg-emerald-100 text-emerald-800"
                      : "bg-rose-100 text-rose-800",
                  )}
                >
                  {impact}
                </span>
              </div>
              <div className="mt-2 h-2 overflow-hidden rounded-full bg-muted">
                <div
                  className={cn("h-full", tone === "positive" ? "bg-emerald-500" : "bg-rose-400")}
                  style={{ width: `${barPct}%` }}
                />
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
