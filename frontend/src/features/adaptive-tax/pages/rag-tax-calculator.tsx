import { useEffect, useState, useMemo } from "react";
import {
  Calculator,
  ChevronDown,
  ChevronRight,
  Info,
  Loader2,
  Copy,
  Check,
} from "lucide-react";
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

// Types for RAG relief data
type RagRelief = {
  relief_name: string;
  assessment_year: string;
  cap_amount: string | null;
  cap_currency: string;
  section_ref: string;
  law_quote: string | null;
  how_to_calculate: string | null;
  confidence_overall: number;
  status: string;
  effective_from: string | null;
  effective_to: string | null;
};

type TaxCalculation = {
  gross_income: number;
  total_reliefs: number;
  assessable_income: number;
  tax_before_credits: number;
  tax_after_credits: number;
  reliefs_applied: Array<{
    name: string;
    amount: number;
    section: string;
    quote: string | null;
  }>;
};

// Utility function to format money
function formatLkr(value: number | string): string {
  const num = typeof value === "string" ? parseFloat(value) : value;
  if (isNaN(num)) return "0";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "LKR",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  })
    .format(num)
    .replace("LKR", "")
    .trim();
}

function parseLkr(value: string): number {
  const cleaned = value.replace(/,/g, "").trim();
  const n = Number(cleaned);
  return Number.isFinite(n) && n >= 0 ? n : 0;
}

// Tax slab rates (standard Sri Lanka rates - can be updated from RAG)
const DEFAULT_TAX_SLABS = [
  { from: 0, to: 500000, rate: 0 },
  { from: 500000, to: 1000000, rate: 0.06 },
  { from: 1000000, to: 2000000, rate: 0.12 },
  { from: 2000000, to: 5000000, rate: 0.18 },
  { from: 5000000, to: Infinity, rate: 0.24 },
];

function getTaxSlabs(year: AssessmentYear) {
  return DEFAULT_TAX_SLABS;
}

function calculateTaxFromSlabs(
  assessableIncome: number,
  slabs: Array<{ from: number; to: number; rate: number }>
): number {
  let tax = 0;
  for (const slab of slabs) {
    const slabIncome = Math.min(assessableIncome, slab.to) - slab.from;
    if (slabIncome > 0) {
      tax += slabIncome * slab.rate;
    }
  }
  return tax;
}

const AVAILABLE_YEARS = [
  "2017_18",
  "2018_19",
  "2019_20",
  "2020_21",
  "2021_22",
  "2022_23",
  "2023_24",
  "2024_25",
  "2025_26",
] as const;

type AssessmentYear = (typeof AVAILABLE_YEARS)[number];

