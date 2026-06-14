import { useCallback, useId, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Check, Loader2, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";

import { postSearchStrategiesFromFinancialInputs, postSearchStrategiesMlRank } from "../api";
import { ExplorerCharts } from "../components/explorer-charts";
import { SearchStrategiesTable } from "../components/search-strategies-table";
import { formatLkrAmount, parseDecimalSafe } from "../format-lkr";
import type {
  TaxOptBEmploymentTypeV1,
  TaxOptBSearchStrategiesFromFinancialInputsRequestV1,
  TaxOptBSearchStrategiesMlRankRequestV1,
  TaxOptBSearchStrategiesResponseV1,
  TaxOptBStrategySearchRankByV1,
} from "../types";

function digitsOnly(s: string): string {
  return s.replace(/\D/g, "");
}

function formatMoneyInputDisplay(digitString: string): string {
  if (!digitString) return "";
  const n = Number(digitString);
  if (!Number.isFinite(n)) return digitString;
  return n.toLocaleString("en-LK");
}

function formatEffectiveRate(rateStr: string | null | undefined): string | null {
  if (rateStr == null || rateStr === "") return null;
  const n = parseFloat(String(rateStr).replace(/%/g, "").trim());
  if (!Number.isFinite(n)) return String(rateStr);
  if (n > 0 && n <= 1) return `${(n * 100).toFixed(2)}%`;
  return `${n}%`;
}


const FILING_DEADLINE = new Date("2026-11-30");

function getDaysUntilDeadline(): number {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const diff = FILING_DEADLINE.getTime() - today.getTime();
  return Math.ceil(diff / (1000 * 60 * 60 * 24));
}

function displayStrategyName(raw: string): string {
  return raw.replace(/\bcap_subset_\d+\b/gi, "").replace(/\s+/g, " ").trim();
}

/** Plain-language cleanup for API-generated ranking copy (no jargon in UI). */
function sanitizeExplorerExplanationText(s: string): string {
  let t = s.trim();
  t = t.replace(/\btop_k\b/gi, "shortlist");
  t = t.replace(/\bdeterministic sort\b/gi, "standard ranking");
  t = t.replace(/\bcap_subset bitmask\b/gi, "relief combination");
  t = t.replace(/\bcap_subset_\d+\b/gi, "");
  t = t.replace(/ties are broken by the relief combination \(lower mask wins\)/gi, "equal tax is broken by internal tie rules");
  t = t.replace(/ties are broken by tie-break rules/gi, "equal tax is broken by internal tie rules");
  t = t.replace(/\(violations empty\)/gi, "");
  t = t.replace(/\bviolations empty\b/gi, "no compliance issues");
  t = t.replace(
    /Among passing strategies in this ranked table \([^)]*\), this candidate is first under the selected objective;[^.]*\./gi,
    "Among the legal strategies in this list, this one ranks first for lowest tax.",
  );
  t = t.replace(
    /Compliance:\s*passed all evaluated cap rules for this strategy[^.]*\./gi,
    "All deduction limits and rules checked out for this strategy.",
  );
  t = t.replace(/\s{2,}/g, " ").replace(/\s+([.,])/g, "$1").trim();
  return t;
}

const ASSESSMENT_YEAR_OPTIONS: readonly { value: string; label: string }[] = Object.freeze(
  Array.from({ length: 2025 - 2018 + 1 }, (_, i) => {
    const y = 2018 + i;
    const yy = (y + 1) % 100;
    return { value: `${y}_${yy.toString().padStart(2, "0")}`, label: `${y}/${yy.toString().padStart(2, "0")}` };
  }),
);

