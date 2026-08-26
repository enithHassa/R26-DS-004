import type { ProfileHistorySnapshot } from "../types";
import { parseLkr } from "./format-lkr";

export type AdoptionVerdict = "strong" | "moderate" | "weak";

export interface NarrativeSection {
  heading: string;
  body: string;
}

export interface Signal {
  key: string;
  label: string;
  detail: string;
  met: boolean;
  weight: "model" | "trend";
}

export interface AdoptionEvidence {
  verdict: AdoptionVerdict;
  verdictSummary: string;
  adoptionProbability: number;
  incomeGrowthPct: number;
  savingsRateStart: number;
  savingsRateEnd: number;
  savingsRateDeltaPts: number;
  debtTrendPct: number;
  liquidSavingsGrowthPct: number;
  investmentGrowthPct: number;
  signals: Signal[];
  narrative: string;
  sections: NarrativeSection[];
  chartData: { month: string; income: number; savingsRatePct: number }[];
  indexedChartData: {
    month: string;
    income: number;
    debt: number | null;
    liquidSavings: number;
    investments: number;
  }[];
}

const direction = (n: number) => (n >= 0 ? "risen" : "fallen");
const changeWord = (n: number) => (n >= 0 ? "grown" : "shrunk");

/** Average of the first `n` snapshots — smooths single-month noise out of the
 * "starting point" reading, rather than relying on one snapshot. */
function averageOf(history: ProfileHistorySnapshot[], n: number, field: keyof ProfileHistorySnapshot): number {
  const slice = history.slice(0, n);
  const sum = slice.reduce((acc, h) => acc + parseLkr(h[field] as string), 0);
  return sum / slice.length;
}

function averageOfEnd(history: ProfileHistorySnapshot[], n: number, field: keyof ProfileHistorySnapshot): number {
  const slice = history.slice(-n);
  const sum = slice.reduce((acc, h) => acc + parseLkr(h[field] as string), 0);
  return sum / slice.length;
}

function pctChange(start: number, end: number): number {
  return start > 0 ? ((end - start) / start) * 100 : 0;
}

/** Rebase a series to 100 at its first value, so income (LKR hundred-thousands),
 * debt, liquid savings, and investments — all wildly different magnitudes —
 * can be plotted on one comparable axis. */
function indexSeries(values: number[]): number[] {
  const base = values[0];
  if (!base || base <= 0) return values.map(() => 100);
  return values.map((v) => Number(((v / base) * 100).toFixed(1)));
}

/**
 * Derives an "is this profile likely to adopt this strategy" analysis from
 * its synthetic historical trend plus the recommendation's own modelled
 * adoption probability. The trend doesn't drive the probability (the ranking
 * model already computed that) — it independently checks whether the
 * profile's trajectory is consistent with that number, and the two are kept
 * visibly separate (see `signals`) rather than blended into one figure.
 *
 * Start/end readings are averaged over a small window (up to 3 months) at
 * each end of the history rather than taken from a single snapshot, so one
 * noisy month doesn't skew the whole trend read.
 */
