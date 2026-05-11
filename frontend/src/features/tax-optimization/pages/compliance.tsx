import { useCallback, useId, useMemo, useState, type FormEvent } from "react";
import { AlertCircle, CheckCircle2, Loader2, Plus, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";

import {
  postCompareStrategiesFromFinancialInputs,
  postComplianceCheck,
  postComplianceCheckFromFinancialInputs,
  postComplianceCheckFromTransactions,
  postComputeTax,
  postComputeTaxFromFinancialInputs,
} from "../api";
import type {
  ComplianceCheckRequest,
  ComplianceResult,
  TaxOptBCompareFromFinancialInputsRequestV1,
  TaxOptBComplianceFromFinancialInputsRequestV1,
  TaxOptBComputeTaxResponseV1,
  TaxOptBDeductionLineV1,
  TaxOptBEmploymentTypeV1,
  TaxOptBExplanationBundleV1,
  TaxOptBInvestmentLineV1,
  TaxOptBInvestmentTaxTreatmentV1,
  TaxOptBStrategyVariantV1,
  TaxOptBCompareStrategiesResponseV1,
} from "../types";
import { TAX_OPT_B_MVP_RELIEF_CODES } from "../types";

/* eslint-disable @typescript-eslint/no-unused-vars --
 * Advanced/compare/transaction handlers and related state are kept for API parity; this screen only wires the simplified form.
 */
const DEFAULT_STRATEGY_JSON = `{
  "claims": [
    { "relief_code": "life_insurance_premium", "claimed_amount_annual": "50000" }
  ],
  "notes": null
}`;

const DEFAULT_COMPARE_EXTRA_VARIANTS_JSON = `[
  {
    "variant_id": "no_relief",
    "label": "No statutory reliefs",
    "strategy": { "claims": [] }
  }
]`;

const RELIEF_LABELS: Record<string, string> = {
  life_insurance_premium: "Life insurance premium",
  health_insurance_premium: "Health insurance premium",
  home_loan_interest: "Home loan interest",
  rent_relief: "Rent relief",
  charitable_donations: "Charitable donations",
  retirement_contribution: "Retirement contribution",
};

const EMPLOYMENT_LABELS: Record<TaxOptBEmploymentTypeV1, string> = {
  employee: "Employee",
  self_employed: "Self-employed",
  business_owner: "Business owner",
  other: "Other",
};

/** API values ``2018_19`` … ``2025_26`` (aligned with Component B). Labels: ``18/19`` … ``25/26``. */
const ASSESSMENT_YEAR_OPTIONS: readonly { value: string; label: string }[] = Object.freeze(
  Array.from({ length: 2025 - 2018 + 1 }, (_, i) => {
    const y = 2018 + i;
    const yy = (y + 1) % 100;
    return {
      value: `${y}_${String(yy).padStart(2, "0")}`,
      label: `${y}/${String(yy).padStart(2, "0")}`,
    };
  }),
);

function nextRowId(): string {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`;
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

/** LKR amounts with comma grouping (en-LK). */
function formatLkrAmount(value: unknown): string {
  const n = parseAmount(value);
  return `LKR ${n.toLocaleString("en-LK")}`;
}

function formatAssessmentYearLabel(apiValue: string): string {
  const m = /^(\d{4})_(\d{2})$/.exec(apiValue.trim());
  if (!m) return apiValue;
  const y1 = Number(m[1]);
  const y2 = Number(m[2]);
  return `${y1}/${String(y2).padStart(2, "0")}`;
}

/** Keep only digits in state; show thousands separators in the field. */
function digitsOnly(s: string): string {
  return s.replace(/\D/g, "");
}

function formatMoneyInputDisplay(digitString: string): string {
  if (!digitString) return "";
  const n = Number(digitString);
  if (!Number.isFinite(n)) return digitString;
  return n.toLocaleString("en-LK");
}

function reliefDisplayName(code: string): string {
  return RELIEF_LABELS[code] ?? code.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function normalizeReliefEntry(value: unknown): { claimed: string; cap: string; allowed: string } {
  const src = (value ?? {}) as Record<string, unknown>;
  return {
    claimed: String(src.claimed ?? src.claimed_amount ?? src.claimed_amount_annual ?? "0"),
    cap: String(src.cap ?? src.cap_amount ?? src.cap_annual ?? "0"),
    allowed: String(src.allowed ?? src.allowed_amount ?? src.allowed_amount_annual ?? "0"),
  };
}

function formatSlabRate(rateStr: string): string {
  const s = rateStr.trim();
  const n = Number(s.replace(/%/g, ""));
  if (!Number.isFinite(n)) return s;
  if (n > 0 && n <= 1) return `${(n * 100).toFixed(2).replace(/\.?0+$/, "")}%`;
  return `${n}%`;
}

function extractAdvisoryNarrative(bundle: TaxOptBExplanationBundleV1 | null | undefined): string | null {
  if (!bundle) return null;
  const parts: string[] = [];
  if (bundle.summary?.trim()) parts.push(bundle.summary.trim());
  for (const sec of bundle.sections) {
    if (sec.title === "Tax computation walk") continue;
    for (const b of sec.bullets) {
      if (b.text?.trim()) parts.push(b.text.trim());
      if (b.detail_text?.trim()) parts.push(b.detail_text.trim());
    }
  }
  const text = parts.join("\n\n").trim();
  return text.length > 0 ? text : null;
}

function parseStrategyJson(strategyJson: string): ComplianceCheckRequest["strategy"] {
  try {
    return JSON.parse(strategyJson) as ComplianceCheckRequest["strategy"];
  } catch {
    throw new Error("Strategy JSON is invalid. Check commas and quotes.");
  }
}

function buildManualRequest(
  taxYear: string,
  employmentType: TaxOptBEmploymentTypeV1,
  dependents: string,
  gross: string,
  taxable: string,
  strategyJson: string,
): ComplianceCheckRequest {
  const strategy = parseStrategyJson(strategyJson);
  const taxableTrim = taxable.trim();
  const profile: ComplianceCheckRequest["profile"] = {
    tax_year: taxYear.trim(),
    employment_type: employmentType,
    dependents: Math.max(0, Math.min(20, parseInt(dependents, 10) || 0)),
    annual_gross_income: gross.trim() || "0",
  };
  if (taxableTrim.length > 0) {
    profile.estimated_annual_taxable_income = taxableTrim;
  }
  return { profile, strategy };
}

type DeductionRow = TaxOptBDeductionLineV1 & { _id: string };
type InvestmentRow = TaxOptBInvestmentLineV1 & { _id: string };

export function CompliancePage() {
  const formId = useId();
  const [advancedMode, setAdvancedMode] = useState(false);
  const [showReliefClaims, setShowReliefClaims] = useState(false);

  const [userId, setUserId] = useState("demo-user-1");
  const [taxYear, setTaxYear] = useState("2024_25");
  const [employmentType, setEmploymentType] = useState<TaxOptBEmploymentTypeV1>("employee");
  const dependents = "0";
  const [salary, setSalary] = useState("2000000");
  const [business, setBusiness] = useState("400000");
  const [investment, setInvestment] = useState("0");
  const [otherIncome, setOtherIncome] = useState("0");
  const [strategyNotes, setStrategyNotes] = useState("");
  const [deductionRows, setDeductionRows] = useState<DeductionRow[]>([]);
  const [investmentRows, setInvestmentRows] = useState<InvestmentRow[]>([]);

  const [gross, setGross] = useState("2400000");
  const [taxable, setTaxable] = useState("1800000");
  const [strategyJson, setStrategyJson] = useState(DEFAULT_STRATEGY_JSON);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ComplianceResult | null>(null);
  const [taxCompute, setTaxCompute] = useState<TaxOptBComputeTaxResponseV1 | null>(null);
  const [taxLoading, setTaxLoading] = useState(false);
  const [openRefs, setOpenRefs] = useState<Record<string, boolean>>({});

  const [compareExtraVariantsJson, setCompareExtraVariantsJson] = useState(
    DEFAULT_COMPARE_EXTRA_VARIANTS_JSON,
  );
  const [compareIncludeMapped, setCompareIncludeMapped] = useState(true);
  const [compareBaselineId, setCompareBaselineId] = useState("from_intake");
  const [compareLoading, setCompareLoading] = useState(false);
  const [compareError, setCompareError] = useState<string | null>(null);
  const [compareResult, setCompareResult] = useState<TaxOptBCompareStrategiesResponseV1 | null>(null);
  const [compareExpanded, setCompareExpanded] = useState<Record<string, boolean>>({});
  const [includeExplanations, setIncludeExplanations] = useState(true);
  const [explanationDetail, setExplanationDetail] = useState<"summary" | "detailed">("summary");
  const [showSlabDetails, setShowSlabDetails] = useState(false);
  const [showCompareAdvanced, setShowCompareAdvanced] = useState(false);

  const taxComputeForDisplay = useMemo((): TaxOptBComputeTaxResponseV1 | null => {
    if (!taxCompute) return null;
    if (!includeExplanations) {
      return taxCompute.explanations != null
        ? { ...taxCompute, explanations: undefined }
        : taxCompute;
    }
    if (
      taxCompute.explanations &&
      taxCompute.explanations.detail_level !== explanationDetail
    ) {
      return { ...taxCompute, explanations: undefined };
    }
    return taxCompute;
  }, [taxCompute, includeExplanations, explanationDetail]);

  const toggleCompareExpand = useCallback((variantId: string) => {
    setCompareExpanded((prev) => ({ ...prev, [variantId]: !prev[variantId] }));
  }, []);

  const toggleRef = useCallback((id: string) => {
    setOpenRefs((prev) => ({ ...prev, [id]: !prev[id] }));
  }, []);

  const buildFinancialPayload = useCallback((): TaxOptBComplianceFromFinancialInputsRequestV1 => {
    const deductions: TaxOptBDeductionLineV1[] = deductionRows
      .map(({ relief_code, amount_annual, description }) => ({
        relief_code: relief_code.trim(),
        amount_annual: amount_annual.trim() || "0",
        description: description?.trim() || null,
      }))
      .filter((r) => r.relief_code.length > 0);

    const investments: TaxOptBInvestmentLineV1[] = investmentRows.map(
      ({ investment_type, amount_annual, tax_treatment, relief_code }) => ({
        investment_type: investment_type.trim() || "unspecified",
        amount_annual: amount_annual.trim() || "0",
        tax_treatment: tax_treatment as TaxOptBInvestmentTaxTreatmentV1,
        relief_code:
          tax_treatment === "map_to_relief" ? (relief_code?.trim() || null) : null,
      }),
    );

    const body: TaxOptBComplianceFromFinancialInputsRequestV1 = {
      tax_year: taxYear.trim(),
      employment_type: employmentType,
      dependents: Math.max(0, Math.min(20, parseInt(dependents, 10) || 0)),
      annual_salary_income: salary.trim() || "0",
      annual_business_income: business.trim() || "0",
      annual_investment_income: investment.trim() || "0",
      annual_other_income: otherIncome.trim() || "0",
      deductions,
      investments,
      strategy_notes: strategyNotes.trim() || null,
    };
    return body;
  }, [
    taxYear,
    employmentType,
    dependents,
    salary,
    business,
    investment,
    otherIncome,
    strategyNotes,
    deductionRows,
    investmentRows,
  ]);

  const runCompareScenarios = async () => {
    setCompareError(null);
    setCompareResult(null);
    let variants: TaxOptBStrategyVariantV1[];
    try {
      const raw = JSON.parse(compareExtraVariantsJson) as unknown;
      if (!Array.isArray(raw)) {
        throw new Error("Extra scenarios must be a JSON array of strategy variants.");
      }
      variants = raw as TaxOptBStrategyVariantV1[];
    } catch (e) {
      setCompareError(e instanceof Error ? e.message : "Invalid JSON for extra scenarios.");
      return;
    }
    setCompareLoading(true);
    try {
      const base = buildFinancialPayload();
      let baseline: string | null = compareBaselineId.trim() || null;
      if (baseline === "from_intake" && !compareIncludeMapped) {
        baseline = null;
      }
      const body: TaxOptBCompareFromFinancialInputsRequestV1 = {
        ...base,
        strategy_variants: variants,
        include_mapped_strategy: compareIncludeMapped,
        baseline_variant_id: baseline,
        include_result_detail: true,
        include_explanations: includeExplanations,
        explanation_detail: explanationDetail,
      };
      const data = await postCompareStrategiesFromFinancialInputs(body);
      setCompareResult(data);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setCompareError(msg);
    } finally {
      setCompareLoading(false);
    }
  };

  const runStructured = async () => {
    setError(null);
    setResult(null);
    setTaxCompute(null);
    setLoading(true);
    try {
      const data = await postComplianceCheckFromFinancialInputs(buildFinancialPayload());
      setResult(data);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const runFromTransactions = async () => {
    setError(null);
    setResult(null);
    setTaxCompute(null);
    setLoading(true);
    try {
      const strategy = parseStrategyJson(strategyJson);
      const data = await postComplianceCheckFromTransactions({
        user_id: userId.trim(),
        tax_year: taxYear.trim(),
        employment_type: employmentType,
        dependents: Math.max(0, Math.min(20, parseInt(dependents, 10) || 0)),
        strategy,
      });
      setResult(data);
      if (data.income_snapshot) {
        setGross(String(data.income_snapshot.annual_gross_income));
        setTaxable(String(data.income_snapshot.estimated_annual_taxable_income));
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const onSubmitAdvanced = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setResult(null);
    setTaxCompute(null);
    setLoading(true);
    try {
      const body = buildManualRequest(taxYear, employmentType, dependents, gross, taxable, strategyJson);
      const data = await postComplianceCheck(body);
      setResult(data);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const onStructuredSubmit = (e: FormEvent) => {
    e.preventDefault();
    void runStructured();
  };

  const runEstimateTaxStructured = async () => {
    setError(null);
    setTaxLoading(true);
    try {
      const data = await postComputeTaxFromFinancialInputs({
        ...buildFinancialPayload(),
        include_explanations: includeExplanations,
        explanation_detail: explanationDetail,
      });
      setTaxCompute(data);
      setResult(data.compliance);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
    } finally {
      setTaxLoading(false);
    }
  };

  const runEstimateTaxAdvanced = async () => {
    setError(null);
    setTaxLoading(true);
    try {
      const body = buildManualRequest(taxYear, employmentType, dependents, gross, taxable, strategyJson);
      const data = await postComputeTax({
        ...body,
        include_explanations: includeExplanations,
        explanation_detail: explanationDetail,
      });
      setTaxCompute(data);
      setResult(data.compliance);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
    } finally {
      setTaxLoading(false);
    }
  };

  const addDeductionRow = () => {
    setDeductionRows((prev) => [
      ...prev,
      { _id: nextRowId(), relief_code: "life_insurance_premium", amount_annual: "0" },
    ]);
  };

  const removeDeductionRow = (id: string) => {
    setDeductionRows((prev) => prev.filter((r) => r._id !== id));
  };

  const addInvestmentRow = () => {
    setInvestmentRows((prev) => [
      ...prev,
      {
        _id: nextRowId(),
        investment_type: "",
        amount_annual: "0",
        tax_treatment: "informational",
        relief_code: null,
      },
    ]);
  };

  const removeInvestmentRow = (id: string) => {
    setInvestmentRows((prev) => prev.filter((r) => r._id !== id));
  };

  const advisoryText = extractAdvisoryNarrative(taxComputeForDisplay?.explanations);
  const isCalculating = taxLoading;
  const tc = taxCompute?.tax_computation;
  const grossForRate = tc ? parseAmount(tc.annual_gross_income) : 0;
  const taxForRate = tc ? parseAmount(tc.total_tax) : 0;
  const effectiveRatePct =
    grossForRate > 0 ? ((taxForRate / grossForRate) * 100).toFixed(2) : null;

  const assessmentYearLabel = formatAssessmentYearLabel(taxYear);

  return (
    <div className="flex flex-col gap-8 pb-10">
      <div className="overflow-hidden rounded-xl border border-border/80 bg-card shadow-sm">
        <div
          className="h-1.5 w-full bg-gradient-to-r from-primary via-primary/90 to-emerald-800/80"
          aria-hidden
        />
        <div className="px-6 py-5">
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">Check My Tax</h1>
          <p className="mt-2 w-full text-sm leading-relaxed text-muted-foreground">
            Enter your income details to check your tax compliance and get an estimated tax amount for
            assessment year <span className="font-medium text-foreground">{assessmentYearLabel}</span> (April–March).
            Add any tax relief claims you plan to make and we will tell you how much tax you owe.
          </p>
          <p className="mt-2 w-full text-xs leading-relaxed text-muted-foreground">
            Personal relief is applied automatically based on the correct amount for your selected assessment year,
            following the IRD published schedule. Results are estimates — verify with the Inland Revenue Department before filing.
          </p>
        </div>
      </div>

      <form
        className="flex flex-col gap-8"
        onSubmit={(e) => {
          e.preventDefault();
          void runEstimateTaxStructured();
        }}
      >
        <Card className="rounded-xl border border-border bg-card shadow-sm">
          <CardContent className="space-y-6 p-6">
            <h2 className="text-base font-semibold">Your income details</h2>

            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 md:gap-x-4 md:gap-y-2">
              <Label htmlFor={`${formId}-emp-s`} className="md:col-start-1 md:row-start-1">
                Employment type
              </Label>
              <Select
                id={`${formId}-emp-s`}
                value={employmentType}
                onChange={(e) => setEmploymentType(e.target.value as TaxOptBEmploymentTypeV1)}
                className="h-10 md:col-start-1 md:row-start-2"
              >
                {(Object.keys(EMPLOYMENT_LABELS) as TaxOptBEmploymentTypeV1[]).map((key) => (
                  <option key={key} value={key}>
                    {EMPLOYMENT_LABELS[key]}
                  </option>
                ))}
              </Select>
              <Label htmlFor={`${formId}-ty-s`} className="md:col-start-2 md:row-start-1">
                Assessment year
              </Label>
              <Select
                id={`${formId}-ty-s`}
                value={taxYear}
                onChange={(e) => setTaxYear(e.target.value)}
                className="h-10 md:col-start-2 md:row-start-2"
              >
                {ASSESSMENT_YEAR_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </Select>
              <p className="text-xs text-muted-foreground md:col-start-2 md:row-start-3">
                April–March period (e.g. 24/25)
              </p>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="grid gap-2">
                <Label htmlFor={`${formId}-sal`}>Annual salary</Label>
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
                <Label htmlFor={`${formId}-bus`}>Annual business income</Label>
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
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="grid gap-2">
                <div>
                  <Label htmlFor={`${formId}-inv`}>Annual investment income</Label>
                  <p className="text-xs text-muted-foreground">Dividends, interest, rental income (IRD IT01)</p>
                </div>
                <div className="flex overflow-hidden rounded-md border border-input shadow-sm focus-within:ring-2 focus-within:ring-ring">
                  <span className="flex items-center border-r border-input bg-muted/30 px-3 text-sm text-muted-foreground">
                    LKR
                  </span>
                  <Input
                    id={`${formId}-inv`}
                    inputMode="numeric"
                    autoComplete="off"
                    value={formatMoneyInputDisplay(investment)}
                    onChange={(e) => setInvestment(digitsOnly(e.target.value))}
                    className="h-10 border-0 text-right tabular-nums focus-visible:ring-0 focus-visible:ring-offset-0"
                  />
                </div>
              </div>
              <div className="grid gap-2">
                <div>
                  <Label htmlFor={`${formId}-oth`}>Annual other income</Label>
                  <p className="text-xs text-muted-foreground">&nbsp;</p>
                </div>
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
            </div>

            <div className="border-t border-border pt-4">
              <button
                type="button"
                onClick={() => setShowReliefClaims((prev) => !prev)}
                className="flex items-center gap-1.5 text-sm font-medium text-primary hover:underline"
              >
                {showReliefClaims ? "▲ Hide relief claims" : "▼ I already know my relief claims (optional)"}
              </button>
              <p className="mt-1 text-xs text-muted-foreground">
                Not sure which reliefs to claim?{" "}
                <a href="/tax-optimization/explorer" className="underline hover:text-foreground">
                  Find Best Strategy
                </a>{" "}
                — our AI will find the best combination for you automatically.
              </p>

              {showReliefClaims ? (
                <div className="mt-4 space-y-3">
                  {deductionRows.map((row, idx) => (
                    <div
                      key={row._id}
                      className="flex flex-col gap-3 rounded-lg border border-border/80 bg-muted/10 p-3 sm:flex-row sm:items-end"
                    >
                      <div className="grid min-w-0 flex-1 gap-2">
                        <Label className="text-xs text-muted-foreground">Relief type</Label>
                        <Select
                          aria-label={`Relief ${idx + 1}`}
                          value={row.relief_code}
                          onChange={(e) => {
                            const v = e.target.value;
                            setDeductionRows((prev) =>
                              prev.map((r) => (r._id === row._id ? { ...r, relief_code: v } : r)),
                            );
                          }}
                          className="h-10"
                        >
                          {TAX_OPT_B_MVP_RELIEF_CODES.map((code) => (
                            <option key={code} value={code}>
                              {RELIEF_LABELS[code] ?? code}
                            </option>
                          ))}
                        </Select>
                      </div>
                      <div className="grid min-w-0 flex-1 gap-2">
                        <Label className="text-xs text-muted-foreground">Amount</Label>
                        <div className="flex overflow-hidden rounded-md border border-input shadow-sm focus-within:ring-2 focus-within:ring-ring">
                          <span className="flex items-center border-r border-input bg-muted/30 px-3 text-sm text-muted-foreground">
                            LKR
                          </span>
                          <Input
                            inputMode="numeric"
                            autoComplete="off"
                            value={formatMoneyInputDisplay(row.amount_annual)}
                            onChange={(e) => {
                              const v = digitsOnly(e.target.value);
                              setDeductionRows((prev) =>
                                prev.map((r) => (r._id === row._id ? { ...r, amount_annual: v } : r)),
                              );
                            }}
                            className="h-10 border-0 text-right tabular-nums focus-visible:ring-0 focus-visible:ring-offset-0"
                          />
                        </div>
                      </div>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="shrink-0"
                        onClick={() => removeDeductionRow(row._id)}
                        aria-label="Remove row"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                  <Button
                    type="button"
                    variant="link"
                    size="sm"
                    className="mt-2 h-auto p-0 text-sm font-normal text-primary"
                    onClick={addDeductionRow}
                  >
                    <Plus className="mr-1 inline h-3.5 w-3.5" />
                    Add row
                  </Button>
                </div>
              ) : null}
            </div>

            {!showReliefClaims ? (
              <p className="text-center text-xs text-muted-foreground">
                This will calculate your tax with personal relief only — no deductions claimed.
              </p>
            ) : null}

            <Button type="submit" disabled={isCalculating} className="h-11 w-full">
              {isCalculating ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Working…
                </>
              ) : (
                "Calculate my tax"
              )}
            </Button>
          </CardContent>
        </Card>
      </form>

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

      {result ? (
        <>
          <div
            className={
              result.passed
                ? "overflow-hidden rounded-xl border border-border bg-card shadow-sm ring-1 ring-emerald-600/15"
                : "overflow-hidden rounded-xl border border-destructive/35 bg-card shadow-sm ring-1 ring-destructive/10"
            }
          >
            {result.passed ? (
              <div className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:gap-5">
                <div
                  className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-600 to-emerald-700 text-white shadow-md"
                  aria-hidden
                >
                  <CheckCircle2 className="h-8 w-8 stroke-[2]" />
                </div>
                <div className="min-w-0 flex-1 space-y-1">
                  <p className="text-base font-semibold leading-snug text-foreground">
                    Your tax is calculated
                  </p>
                  <p className="text-sm leading-relaxed text-muted-foreground">
                    Your income and relief claims look good for{" "}
                    <span className="font-medium text-foreground">{assessmentYearLabel}</span>. Your
                    estimated tax and breakdown are below.
                  </p>
                </div>
              </div>
            ) : (
              <div className="flex flex-col gap-4 p-5 sm:flex-row sm:items-start sm:gap-5">
                <div
                  className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-destructive/12 text-destructive ring-1 ring-destructive/25"
                  aria-hidden
                >
                  <AlertCircle className="h-8 w-8 stroke-[2]" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-base font-semibold text-foreground">We need a quick fix</p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Adjust the items below, then run the calculation again.
                  </p>
                  {result.violations.length > 0 ? (
                    <ul className="mt-3 list-disc space-y-1.5 pl-5 text-sm text-foreground">
                      {result.violations.map((v, i) => (
                        <li key={`v-${i}`}>{v.message}</li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              </div>
            )}
          </div>

          {tc ? (
            <Card className="rounded-xl border border-border bg-card shadow-sm">
              <CardContent className="space-y-6 p-6">
                <div>
                  <p className="text-sm text-muted-foreground">Your estimated tax</p>
                  <p className="mt-1 text-3xl font-semibold tracking-tight">
                    {formatLkrAmount(tc.total_tax)}
                  </p>
                </div>

                <div className="space-y-3 text-sm">
                  <div className="flex justify-between gap-4 border-b border-border pb-3">
                    <span className="text-muted-foreground">Gross income</span>
                    <span className="font-medium tabular-nums">{formatLkrAmount(tc.annual_gross_income)}</span>
                  </div>
                  <div className="flex justify-between gap-4 border-b border-border pb-3">
                    <span className="text-muted-foreground">Personal relief</span>
                    <span className="font-medium tabular-nums">{formatLkrAmount(tc.personal_relief_annual)}</span>
                  </div>
                  <div className="flex justify-between gap-4 border-b border-border pb-3">
                    <span className="text-muted-foreground">Allowed deductions</span>
                    <span className="font-medium tabular-nums">{formatLkrAmount(tc.total_allowed_deductions)}</span>
                  </div>
                  <div className="flex justify-between gap-4 border-b border-border pb-3">
                    <span className="text-muted-foreground">Taxable income</span>
                    <span className="font-medium tabular-nums">{formatLkrAmount(tc.taxable_after_deductions)}</span>
                  </div>
                  <div className="flex justify-between gap-4 border-t border-foreground/20 pt-3 font-semibold">
                    <span>Total tax</span>
                    <span className="tabular-nums">{formatLkrAmount(tc.total_tax)}</span>
                  </div>
                  {effectiveRatePct != null ? (
                    <div className="flex justify-between gap-4 pt-1 text-sm">
                      <span className="text-muted-foreground">Effective rate</span>
                      <span className="font-medium tabular-nums">{effectiveRatePct}%</span>
                    </div>
                  ) : null}
                </div>

                <div className="rounded-lg border border-border/80 bg-muted/10">
                  <button
                    type="button"
                    onClick={() => setShowSlabDetails((prev) => !prev)}
                    className="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-medium text-primary hover:underline"
                  >
                    {showSlabDetails ? "Hide tax calculation detail ▲" : "View tax calculation detail ▼"}
                  </button>
                  {showSlabDetails ? (
                    <div className="border-t border-border/80 px-2 pb-3">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-border text-left text-xs text-muted-foreground">
                            <th className="px-2 py-2 font-medium">Rate</th>
                            <th className="px-2 py-2 font-medium">Income in this band</th>
                            <th className="px-2 py-2 font-medium">Tax</th>
                          </tr>
                        </thead>
                        <tbody>
                          {tc.slab_slices.map((s) => (
                            <tr key={s.slab_index} className="border-b border-border/60">
                              <td className="px-2 py-2 tabular-nums">{formatSlabRate(s.rate)}</td>
                              <td className="px-2 py-2 tabular-nums">{formatLkrAmount(s.taxable_in_slice)}</td>
                              <td className="px-2 py-2 tabular-nums">{formatLkrAmount(s.tax_in_slice)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : null}
                </div>
              </CardContent>
            </Card>
          ) : (
            <Card className="rounded-xl border border-border bg-card shadow-sm">
              <CardContent className="p-6">
                <p className="text-sm text-muted-foreground">
                  Adjust your details and try again to see an estimated tax amount.
                </p>
              </CardContent>
            </Card>
          )}

          {Object.keys(result.applied_relief).length > 0 ? (
            <Card className="rounded-xl border border-border bg-card shadow-sm">
              <CardContent className="space-y-4 p-6">
                <h3 className="text-base font-semibold">Applied reliefs</h3>
                <div className="overflow-x-auto rounded-lg border border-border/80">
                  <table className="w-full min-w-[560px] text-sm">
                    <thead>
                      <tr className="border-b border-border bg-muted/30 text-left">
                        <th className="px-4 py-3 font-semibold">Relief</th>
                        <th className="px-4 py-3 font-semibold">You claimed</th>
                        <th className="px-4 py-3 font-semibold">Maximum allowed</th>
                        <th className="px-4 py-3 font-semibold">Applied</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(result.applied_relief).map(([code, raw]) => {
                        const row = normalizeReliefEntry(raw);
                        return (
                          <tr key={code} className="border-b border-border/60 last:border-0">
                            <td className="px-4 py-3">{reliefDisplayName(code)}</td>
                            <td className="px-4 py-3 tabular-nums">{formatLkrAmount(row.claimed)}</td>
                            <td className="px-4 py-3 tabular-nums">{formatLkrAmount(row.cap)}</td>
                            <td className="px-4 py-3 tabular-nums">{formatLkrAmount(row.allowed)}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          ) : null}
        </>
      ) : null}

      {tc ? (
        <div className="rounded-xl border border-border bg-card border-l-4 border-l-emerald-600/70 pl-5 pr-6 py-6 shadow-sm">
          <h3 className="text-base font-semibold">What this means for you</h3>
          <ul className="mt-3 space-y-2 text-sm leading-relaxed text-foreground">
            <li>
              💰 Your total income for {assessmentYearLabel} is{" "}
              <span className="font-semibold">{formatLkrAmount(tc.annual_gross_income)}</span>.
            </li>
            <li>
              🛡️ You automatically receive a personal relief of{" "}
              <span className="font-semibold">{formatLkrAmount(tc.personal_relief_annual)}</span> — this is the government's
              tax-free allowance that every taxpayer gets, so you don't pay tax on that amount.
            </li>
            {parseAmount(tc.total_allowed_deductions) > 0 ? (
              <li>
                📄 Your relief claims reduced your taxable income by a further{" "}
                <span className="font-semibold">{formatLkrAmount(tc.total_allowed_deductions)}</span>.
              </li>
            ) : (
              <li>
                📄 You haven't claimed any additional tax reliefs yet. You may be able to reduce your tax further —
                try <a href="/tax-optimization/explorer" className="underline text-primary">Find Best Strategy</a> to
                see what reliefs you qualify for.
              </li>
            )}
            <li>
              📊 After applying your reliefs, your taxable income is{" "}
              <span className="font-semibold">{formatLkrAmount(tc.taxable_after_deductions)}</span>. This is the amount
              Sri Lankan income tax is calculated on.
            </li>
            <li>
              🧾 Your estimated tax bill is{" "}
              <span className="font-semibold text-primary">{formatLkrAmount(tc.total_tax)}</span>
              {effectiveRatePct ? ` — that's ${effectiveRatePct}% of your total income` : ""}.
            </li>
          </ul>
        </div>
      ) : null}

      <p className="text-center text-xs text-muted-foreground">
        This estimate is based on Sri Lankan income tax rules and is not legal or filing advice. Verify with the Inland Revenue Department.
      </p>
    </div>
  );
}
