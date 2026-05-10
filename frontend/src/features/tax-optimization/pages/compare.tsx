import { useCallback, useId, useMemo, useState } from "react";
import { Check, CheckCircle2, ChevronDown, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";

import { postCompareStrategies } from "../api";
import { ExplanationPanel } from "../components/explanation-panel";
import type {
  TaxOptBCompareStrategiesRequestV1,
  TaxOptBCompareStrategiesResponseV1,
  TaxOptBEmploymentTypeV1,
  TaxOptBStrategyProposalV1,
  TaxOptBStrategyVariantV1,
} from "../types";

const LOCKED_TAX_YEAR = "2024_25";
const LOCKED_TAX_YEAR_LABEL = "2024/25";

const EMPLOYMENT_LABELS: Record<TaxOptBEmploymentTypeV1, string> = {
  employee: "Employee",
  self_employed: "Self-employed",
  business_owner: "Business owner",
  other: "Other",
};

const BASELINE_VARIANT_ID = "none";

type OptionalStrategyKey = "life" | "health" | "home" | "charitable" | "retirement" | "all";

type StrategyCardDef = {
  key: "baseline" | OptionalStrategyKey;
  variantId: string;
  title: string;
  description: string;
  bestFor?: string;
  isBaseline: boolean;
  buildStrategy: (estimatedTaxableAnnual: number) => TaxOptBStrategyProposalV1;
};

function digitsOnly(s: string): string {
  return s.replace(/\D/g, "");
}

function formatMoneyInputDisplay(digitString: string): string {
  if (!digitString) return "";
  const n = Number(digitString);
  if (!Number.isFinite(n)) return digitString;
  return n.toLocaleString("en-LK");
}

function parseAmount(value: unknown): number {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const cleaned = value.replace(/,/g, "").trim();
    const n = Number(cleaned);
    return Number.isFinite(n) ? n : 0;
  }
  return 0;
}

function formatLkrAmount(value: unknown): string {
  const n = parseAmount(value);
  return `LKR ${n.toLocaleString("en-LK")}`;
}


function charitableClaimAnnual(estimatedTaxableAnnual: number): string {
  return String(Math.max(0, Math.floor(estimatedTaxableAnnual * 0.33)));
}

const STRATEGY_CARDS: readonly StrategyCardDef[] = [
  {
    key: "baseline",
    variantId: BASELINE_VARIANT_ID,
    title: "No relief claims",
    description: "Your tax with no deductions applied",
    isBaseline: true,
    buildStrategy: () => ({ claims: [] }),
  },
  {
    key: "life",
    variantId: "strat_life",
    title: "Life insurance premium",
    description: "Claim life insurance up to LKR 100,000/year",
    bestFor: "Best for: employees with an active life insurance policy",
    isBaseline: false,
    buildStrategy: () => ({
      claims: [{ relief_code: "life_insurance_premium", claimed_amount_annual: "100000" }],
    }),
  },
  {
    key: "health",
    variantId: "strat_health",
    title: "Health insurance premium",
    description: "Claim health insurance up to LKR 75,000/year",
    bestFor: "Best for: those paying private health insurance premiums",
    isBaseline: false,
    buildStrategy: () => ({
      claims: [{ relief_code: "health_insurance_premium", claimed_amount_annual: "75000" }],
    }),
  },
  {
    key: "home",
    variantId: "strat_home",
    title: "Home loan interest",
    description: "Deduct housing loan interest up to LKR 600,000/year",
    bestFor: "Best for: individuals repaying a housing loan",
    isBaseline: false,
    buildStrategy: () => ({
      claims: [{ relief_code: "home_loan_interest", claimed_amount_annual: "600000" }],
    }),
  },
  {
    key: "charitable",
    variantId: "strat_charitable",
    title: "Charitable donations",
    description: "Donations relief up to 33% of taxable income",
    bestFor: "Best for: those who make significant charitable donations",
    isBaseline: false,
    buildStrategy: (taxable) => ({
      claims: [
        {
          relief_code: "charitable_donations",
          claimed_amount_annual: charitableClaimAnnual(taxable),
        },
      ],
    }),
  },
  {
    key: "retirement",
    variantId: "strat_retirement",
    title: "Retirement contribution",
    description: "Pension/EPF contributions up to LKR 600,000/year",
    bestFor: "Best for: self-employed or those making EPF/pension contributions",
    isBaseline: false,
    buildStrategy: () => ({
      claims: [{ relief_code: "retirement_contribution", claimed_amount_annual: "600000" }],
    }),
  },
  {
    key: "all",
    variantId: "strat_all",
    title: "All reliefs combined",
    description: "Maximum benefit from all available deductions",
    bestFor: "Best for: seeing the theoretical maximum combined relief",
    isBaseline: false,
    buildStrategy: (taxable) => ({
      claims: [
        { relief_code: "life_insurance_premium", claimed_amount_annual: "100000" },
        { relief_code: "health_insurance_premium", claimed_amount_annual: "75000" },
        { relief_code: "home_loan_interest", claimed_amount_annual: "600000" },
        {
          relief_code: "charitable_donations",
          claimed_amount_annual: charitableClaimAnnual(taxable),
        },
        { relief_code: "retirement_contribution", claimed_amount_annual: "600000" },
      ],
    }),
  },
] as const;

