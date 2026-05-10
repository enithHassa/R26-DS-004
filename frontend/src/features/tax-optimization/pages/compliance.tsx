import { useCallback, useId, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ChevronDown, ChevronRight, Loader2, Plus, ShieldCheck, Trash2 } from "lucide-react";

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

import {
  postCompareStrategiesFromFinancialInputs,
  postComplianceCheck,
  postComplianceCheckFromFinancialInputs,
  postComplianceCheckFromTransactions,
  postComputeTax,
  postComputeTaxFromFinancialInputs,
} from "../api";
import { CompareStrategiesTable } from "../components/compare-strategies-table";
import { ExplanationPanel } from "../components/explanation-panel";
import type {
  ComplianceCheckRequest,
  ComplianceResult,
  TaxOptBCompareFromFinancialInputsRequestV1,
  TaxOptBComplianceFromFinancialInputsRequestV1,
  TaxOptBComputeTaxResponseV1,
  TaxOptBDeductionLineV1,
  TaxOptBEmploymentTypeV1,
  TaxOptBInvestmentLineV1,
  TaxOptBInvestmentTaxTreatmentV1,
  TaxOptBStrategyVariantV1,
  TaxOptBCompareStrategiesResponseV1,
} from "../types";
import { TAX_OPT_B_MVP_RELIEF_CODES } from "../types";

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

