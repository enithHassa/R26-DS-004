import { CATALOG_STRATEGIES } from "../constants/strategies";
import type { RecommendationExplanation } from "../types";
import { describeShapFeature, friendlyShapFeature } from "./shap-labels";

const NEGLIGIBLE = 0.0001;

type Attribution = RecommendationExplanation["top_reasons"][number];

/** Extract catalog strategy id from one-hot pair feature names. */
export function strategyIdFromShapFeature(raw: string): string | null {
  if (!raw.startsWith("cat__strategy_id_")) return null;
  return raw.replace("cat__strategy_id_", "");
}

/** Drop other strategies' one-hot features and near-zero attributions. */
export function filterShapForStrategy(
  items: Attribution[],
  strategyCode: string,
): Attribution[] {
  const needle = strategyCode.toLowerCase();
  const prefix = needle.split("_")[0];

  return items.filter((item) => {
    if (Math.abs(item.shap_value) < NEGLIGIBLE) return false;

    const sid = strategyIdFromShapFeature(item.feature);
    if (sid === null) return true;

    const sidLower = sid.toLowerCase();
    return sidLower === needle || sidLower.startsWith(prefix);
  });
}

export function shapImpactLabel(absValue: number, maxAbs: number): string {
  if (maxAbs <= 0) return "Minor influence";
  const ratio = absValue / maxAbs;
  if (ratio >= 0.75) return "Strong influence";
  if (ratio >= 0.35) return "Moderate influence";
  return "Minor influence";
}

export function buildShapNarrative(
  topReasons: Attribution[],
  strategyLabel: string,
): string {
  const drivers = topReasons.slice(0, 3);
  if (drivers.length === 0) {
    return `The ranking model scored "${strategyLabel}" using this taxpayer's income, savings, debt, and eligibility signals.`;
  }

  const parts = drivers.map((d) => {
    const label = friendlyShapFeature(d.feature);
    const direction = d.shap_value >= 0 ? "raised" : "lowered";
    return `${label} (${direction} the score)`;
  });

  return `This strategy ranks well mainly because ${parts.join("; ")}.`;
}

export function prepareShapExplanation(
  data: RecommendationExplanation,
  strategyCode: string,
  strategyLabel: string,
) {
  const positive = filterShapForStrategy(
    data.top_reasons.filter((r) => r.shap_value > 0),
    strategyCode,
  ).slice(0, 5);

  const negative = filterShapForStrategy(
    data.bottom_reasons.filter((r) => r.shap_value < 0),
    strategyCode,
  ).slice(0, 5);

  const narrative = buildShapNarrative(positive, strategyLabel);

  return { positive, negative, narrative };
}

export function strategyLabelFromCode(code: string): string {
  const hit = CATALOG_STRATEGIES.find(
    (s) => s.code.toLowerCase() === code.toLowerCase() || code.toLowerCase().includes(s.code.split("_")[0].toLowerCase()),
  );
  return hit?.label ?? code.replace(/_/g, " ");
}

export { describeShapFeature };
