import { useCallback, useId, useMemo, useState } from "react";
import { Check, Loader2, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";

import { postSearchStrategiesFromFinancialInputs, postSearchStrategiesMlRank } from "../api";
import { ExplanationPanel } from "../components/explanation-panel";
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

const LOCKED_TAX_YEAR_LABEL = "2024/25";

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

export function ExplorerPage() {
  const formId = useId();
  const [taxYear] = useState("2024_25");
  const [employmentType, setEmploymentType] = useState<TaxOptBEmploymentTypeV1>("employee");
  const [dependents, setDependents] = useState("0");
  const [salary, setSalary] = useState("2000000");
  const [business, setBusiness] = useState("400000");
  const [otherIncome, setOtherIncome] = useState("0");
  const [topK] = useState("10");
  const [rankBy] = useState<TaxOptBStrategySearchRankByV1>("total_tax");
  const [maxCandidates] = useState("500");
  const [includeExplanations, setIncludeExplanations] = useState(true);
  const [explanationDetail] = useState<"summary" | "detailed">("summary");
  const [includeAiAnalysis, setIncludeAiAnalysis] = useState(true);

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
      annual_other_income: otherIncome.trim().replace(/,/g, "") || "0",
      deductions: [],
      investments: [],
      strategy_notes: null,
      top_k: k,
      rank_by: rankBy,
      max_candidates: maxC,
      baseline_candidate_id: null,
      include_result_detail: true,
      include_explanations: includeExplanations,
      explanation_detail: explanationDetail,
    };
  }, [
    taxYear,
    employmentType,
    dependents,
    salary,
    business,
    otherIncome,
    topK,
    rankBy,
    maxCandidates,
    includeExplanations,
    explanationDetail,
  ]);

  const buildMlPayload = useCallback((): TaxOptBSearchStrategiesMlRankRequestV1 => {
    const base = buildPayload();
    const cap = base.max_candidates ?? 500;
    return {
      ...base,
      feature_version: "v2",
      max_ml_candidates: Math.min(50_000, Math.max(cap, 2048)),
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
      if (includeAiAnalysis) {
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
      } else {
        const result = await postSearchStrategiesFromFinancialInputs(buildPayload());
        setRuleData(result);
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
        ? "Ranked by AI recommendation among compliant strategies"
        : "Ranked by lowest total tax",
    [mlData],
  );

  const rankingLine = useMemo(
    () => `Assessment year ${LOCKED_TAX_YEAR_LABEL} · Rule-based${mlData ? " + AI analysis" : " ranking"}`,
    [mlData],
  );

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-8 pb-10">
      <div className="overflow-hidden rounded-xl border border-border/80 bg-card shadow-sm">
        <div
          className="h-1.5 w-full bg-gradient-to-r from-primary via-primary/90 to-emerald-800/80"
          aria-hidden
        />
        <div className="px-6 py-5">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-semibold tracking-tight text-foreground">Find my best strategy</h1>
            <span className="rounded-full bg-muted px-2.5 py-0.5 text-[10px] font-medium text-muted-foreground">
              Powered by ML + rule engine
            </span>
          </div>
          <p className="mt-3 w-full text-sm leading-relaxed text-muted-foreground">
            Our AI evaluates every legal tax relief combination under Sri Lankan law and recommends the
            strategy that minimises your tax the most.
          </p>
        </div>
      </div>

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
                  value={formatMoneyInputDisplay(salary)}
                  onChange={(e) => setSalary(digitsOnly(e.target.value))}
                  className="h-10 border-0 text-right tabular-nums focus-visible:ring-0 focus-visible:ring-offset-0"
                />
              </div>
            </div>
            <div className="grid gap-2">
              <Label htmlFor={`${formId}-business`}>Annual business income (LKR)</Label>
              <div className="flex overflow-hidden rounded-md border border-input shadow-sm focus-within:ring-2 focus-within:ring-ring">
                <span className="flex items-center border-r border-input bg-muted/30 px-3 text-sm text-muted-foreground">
                  LKR
                </span>
                <Input
                  id={`${formId}-business`}
                  inputMode="numeric"
                  autoComplete="off"
                  value={formatMoneyInputDisplay(business)}
                  onChange={(e) => setBusiness(digitsOnly(e.target.value))}
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
                  value={formatMoneyInputDisplay(otherIncome)}
                  onChange={(e) => setOtherIncome(digitsOnly(e.target.value))}
                  className="h-10 border-0 text-right tabular-nums focus-visible:ring-0 focus-visible:ring-offset-0"
                />
              </div>
            </div>
            <div className="grid gap-2">
              <Label htmlFor={`${formId}-dependents`}>Dependents</Label>
              <Input
                id={`${formId}-dependents`}
                value={dependents}
                onChange={(e) => setDependents(e.target.value)}
                inputMode="numeric"
                className="h-10"
                min={0}
                max={20}
                type="number"
              />
            </div>
            <div className="hidden md:block" aria-hidden />
          </div>

          <div className="flex flex-col gap-3">
            <label className="flex cursor-pointer items-center gap-2 text-sm text-foreground">
              <input
                type="checkbox"
                checked={includeExplanations}
                onChange={(e) => setIncludeExplanations(e.target.checked)}
                className="h-4 w-4 rounded border-input"
              />
              Include explanation notes
            </label>
            <label className="flex cursor-pointer items-center gap-2 text-sm text-foreground">
              <input
                type="checkbox"
                checked={includeAiAnalysis}
                onChange={(e) => setIncludeAiAnalysis(e.target.checked)}
                className="h-4 w-4 rounded border-input"
              />
              <span>
                Include AI analysis{" "}
                <span className="rounded bg-violet-600/15 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-violet-700 dark:text-violet-300">
                  AI
                </span>
              </span>
            </label>
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

      {ruleData?.optimization_meta ? (
        <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-lg bg-muted/40 px-4 py-4">
              <p className="text-xs font-medium text-muted-foreground">Strategies evaluated</p>
              <p className="mt-1 text-2xl font-semibold tabular-nums text-foreground">
                {ruleData.optimization_meta.strategies_evaluated}
              </p>
            </div>
            <div className="rounded-lg bg-muted/40 px-4 py-4">
              <p className="text-xs font-medium text-muted-foreground">Legal strategies</p>
              <p className="mt-1 text-2xl font-semibold tabular-nums text-emerald-600 dark:text-emerald-400">
                {ruleData.optimization_meta.legal_strategies_count}
              </p>
            </div>
            <div className="rounded-lg bg-muted/40 px-4 py-4">
              <p className="text-xs font-medium text-muted-foreground">Rejected</p>
              <p
                className={`mt-1 text-2xl font-semibold tabular-nums ${
                  ruleData.optimization_meta.rejected_strategies_count > 0
                    ? "text-destructive"
                    : "text-muted-foreground"
                }`}
              >
                {ruleData.optimization_meta.rejected_strategies_count}
              </p>
            </div>
          </div>
          <p className="text-xs text-muted-foreground">{rankingLine}</p>
        </div>
      ) : null}

      {ruleData && baselineRow && hybridBestRow ? (
        <Card className="overflow-hidden rounded-xl border border-border/80 bg-card shadow-sm">
          <div className="h-1 w-full bg-gradient-to-r from-emerald-600/80 via-primary to-emerald-800/60" aria-hidden />
          <div className="space-y-4 p-6">
            <div className="grid gap-4 md:grid-cols-2">
              {/* Baseline — no relief */}
              <div className="rounded-xl border border-border/80 bg-muted/20 p-5">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Without any relief
                </p>
                <p className="mt-2 text-3xl font-semibold tracking-tight text-foreground tabular-nums">
                  {formatLkrAmount(parseDecimalSafe(baselineRow.total_tax) ?? baselineRow.total_tax)}
                </p>
                {formatEffectiveRate(baselineRow.effective_rate) ? (
                  <p className="mt-2 text-sm text-muted-foreground">
                    Effective rate {formatEffectiveRate(baselineRow.effective_rate)}
                  </p>
                ) : null}
              </div>

              {/* Single hybrid recommendation */}
              <div
                className={`rounded-xl border p-5 shadow-sm ring-1 bg-card ${
                  hybridIsAi
                    ? "border-violet-600/35 ring-violet-600/15"
                    : "border-amber-500/35 ring-amber-500/15"
                }`}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-xs font-semibold text-white ${
                      hybridIsAi ? "bg-violet-600" : "bg-amber-500"
                    }`}
                  >
                    Recommended strategy
                  </span>
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                      hybridIsAi
                        ? "bg-violet-100 text-violet-800 dark:bg-violet-900/40 dark:text-violet-200"
                        : "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200"
                    }`}
                  >
                    {hybridIsAi ? "AI-powered" : "Rule-based"}
                  </span>
                </div>
                <p className="mt-3 text-base font-semibold leading-snug text-foreground">
                  {displayStrategyName(hybridBestRow.display_name)}
                </p>
                <p className="mt-2 text-3xl font-semibold tracking-tight text-foreground tabular-nums">
                  {formatLkrAmount(parseDecimalSafe(hybridBestRow.total_tax) ?? hybridBestRow.total_tax)}
                </p>
                {(() => {
                  const { lkr, pct } = computeSavings(baselineRow.total_tax, hybridBestRow.total_tax);
                  return lkr != null && lkr > 0 ? (
                    <p className="mt-2 text-sm font-medium text-emerald-700 dark:text-emerald-400">
                      You save {formatLkrAmount(lkr)}{pct != null ? ` (${pct}% less than no reliefs)` : ""}
                    </p>
                  ) : null;
                })()}
                {formatEffectiveRate(hybridBestRow.effective_rate) ? (
                  <p className="mt-2 text-sm text-muted-foreground">
                    Effective rate {formatEffectiveRate(hybridBestRow.effective_rate)}
                  </p>
                ) : null}
              </div>
            </div>

            {/* Context note */}
            {hybridIsAi && !strategiesAgree && ruleBestRow ? (
              <div className="rounded-lg border border-muted bg-muted/30 px-4 py-3 text-sm text-muted-foreground">
                <span className="font-medium text-foreground">How this was chosen: </span>
                {mlData?.ml_meta?.utility_alpha != null
                  ? `The AI weighted ${Math.round(mlData.ml_meta.utility_alpha * 100)}% on tax savings and ${Math.round((1 - mlData.ml_meta.utility_alpha) * 100)}% on upfront cash required.`
                  : "The AI balanced tax savings against upfront cash required."}{" "}
                A higher-deduction option ({displayStrategyName(ruleBestRow.display_name)}) achieves{" "}
                {formatLkrAmount(parseDecimalSafe(ruleBestRow.total_tax) ?? ruleBestRow.total_tax)} tax but requires
                more upfront cash outlay — compare strategies in the table below to decide what fits your situation.
              </div>
            ) : hybridIsAi && strategiesAgree ? (
              <div className="rounded-lg border border-emerald-600/25 bg-emerald-50/60 px-4 py-3 text-sm text-emerald-900 dark:border-emerald-600/30 dark:bg-emerald-950/40 dark:text-emerald-50">
                Both the AI and rule-based analysis agree — this strategy gives the lowest tax and is also the most practical choice.
              </div>
            ) : null}
          </div>
        </Card>
      ) : null}

      {(mlData ?? ruleData)?.top_rank_explanation ? (
        <Card className="rounded-xl border border-border/80 bg-card shadow-sm">
          <CardHeader className="p-6 pb-2">
            <CardTitle className="text-base font-semibold">Why this strategy?</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 px-6 pb-6 pt-0">
            {mlData?.ml_meta?.utility_alpha != null ? (
              <div className="flex items-center gap-2">
                <span className="rounded-full bg-violet-600/15 px-2.5 py-0.5 text-xs font-semibold text-violet-900 dark:text-violet-100">
                  Ranked by Pareto utility (α={mlData.ml_meta.utility_alpha})
                </span>
                <span className="text-xs text-muted-foreground">
                  {Math.round(mlData.ml_meta.utility_alpha * 100)}% savings · {Math.round((1 - mlData.ml_meta.utility_alpha) * 100)}% liquidity
                </span>
              </div>
            ) : null}
            <div className="rounded-lg border border-emerald-700/25 bg-emerald-50 px-4 py-3 text-sm font-medium leading-relaxed text-emerald-950 dark:border-emerald-600/40 dark:bg-emerald-950/55 dark:text-emerald-50">
              {sanitizeExplorerExplanationText((mlData ?? ruleData)!.top_rank_explanation!.headline)}
            </div>
            <ul className="space-y-3">
              {(mlData ?? ruleData)!.top_rank_explanation!.bullets.map((b, i) => (
                <li key={i} className="flex gap-3 text-sm leading-relaxed text-foreground">
                  <Check className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600 dark:text-emerald-400" aria-hidden />
                  <span>{sanitizeExplorerExplanationText(b)}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ) : null}

      {mlData?.ml_meta?.utility_alpha != null ? (
        <Card className="rounded-xl border border-violet-600/30 bg-violet-50/40 dark:bg-violet-950/20 shadow-sm">
          <CardContent className="px-6 py-4">
            <div className="flex flex-wrap items-start gap-3">
              <span className="mt-0.5 shrink-0 rounded-full bg-violet-600/15 px-2.5 py-0.5 text-xs font-semibold text-violet-900 dark:text-violet-100">
                AI Ranking Method
              </span>
              <p className="text-sm leading-relaxed text-foreground">
                <span className="font-semibold">
                  {mlData.ml_meta.optimization_objective_label ?? `Pareto utility (α=${mlData.ml_meta.utility_alpha})`}
                </span>
                {" — "}
                This model balances{" "}
                <span className="font-medium">{Math.round(mlData.ml_meta.utility_alpha * 100)}% weight on tax savings</span>
                {" and "}
                <span className="font-medium">{Math.round((1 - mlData.ml_meta.utility_alpha) * 100)}% on financial practicality</span>
                {" "}(how much upfront cash each strategy requires). A strategy needing less cash may rank higher than one with slightly more savings.
              </p>
            </div>
          </CardContent>
        </Card>
      ) : null}

      {ruleData && baselineRow && ruleBestRow ? (
        <Card className="rounded-xl border border-border/80 bg-card p-6 shadow-sm">
          <CardHeader className="p-0 pb-4">
            <CardTitle className="text-base font-semibold">Tax comparison</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <ExplorerCharts
              data={mlData ?? ruleData}
              baselineRow={baselineRow}
              bestRow={hybridBestRow}
              mlAssisted={!!mlData?.ml_meta}
            />
          </CardContent>
        </Card>
      ) : null}

      <SearchStrategiesTable
        data={mlData ?? ruleData}
        expanded={expanded}
        onToggleExpand={toggleExpand}
        mlAssisted={Boolean(mlData?.ml_meta)}
        baselineCandidateId={(mlData ?? ruleData)?.baseline_candidate_id ?? null}
        rankedBySubtitle={tableRankedBySubtitle}
      />

      {(mlData ?? ruleData)?.explanations ? (
        <ExplanationPanel bundle={(mlData ?? ruleData)!.explanations!} title="AI advisory narrative" presentation="advisory" />
      ) : null}

      <p className="text-center text-xs text-muted-foreground">
        Estimates use MVP rules and are not legal or filing advice. Verify with the Inland Revenue Department.
      </p>
    </div>
  );
}
