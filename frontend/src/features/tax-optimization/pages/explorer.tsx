import { useCallback, useId, useState } from "react";
import { Link } from "react-router-dom";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";

import { postSearchStrategiesFromFinancialInputs } from "../api";
import { formatLkrAmount, parseDecimalSafe } from "../format-lkr";
import { ExplanationPanel } from "../components/explanation-panel";
import { ExplorerCharts } from "../components/explorer-charts";
import { SearchStrategiesTable } from "../components/search-strategies-table";
import type {
  TaxOptBEmploymentTypeV1,
  TaxOptBSearchStrategiesFromFinancialInputsRequestV1,
  TaxOptBSearchStrategiesResponseV1,
  TaxOptBStrategySearchRankByV1,
} from "../types";

export function ExplorerPage() {
  const formId = useId();
  const [taxYear, setTaxYear] = useState("2024_25");
  const [employmentType, setEmploymentType] = useState<TaxOptBEmploymentTypeV1>("employee");
  const [dependents, setDependents] = useState("0");
  const [salary, setSalary] = useState("2000000");
  const [business, setBusiness] = useState("400000");
  const [otherIncome, setOtherIncome] = useState("0");
  const [topK, setTopK] = useState("10");
  const [rankBy, setRankBy] = useState<TaxOptBStrategySearchRankByV1>("total_tax");
  const [maxCandidates, setMaxCandidates] = useState("500");
  const [includeExplanations, setIncludeExplanations] = useState(true);
  const [explanationDetail, setExplanationDetail] = useState<"summary" | "detailed">("summary");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<TaxOptBSearchStrategiesResponseV1 | null>(null);
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
      annual_salary_income: salary.trim() || "0",
      annual_business_income: business.trim() || "0",
      annual_other_income: otherIncome.trim() || "0",
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

  const onRun = async () => {
    setError(null);
    setData(null);
    setLoading(true);
    try {
      const out = await postSearchStrategiesFromFinancialInputs(buildPayload());
      setData(out);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const baselineRow = data?.rows.find((r) => r.candidate_id === data.baseline_candidate_id);
  const bestRow = data?.rows[0];

  const savingsPct =
    baselineRow && bestRow
      ? (() => {
          const b = parseFloat(baselineRow.total_tax);
          const t = parseFloat(bestRow.total_tax);
          if (!Number.isFinite(b) || !Number.isFinite(t) || b <= 0) return null;
          return (((b - t) / b) * 100).toFixed(1);
        })()
      : null;

  return (
    <div className="mx-auto max-w-6xl space-y-8 px-1 sm:px-0">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Strategy explorer</h1>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-muted-foreground">
          <strong className="text-foreground">Compliance-aware optimization</strong> via{" "}
          <strong className="text-foreground">deterministic strategy simulation</strong> — enumerated statutory relief
          combinations at MVP caps, transparent rule evaluation, and{" "}
          <strong className="text-foreground">legal strategy ranking</strong>. Dissertation-friendly: no ML, full{" "}
          <strong className="text-foreground">optimization traceability</strong> to YAML rule ids.
        </p>
        <p className="mt-2 text-sm text-muted-foreground">
          Gross profile only (salary + business + other); form deductions are not used for the grid.{" "}
          <Link to="/tax-optimization/compliance" className="text-primary underline">
            Compliance
          </Link>{" "}
          for full intake.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Profile &amp; search</CardTitle>
          <CardDescription>
            POST <span className="font-mono">/compliance/search-strategies-from-financial-inputs</span>
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor={`${formId}-tax-year`}>Tax year</Label>
            <Input
              id={`${formId}-tax-year`}
              value={taxYear}
              onChange={(e) => setTaxYear(e.target.value)}
              className="font-mono text-sm"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor={`${formId}-employment`}>Employment type</Label>
            <Select
              id={`${formId}-employment`}
              value={employmentType}
              onChange={(e) => setEmploymentType(e.target.value as TaxOptBEmploymentTypeV1)}
            >
              <option value="employee">Employee</option>
              <option value="self_employed">Self-employed</option>
              <option value="business_owner">Business owner</option>
              <option value="other">Other</option>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor={`${formId}-dependents`}>Dependents</Label>
            <Input
              id={`${formId}-dependents`}
              value={dependents}
              onChange={(e) => setDependents(e.target.value)}
              inputMode="numeric"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor={`${formId}-salary`}>Annual salary (LKR)</Label>
            <Input
              id={`${formId}-salary`}
              value={salary}
              onChange={(e) => setSalary(e.target.value)}
              className="font-mono text-sm"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor={`${formId}-business`}>Annual business (LKR)</Label>
            <Input
              id={`${formId}-business`}
              value={business}
              onChange={(e) => setBusiness(e.target.value)}
              className="font-mono text-sm"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor={`${formId}-other`}>Annual other income (LKR)</Label>
            <Input
              id={`${formId}-other`}
              value={otherIncome}
              onChange={(e) => setOtherIncome(e.target.value)}
              className="font-mono text-sm"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor={`${formId}-topk`}>Top K</Label>
            <Input
              id={`${formId}-topk`}
              value={topK}
              onChange={(e) => setTopK(e.target.value)}
              inputMode="numeric"
              min={1}
              max={64}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor={`${formId}-rank`}>Rank by</Label>
            <Select
              id={`${formId}-rank`}
              value={rankBy}
              onChange={(e) => setRankBy(e.target.value as TaxOptBStrategySearchRankByV1)}
            >
              <option value="total_tax">Total tax (ascending)</option>
              <option value="effective_rate">Effective rate (ascending)</option>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor={`${formId}-maxc`}>Max candidates guard</Label>
            <Input
              id={`${formId}-maxc`}
              value={maxCandidates}
              onChange={(e) => setMaxCandidates(e.target.value)}
              inputMode="numeric"
            />
          </div>
          <div className="flex flex-col justify-end gap-2 sm:col-span-2">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={includeExplanations}
                onChange={(e) => setIncludeExplanations(e.target.checked)}
              />
              Include explanations (FR5)
            </label>
            {includeExplanations ? (
              <Select
                value={explanationDetail}
                onChange={(e) => setExplanationDetail(e.target.value as "summary" | "detailed")}
                aria-label="Explanation detail"
              >
                <option value="summary">Summary</option>
                <option value="detailed">Detailed</option>
              </Select>
            ) : null}
          </div>
          <div className="sm:col-span-2">
            <Button type="button" disabled={loading} onClick={() => void onRun()}>
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Searching…
                </>
              ) : (
                "Run search"
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      {data?.optimization_meta ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Optimization metrics</CardTitle>
            <CardDescription>
              Transparency metadata for this search run — reproducible grid enumeration, no stochastic tuning.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <div className="rounded-lg border border-border/60 bg-muted/20 p-4">
                <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Strategies evaluated
                </dt>
                <dd className="mt-1 font-mono text-2xl font-semibold tabular-nums">
                  {data.optimization_meta.strategies_evaluated}
                </dd>
              </div>
              <div className="rounded-lg border border-border/60 bg-muted/20 p-4">
                <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Legal (passing)
                </dt>
                <dd className="mt-1 font-mono text-2xl font-semibold tabular-nums text-emerald-700 dark:text-emerald-400">
                  {data.optimization_meta.legal_strategies_count}
                </dd>
              </div>
              <div className="rounded-lg border border-border/60 bg-muted/20 p-4">
                <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Rejected</dt>
                <dd className="mt-1 font-mono text-2xl font-semibold tabular-nums">
                  {data.optimization_meta.rejected_strategies_count}
                </dd>
              </div>
              <div className="rounded-lg border border-border/60 bg-muted/20 p-4 sm:col-span-2 lg:col-span-3">
                <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Mode</dt>
                <dd className="mt-1 text-sm font-medium">{data.optimization_meta.optimization_mode}</dd>
                <p className="mt-2 text-xs text-muted-foreground">
                  {data.optimization_meta.search_space_description} · objective{" "}
                  <span className="font-mono">{data.optimization_meta.optimization_objective}</span>
                </p>
                <p className="mt-1 font-mono text-[11px] text-muted-foreground">
                  reproducibility_id {data.optimization_meta.reproducibility_id}
                </p>
              </div>
            </dl>
          </CardContent>
        </Card>
      ) : null}

      {data && baselineRow && bestRow ? (
        <Card className="border-primary/20">
          <CardHeader>
            <CardTitle className="text-lg">Baseline vs optimized strategy</CardTitle>
            <CardDescription>
              Comparison uses the selected baseline id{" "}
              <span className="font-mono text-xs">{data.baseline_candidate_id}</span> and the best-ranked row in this
              response.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {data.comparison_summary ? (
              <p className="rounded-lg border border-border/60 bg-muted/30 px-4 py-3 text-sm leading-relaxed">
                {data.comparison_summary}
              </p>
            ) : null}
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="rounded-xl border border-border/80 p-4">
                <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Baseline</div>
                <div className="mt-1 font-medium leading-snug">{baselineRow.display_name}</div>
                <div className="mt-1 font-mono text-[11px] text-muted-foreground">{baselineRow.candidate_id}</div>
                <div className="mt-3 font-mono text-2xl font-semibold tabular-nums">
                  {formatLkrAmount(parseDecimalSafe(baselineRow.total_tax) ?? baselineRow.total_tax)}
                </div>
                <div className="text-xs text-muted-foreground">Total tax</div>
                {baselineRow.effective_rate ? (
                  <div className="mt-1 text-xs text-muted-foreground">Effective rate {baselineRow.effective_rate}</div>
                ) : null}
              </div>
              <div className="rounded-xl border-2 border-primary/35 bg-primary/[0.07] p-4">
                <div className="text-xs font-semibold uppercase tracking-wide text-primary">Best in this view</div>
                <div className="mt-1 font-medium leading-snug">{bestRow.display_name}</div>
                <div className="mt-1 font-mono text-[11px] text-muted-foreground">{bestRow.candidate_id}</div>
                <div className="mt-3 font-mono text-2xl font-semibold tabular-nums text-primary">
                  {formatLkrAmount(parseDecimalSafe(bestRow.total_tax) ?? bestRow.total_tax)}
                </div>
                <div className="text-xs text-muted-foreground">Total tax</div>
                {bestRow.metrics?.tax_savings_vs_baseline_lkr != null ? (
                  <div className="mt-3 rounded-md bg-background/60 px-3 py-2 text-sm">
                    <span className="text-muted-foreground">Tax saving vs baseline: </span>
                    <span className="font-mono font-semibold text-emerald-700 dark:text-emerald-400">
                      {formatLkrAmount(bestRow.metrics.tax_savings_vs_baseline_lkr)}
                    </span>
                    {savingsPct != null ? (
                      <span className="ml-2 text-muted-foreground">({savingsPct}% of baseline tax)</span>
                    ) : null}
                  </div>
                ) : null}
                {bestRow.effective_rate ? (
                  <div className="mt-2 text-xs text-muted-foreground">Effective rate {bestRow.effective_rate}</div>
                ) : null}
              </div>
            </div>
          </CardContent>
        </Card>
      ) : null}

      {data?.top_rank_explanation ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Why rank #1?</CardTitle>
            <CardDescription>Deterministic reasoning for the top-ranked legal strategy in this response.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm font-medium leading-relaxed">{data.top_rank_explanation.headline}</p>
            <ul className="list-inside list-disc space-y-2 text-sm text-muted-foreground">
              {data.top_rank_explanation.bullets.map((b, i) => (
                <li key={i}>{b}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ) : null}

      {data && baselineRow && bestRow ? (
        <div className="space-y-3">
          <h2 className="text-base font-semibold tracking-tight">Comparison visuals</h2>
          <ExplorerCharts data={data} baselineRow={baselineRow} bestRow={bestRow} />
        </div>
      ) : null}

      <SearchStrategiesTable data={data} expanded={expanded} onToggleExpand={toggleExpand} />

      {data?.traceability ? (
        <p className="text-center text-[11px] text-muted-foreground">
          Traceability · grid <span className="font-mono">{data.traceability.grid_version}</span> · space{" "}
          <span className="font-mono">{data.traceability.search_space_id}</span>
          {data.traceability.ruleset_assessment_year
            ? ` · year ${data.traceability.ruleset_assessment_year}`
            : ""}
          {data.traceability.rules_version_label
            ? ` · build ${data.traceability.rules_version_label}`
            : ""}
        </p>
      ) : null}

      {data?.explanations ? <ExplanationPanel bundle={data.explanations} title="Search explanations (FR5)" /> : null}
    </div>
  );
}