export function ExplorerPage() {
  const formId = useId();
  const [taxYear, setTaxYear] = useState("2024_25");
  const [employmentType, setEmploymentType] = useState<TaxOptBEmploymentTypeV1>("employee");
  const residency = "resident" as const;
  const dependents = "0";
  const [salary, setSalary] = useState("20000000");
  const [business, setBusiness] = useState("400000");
  const [investment, setInvestment] = useState("10000");
  const [otherIncome, setOtherIncome] = useState("0");
  const [topK] = useState("5");
  const [rankBy] = useState<TaxOptBStrategySearchRankByV1>("total_tax");
  const [maxCandidates] = useState("100");
  const [explanationDetail] = useState<"summary" | "detailed">("summary");
  const [showSpending, setShowSpending] = useState(false);
  const [actualSpending, setActualSpending] = useState<Record<string, string>>({});

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mlError, setMlError] = useState<string | null>(null);
  const [ruleData, setRuleData] = useState<TaxOptBSearchStrategiesResponseV1 | null>(null);
  const [mlData, setMlData] = useState<TaxOptBSearchStrategiesResponseV1 | null>(null);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const toggleExpand = useCallback((candidateId: string) => {
    setExpanded((p) => ({ ...p, [candidateId]: !p[candidateId] }));
  }, []);

  const buildPayload = useCallback((): TaxOptBSearchStrategiesFromFinancialInputsRequestV1 => {
    const k = Math.max(1, Math.min(64, parseInt(topK, 10) || 10));
    const maxC = Math.max(1, Math.min(10_000, parseInt(maxCandidates, 10) || 500));
    return {
      tax_year: taxYear.trim(),
      employment_type: employmentType,
      dependents: Math.max(0, Math.min(20, parseInt(dependents, 10) || 0)),
      annual_salary_income: salary.trim().replace(/,/g, "") || "0",
      annual_business_income: business.trim().replace(/,/g, "") || "0",
      annual_investment_income: investment.trim().replace(/,/g, "") || "0",
      annual_other_income: otherIncome.trim().replace(/,/g, "") || "0",
      residency,
      deductions: Object.entries(actualSpending)
        .filter(([, amt]) => amt && Number(amt.replace(/,/g, "")) > 0)
        .map(([relief_code, amount_annual]) => ({
          relief_code,
          amount_annual: amount_annual.replace(/,/g, ""),
        })),
      investments: [],
      strategy_notes: null,
      top_k: k,
      rank_by: rankBy,
      max_candidates: maxC,
      baseline_candidate_id: null,
      include_result_detail: true,
      include_explanations: true,
      explanation_detail: explanationDetail,
    };
  }, [
    taxYear,
    employmentType,
    dependents,
    salary,
    business,
    investment,
    otherIncome,
    residency,
    topK,
    rankBy,
    maxCandidates,
    explanationDetail,
    actualSpending,
  ]);

  const buildMlPayload = useCallback((): TaxOptBSearchStrategiesMlRankRequestV1 => {
    const base = buildPayload();
    const cap = base.max_candidates ?? 500;
    return {
      ...base,
      feature_version: "v2",
      max_ml_candidates: Math.min(500, Math.max(cap, 100)),
      model_bundle_path: null,
    };
  }, [buildPayload]);

  const onRun = async () => {
    setError(null);
    setMlError(null);
    setRuleData(null);
    setMlData(null);
    setLoading(true);
    try {
      const [ruleResult, mlResult] = await Promise.allSettled([
        postSearchStrategiesFromFinancialInputs(buildPayload()),
        postSearchStrategiesMlRank(buildMlPayload()),
      ]);
      if (ruleResult.status === "rejected") {
        setError(ruleResult.reason instanceof Error ? ruleResult.reason.message : String(ruleResult.reason));
        return;
      }
      setRuleData(ruleResult.value);
      if (mlResult.status === "rejected") {
        setMlError(mlResult.reason instanceof Error ? mlResult.reason.message : String(mlResult.reason));
      } else {
        setMlData(mlResult.value);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  const baselineRow = ruleData?.rows.find((r) => r.candidate_id === ruleData.baseline_candidate_id);
  const ruleBestRow = ruleData?.rows[0];
  const mlBestRow = mlData?.rows[0];
  const strategiesAgree =
    mlBestRow != null &&
    ruleBestRow != null &&
    mlBestRow.candidate_id === ruleBestRow.candidate_id;
  const hybridBestRow = mlBestRow ?? ruleBestRow;
  const hybridIsAi = mlBestRow != null;

  function computeSavings(baseline: string | null | undefined, best: string | null | undefined) {
    const b = parseDecimalSafe(baseline);
    const t = parseDecimalSafe(best);
    if (b == null || t == null || b <= 0) return { lkr: null, pct: null };
    const lkr = Math.max(0, b - t);
    const pct = (((b - t) / b) * 100).toFixed(1);
    return { lkr, pct };
  }

  const tableRankedBySubtitle = useMemo(
    () =>
      mlData
        ? "Ranked by highest tax saving among compliant strategies"
        : "Ranked by lowest total tax",
    [mlData],
  );

  const taxYearLabel = ASSESSMENT_YEAR_OPTIONS.find((o) => o.value === taxYear)?.label ?? taxYear;
  const rankingLine = useMemo(
    () => `Assessment year ${taxYearLabel} · Rule-based${mlData ? " + AI analysis" : " ranking"}`,
    [taxYearLabel, mlData],
  );

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-8 pb-10">
      <div className="overflow-hidden rounded-xl border border-border/80 bg-card shadow-sm">
        <div
          className="h-1.5 w-full bg-gradient-to-r from-primary via-primary/90 to-emerald-800/80"
          aria-hidden
        />
        <div className="px-6 py-5">
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">Find My Best Tax Strategy</h1>
          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
            Tell us your income and we'll instantly rank every legal relief combination, showing you exactly how much you could save this year.
          </p>
        </div>
      </div>

      <div className="rounded-2xl border border-border bg-card px-6 py-5 shadow-sm">
        <p className="mb-4 text-xs font-semibold uppercase tracking-widest text-muted-foreground">How it works</p>
        <div className="flex items-center">
          {([
            { n: 1, label: "Enter your income", sub: "Salary, business & more" },
            { n: 2, label: "We test 64 combos", sub: "Every legal relief mix" },
            { n: 3, label: "AI picks the best", sub: "Ranked by tax savings" },
            { n: 4, label: "See why it wins", sub: "Transparent rule trace" },
            { n: 5, label: "Plan your payments", sub: "Quarterly schedule" },
          ] as const).map((step, i, arr) => (
            <div key={step.n} className="flex flex-1 items-center">
              <div className="flex flex-col items-center gap-2 text-center">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-bold text-primary-foreground shadow-md">
                  {step.n}
                </div>
                <div>
                  <p className="text-xs font-semibold text-foreground">{step.label}</p>
                  <p className="text-[10px] text-muted-foreground">{step.sub}</p>
                </div>
              </div>
              {i < arr.length - 1 ? (
                <div className="mb-7 h-px flex-1 bg-gradient-to-r from-primary/40 to-primary/10" />
              ) : null}
            </div>
          ))}
        </div>
      </div>

      {(() => {
        const daysLeft = getDaysUntilDeadline();
        if (daysLeft < 0) return null;
        const urgent = daysLeft <= 60;
        return (
          <div className={`flex items-center gap-3 rounded-xl border px-5 py-3 text-sm ${
            urgent
              ? "border-red-500/30 bg-red-50/60 text-red-900 dark:bg-red-950/30 dark:text-red-100"
              : "border-amber-500/30 bg-amber-50/50 text-amber-950 dark:bg-amber-950/30 dark:text-amber-100"
          }`}>
            <span className={`text-xl ${urgent ? "animate-pulse" : ""}`}>📅</span>
            <div>
              <span className="font-semibold">
                {daysLeft} day{daysLeft !== 1 ? "s" : ""} until filing deadline —
              </span>
              {" "}Income tax returns for 2025/26 must be filed by{" "}
              <span className="font-semibold">November 30, 2026</span>.
              {" "}Find your best strategy below before the deadline.
            </div>
          </div>
        );
      })()}

      <Card className="rounded-xl border border-border/80 bg-card shadow-sm">
        <CardHeader className="p-6 pb-2">
          <CardTitle className="text-base font-semibold">Your financial profile</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6 p-6 pt-2">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="grid gap-2">
              <Label htmlFor={`${formId}-employment`}>Employment type</Label>
              <Select
                id={`${formId}-employment`}
                value={employmentType}
                onChange={(e) => setEmploymentType(e.target.value as TaxOptBEmploymentTypeV1)}
                className="h-10"
              >
                <option value="employee">Employee</option>
                <option value="self_employed">Self-employed</option>
                <option value="business_owner">Business owner</option>
                <option value="other">Other</option>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor={`${formId}-salary`}>Annual salary (LKR)</Label>
              <div className="flex overflow-hidden rounded-md border border-input shadow-sm focus-within:ring-2 focus-within:ring-ring">
                <span className="flex items-center border-r border-input bg-muted/30 px-3 text-sm text-muted-foreground">
                  LKR
                </span>
                <Input
                  id={`${formId}-salary`}
                  inputMode="numeric"
                  autoComplete="off"
                  placeholder="20,000,000"
                  value={formatMoneyInputDisplay(salary)}
                  onChange={(e) => setSalary(digitsOnly(e.target.value))}
                  className="h-10 border-0 text-right tabular-nums focus-visible:ring-0 focus-visible:ring-offset-0"
                />
              </div>
            </div>
            <div className="grid gap-2">
              <div>
                <Label htmlFor={`${formId}-business`}>Annual business income (LKR)</Label>
                <p className="text-xs text-muted-foreground">&nbsp;</p>
              </div>
              <div className="flex overflow-hidden rounded-md border border-input shadow-sm focus-within:ring-2 focus-within:ring-ring">
                <span className="flex items-center border-r border-input bg-muted/30 px-3 text-sm text-muted-foreground">
                  LKR
                </span>
                <Input
                  id={`${formId}-business`}
                  inputMode="numeric"
                  autoComplete="off"
                  placeholder="400,000"
                  value={formatMoneyInputDisplay(business)}
                  onChange={(e) => setBusiness(digitsOnly(e.target.value))}
                  className="h-10 border-0 text-right tabular-nums focus-visible:ring-0 focus-visible:ring-offset-0"
                />
              </div>
            </div>
            <div className="grid gap-2">
              <div>
                <Label htmlFor={`${formId}-investment`}>Annual investment income (LKR)</Label>
                <p className="text-xs text-muted-foreground">Dividends, interest, rental income (IRD Form IT01)</p>
              </div>
              <div className="flex overflow-hidden rounded-md border border-input shadow-sm focus-within:ring-2 focus-within:ring-ring">
                <span className="flex items-center border-r border-input bg-muted/30 px-3 text-sm text-muted-foreground">
                  LKR
                </span>
                <Input
                  id={`${formId}-investment`}
                  inputMode="numeric"
                  autoComplete="off"
                  placeholder="10,000"
                  value={formatMoneyInputDisplay(investment)}
                  onChange={(e) => setInvestment(digitsOnly(e.target.value))}
                  className="h-10 border-0 text-right tabular-nums focus-visible:ring-0 focus-visible:ring-offset-0"
                />
              </div>
            </div>
            <div className="grid gap-2">
              <Label htmlFor={`${formId}-other`}>Annual other income (LKR)</Label>
              <div className="flex overflow-hidden rounded-md border border-input shadow-sm focus-within:ring-2 focus-within:ring-ring">
                <span className="flex items-center border-r border-input bg-muted/30 px-3 text-sm text-muted-foreground">
                  LKR
                </span>
                <Input
                  id={`${formId}-other`}
                  inputMode="numeric"
                  autoComplete="off"
                  placeholder="0"
                  value={formatMoneyInputDisplay(otherIncome)}
                  onChange={(e) => setOtherIncome(digitsOnly(e.target.value))}
                  className="h-10 border-0 text-right tabular-nums focus-visible:ring-0 focus-visible:ring-offset-0"
                />
              </div>
            </div>
            <div className="grid gap-2">
              <Label htmlFor={`${formId}-year`}>Assessment year</Label>
              <Select
                id={`${formId}-year`}
                value={taxYear}
                onChange={(e) => setTaxYear(e.target.value)}
                className="h-10"
              >
                {ASSESSMENT_YEAR_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </Select>
            </div>
          </div>

          <div className="border-t border-border pt-4">
            <button
              type="button"
              onClick={() => setShowSpending((p) => !p)}
              className="flex items-center gap-1.5 text-sm font-medium text-primary hover:underline"
            >
              {showSpending ? "▲ Hide actual spending" : "▼ Enter what you actually spent this year (optional)"}
            </button>
            <p className="mt-1 text-xs text-muted-foreground">
              Enter real amounts you paid — the system will cap them at the statutory limit and find the best combination from your actual spending.
            </p>
            {showSpending ? (
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                {([
                  { code: "life_insurance_premium",   label: "Life insurance paid",       cap: "Cap: LKR 100,000" },
                  { code: "health_insurance_premium",  label: "Health insurance paid",     cap: "Cap: LKR 75,000" },
                  { code: "home_loan_interest",        label: "Home loan interest paid",   cap: "Cap: LKR 600,000" },
                  { code: "rent_relief",               label: "Rent paid this year",       cap: "Cap: 25% of rent, max LKR 300,000" },
                  { code: "charitable_donations",      label: "Charitable donations",      cap: "Cap: 33% of taxable income" },
                  { code: "retirement_contribution",   label: "Retirement contribution",   cap: "Cap: LKR 600,000" },
                ] as const).map(({ code, label, cap }) => (
                  <div key={code} className="grid gap-1">
                    <label className="text-xs font-medium text-foreground">{label}</label>
                    <p className="text-[10px] text-muted-foreground">{cap}</p>
                    <div className="flex overflow-hidden rounded-md border border-input shadow-sm focus-within:ring-2 focus-within:ring-ring">
                      <span className="flex items-center border-r border-input bg-muted/30 px-3 text-sm text-muted-foreground">
                        LKR
                      </span>
                      <Input
                        inputMode="numeric"
                        autoComplete="off"
                        placeholder="0"
                        value={actualSpending[code] ? formatMoneyInputDisplay(actualSpending[code].replace(/,/g, "")) : ""}
                        onChange={(e) => {
                          const v = digitsOnly(e.target.value);
                          setActualSpending((prev) => ({ ...prev, [code]: v }));
                        }}
                        className="h-9 border-0 text-right tabular-nums focus-visible:ring-0 focus-visible:ring-offset-0"
                      />
                    </div>
                  </div>
                ))}
              </div>
            ) : null}
          </div>

          <Button
            type="button"
            disabled={loading}
            onClick={() => void onRun()}
            className="h-11 w-full bg-primary text-primary-foreground hover:bg-primary/90"
          >
            {loading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Searching…
              </>
            ) : (
              <>
                <Sparkles className="mr-2 h-4 w-4 opacity-90" />
                Find my best strategy
              </>
            )}
          </Button>
        </CardContent>
      </Card>

      {error ? (
        <Card className="rounded-xl border border-destructive/30 bg-destructive/5">
          <CardHeader className="p-6 pb-2">
            <CardTitle className="text-base font-semibold text-destructive">We couldn&apos;t finish that</CardTitle>
          </CardHeader>
          <CardContent className="px-6 pb-6 pt-0">
            <p className="text-sm text-destructive/90">{error}</p>
          </CardContent>
        </Card>
      ) : null}

      {mlError && !error ? (
        <Card className="rounded-xl border border-amber-500/30 bg-amber-50/40 dark:bg-amber-950/20">
          <CardContent className="px-6 py-4">
            <p className="text-sm text-amber-900 dark:text-amber-100">
              <span className="font-semibold">AI analysis unavailable: </span>
              The AI ranking service timed out or returned an error. Rule-based results are shown below.
            </p>
          </CardContent>
        </Card>
      ) : null}

      {/* ── 1. Stats bar ── */}
      {ruleData?.optimization_meta && baselineRow && hybridBestRow ? (() => {
        const { lkr: savingsLkr } = computeSavings(baselineRow.total_tax, hybridBestRow.total_tax);
        const total = ruleData.optimization_meta.strategies_evaluated;
        const legal = ruleData.optimization_meta.legal_strategies_count;
        const rejected = ruleData.optimization_meta.rejected_strategies_count;
        return (
          <div className="overflow-hidden rounded-xl border border-border/70 bg-card shadow-sm">
            <div className="h-1 w-full bg-gradient-to-r from-emerald-500 via-primary to-rose-900" aria-hidden />
            <div className="grid divide-y divide-border/50 sm:divide-x sm:divide-y-0 sm:grid-cols-4">
              <div className="flex flex-col items-center justify-center px-4 py-5 text-center">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">We checked</p>
                <p className="mt-1.5 text-2xl font-bold tabular-nums text-foreground">{total}</p>
                <p className="mt-0.5 text-[11px] text-muted-foreground">combinations</p>
              </div>
              <div className="flex flex-col items-center justify-center px-4 py-5 text-center">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Within IRD rules</p>
                <p className="mt-1.5 text-2xl font-bold tabular-nums text-emerald-600 dark:text-emerald-400">{legal}</p>
                <p className="mt-0.5 text-[11px] text-muted-foreground">all passed ✓</p>
              </div>
              <div className="flex flex-col items-center justify-center px-4 py-5 text-center">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Rejected</p>
                <p className={`mt-1.5 text-2xl font-bold tabular-nums ${rejected > 0 ? "text-destructive" : "text-muted-foreground"}`}>{rejected}</p>
                <p className="mt-0.5 text-[11px] text-muted-foreground">illegal / over cap</p>
              </div>
              <div className="flex flex-col items-center justify-center px-4 py-5 text-center">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">You could save</p>
                <p className="mt-1.5 text-2xl font-bold tabular-nums text-primary">
                  {savingsLkr != null && savingsLkr > 0 ? formatLkrAmount(savingsLkr) : "—"}
                </p>
                <p className="mt-0.5 text-[11px] text-muted-foreground">vs claiming nothing</p>
              </div>
            </div>
            <div className="border-t border-border/40 px-5 py-2">
              <p className="text-[11px] text-muted-foreground">{rankingLine}</p>
            </div>
          </div>
        );
      })() : null}

      {/* ── 2. Recommendation cards ── */}
      {ruleData && baselineRow && hybridBestRow ? (
        <Card className="overflow-hidden rounded-xl border border-border/80 bg-card shadow-sm">
          <div className="h-1 w-full bg-gradient-to-r from-emerald-600/80 via-primary to-emerald-800/60" aria-hidden />
          <div className="space-y-4 p-6">
            <p className="text-sm text-muted-foreground">
              We tested <strong className="text-foreground">{ruleData.optimization_meta?.strategies_evaluated ?? 64} combinations</strong> of legal tax reliefs for your income profile. Here's what we found:
            </p>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="flex flex-col gap-3 rounded-2xl border border-border bg-muted/30 p-6">
                <div className="flex items-center gap-2">
                  <span className="flex h-7 w-7 items-center justify-center rounded-full bg-muted text-base">❌</span>
                  <p className="text-sm font-semibold text-foreground">If you claim nothing</p>
                </div>
                <p className="text-xs text-muted-foreground">What you'd owe with zero deductions claimed on your tax return</p>
                <div className="mt-1">
                  <p className="text-4xl font-bold tracking-tight text-foreground tabular-nums">
                    {formatLkrAmount(parseDecimalSafe(baselineRow.total_tax) ?? baselineRow.total_tax)}
                  </p>
                  {formatEffectiveRate(baselineRow.effective_rate) ? (
                    <p className="mt-1.5 text-sm text-muted-foreground">Effective tax rate: {formatEffectiveRate(baselineRow.effective_rate)}</p>
                  ) : null}
                </div>
              </div>
              <div className={`relative flex flex-col gap-3 overflow-hidden rounded-2xl border-2 p-6 shadow-md ${hybridIsAi ? "border-primary bg-gradient-to-br from-primary/5 via-card to-card" : "border-amber-400 bg-gradient-to-br from-amber-50/80 via-card to-card dark:from-amber-950/30"}`}>
                <div className="flex flex-wrap items-center gap-2">
                  <span className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-bold text-white shadow ${hybridIsAi ? "bg-primary" : "bg-amber-500"}`}>✦ Recommended strategy</span>
                  <span className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-semibold ${hybridIsAi ? "bg-primary text-primary-foreground" : "bg-amber-500 text-white"}`}>{hybridIsAi ? "🤖 AI-powered" : "📋 Rule-based"}</span>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Our best pick for you</p>
                  <p className="mt-1 text-lg font-bold leading-snug text-foreground">{displayStrategyName(hybridBestRow.display_name)}</p>
                </div>
                <div>
                  <p className="text-4xl font-bold tracking-tight text-foreground tabular-nums">
                    {formatLkrAmount(parseDecimalSafe(hybridBestRow.total_tax) ?? hybridBestRow.total_tax)}
                  </p>
                  {(() => {
                    const { lkr, pct } = computeSavings(baselineRow.total_tax, hybridBestRow.total_tax);
                    return lkr != null && lkr > 0 ? (
                      <p className="mt-2 inline-block rounded-full bg-emerald-100 px-3 py-1 text-sm font-semibold text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300">
                        💰 You save {formatLkrAmount(lkr)}{pct != null ? ` — ${pct}% less` : ""}
                      </p>
                    ) : null;
                  })()}
                  {formatEffectiveRate(hybridBestRow.effective_rate) ? (
                    <p className="mt-2 text-sm text-muted-foreground">Effective tax rate: {formatEffectiveRate(hybridBestRow.effective_rate)}</p>
                  ) : null}
                </div>
              </div>
            </div>
            {hybridIsAi && !strategiesAgree && ruleBestRow ? (
              <div className="flex items-start gap-3 rounded-xl border border-primary/20 bg-primary/5 px-4 py-3">
                <span className="mt-0.5 text-base">💡</span>
                <p className="text-sm text-foreground"><span className="font-semibold">Why this one?</span>{" "}Our AI tested every legal combination and picked this one because it saves you the most money while keeping upfront costs low.</p>
              </div>
            ) : hybridIsAi && strategiesAgree ? (
              <div className="flex items-start gap-3 rounded-xl border border-emerald-300 bg-emerald-50/60 px-4 py-3 dark:border-emerald-700/40 dark:bg-emerald-950/30">
                <span className="mt-0.5 text-base">✅</span>
                <p className="text-sm text-foreground"><span className="font-semibold">Great news!</span>{" "}Both our AI and rule-based checks agree — this is the best and most practical strategy for your profile.</p>
              </div>
            ) : null}
          </div>
        </Card>
      ) : null}

      {/* ── 3. Why this strategy wins ── */}
      {hybridBestRow ? (
        <div className="overflow-hidden rounded-2xl border border-border/60 bg-card shadow-sm">
          <div className="border-b border-border/60 px-6 py-4">
            <div className="flex items-center gap-2">
              <span className="text-lg">💡</span>
              <h3 className="text-base font-bold text-foreground">Why we picked this strategy</h3>
            </div>
            <p className="mt-1 text-sm text-muted-foreground">Here's a simple explanation of how this recommendation was chosen</p>
          </div>
          <div className="grid gap-3 px-6 py-4 sm:grid-cols-3">
            <div className="rounded-xl border border-border/60 bg-muted/20 px-4 py-3">
              <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Step 1 — We tested everything</div>
              <div className="text-sm text-foreground">We checked all <strong>64 possible combinations</strong> of tax reliefs against IRD rules. Only the ones that pass every rule are shown to you.</div>
            </div>
            <div className="rounded-xl border border-primary/30 bg-primary/5 px-4 py-3">
              <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-primary">Step 2 — AI ranked them</div>
              <div className="text-sm text-foreground">Our AI model ranked the passing strategies by <strong>how much tax each one saves</strong>. The strategy at rank #1 gives you the <strong>biggest legal tax reduction</strong> for your income profile.</div>
            </div>
            <div className="rounded-xl border border-emerald-300/60 bg-emerald-50/40 px-4 py-3 dark:border-emerald-700/40 dark:bg-emerald-950/20">
              <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-emerald-700 dark:text-emerald-400">Step 3 — It's fully compliant</div>
              <div className="text-sm text-foreground">Every relief in this strategy is <strong>within IRD limits</strong>. No rule was broken — you can file this with confidence.</div>
            </div>
          </div>
        </div>
      ) : null}

      {/* ── 4. Table intro + Strategies table ── */}
      {ruleData?.optimization_meta ? (
        <div className="rounded-2xl border border-border/60 bg-muted/20 px-5 py-4">
          <div className="flex items-start gap-3">
            <span className="mt-0.5 text-lg">🔎</span>
            <div>
              <p className="text-sm font-semibold text-foreground">
                Why do you see only {(mlData ?? ruleData)?.rows?.length ?? 5} strategies here?
              </p>
              <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                We tested all <strong className="text-foreground">{ruleData.optimization_meta.strategies_evaluated}</strong> combinations behind the scenes and kept only the <strong className="text-foreground">top {(mlData ?? ruleData)?.rows?.length ?? 5}</strong> to show you — ranked by how much tax each one saves. The table includes the <strong className="text-foreground">baseline (no claims)</strong> at the bottom so you can see your starting point.
              </p>
            </div>
          </div>
        </div>
      ) : null}

      <SearchStrategiesTable
        data={mlData ?? ruleData}
        expanded={expanded}
        onToggleExpand={toggleExpand}
        mlAssisted={Boolean(mlData?.ml_meta)}
        baselineCandidateId={(mlData ?? ruleData)?.baseline_candidate_id ?? null}
        rankedBySubtitle={tableRankedBySubtitle}
      />

      {/* ── 5. Tax comparison charts ── */}
      {ruleData && baselineRow && ruleBestRow ? (
        <Card className="rounded-xl border border-border/80 bg-card p-6 shadow-sm">
          <CardHeader className="p-0 pb-4">
            <CardTitle className="text-base font-semibold">Tax comparison</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {hybridBestRow ? (
              <ExplorerCharts
                data={mlData ?? ruleData}
                baselineRow={baselineRow}
                bestRow={hybridBestRow}
                mlAssisted={!!mlData?.ml_meta}
              />
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      {/* ── 6. Strategy breakdown ── */}
      {hybridBestRow?.breakdown ? (
        <Card className="rounded-xl border border-border/80 bg-card shadow-sm">
          <CardHeader className="p-6 pb-2">
            <CardTitle className="text-base font-semibold">How your tax was calculated</CardTitle>
            <p className="mt-1 text-sm text-muted-foreground">Step-by-step breakdown for the recommended strategy</p>
          </CardHeader>
          <CardContent className="px-6 pb-6 pt-0">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
              {([
                { label: "Total income",          value: hybridBestRow.breakdown.gross_income_lkr,                    highlight: false },
                { label: "Personal relief",        value: hybridBestRow.breakdown.personal_relief_lkr,                highlight: false },
                { label: "Relief deductions",      value: hybridBestRow.breakdown.total_statutory_deductions_lkr,     highlight: false },
                { label: "Total reliefs applied",  value: hybridBestRow.breakdown.total_reliefs_lkr,                  highlight: false },
                { label: "Taxable income",         value: hybridBestRow.breakdown.taxable_income_lkr,                 highlight: false },
                { label: "Total tax",              value: hybridBestRow.breakdown.total_tax_lkr,                      highlight: false },
                { label: "Effective tax rate",     value: hybridBestRow.breakdown.effective_tax_rate,                 highlight: false, isRate: true },
                { label: "You save vs no claims",  value: hybridBestRow.breakdown.tax_savings_vs_baseline_lkr,        highlight: true },
              ] as { label: string; value: unknown; highlight: boolean; isRate?: boolean }[]).map(({ label, value, highlight, isRate }) => (
                <div key={label} className={`rounded-lg px-3 py-3 ${highlight ? "border border-emerald-300/60 bg-emerald-50/60 dark:border-emerald-700/40 dark:bg-emerald-950/20" : "bg-muted/40"}`}>
                  <p className={`text-xs font-medium ${highlight ? "text-emerald-700 dark:text-emerald-400" : "text-muted-foreground"}`}>{label}</p>
                  <p className={`mt-1 text-sm font-semibold tabular-nums ${highlight ? "text-emerald-700 dark:text-emerald-400" : "text-foreground"}`}>
                    {isRate ? String(value ?? "—") : value != null ? formatLkrAmount(parseDecimalSafe(String(value)) ?? Number(value)) : "—"}
                  </p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      ) : null}

      {/* ── 7. Applied reliefs rule trace ── */}
      {hybridBestRow?.applied_relief_summary && hybridBestRow.applied_relief_summary.length > 0 ? (
        <Card className="rounded-xl border border-border/80 bg-card shadow-sm">
          <CardHeader className="p-6 pb-2">
            <CardTitle className="text-base font-semibold">Reliefs that reduced your tax</CardTitle>
            <p className="mt-1 text-sm text-muted-foreground">Each of these was claimed up to the IRD legal limit</p>
          </CardHeader>
          <CardContent className="px-6 pb-6 pt-0">
            <div className="grid gap-2 sm:grid-cols-2 md:grid-cols-3">
              {hybridBestRow.applied_relief_summary
                .filter((r) => r.relief_code !== "compliance_validation" && parseDecimalSafe(r.allowed ?? "") !== 0)
                .map((relief, i) => (
                <div key={`${relief.relief_code}-${i}`} className="flex items-center justify-between rounded-lg border border-border/60 bg-muted/20 px-4 py-3">
                  <span className="text-sm font-medium text-foreground capitalize">
                    {(relief.label || relief.relief_code || "").replace(/_/g, " ")}
                  </span>
                  {relief.allowed != null && relief.allowed !== "" ? (
                    <span className="ml-3 shrink-0 rounded-full bg-primary px-2.5 py-0.5 text-xs font-semibold text-primary-foreground">
                      {formatLkrAmount(parseDecimalSafe(relief.allowed) ?? Number(relief.allowed))}
                    </span>
                  ) : null}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      ) : null}

      {/* ── 8. Tax payment schedule ── */}
      {hybridBestRow?.breakdown?.total_tax_lkr != null ? (() => {
        const totalTax = parseDecimalSafe(hybridBestRow.breakdown.total_tax_lkr) ?? 0;
        const q = Math.round(totalTax / 4);
        const installments = [
          { date: "15 Aug 2025", label: "1st payment", amount: q },
          { date: "15 Nov 2025", label: "2nd payment", amount: q },
          { date: "15 Feb 2026", label: "3rd payment", amount: q },
          { date: "15 May 2026", label: "4th payment", amount: q },
          { date: "30 Nov 2026", label: "Final + filing", amount: Math.round(totalTax - q * 4 + q), isFinal: true },
        ];
        return (
          <Card className="rounded-xl border border-border/80 bg-card shadow-sm">
            <CardHeader className="p-6 pb-4">
              <CardTitle className="text-base font-semibold">When to pay your tax — 2025/26</CardTitle>
              <p className="mt-1 text-sm text-muted-foreground">
                IRD requires 4 quarterly payments. Your total tax is{" "}
                <span className="font-semibold text-foreground">{formatLkrAmount(totalTax)}</span> — split evenly below.
              </p>
            </CardHeader>
            <CardContent className="px-6 pb-6 pt-0">
              <div className="grid gap-2 sm:grid-cols-5">
                {installments.map(({ date, label, amount, isFinal }) => (
                  <div
                    key={date}
                    className={`rounded-xl border px-3 py-3 text-center ${isFinal ? "border-primary/40 bg-primary/5" : "border-border/60 bg-muted/20"}`}
                  >
                    <p className={`text-[10px] font-semibold uppercase tracking-wide ${isFinal ? "text-primary" : "text-muted-foreground"}`}>{label}</p>
                    <p className="mt-1 text-sm font-bold tabular-nums text-foreground">{formatLkrAmount(amount)}</p>
                    <p className="mt-1 text-[10px] text-muted-foreground">{date}</p>
                  </div>
                ))}
              </div>
              <p className="mt-3 text-xs text-muted-foreground">These are estimates. Confirm exact amounts via the IRD e-services portal before paying.</p>
            </CardContent>
          </Card>
        );
      })() : null}

      {/* ── 9. What to do next ── */}
      {hybridBestRow && ruleData ? (
        <div className="rounded-2xl border border-primary/20 bg-primary/5 px-6 py-5">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-base font-bold text-foreground">What to do next</h3>
            <span className="rounded-full border border-primary/30 bg-background px-3 py-1 text-xs font-semibold text-primary">
              Filing deadline: Nov 30, 2026
            </span>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {([
              { num: "1", title: "Check your eligibility", desc: `Make sure you actually paid for each relief in the recommended strategy — check your receipts.` },
              { num: "2", title: "Gather your documents", desc: "Collect receipts, certificates, and proof of payment for every relief you plan to claim." },
              { num: "3", title: "Compare other options", desc: "Use the Compare Strategies page to see all alternatives side by side before deciding." },
              { num: "4", title: "File your return", desc: "Submit your tax return via the IRD e-services portal before November 30, 2026." },
            ]).map((step) => (
              <div key={step.num} className="flex items-start gap-3 rounded-xl border border-border/60 bg-card px-4 py-3.5">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-[11px] font-bold text-primary-foreground">
                  {step.num}
                </span>
                <div>
                  <p className="text-sm font-semibold text-foreground">{step.title}</p>
                  <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">{step.desc}</p>
                </div>
              </div>
            ))}
          </div>
          <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-[11px] text-muted-foreground">
              These are estimates only — not legal or filing advice. Always verify with the Inland Revenue Department before filing.
            </p>
            <Button asChild variant="outline" className="shrink-0">
              <Link to="/tax/filing">Estimate tax for filing 2025/26</Link>
            </Button>
          </div>
        </div>
      ) : null}

    </div>
  );
}