function buildVariants(
  selectedOptional: ReadonlySet<OptionalStrategyKey>,
  estimatedTaxableAnnual: number,
): TaxOptBStrategyVariantV1[] {
  const variants: TaxOptBStrategyVariantV1[] = [];
  for (const def of STRATEGY_CARDS) {
    if (def.isBaseline) {
      variants.push({
        variant_id: def.variantId,
        label: def.title,
        strategy: def.buildStrategy(estimatedTaxableAnnual),
      });
      continue;
    }
    if (def.key !== "baseline" && selectedOptional.has(def.key)) {
      variants.push({
        variant_id: def.variantId,
        label: def.title,
        strategy: def.buildStrategy(estimatedTaxableAnnual),
      });
    }
  }
  return variants;
}

function strategyTitleForRow(
  row: TaxOptBCompareStrategiesResponseV1["rows"][number],
): string {
  if (row.label?.trim()) return row.label.trim();
  const found = STRATEGY_CARDS.find((c) => c.variantId === row.variant_id);
  return found?.title ?? "Strategy";
}

function formatSavesVsBaseline(
  isBaselineRow: boolean,
  deltaStr: string | null | undefined,
): { text: string; tone: "neutral" | "better" | "worse" } {
  if (isBaselineRow) return { text: "—", tone: "neutral" };
  if (deltaStr == null || deltaStr === "") return { text: "—", tone: "neutral" };
  const delta = parseAmount(deltaStr);
  if (delta === 0) return { text: "Same as baseline", tone: "neutral" };
  const abs = Math.abs(Math.round(delta));
  if (delta < 0) return { text: `LKR ${abs.toLocaleString("en-LK")} less`, tone: "better" };
  return { text: `LKR ${abs.toLocaleString("en-LK")} more`, tone: "worse" };
}