function nextRowId(): string {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`;
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

  const [userId, setUserId] = useState("demo-user-1");
  const [taxYear, setTaxYear] = useState("2024_25");
  const [employmentType, setEmploymentType] = useState<TaxOptBEmploymentTypeV1>("employee");
  const [dependents, setDependents] = useState("0");
  const [salary, setSalary] = useState("2000000");
  const [business, setBusiness] = useState("400000");
  const [otherIncome, setOtherIncome] = useState("0");
  const [strategyNotes, setStrategyNotes] = useState("");
  const [deductionRows, setDeductionRows] = useState<DeductionRow[]>([
    { _id: nextRowId(), relief_code: "life_insurance_premium", amount_annual: "50000" },
  ]);
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

  const stripExplanationsFromCached = useCallback(() => {
    setTaxCompute((prev) =>
      prev?.explanations != null ? { ...prev, explanations: undefined } : prev,
    );
    setCompareResult((prev) =>
      prev?.explanations != null ? { ...prev, explanations: undefined } : prev,
    );
  }, []);

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

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Compliance check</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Component B — Function 1. Use structured inputs (salary, business, deductions, investments)
          mapped to profile and relief claims, or switch to advanced mode for raw profile + strategy JSON
          and the Component 1 snapshot path (
          <code className="text-xs">/api/v1/optimization/compliance/…</code>).
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-muted/20 px-4 py-3">
        <span className="text-sm font-medium">Input mode</span>
        <div className="flex gap-2">
          <Button
            type="button"
            size="sm"
            variant={!advancedMode ? "default" : "secondary"}
            onClick={() => setAdvancedMode(false)}
          >
            Structured
          </Button>
          <Button
            type="button"
            size="sm"
            variant={advancedMode ? "default" : "secondary"}
            onClick={() => setAdvancedMode(true)}
          >
            Advanced (JSON)
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-4 rounded-lg border border-border bg-muted/15 px-4 py-3">
        <label className="flex cursor-pointer items-center gap-2 text-sm">
          <input
            type="checkbox"
            className="rounded border-input"
            checked={includeExplanations}
            onChange={(e) => {
              setIncludeExplanations(e.target.checked);
              stripExplanationsFromCached();
            }}
          />
          Include explanations (FR5) on <strong className="font-medium">estimate tax</strong> &{" "}
          <strong className="font-medium">compare</strong>
        </label>
        <div className="flex flex-wrap items-center gap-2">
          <Label htmlFor={`${formId}-explain-detail`} className="text-sm text-muted-foreground">
            Detail
          </Label>
          <Select
            id={`${formId}-explain-detail`}
            value={explanationDetail}
            disabled={!includeExplanations}
            onChange={(e) => {
              setExplanationDetail(e.target.value as "summary" | "detailed");
              stripExplanationsFromCached();
            }}
            className="h-9 w-36"
          >
            <option value="summary">summary</option>
            <option value="detailed">detailed</option>
          </Select>
        </div>
        <p className="text-xs text-muted-foreground">
          Changing detail or turning explanations off clears the narrative until you run{" "}
          <strong>Estimate tax (MVP)</strong> or <strong>Compare scenarios</strong> again.
        </p>
        <p className="text-xs text-muted-foreground">
          Compliance-only runs do not return narratives — use <strong>Estimate tax (MVP)</strong> or{" "}
          <strong>Compare scenarios</strong>.
        </p>
      </div>

      {!advancedMode ? (
        <form onSubmit={onStructuredSubmit} className="space-y-8">
          <div className="grid gap-8 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Income</CardTitle>
                <CardDescription>
                  Annual figures in LKR. Gross is salary + business + other; that total drives tax slabs,
                  personal relief, and donation % caps (no separate &quot;estimated taxable&quot; field).
                </CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4">
                <div className="grid gap-2">
                  <Label htmlFor={`${formId}-ty-s`}>Tax year</Label>
                  <Input
                    id={`${formId}-ty-s`}
                    value={taxYear}
                    onChange={(e) => setTaxYear(e.target.value)}
                    className="font-mono text-sm"
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor={`${formId}-emp-s`}>Employment type</Label>
                  <Select
                    id={`${formId}-emp-s`}
                    value={employmentType}
                    onChange={(e) => setEmploymentType(e.target.value as TaxOptBEmploymentTypeV1)}
                  >
                    <option value="employee">employee</option>
                    <option value="self_employed">self_employed</option>
                    <option value="business_owner">business_owner</option>
                    <option value="other">other</option>
                  </Select>
                </div>
                <div className="grid gap-2">
                  <Label htmlFor={`${formId}-dep-s`}>Dependents</Label>
                  <Input
                    id={`${formId}-dep-s`}
                    type="number"
                    min={0}
                    max={20}
                    value={dependents}
                    onChange={(e) => setDependents(e.target.value)}
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor={`${formId}-sal`}>Salary (annual)</Label>
                  <Input
                    id={`${formId}-sal`}
                    value={salary}
                    onChange={(e) => setSalary(e.target.value)}
                    className="font-mono text-sm"
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor={`${formId}-bus`}>Business income (annual)</Label>
                  <Input
                    id={`${formId}-bus`}
                    value={business}
                    onChange={(e) => setBusiness(e.target.value)}
                    className="font-mono text-sm"
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor={`${formId}-oth`}>Other income (annual)</Label>
                  <Input
                    id={`${formId}-oth`}
                    value={otherIncome}
                    onChange={(e) => setOtherIncome(e.target.value)}
                    className="font-mono text-sm"
                  />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Notes</CardTitle>
                <CardDescription>Optional text stored on the generated strategy proposal.</CardDescription>
              </CardHeader>
              <CardContent>
                <Input
                  value={strategyNotes}
                  onChange={(e) => setStrategyNotes(e.target.value)}
                  placeholder="Optional notes"
                />
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-2">
              <div>
                <CardTitle className="text-lg">Deductions</CardTitle>
                <CardDescription>
                  Each row maps to a statutory relief code (MVP pack). Amounts are summed per code.
                </CardDescription>
              </div>
              <Button type="button" size="sm" variant="outline" onClick={addDeductionRow}>
                <Plus className="mr-1 h-4 w-4" />
                Add row
              </Button>
            </CardHeader>
            <CardContent className="space-y-3">
              {deductionRows.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No deduction rows. Add a row to propose statutory reliefs, or submit with none (no
                  claims).
                </p>
              ) : null}
              {deductionRows.map((row, idx) => (
                <div
                  key={row._id}
                  className="flex flex-col gap-2 rounded-md border border-border/80 bg-muted/20 p-3 sm:flex-row sm:items-end"
                >
                  <div className="grid flex-1 gap-2">
                    <Label className="text-xs text-muted-foreground">Relief code</Label>
                    <Select
                      aria-label={`Deduction relief ${idx + 1}`}
                      value={row.relief_code}
                      onChange={(e) => {
                        const v = e.target.value;
                        setDeductionRows((prev) =>
                          prev.map((r) => (r._id === row._id ? { ...r, relief_code: v } : r)),
                        );
                      }}
                    >
                      {TAX_OPT_B_MVP_RELIEF_CODES.map((code) => (
                        <option key={code} value={code}>
                          {code}
                        </option>
                      ))}
                    </Select>
                  </div>
                  <div className="grid flex-1 gap-2">
                    <Label className="text-xs text-muted-foreground">Amount (LKR / year)</Label>
                    <Input
                      className="font-mono text-sm"
                      value={row.amount_annual}
                      onChange={(e) => {
                        const v = e.target.value;
                        setDeductionRows((prev) =>
                          prev.map((r) => (r._id === row._id ? { ...r, amount_annual: v } : r)),
                        );
                      }}
                    />
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="shrink-0"
                    onClick={() => removeDeductionRow(row._id)}
                    aria-label="Remove deduction row"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-2">
              <div>
                <CardTitle className="text-lg">Investments</CardTitle>
                <CardDescription>
                  Informational rows are kept for your records only. &quot;Map to relief&quot; adds the
                  amount to the generated claim for the chosen code (e.g. retirement contributions).
                </CardDescription>
              </div>
              <Button type="button" size="sm" variant="outline" onClick={addInvestmentRow}>
                <Plus className="mr-1 h-4 w-4" />
                Add row
              </Button>
            </CardHeader>
            <CardContent className="space-y-3">
              {investmentRows.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No investment rows (optional). Add rows to record holdings or map amounts to a
                  relief code.
                </p>
              ) : null}
              {investmentRows.map((row, idx) => (
                <div
                  key={row._id}
                  className="flex flex-col gap-3 rounded-md border border-border/80 bg-muted/20 p-3 lg:flex-row lg:items-end"
                >
                  <div className="grid min-w-0 flex-1 gap-2">
                    <Label className="text-xs text-muted-foreground">Type / label</Label>
                    <Input
                      value={row.investment_type}
                      onChange={(e) => {
                        const v = e.target.value;
                        setInvestmentRows((prev) =>
                          prev.map((r) => (r._id === row._id ? { ...r, investment_type: v } : r)),
                        );
                      }}
                      placeholder="e.g. listed shares, unit trust"
                    />
                  </div>
                  <div className="grid w-full gap-2 sm:w-40">
                    <Label className="text-xs text-muted-foreground">Amount (year)</Label>
                    <Input
                      className="font-mono text-sm"
                      value={row.amount_annual}
                      onChange={(e) => {
                        const v = e.target.value;
                        setInvestmentRows((prev) =>
                          prev.map((r) => (r._id === row._id ? { ...r, amount_annual: v } : r)),
                        );
                      }}
                    />
                  </div>
                  <div className="grid w-full gap-2 sm:w-48">
                    <Label className="text-xs text-muted-foreground">Tax treatment</Label>
                    <Select
                      aria-label={`Investment treatment ${idx + 1}`}
                      value={row.tax_treatment}
                      onChange={(e) => {
                        const v = e.target.value as TaxOptBInvestmentTaxTreatmentV1;
                        setInvestmentRows((prev) =>
                          prev.map((r) =>
                            r._id === row._id
                              ? {
                                  ...r,
                                  tax_treatment: v,
                                  relief_code: v === "map_to_relief" ? r.relief_code ?? "retirement_contribution" : null,
                                }
                              : r,
                          ),
                        );
                      }}
                    >
                      <option value="informational">informational</option>
                      <option value="map_to_relief">map_to_relief</option>
                    </Select>
                  </div>
                  {row.tax_treatment === "map_to_relief" ? (
                    <div className="grid w-full gap-2 sm:w-56">
                      <Label className="text-xs text-muted-foreground">Relief code</Label>
                      <Select
                        aria-label={`Investment relief ${idx + 1}`}
                        value={row.relief_code ?? "retirement_contribution"}
                        onChange={(e) => {
                          const v = e.target.value;
                          setInvestmentRows((prev) =>
                            prev.map((r) => (r._id === row._id ? { ...r, relief_code: v } : r)),
                          );
                        }}
                      >
                        {TAX_OPT_B_MVP_RELIEF_CODES.map((code) => (
                          <option key={code} value={code}>
                            {code}
                          </option>
                        ))}
                      </Select>
                    </div>
                  ) : null}
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="shrink-0"
                    onClick={() => removeInvestmentRow(row._id)}
                    aria-label="Remove investment row"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              ))}
            </CardContent>
          </Card>

          <div className="flex flex-wrap gap-3">
            <Button type="submit" disabled={loading} className="w-full sm:w-auto">
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Checking…
                </>
              ) : (
                "Run compliance (structured inputs)"
              )}
            </Button>
            <Button
              type="button"
              variant="outline"
              disabled={loading || taxLoading}
              className="w-full sm:w-auto"
              onClick={() => void runEstimateTaxStructured()}
            >
              {taxLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Estimating…
                </>
              ) : (
                "Estimate tax (MVP)"
              )}
            </Button>
          </div>
        </form>
      ) : (
        <form onSubmit={onSubmitAdvanced} className="grid gap-8 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <ShieldCheck className="h-5 w-5 text-primary" />
                Profile (manual)
            </CardTitle>
            <CardDescription>
                Raw TaxOptBProfileV1 for the manual check. Transaction-backed run overwrites gross /
                taxable from the snapshot in the result.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4">
            <div className="grid gap-2">
              <Label htmlFor={`${formId}-uid`}>User id (Component 1 snapshot)</Label>
              <Input
                id={`${formId}-uid`}
                value={userId}
                onChange={(e) => setUserId(e.target.value)}
                placeholder="demo-user-1"
                className="font-mono text-sm"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor={`${formId}-ty`}>Tax year</Label>
              <Input
                id={`${formId}-ty`}
                value={taxYear}
                onChange={(e) => setTaxYear(e.target.value)}
                className="font-mono text-sm"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor={`${formId}-emp`}>Employment type</Label>
              <Select
                id={`${formId}-emp`}
                value={employmentType}
                onChange={(e) => setEmploymentType(e.target.value as TaxOptBEmploymentTypeV1)}
              >
                <option value="employee">employee</option>
                <option value="self_employed">self_employed</option>
                <option value="business_owner">business_owner</option>
                <option value="other">other</option>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor={`${formId}-dep`}>Dependents</Label>
              <Input
                id={`${formId}-dep`}
                type="number"
                min={0}
                max={20}
                value={dependents}
                onChange={(e) => setDependents(e.target.value)}
              />
            </div>
            <div className="grid gap-2">
                <Label htmlFor={`${formId}-gross`}>Annual gross income (LKR)</Label>
              <Input
                id={`${formId}-gross`}
                value={gross}
                onChange={(e) => setGross(e.target.value)}
                className="font-mono text-sm"
              />
            </div>
            <div className="grid gap-2">
                <Label htmlFor={`${formId}-tax`}>Estimated annual taxable income</Label>
              <Input
                id={`${formId}-tax`}
                value={taxable}
                onChange={(e) => setTaxable(e.target.value)}
                placeholder="optional — leave empty to omit"
                className="font-mono text-sm"
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Strategy proposal (JSON)</CardTitle>
            <CardDescription>
                TaxOptBStrategyProposalV1 — used for manual check and for the transaction-backed check.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4">
            <textarea
              value={strategyJson}
              onChange={(e) => setStrategyJson(e.target.value)}
              spellCheck={false}
              rows={14}
              className="w-full resize-y rounded-md border border-input bg-background px-3 py-2 font-mono text-xs leading-relaxed shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              aria-label="Strategy JSON"
            />
            <Button type="submit" disabled={loading} className="w-full sm:w-auto">
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Checking…
                </>
              ) : (
                "Run compliance check (manual profile)"
              )}
            </Button>
            <Button
              type="button"
              variant="secondary"
              disabled={loading}
              className="w-full sm:w-auto"
              onClick={() => void runFromTransactions()}
            >
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Checking…
                </>
              ) : (
                "Run using Component 1 income snapshot"
              )}
            </Button>
              <Button
                type="button"
                variant="outline"
                disabled={loading || taxLoading}
                className="w-full sm:w-auto"
                onClick={() => void runEstimateTaxAdvanced()}
              >
                {taxLoading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Estimating…
                  </>
                ) : (
                  "Estimate tax (MVP)"
                )}
              </Button>
          </CardContent>
        </Card>
      </form>
      )}

      {error ? (
        <Card className="border-destructive/50 bg-destructive/5">
          <CardHeader>
            <CardTitle className="text-destructive text-base">Request failed</CardTitle>
            <CardDescription className="text-destructive/90">{error}</CardDescription>
          </CardHeader>
        </Card>
      ) : null}

      {result ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Result</CardTitle>
            <CardDescription>
              Ruleset {result.ruleset_assessment_year ?? "—"} (schema {result.ruleset_schema_version ?? "—"})
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div
              className={
                result.passed
                  ? "inline-flex rounded-md border border-emerald-500/40 bg-emerald-500/10 px-3 py-1.5 text-sm font-medium text-emerald-800 dark:text-emerald-200"
                  : "inline-flex rounded-md border border-destructive/40 bg-destructive/10 px-3 py-1.5 text-sm font-medium text-destructive"
              }
            >
              {result.passed ? "Passed" : "Failed"}
            </div>

            {result.mapped_profile ? (
              <div className="rounded-lg border border-border/80 bg-muted/20 p-3 text-sm">
                <div className="font-medium">Mapped profile (from structured inputs)</div>
                <pre className="mt-2 max-h-48 overflow-auto rounded-md border bg-muted/40 p-2 text-xs">
                  {JSON.stringify(result.mapped_profile, null, 2)}
                </pre>
              </div>
            ) : null}

            {result.mapped_strategy ? (
              <div className="rounded-lg border border-border/80 bg-muted/20 p-3 text-sm">
                <div className="font-medium">Mapped strategy (generated claims)</div>
                <pre className="mt-2 max-h-48 overflow-auto rounded-md border bg-muted/40 p-2 text-xs">
                  {JSON.stringify(result.mapped_strategy, null, 2)}
                </pre>
              </div>
            ) : null}

            {result.income_snapshot ? (
              <div className="rounded-lg border border-border/80 bg-muted/20 p-3 text-sm">
                <div className="font-medium">Income snapshot (Component 1)</div>
                <p className="mt-1 text-xs text-muted-foreground">
                  {result.income_snapshot.derivation_summary}
                </p>
                <dl className="mt-2 grid gap-1 text-xs font-mono sm:grid-cols-2">
                  <div>
                    <dt className="text-muted-foreground">source</dt>
                    <dd>{result.income_snapshot.source}</dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">pipeline</dt>
                    <dd>{result.income_snapshot.pipeline_version}</dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">gross</dt>
                    <dd>{result.income_snapshot.annual_gross_income}</dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">taxable</dt>
                    <dd>{result.income_snapshot.estimated_annual_taxable_income}</dd>
                  </div>
                </dl>
              </div>
            ) : null}

            {result.violations.length > 0 ? (
              <ul className="space-y-3">
                {result.violations.map((v, i) => {
                  const key = `${v.rule_id}-${i}`;
                  const open = openRefs[key];
                  return (
                    <li
                      key={key}
                      className="rounded-lg border border-border/80 bg-muted/30 px-3 py-2 text-sm"
                    >
                      <div className="font-mono text-xs text-muted-foreground">{v.rule_id}</div>
                      <div className="mt-1">{v.message}</div>
                      {v.reference ? (
                        <button
                          type="button"
                          onClick={() => toggleRef(key)}
                          className="mt-2 flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                        >
                          {open ? (
                            <ChevronDown className="h-3.5 w-3.5" />
                          ) : (
                            <ChevronRight className="h-3.5 w-3.5" />
                          )}
                          Rule reference
                        </button>
                      ) : null}
                      {open && v.reference ? (
                        <p className="mt-2 border-l-2 border-primary/40 pl-3 text-xs text-muted-foreground">
                          {v.reference}
                        </p>
                      ) : null}
                    </li>
                  );
                })}
              </ul>
            ) : null}

            {result.passed && Object.keys(result.applied_relief).length > 0 ? (
              <div>
                <div className="mb-2 text-sm font-medium">Applied relief (caps)</div>
                <pre className="max-h-64 overflow-auto rounded-md border bg-muted/40 p-3 text-xs">
                  {JSON.stringify(result.applied_relief, null, 2)}
                </pre>
              </div>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      {taxCompute ? (
        <Card className="border-amber-500/40 bg-amber-500/5">
          <CardHeader>
            <CardTitle className="text-base">Tax estimate (MVP)</CardTitle>
            <CardDescription className="text-amber-950/80 dark:text-amber-100/90">
              {taxCompute.research_disclaimer}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {taxCompute.tax_computation ? (
              <>
                <div className="text-lg font-semibold">
                  Total tax (LKR):{" "}
                  <span className="font-mono">{taxCompute.tax_computation.total_tax}</span>
                </div>
                <dl className="grid gap-2 text-sm sm:grid-cols-2">
                  <div>
                    <dt className="text-muted-foreground">Income basis (before personal relief)</dt>
                    <dd className="font-mono">{taxCompute.tax_computation.income_basis_before_personal_relief}</dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">Personal relief</dt>
                    <dd className="font-mono">{taxCompute.tax_computation.personal_relief_annual}</dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">Taxable after personal relief</dt>
                    <dd className="font-mono">{taxCompute.tax_computation.taxable_after_personal_relief}</dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">Allowed deductions (total)</dt>
                    <dd className="font-mono">{taxCompute.tax_computation.total_allowed_deductions}</dd>
                  </div>
                  <div className="sm:col-span-2">
                    <dt className="text-muted-foreground">Taxable after deductions (slab base)</dt>
                    <dd className="font-mono">{taxCompute.tax_computation.taxable_after_deductions}</dd>
                  </div>
                </dl>
                <div>
                  <div className="mb-2 text-sm font-medium">Slab allocation</div>
                  <ul className="space-y-1 font-mono text-xs">
                    {taxCompute.tax_computation.slab_slices.map((s) => (
                      <li key={s.slab_index}>
                        Band {s.slab_index}: rate {s.rate} — slice {s.taxable_in_slice} LKR → tax{" "}
                        {s.tax_in_slice}
                        {s.slice_width_cap ? ` (cap width ${s.slice_width_cap})` : " (remainder)"}
                      </li>
                    ))}
                  </ul>
                </div>
                <p className="text-xs text-muted-foreground">{taxCompute.tax_computation.algorithm_documentation}</p>
                <pre className="max-h-40 overflow-auto rounded-md border bg-muted/40 p-2 text-xs">
                  {JSON.stringify(taxCompute.tax_computation.per_deduction_allowed, null, 2)}
                </pre>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">
                Compliance did not pass, so no tax figure was produced. Fix violations and try again.
              </p>
            )}
            <ExplanationPanel
              bundle={taxCompute.explanations}
              title="Narrative — tax estimate (FR5)"
            />
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Compare scenarios (FR6)</CardTitle>
          <CardDescription>
            Uses your structured intake above plus optional extra strategies. Enable{" "}
            <strong>Mapped intake</strong> to include <span className="font-mono">from_intake</span>{" "}
            (deductions from this form). Edit JSON to add more variants.{" "}
            <Link to="/tax-optimization/compare" className="text-primary underline">
              Manual profile JSON
            </Link>
            . For enumerated max-cap search (Function 2), use the{" "}
            <Link to="/tax-optimization/explorer" className="text-primary underline">
              Strategy explorer
            </Link>
            .
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center gap-4">
            <label className="flex cursor-pointer items-center gap-2 text-sm">
              <input
                type="checkbox"
                className="rounded border-input"
                checked={compareIncludeMapped}
                onChange={(e) => setCompareIncludeMapped(e.target.checked)}
              />
              Include mapped intake (<span className="font-mono">from_intake</span>)
            </label>
            <div className="flex flex-col gap-1">
              <Label htmlFor={`${formId}-baseline`} className="text-xs">
                Baseline variant id (optional)
              </Label>
              <Input
                id={`${formId}-baseline`}
                value={compareBaselineId}
                onChange={(e) => setCompareBaselineId(e.target.value)}
                placeholder="e.g. from_intake"
                className="h-9 w-48 font-mono text-sm"
              />
            </div>
            <Button
              type="button"
              disabled={compareLoading}
              onClick={() => void runCompareScenarios()}
              className="mt-auto"
            >
              {compareLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Comparing…
                </>
              ) : (
                "Compare scenarios"
              )}
            </Button>
          </div>
          <div>
            <Label htmlFor={`${formId}-compare-extras`} className="text-xs">
              Extra strategy variants (JSON array)
            </Label>
            <textarea
              id={`${formId}-compare-extras`}
              value={compareExtraVariantsJson}
              onChange={(e) => setCompareExtraVariantsJson(e.target.value)}
              spellCheck={false}
              rows={8}
              className="mt-1 w-full resize-y rounded-md border border-input bg-background px-3 py-2 font-mono text-xs leading-relaxed shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          </div>
          {compareError ? (
            <p className="text-sm text-destructive">{compareError}</p>
          ) : null}
          <CompareStrategiesTable
            data={compareResult}
            expanded={compareExpanded}
            onToggleExpand={toggleCompareExpand}
          />
          <ExplanationPanel
            bundle={compareResult?.explanations}
            title="Narrative — scenario comparison (FR5)"
          />
        </CardContent>
      </Card>
    </div>
  );
}