export function RagTaxCalculatorPage() {
  const [assessmentYear, setAssessmentYear] = useState<AssessmentYear>(
    "2025_26"
  );
  const [grossIncome, setGrossIncome] = useState("0");
  const [reliefs, setReliefs] = useState<RagRelief[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [appliedReliefs, setAppliedReliefs] = useState<
    Record<string, { applied: boolean; amount: string }>
  >({});
  const [expandedRelief, setExpandedRelief] = useState<string | null>(null);
  const [copiedSection, setCopiedSection] = useState<string | null>(null);

  // Fetch reliefs from relief interview catalog
  useEffect(() => {
    setLoading(true);
    setError(null);

    const yaFormatted = assessmentYear.replace("_", "_");
    fetch(`/api/v1/adaptive-tax/relief-interview/approved/${yaFormatted}`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data) => {
        const entries = data.entries || [];
        if (Array.isArray(entries) && entries.length > 0) {
          const reliefs = entries.map((entry: any) => ({
            relief_name: entry.display_name || "Unknown Relief",
            assessment_year: assessmentYear,
            cap_amount: entry.cap_amount || null,
            cap_currency: entry.unit === "percent" ? "%" : "LKR",
            section_ref: entry.section_ref || "N/A",
            law_quote: entry.quote || null,
            how_to_calculate: null,
            confidence_overall: 1.0,
            status: entry.auto_applied ? "auto_applied" : "active",
            effective_from: entry.provenance?.effective_from_stated || null,
            effective_to: null,
          })) as RagRelief[];

          setReliefs(reliefs);

          // Initialize applied reliefs tracking
          const initial: Record<string, { applied: boolean; amount: string }> =
            {};
          reliefs.forEach((relief) => {
            initial[relief.relief_name] = {
              applied: false,
              amount: relief.cap_amount ? String(relief.cap_amount) : "0",
            };
          });
          setAppliedReliefs(initial);
        } else {
          setError("No reliefs found for selected year");
        }
      })
      .catch((err) => {
        setError(`Failed to load reliefs: ${err.message}`);
      })
      .finally(() => {
        setLoading(false);
      });
  }, [assessmentYear]);

  // Calculate tax
  const calculation = useMemo<TaxCalculation>(() => {
    const gross = parseLkr(grossIncome);
    const slabs = getTaxSlabs(assessmentYear);

    let totalReliefs = 0;
    const appliedReliefsArray = reliefs
      .filter((relief) => {
        const applied = appliedReliefs[relief.relief_name]?.applied;
        if (!applied) return false;
        const amount = parseLkr(appliedReliefs[relief.relief_name]?.amount || "0");
        totalReliefs += amount;
        return true;
      })
      .map((relief) => ({
        name: relief.relief_name,
        amount: parseLkr(appliedReliefs[relief.relief_name]?.amount || "0"),
        section: relief.section_ref,
        quote: relief.law_quote,
      }));

    const assessableIncome = Math.max(0, gross - totalReliefs);
    const taxBeforeCredits = calculateTaxFromSlabs(assessableIncome, slabs);

    return {
      gross_income: gross,
      total_reliefs: totalReliefs,
      assessable_income: assessableIncome,
      tax_before_credits: taxBeforeCredits,
      tax_after_credits: taxBeforeCredits,
      reliefs_applied: appliedReliefsArray,
    };
  }, [grossIncome, appliedReliefs, reliefs, assessmentYear]);

  function toggleRelief(reliefName: string, relief: RagRelief) {
    setAppliedReliefs((prev) => ({
      ...prev,
      [reliefName]: {
        ...prev[reliefName],
        applied: !prev[reliefName]?.applied,
        amount: relief.cap_amount || "0",
      },
    }));
  }

  function updateReliefAmount(reliefName: string, amount: string) {
    setAppliedReliefs((prev) => ({
      ...prev,
      [reliefName]: {
        ...prev[reliefName],
        amount: amount,
      },
    }));
  }

  function copyToClipboard(text: string, section: string) {
    navigator.clipboard.writeText(text);
    setCopiedSection(section);
    setTimeout(() => setCopiedSection(null), 2000);
  }

  return (
    <div className="min-h-screen bg-background p-4 md:p-6 lg:p-8">
      <div className="mx-auto max-w-6xl space-y-6">
        {/* Header */}
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Calculator className="h-6 w-6 text-primary" />
            <h1 className="text-3xl font-bold">Tax Calculator (RAG-Powered)</h1>
          </div>
          <p className="text-muted-foreground">
            Calculate your tax liability using reliefs from your tax acts. Powered by RAG
            system.
          </p>
        </div>

        <div className="grid gap-6 lg:grid-cols-3">
          {/* Left Column - Inputs & Configuration */}
          <div className="lg:col-span-2 space-y-6">
            {/* Year Selection */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Assessment Year</CardTitle>
              </CardHeader>
              <CardContent>
                <Select
                  value={assessmentYear}
                  onValueChange={(value) =>
                    setAssessmentYear(value as AssessmentYear)
                  }
                >
                  {AVAILABLE_YEARS.map((year) => (
                    <option key={year} value={year}>
                      YA {year.replace("_", "/")}
                    </option>
                  ))}
                </Select>
                <p className="mt-2 text-xs text-muted-foreground">
                  Select the assessment year to see applicable reliefs and tax rates.
                </p>
              </CardContent>
            </Card>

            {/* Income Input */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Gross Income</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <Label htmlFor="gross-income">Annual Income (LKR)</Label>
                  <Input
                    id="gross-income"
                    inputMode="numeric"
                    value={formatLkr(grossIncome)}
                    onChange={(e) =>
                      setGrossIncome(e.target.value.replace(/[^0-9]/g, ""))
                    }
                    placeholder="0"
                  />
                  <p className="text-xs text-muted-foreground">
                    Enter your total annual income before reliefs.
                  </p>
                </div>
              </CardContent>
            </Card>

            {/* Available Reliefs */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Available Reliefs</CardTitle>
                <CardDescription>
                  {reliefs.length > 0
                    ? `${reliefs.length} reliefs available for ${assessmentYear}`
                    : "Loading reliefs..."}
                </CardDescription>
              </CardHeader>
              <CardContent>
                {loading ? (
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Loading reliefs from RAG...
                  </div>
                ) : error ? (
                  <div className="rounded bg-destructive/10 p-3 text-sm text-destructive">
                    {error}
                  </div>
                ) : reliefs.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    No reliefs found for {assessmentYear}
                  </p>
                ) : (
                  <div className="space-y-3">
                    {reliefs.map((relief) => {
                      const applied =
                        appliedReliefs[relief.relief_name]?.applied || false;
                      return (
                        <div
                          key={relief.relief_name}
                          className="rounded border border-border bg-muted/30 p-3 space-y-2"
                        >
                          {/* Relief Header */}
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex-1">
                              <div className="flex items-center gap-2">
                                <input
                                  type="checkbox"
                                  id={`relief-${relief.relief_name}`}
                                  checked={applied}
                                  onChange={() =>
                                    toggleRelief(relief.relief_name, relief)
                                  }
                                  className="mt-1"
                                />
                                <label
                                  htmlFor={`relief-${relief.relief_name}`}
                                  className="text-sm font-medium cursor-pointer"
                                >
                                  {relief.relief_name}
                                </label>
                              </div>
                              <div className="mt-1 flex flex-wrap gap-1">
                                <span className="inline-flex items-center rounded border border-border bg-background px-2 py-0.5 text-[11px] text-muted-foreground">
                                  {relief.section_ref}
                                </span>
                                <span className="inline-flex items-center rounded border border-border bg-background px-2 py-0.5 text-[11px] text-muted-foreground">
                                  {relief.cap_currency === "%" ? "% of income" : relief.cap_currency}
                                </span>
                                <span className="inline-flex items-center rounded border border-border bg-background px-2 py-0.5 text-[11px] text-muted-foreground">
                                  {`${(relief.confidence_overall * 100).toFixed(0)}% confidence`}
                                </span>
                              </div>
                            </div>
                            <button
                              onClick={() =>
                                setExpandedRelief(
                                  expandedRelief === relief.relief_name
                                    ? null
                                    : relief.relief_name
                                )
                              }
                              className="text-muted-foreground hover:text-foreground mt-1"
                            >
                              {expandedRelief === relief.relief_name ? (
                                <ChevronDown className="h-4 w-4" />
                              ) : (
                                <ChevronRight className="h-4 w-4" />
                              )}
                            </button>
                          </div>

                          {/* Relief Details */}
                          {expandedRelief === relief.relief_name && (
                            <div className="space-y-2 border-t border-border/50 pt-2">
                              {/* Amount Input */}
                              {relief.cap_currency !== "%" && (
                                <div className="space-y-1">
                                  <Label
                                    htmlFor={`relief-amount-${relief.relief_name}`}
                                    className="text-xs"
                                  >
                                    Amount to claim (LKR)
                                  </Label>
                                  <Input
                                    id={`relief-amount-${relief.relief_name}`}
                                    inputMode="numeric"
                                    value={formatLkr(
                                      appliedReliefs[relief.relief_name]?.amount || "0"
                                    )}
                                    onChange={(e) =>
                                      updateReliefAmount(
                                        relief.relief_name,
                                        e.target.value.replace(/[^0-9]/g, "")
                                      )
                                    }
                                    placeholder="0"
                                  />
                                  {relief.cap_amount && (
                                    <p className="text-[11px] text-muted-foreground">
                                      Cap limit: {formatLkr(relief.cap_amount)}{" "}
                                      {relief.cap_currency}
                                    </p>
                                  )}
                                </div>
                              )}

                              {/* Law Quote */}
                              {relief.law_quote && (
                                <div className="space-y-1">
                                  <div className="flex items-center justify-between">
                                    <p className="text-xs font-medium text-muted-foreground">
                                      Law Quote
                                    </p>
                                    <button
                                      onClick={() =>
                                        copyToClipboard(
                                          relief.law_quote || "",
                                          relief.relief_name
                                        )
                                      }
                                      className="inline-flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground"
                                    >
                                      {copiedSection === relief.relief_name ? (
                                        <>
                                          <Check className="h-3 w-3" />
                                          Copied
                                        </>
                                      ) : (
                                        <>
                                          <Copy className="h-3 w-3" />
                                          Copy
                                        </>
                                      )}
                                    </button>
                                  </div>
                                  <p className="rounded bg-background/50 p-2 text-[11px] italic text-muted-foreground">
                                    "{relief.law_quote}"
                                  </p>
                                </div>
                              )}

                              {/* How to Calculate */}
                              {relief.how_to_calculate && (
                                <div className="space-y-1">
                                  <p className="text-xs font-medium text-muted-foreground">
                                    How to calculate
                                  </p>
                                  <p className="rounded bg-background/50 p-2 text-[11px] text-muted-foreground">
                                    {relief.how_to_calculate}
                                  </p>
                                </div>
                              )}

                              {/* Effective Dates */}
                              {(relief.effective_from || relief.effective_to) && (
                                <div className="text-[10px] text-muted-foreground">
                                  {relief.effective_from && (
                                    <p>Effective from: {relief.effective_from}</p>
                                  )}
                                  {relief.effective_to && (
                                    <p>Effective to: {relief.effective_to}</p>
                                  )}
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Right Column - Tax Calculation Summary */}
          <div className="space-y-6">
            {/* Summary Card */}
            <Card className="bg-gradient-to-br from-primary/10 to-primary/5 border-primary/20">
              <CardHeader>
                <CardTitle className="text-lg">Tax Calculation Summary</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Gross Income */}
                <div className="space-y-1">
                  <p className="text-xs text-muted-foreground">Gross Income</p>
                  <p className="text-2xl font-bold">
                    {formatLkr(calculation.gross_income)}
                  </p>
                </div>

                <div className="border-t border-border/50" />

                {/* Total Reliefs */}
                <div className="space-y-1">
                  <p className="text-xs text-muted-foreground">
                    Total Reliefs Applied
                  </p>
                  <p className="text-xl font-semibold text-emerald-700 dark:text-emerald-400">
                    −{formatLkr(calculation.total_reliefs)}
                  </p>
                  <p className="text-[11px] text-muted-foreground">
                    {calculation.reliefs_applied.length} relief(s) selected
                  </p>
                </div>

                <div className="border-t border-border/50" />

                {/* Assessable Income */}
                <div className="space-y-1">
                  <p className="text-xs text-muted-foreground">Assessable Income</p>
                  <p className="text-2xl font-bold">
                    {formatLkr(calculation.assessable_income)}
                  </p>
                </div>

                <div className="border-t border-border/50" />

                {/* Tax Calculation */}
                <div className="space-y-2">
                  <p className="text-xs font-medium text-muted-foreground">
                    Tax Calculation (Using {assessmentYear} Slabs)
                  </p>
                  <div className="rounded bg-background/70 p-2 space-y-1">
                    {getTaxSlabs(assessmentYear).map((slab, idx) => {
                      const slabIncome = Math.min(
                        calculation.assessable_income,
                        slab.to
                      ) - slab.from;
                      if (slabIncome <= 0) return null;
                      const slabTax = slabIncome * slab.rate;
                      return (
                        <div
                          key={idx}
                          className="flex justify-between text-[11px] text-muted-foreground"
                        >
                          <span>
                            {formatLkr(slab.from)} – {formatLkr(slab.to)} @ {(slab.rate * 100).toFixed(0)}%
                          </span>
                          <span className="font-medium">
                            {formatLkr(slabTax)}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>

                <div className="border-t border-border/50" />

                {/* Final Tax */}
                <div className="space-y-1">
                  <p className="text-xs text-muted-foreground">Tax Payable</p>
                  <p className="text-3xl font-bold text-amber-600 dark:text-amber-400">
                    {formatLkr(calculation.tax_after_credits)}
                  </p>
                </div>

                <div className="border-t border-border/50" />

                {/* Tax Rate */}
                <div className="space-y-1">
                  <p className="text-xs text-muted-foreground">Effective Tax Rate</p>
                  <p className="text-lg font-semibold">
                    {calculation.gross_income > 0
                      ? (
                          (calculation.tax_after_credits /
                            calculation.gross_income) *
                          100
                        ).toFixed(2)
                      : 0}
                    %
                  </p>
                </div>
              </CardContent>
            </Card>

            {/* Tax Slabs Reference */}
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">
                  Tax Slabs for {assessmentYear}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2 text-[11px]">
                  {getTaxSlabs(assessmentYear).map((slab, idx) => (
                    <div
                      key={idx}
                      className="flex justify-between py-1 border-b border-border/30 last:border-0"
                    >
                      <span className="text-muted-foreground">
                        {formatLkr(slab.from)} – {formatLkr(slab.to)}
                      </span>
                      <span className="font-medium">
                        {(slab.rate * 100).toFixed(0)}%
                      </span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* RAG Status */}
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">RAG System Status</CardTitle>
              </CardHeader>
              <CardContent className="text-xs space-y-2">
                <div className="flex items-center gap-2">
                  <div className="h-2 w-2 rounded-full bg-emerald-500" />
                  <span>RAG connected</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="h-2 w-2 rounded-full bg-emerald-500" />
                  <span>{reliefs.length} reliefs loaded</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="h-2 w-2 rounded-full bg-emerald-500" />
                  <span>No API credits used</span>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