export function ComparePage() {
  const formId = useId();
  const [employmentType, setEmploymentType] = useState<TaxOptBEmploymentTypeV1>("employee");
  const [salary, setSalary] = useState("2000000");
  const [business, setBusiness] = useState("400000");
  const [otherIncome, setOtherIncome] = useState("0");
  const [dependents, setDependents] = useState("0");
  const [selectedOptional, setSelectedOptional] = useState<Set<OptionalStrategyKey>>(() => new Set());

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<TaxOptBCompareStrategiesResponseV1 | null>(null);
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  const grossAnnual = useMemo(() => {
    return parseAmount(salary) + parseAmount(business) + parseAmount(otherIncome);
  }, [salary, business, otherIncome]);

  const estimatedTaxableAnnual = useMemo(() => {
    if (grossAnnual <= 0) return 0;
    return Math.round(grossAnnual * 0.75);
  }, [grossAnnual]);

  const toggleOptional = useCallback((key: OptionalStrategyKey) => {
    setSelectedOptional((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  const isCardSelected = useCallback(
    (def: StrategyCardDef) => {
      if (def.isBaseline) return true;
      return def.key !== "baseline" && selectedOptional.has(def.key);
    },
    [selectedOptional],
  );

  const onRun = async () => {
    setError(null);
    setData(null);
    setExpandedRow(null);
    setLoading(true);
    try {
      const variants = buildVariants(selectedOptional, estimatedTaxableAnnual);
      const parsed: TaxOptBCompareStrategiesRequestV1 = {
        profile: {
          tax_year: LOCKED_TAX_YEAR,
          employment_type: employmentType,
          dependents: Math.max(0, Math.min(20, parseInt(dependents, 10) || 0)),
          annual_gross_income: String(Math.max(0, Math.round(grossAnnual))),
          estimated_annual_taxable_income: String(Math.max(0, estimatedTaxableAnnual)),
        },
        variants,
        baseline_variant_id: BASELINE_VARIANT_ID,
        include_result_detail: true,
        include_explanations: true,
        explanation_detail: "summary",
      };
      const out = await postCompareStrategies(parsed);
      setData(out);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const sortedRows = useMemo(() => {
    if (!data?.rows.length) return [];
    return [...data.rows].sort((a, b) => {
      const ra = a.rank ?? 999;
      const rb = b.rank ?? 999;
      if (ra !== rb) return ra - rb;
      return strategyTitleForRow(a).localeCompare(strategyTitleForRow(b));
    });
  }, [data]);

  const summaryStats = useMemo(() => {
    if (!data?.rows.length) return null;
    const baselineRow = data.rows.find((r) => r.variant_id === BASELINE_VARIANT_ID);
    const rankOne = data.rows.find((r) => r.rank === 1);
    const baselineTax = baselineRow?.total_tax != null ? parseAmount(baselineRow.total_tax) : null;
    const bestTax =
      rankOne?.passed && rankOne.total_tax != null ? parseAmount(rankOne.total_tax) : null;
    let savings: number | null = null;
    if (baselineTax != null && bestTax != null) savings = baselineTax - bestTax;
    return {
      n: data.rows.length,
      savings,
      baselineTax,
      rankOne,
      rankOneIsBaseline: rankOne?.variant_id === BASELINE_VARIANT_ID,
    };
  }, [data]);

  return (
    <div className="flex flex-col gap-8 pb-10">
      <div className="overflow-hidden rounded-xl border border-border/80 bg-card shadow-sm">
        <div
          className="h-1.5 w-full bg-gradient-to-r from-primary via-primary/90 to-emerald-800/80"
          aria-hidden
        />
        <div className="px-6 py-5">
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">Compare strategies</h1>
          <p className="mt-2 w-full text-sm leading-relaxed text-muted-foreground">
            See how different tax relief combinations affect your annual tax. Pick from common strategies
            or customize.
          </p>
        </div>
      </div>

      <Card className="rounded-xl border border-border bg-card shadow-sm">
        <CardContent className="space-y-6 p-6">
          <div>
            <h2 className="text-base font-semibold text-foreground">Your income profile</h2>
            <p className="mt-1 text-xs text-muted-foreground">
              Assessment year {LOCKED_TAX_YEAR_LABEL} (fixed). Income fields use LKR; taxable income for
              this comparison is estimated at 75% of gross, matching the standard demo profile shape.
            </p>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="grid gap-2">
              <Label htmlFor={`${formId}-emp`}>Employment type</Label>
              <Select
                id={`${formId}-emp`}
                value={employmentType}
                onChange={(e) => setEmploymentType(e.target.value as TaxOptBEmploymentTypeV1)}
                className="h-10"
              >
                {(Object.keys(EMPLOYMENT_LABELS) as TaxOptBEmploymentTypeV1[]).map((key) => (
                  <option key={key} value={key}>
                    {EMPLOYMENT_LABELS[key]}
                  </option>
                ))}
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor={`${formId}-sal`}>Annual salary (LKR)</Label>
              <div className="flex overflow-hidden rounded-md border border-input shadow-sm focus-within:ring-2 focus-within:ring-ring">
                <span className="flex items-center border-r border-input bg-muted/30 px-3 text-sm text-muted-foreground">
                  LKR
                </span>
                <Input
                  id={`${formId}-sal`}
                  inputMode="numeric"
                  autoComplete="off"
                  value={formatMoneyInputDisplay(salary)}
                  onChange={(e) => setSalary(digitsOnly(e.target.value))}
                  className="h-10 border-0 text-right tabular-nums focus-visible:ring-0 focus-visible:ring-offset-0"
                />
              </div>
            </div>
            <div className="grid gap-2">
              <Label htmlFor={`${formId}-bus`}>Annual business income (LKR)</Label>
              <div className="flex overflow-hidden rounded-md border border-input shadow-sm focus-within:ring-2 focus-within:ring-ring">
                <span className="flex items-center border-r border-input bg-muted/30 px-3 text-sm text-muted-foreground">
                  LKR
                </span>
                <Input
                  id={`${formId}-bus`}
                  inputMode="numeric"
                  autoComplete="off"
                  value={formatMoneyInputDisplay(business)}
                  onChange={(e) => setBusiness(digitsOnly(e.target.value))}
                  className="h-10 border-0 text-right tabular-nums focus-visible:ring-0 focus-visible:ring-offset-0"
                />
              </div>
            </div>
            <div className="grid gap-2">
              <Label htmlFor={`${formId}-oth`}>Annual other income (LKR)</Label>
              <div className="flex overflow-hidden rounded-md border border-input shadow-sm focus-within:ring-2 focus-within:ring-ring">
                <span className="flex items-center border-r border-input bg-muted/30 px-3 text-sm text-muted-foreground">
                  LKR
                </span>
                <Input
                  id={`${formId}-oth`}
                  inputMode="numeric"
                  autoComplete="off"
                  value={formatMoneyInputDisplay(otherIncome)}
                  onChange={(e) => setOtherIncome(digitsOnly(e.target.value))}
                  className="h-10 border-0 text-right tabular-nums focus-visible:ring-0 focus-visible:ring-offset-0"
                />
              </div>
            </div>
            <div className="grid gap-2 md:col-span-2 md:max-w-xs">
              <Label htmlFor={`${formId}-dep`}>Dependents</Label>
              <Input
                id={`${formId}-dep`}
                type="number"
                min={0}
                max={20}
                value={dependents}
                onChange={(e) => setDependents(e.target.value)}
                className="h-10"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="space-y-4">
        <div>
          <h2 className="text-base font-semibold text-foreground">Choose strategies to compare</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Select which relief strategies to compare against your baseline (no reliefs claimed).
          </p>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          {STRATEGY_CARDS.map((def) => {
            const selected = isCardSelected(def);
            return (
              <button
                key={def.key}
                type="button"
                disabled={def.isBaseline}
                onClick={() => {
                  if (!def.isBaseline && def.key !== "baseline") {
                    toggleOptional(def.key);
                  }
                }}
                className={[
                  "flex flex-col rounded-lg border bg-card p-4 text-left shadow-sm transition-colors",
                  selected
                    ? "border-primary bg-primary/5 ring-1 ring-primary/25"
                    : "border-border hover:border-primary/40",
                  def.isBaseline ? "cursor-default" : "cursor-pointer",
                ].join(" ")}
              >
                <div className="flex items-start gap-3">
                  <span
                    className={[
                      "mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded border",
                      selected
                        ? "border-primary bg-primary text-primary-foreground"
                        : "border-input bg-background",
                    ].join(" ")}
                    aria-hidden
                  >
                    {selected ? <Check className="h-3 w-3 stroke-[3]" /> : null}
                  </span>
                  <div className="min-w-0 flex-1 space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium text-foreground">{def.title}</span>
                      {def.isBaseline ? (
                        <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
                          Baseline
                        </span>
                      ) : null}
                    </div>
                    <p className="text-xs leading-relaxed text-muted-foreground">{def.description}</p>
                    {def.bestFor ? (
                      <p className="mt-1.5 text-[11px] font-medium text-primary/70">{def.bestFor}</p>
                    ) : null}
                  </div>
                </div>
              </button>
            );
          })}
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
              Comparing…
            </>
          ) : (
            "Compare selected strategies"
          )}
        </Button>
      </div>

      {error ? (
        <Card className="rounded-xl border border-destructive/30 bg-destructive/5">
          <CardContent className="p-6">
            <p className="text-base font-semibold text-destructive">We couldn&apos;t finish that</p>
            <p className="mt-2 text-sm text-destructive/90">{error}</p>
          </CardContent>
        </Card>
      ) : null}

      {data && summaryStats ? (
        <>
          <div
            className={[
              "overflow-hidden rounded-xl border shadow-sm",
              summaryStats.savings != null && summaryStats.savings > 0 && !summaryStats.rankOneIsBaseline
                ? "border-border bg-card ring-1 ring-emerald-600/15"
                : "border-border bg-card shadow-sm",
            ].join(" ")}
          >
            {summaryStats.savings != null &&
            summaryStats.savings > 0 &&
            !summaryStats.rankOneIsBaseline ? (
              <div className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:gap-5">
                <div
                  className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-600 to-emerald-700 text-white shadow-md"
                  aria-hidden
                >
                  <CheckCircle2 className="h-8 w-8 stroke-[2]" />
                </div>
                <div className="min-w-0 flex-1 space-y-1">
                  <p className="text-base font-semibold leading-snug text-foreground">
                    <span>{summaryStats.n} strategies compared</span>
                  </p>
                  <p className="text-sm leading-relaxed text-muted-foreground">
                    Best strategy saves{" "}
                    <span className="font-semibold tabular-nums text-foreground">
                      {formatLkrAmount(summaryStats.savings)}
                    </span>{" "}
                    vs no reliefs
                  </p>
                </div>
              </div>
            ) : (
              <div className="px-5 py-4">
                <p className="text-[15px] font-medium text-foreground">
                  <span className="font-semibold">{summaryStats.n} strategies compared</span>
                  {summaryStats.rankOneIsBaseline
                    ? " — baseline (no reliefs) is the lowest-tax option among your selections."
                    : " — adjust selections or income to see tax savings from reliefs."}
                </p>
              </div>
            )}
          </div>

          <Card className="rounded-xl border border-border bg-card shadow-sm">
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full min-w-[640px] text-sm">
                  <thead>
                    <tr className="border-b border-border text-left text-xs font-medium text-muted-foreground">
                      <th className="px-4 py-3">Rank</th>
                      <th className="px-4 py-3">Strategy name</th>
                      <th className="px-4 py-3 text-right">Total tax (LKR)</th>
                      <th className="px-4 py-3 text-right">Saves vs baseline</th>
                      <th className="px-4 py-3">Compliant?</th>
                      <th className="px-4 py-3 w-8" />
                    </tr>
                  </thead>
                  <tbody>
                    {sortedRows.map((row) => {
                      const title = strategyTitleForRow(row);
                      const isBaselineRow = row.variant_id === BASELINE_VARIANT_ID;
                      const saves = formatSavesVsBaseline(isBaselineRow, row.delta_total_tax_vs_baseline);
                      const isTop = row.rank === 1;
                      const appliedRelief = row.result?.compliance?.applied_relief;
                      const isExpandable =
                        row.passed &&
                        appliedRelief != null &&
                        Object.keys(appliedRelief).length > 0;
                      const isExpanded = expandedRow === row.variant_id;
                      return (
                        <tr
                          key={row.variant_id}
                          onClick={() => {
                            if (isExpandable) {
                              setExpandedRow((prev) =>
                                prev === row.variant_id ? null : row.variant_id,
                              );
                            }
                          }}
                          className={[
                            "border-b border-border/70 last:border-0",
                            isTop ? "bg-amber-500/10" : "",
                            isExpandable ? "cursor-pointer hover:bg-muted/30" : "",
                          ].join(" ")}
                        >
                          <td className="px-4 py-3 tabular-nums text-muted-foreground">
                            {row.rank ?? "—"}
                          </td>
                          <td className="px-4 py-3 font-medium text-foreground">{title}</td>
                          <td className="px-4 py-3 text-right tabular-nums">
                            {row.total_tax != null ? formatLkrAmount(row.total_tax) : "—"}
                          </td>
                          <td
                            className={[
                              "px-4 py-3 text-right tabular-nums",
                              saves.tone === "better"
                                ? "font-medium text-emerald-700 dark:text-emerald-400"
                                : saves.tone === "worse"
                                  ? "text-amber-800 dark:text-amber-200"
                                  : "text-muted-foreground",
                            ].join(" ")}
                          >
                            {saves.text}
                          </td>
                          <td className="px-4 py-3">
                            {row.passed ? (
                              <span className="font-medium text-emerald-700 dark:text-emerald-400">Yes</span>
                            ) : (
                              <span className="font-medium text-destructive">No</span>
                            )}
                          </td>
                          <td className="px-4 py-3 text-muted-foreground">
                            {isExpandable ? (
                              <ChevronDown
                                className={[
                                  "h-4 w-4 transition-transform",
                                  isExpanded ? "rotate-180" : "",
                                ].join(" ")}
                              />
                            ) : null}
                          </td>
                        </tr>
                      );
                    })}
                    {expandedRow != null && (() => {
                      const row = sortedRows.find((r) => r.variant_id === expandedRow);
                      const appliedRelief = row?.result?.compliance?.applied_relief;
                      if (!row || !appliedRelief) return null;
                      return (
                        <tr key={`${expandedRow}-detail`} className="bg-muted/20 border-b border-border/70">
                          <td />
                          <td colSpan={4} className="px-4 pb-4 pt-2">
                            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                              Applied reliefs
                            </p>
                            <ul className="space-y-1.5 text-sm">
                              {Object.entries(appliedRelief).map(([code, value]) => {
                                const v = value as {
                                  claimed_amount_annual?: unknown;
                                  allowed_amount_annual?: unknown;
                                  cap_amount_annual?: unknown;
                                };
                                const label = code
                                  .replace(/_/g, " ")
                                  .replace(/\b\w/g, (c) => c.toUpperCase());
                                const claimed =
                                  v.claimed_amount_annual != null
                                    ? formatLkrAmount(v.claimed_amount_annual)
                                    : null;
                                const allowed =
                                  v.allowed_amount_annual != null
                                    ? formatLkrAmount(v.allowed_amount_annual)
                                    : null;
                                const cap =
                                  v.cap_amount_annual != null
                                    ? formatLkrAmount(v.cap_amount_annual)
                                    : null;
                                return (
                                  <li
                                    key={code}
                                    className="flex flex-wrap gap-x-4 gap-y-0.5 text-muted-foreground"
                                  >
                                    <span className="font-medium text-foreground">{label}</span>
                                    {claimed ? <span>Claimed: {claimed}</span> : null}
                                    {allowed ? <span>Allowed: {allowed}</span> : null}
                                    {cap ? <span>Cap: {cap}</span> : null}
                                  </li>
                                );
                              })}
                            </ul>
                          </td>
                        </tr>
                      );
                    })()}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          {summaryStats.rankOne &&
          summaryStats.rankOne.variant_id !== BASELINE_VARIANT_ID &&
          summaryStats.rankOne.passed &&
          summaryStats.savings != null &&
          summaryStats.savings > 0 &&
          summaryStats.baselineTax != null &&
          summaryStats.baselineTax > 0 ? (
            <Card className="rounded-xl border-2 border-primary/30 bg-primary/5 shadow-sm">
              <CardContent className="space-y-2 p-6">
                <p className="text-xs font-semibold uppercase tracking-wide text-primary">Recommended strategy</p>
                <p className="text-lg font-semibold text-foreground">
                  {strategyTitleForRow(summaryStats.rankOne)}
                </p>
                <p className="text-sm leading-relaxed text-muted-foreground">
                  This strategy reduces your tax by{" "}
                  <span className="font-medium text-foreground tabular-nums">
                    {formatLkrAmount(summaryStats.savings)}
                  </span>{" "}
                  (
                  <span className="tabular-nums">
                    {((summaryStats.savings / summaryStats.baselineTax) * 100).toFixed(1)}%
                  </span>{" "}
                  saving vs no reliefs).
                </p>
              </CardContent>
            </Card>
          ) : null}

          {data?.explanations ? (
            <ExplanationPanel
              bundle={data.explanations}
              title="Why this strategy won"
              presentation="advisory"
            />
          ) : null}

        </>
      ) : null}

      <p className="text-center text-xs text-muted-foreground">
        This comparison uses MVP rules for {LOCKED_TAX_YEAR_LABEL} and is not legal or filing advice.
        Verify with the Inland Revenue Department.
      </p>
    </div>
  );
}