export function computeAdoptionEvidence(
  history: ProfileHistorySnapshot[],
  adoptionProbability: number,
  estimatedAnnualSavings: number,
): AdoptionEvidence | null {
  if (history.length < 2) return null;

  const windowSize = Math.min(3, Math.floor(history.length / 2));
  const months = history.length;
  const years = (months / 12).toFixed(1);

  const first = history[0];
  const last = history[history.length - 1];

  const incomeStart = averageOf(history, windowSize, "gross_monthly_income");
  const incomeEnd = averageOfEnd(history, windowSize, "gross_monthly_income");
  const incomeGrowthPct = pctChange(incomeStart, incomeEnd);

  const savingsRateStart = first.savings_rate * 100;
  const savingsRateEnd = last.savings_rate * 100;
  const savingsRateDeltaPts = savingsRateEnd - savingsRateStart;

  const debtStart = averageOf(history, windowSize, "total_debt");
  const debtEnd = averageOfEnd(history, windowSize, "total_debt");
  const debtTrendPct = pctChange(debtStart, debtEnd);
  const hasDebt = debtStart > 0 || debtEnd > 0;

  const liquidStart = averageOf(history, windowSize, "liquid_savings");
  const liquidEnd = averageOfEnd(history, windowSize, "liquid_savings");
  const liquidSavingsGrowthPct = pctChange(liquidStart, liquidEnd);

  const investStart =
    averageOf(history, windowSize, "existing_investments") +
    averageOf(history, windowSize, "epf_balance") +
    averageOf(history, windowSize, "etf_balance");
  const investEnd =
    averageOfEnd(history, windowSize, "existing_investments") +
    averageOfEnd(history, windowSize, "epf_balance") +
    averageOfEnd(history, windowSize, "etf_balance");
  const investmentGrowthPct = pctChange(investStart, investEnd);

  // --- Signals: each one independently checkable against the chart above,
  // so the verdict is never a black box. ---
  const modelConfident = adoptionProbability >= 0.6;
  const modelSupportive = adoptionProbability >= 0.4;
  const incomeRisingStrongly = incomeGrowthPct > 5;
  const incomeNotFalling = incomeGrowthPct > 0;
  const savingsRateImproving = savingsRateDeltaPts > 1;
  const savingsRateNotWorsening = savingsRateDeltaPts >= -1;
  const debtFalling = hasDebt ? debtTrendPct < 0 : true;
  const debtNotRisingFast = hasDebt ? debtTrendPct <= 5 : true;

  const trendPositive = incomeNotFalling && savingsRateNotWorsening && debtNotRisingFast;
  const trendStrong = incomeRisingStrongly && savingsRateImproving && debtFalling;

  const signals: Signal[] = [
    {
      key: "model",
      label: "Adoption model confidence",
      detail: `${(adoptionProbability * 100).toFixed(0)}% modelled probability (≥60% threshold for "confident")`,
      met: modelConfident,
      weight: "model",
    },
    {
      key: "income",
      label: "Income rising strongly",
      detail: `${incomeGrowthPct >= 0 ? "+" : ""}${incomeGrowthPct.toFixed(1)}% over ${months} months (>5% threshold)`,
      met: incomeRisingStrongly,
      weight: "trend",
    },
    {
      key: "savings",
      label: "Savings rate improving",
      detail: `${savingsRateDeltaPts >= 0 ? "+" : ""}${savingsRateDeltaPts.toFixed(1)} pts (>1 pt threshold)`,
      met: savingsRateImproving,
      weight: "trend",
    },
    {
      key: "debt",
      label: hasDebt ? "Debt being paid down" : "No debt burden",
      detail: hasDebt
        ? `${debtTrendPct >= 0 ? "+" : ""}${debtTrendPct.toFixed(1)}% (falling debt required)`
        : "No recorded debt over this period",
      met: debtFalling,
      weight: "trend",
    },
  ];

  let verdict: AdoptionVerdict;
  if (modelConfident && trendStrong) verdict = "strong";
  else if (modelSupportive && trendPositive) verdict = "moderate";
  else if (modelConfident || trendPositive) verdict = "moderate";
  else verdict = "weak";

  const trendMetCount = signals.filter((s) => s.weight === "trend" && s.met).length;

  const savingsLine = `an estimated LKR ${estimatedAnnualSavings.toLocaleString("en-LK")} a year`;

  let verdictSummary: string;
  if (verdict === "strong") {
    verdictSummary = `All signals align: the model is confident (${(adoptionProbability * 100).toFixed(0)}%) and all ${trendMetCount}/3 trend checks pass, backing ${savingsLine} in potential savings with real behavioural evidence.`;
  } else if (modelConfident && !trendStrong) {
    verdictSummary = `The model is confident (${(adoptionProbability * 100).toFixed(0)}%), but only ${trendMetCount}/3 trend checks fully pass — the historical trend hasn't caught up to what the model expects. Treat the ${savingsLine} estimate as plausible rather than certain.`;
  } else if (!modelConfident && trendPositive) {
    verdictSummary = `The historical trend looks favourable (${trendMetCount}/3 checks pass), but the model itself is only ${(adoptionProbability * 100).toFixed(0)}% confident — the trend alone isn't enough to call the ${savingsLine} estimate a strong case.`;
  } else if (verdict === "weak") {
    verdictSummary = `Neither the model (${(adoptionProbability * 100).toFixed(0)}%) nor the trend (${trendMetCount}/3 checks) clearly support adoption, so the ${savingsLine} estimate should be treated cautiously.`;
  } else {
    verdictSummary = `Mixed signals: model at ${(adoptionProbability * 100).toFixed(0)}%, ${trendMetCount}/3 trend checks pass — worth ${savingsLine} if adopted, but not a confident forecast.`;
  }

  const sections: NarrativeSection[] = [
    {
      heading: "Income trajectory",
      body:
        `Average monthly income has ${direction(incomeGrowthPct)} ${Math.abs(incomeGrowthPct).toFixed(1)}% over ${months} months ` +
        `(~${years} years) — from ${incomeStart.toLocaleString("en-LK", { maximumFractionDigits: 0 })} LKR to ` +
        `${incomeEnd.toLocaleString("en-LK", { maximumFractionDigits: 0 })} LKR, comparing ${windowSize}-month averages at each end. ` +
        `${incomeRisingStrongly ? "This clears the strong-growth bar and typically improves capacity to sustain a new deduction or contribution." : incomeNotFalling ? "This is positive but modest — income growth alone is not decisive here." : "Income has softened, which can make a new ongoing commitment harder to sustain."}`,
    },
    {
      heading: "Savings behaviour",
      body:
        `The savings rate moved from ${savingsRateStart.toFixed(1)}% to ${savingsRateEnd.toFixed(1)}% of income ` +
        `(${savingsRateDeltaPts >= 0 ? "+" : ""}${savingsRateDeltaPts.toFixed(1)} points). ` +
        `${savingsRateImproving ? "A rising savings rate is one of the strongest behavioural signals of adoption readiness." : savingsRateNotWorsening ? "This is essentially flat — savings discipline is neither a tailwind nor a headwind." : "A falling savings rate means affordability is a bigger constraint than desire here."}`,
    },
    {
      heading: "Debt & liquidity",
      body: hasDebt
        ? `Total debt has ${direction(debtTrendPct)} ${Math.abs(debtTrendPct).toFixed(1)}%, while liquid savings have ${changeWord(liquidSavingsGrowthPct)} ` +
          `${Math.abs(liquidSavingsGrowthPct).toFixed(1)}% and investment balances (EPF, ETF, other) have ${changeWord(investmentGrowthPct)} ${Math.abs(investmentGrowthPct).toFixed(1)}%. ` +
          `${debtFalling ? "Falling debt alongside growing cash and investment buffers points to real spare capacity for this strategy." : "Debt is not clearly falling, which competes with any new commitment even if other signals look positive."}`
        : `This profile carries no recorded debt. Liquid savings have ${changeWord(liquidSavingsGrowthPct)} ${Math.abs(liquidSavingsGrowthPct).toFixed(1)}% and investment balances have ${changeWord(investmentGrowthPct)} ${Math.abs(investmentGrowthPct).toFixed(1)}% over the same period, with no debt service competing for cash flow.`,
    },
  ];

  const narrative = `${verdictSummary} ${sections.map((s) => s.body).join(" ")}`;

  const chartData = history.map((h) => ({
    month: h.snapshot_month.slice(0, 7),
    income: parseLkr(h.gross_monthly_income),
    savingsRatePct: Number((h.savings_rate * 100).toFixed(2)),
  }));

  const incomeSeries = history.map((h) => parseLkr(h.gross_monthly_income));
  const debtSeries = history.map((h) => parseLkr(h.total_debt));
  const liquidSeries = history.map((h) => parseLkr(h.liquid_savings));
  const investSeries = history.map(
    (h) => parseLkr(h.existing_investments) + parseLkr(h.epf_balance) + parseLkr(h.etf_balance),
  );

  const incomeIndexed = indexSeries(incomeSeries);
  const debtIndexed = hasDebt ? indexSeries(debtSeries) : null;
  const liquidIndexed = indexSeries(liquidSeries);
  const investIndexed = indexSeries(investSeries);

  const indexedChartData = history.map((h, i) => ({
    month: h.snapshot_month.slice(0, 7),
    income: incomeIndexed[i],
    debt: debtIndexed ? debtIndexed[i] : null,
    liquidSavings: liquidIndexed[i],
    investments: investIndexed[i],
  }));

  return {
    verdict,
    verdictSummary,
    adoptionProbability,
    incomeGrowthPct,
    savingsRateStart,
    savingsRateEnd,
    savingsRateDeltaPts,
    debtTrendPct,
    liquidSavingsGrowthPct,
    investmentGrowthPct,
    signals,
    narrative,
    sections,
    chartData,
    indexedChartData,
  };
}
