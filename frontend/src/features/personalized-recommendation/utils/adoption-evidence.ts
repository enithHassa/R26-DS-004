import type { ProfileHistorySnapshot } from "../types";
import { parseLkr } from "./format-lkr";

export type AdoptionVerdict = "strong" | "moderate" | "weak";

export interface AdoptionEvidence {
  verdict: AdoptionVerdict;
  incomeGrowthPct: number;
  savingsRateStart: number;
  savingsRateEnd: number;
  savingsRateDeltaPts: number;
  debtTrendPct: number;
  narrative: string;
  chartData: { month: string; income: number; savingsRatePct: number }[];
}

/**
 * Derives an "is this profile likely to adopt this strategy" narrative from
 * its synthetic historical trend plus the recommendation's own modelled
 * adoption probability. The trend doesn't drive the probability (the ranking
 * model already computed that) — it explains whether the profile's
 * trajectory is consistent with that number.
 */
export function computeAdoptionEvidence(
  history: ProfileHistorySnapshot[],
  adoptionProbability: number,
  estimatedAnnualSavings: number,
): AdoptionEvidence | null {
  if (history.length < 2) return null;

  const first = history[0];
  const last = history[history.length - 1];

  const incomeStart = parseLkr(first.gross_monthly_income);
  const incomeEnd = parseLkr(last.gross_monthly_income);
  const incomeGrowthPct = incomeStart > 0 ? ((incomeEnd - incomeStart) / incomeStart) * 100 : 0;

  const savingsRateStart = first.savings_rate * 100;
  const savingsRateEnd = last.savings_rate * 100;
  const savingsRateDeltaPts = savingsRateEnd - savingsRateStart;

  const debtStart = parseLkr(first.total_debt);
  const debtEnd = parseLkr(last.total_debt);
  const debtTrendPct = debtStart > 0 ? ((debtEnd - debtStart) / debtStart) * 100 : 0;

  const trendPositive = incomeGrowthPct > 0 && savingsRateDeltaPts >= -1 && debtTrendPct <= 5;
  const trendStrong = incomeGrowthPct > 5 && savingsRateDeltaPts > 1 && debtTrendPct < 0;

  let verdict: AdoptionVerdict;
  if (adoptionProbability >= 0.6 && trendStrong) verdict = "strong";
  else if (adoptionProbability >= 0.4 && trendPositive) verdict = "moderate";
  else if (adoptionProbability >= 0.6 || trendPositive) verdict = "moderate";
  else verdict = "weak";

  const direction = (n: number) => (n >= 0 ? "risen" : "fallen");
  const months = history.length;

  const narrative =
    `Over the past ${months} months, this profile's income has ${direction(incomeGrowthPct)} ` +
    `${Math.abs(incomeGrowthPct).toFixed(1)}%, and the savings rate has moved from ` +
    `${savingsRateStart.toFixed(1)}% to ${savingsRateEnd.toFixed(1)}% of income` +
    `${debtStart > 0 ? `, while total debt has ${direction(debtTrendPct)} ${Math.abs(debtTrendPct).toFixed(1)}%` : ""}. ` +
    `Combined with a modelled adoption probability of ${(adoptionProbability * 100).toFixed(0)}%, ` +
    (verdict === "strong"
      ? `this trajectory strongly supports adopting this strategy for an estimated annual saving of LKR ${estimatedAnnualSavings.toLocaleString("en-LK")}.`
      : verdict === "moderate"
        ? `this trajectory is broadly consistent with adopting this strategy, though the trend is not yet decisive.`
        : `this trajectory does not clearly support adoption — income/savings trends are flat or declining.`);

  const chartData = history.map((h) => ({
    month: h.snapshot_month.slice(0, 7),
    income: parseLkr(h.gross_monthly_income),
    savingsRatePct: Number((h.savings_rate * 100).toFixed(2)),
  }));

  return {
    verdict,
    incomeGrowthPct,
    savingsRateStart,
    savingsRateEnd,
    savingsRateDeltaPts,
    debtTrendPct,
    narrative,
    chartData,
  };
}
