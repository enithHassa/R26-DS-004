import { useId, useState, type FormEvent } from "react";
import { Calendar, Loader2, TrendingDown, TrendingUp } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";

import { postRfTaxPredict } from "../api";
import { formatLkrAmount } from "../format-lkr";
import type {
  TaxOptBEmploymentTypeV1,
  TaxOptBRfTaxPredictRequestV1,
  TaxOptBRfTaxPredictResponseV1,
  TaxOptBShapFeatureContributionV1,
} from "../types";

const EMPLOYMENT_OPTIONS: { value: TaxOptBEmploymentTypeV1; label: string }[] = [
  { value: "employee", label: "Employee" },
  { value: "self_employed", label: "Self-employed" },
  { value: "business_owner", label: "Business owner" },
  { value: "other", label: "Other" },
];

const FEATURE_LABELS: Record<string, string> = {
  annual_salary_income: "Salary income",
  annual_business_income: "Business income",
  annual_investment_income: "Investment income",
  annual_other_income: "Other income",
  total_gross_income: "Total gross income",
  total_relief_claimed: "Total relief claimed",
  dependents: "Number of dependents",
  employment_type_code: "Employment type",
  relief_life_insurance_premium: "Life insurance premium",
  relief_health_insurance_premium: "Health insurance premium",
  relief_home_loan_interest: "Home loan interest",
  relief_rent: "Rent paid",
  relief_charitable_donations: "Charitable donations",
  relief_retirement_contribution: "Retirement contributions",
};

function digitsOnly(s: string): string {
  return s.replace(/\D/g, "");
}

function formatDisplay(digitStr: string): string {
  if (!digitStr) return "";
  return Number(digitStr).toLocaleString("en-LK");
}

function formatUserFacingError(message: string): string {
  if (message.includes("503") || message.toLowerCase().includes("not loaded")) {
    return "The filing calculator model is not available yet. Ask your administrator to run the RF training script and restart the tax service.";
  }
  return message;
}

function ShapBar({
  contribution,
  maxAbs,
}: {
  contribution: TaxOptBShapFeatureContributionV1;
  maxAbs: number;
}) {
  const pct = maxAbs > 0 ? (Math.abs(contribution.shap_value) / maxAbs) * 100 : 0;
  const isPositive = contribution.shap_value > 0;
  const label = FEATURE_LABELS[contribution.feature_name] ?? contribution.feature_name;
  const Icon = isPositive ? TrendingUp : TrendingDown;

  return (
    <div className="flex items-center gap-3 py-1.5">
      <div className="w-5 flex-none">
        <Icon
          className={`h-4 w-4 ${isPositive ? "text-destructive" : "text-emerald-600"}`}
          aria-hidden
        />
      </div>
      <div className="w-44 flex-none truncate text-sm text-muted-foreground">{label}</div>
      <div className="flex-1">
        <div className="h-3 overflow-hidden rounded-full bg-muted">
          <div
            className={`h-full rounded-full transition-all ${isPositive ? "bg-destructive/70" : "bg-emerald-500/70"}`}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>
      <div
        className={`w-32 flex-none text-right text-sm tabular-nums font-medium ${isPositive ? "text-destructive" : "text-emerald-600"}`}
      >
        {isPositive ? "+" : ""}
        {formatLkrAmount(Math.round(contribution.shap_value))}
      </div>
    </div>
  );
}

export function TaxFilingPage() {
  const formId = useId();

  const [employmentType, setEmploymentType] = useState<TaxOptBEmploymentTypeV1>("employee");
  const [dependents, setDependents] = useState("0");
  const [salary, setSalary] = useState("");
  const [business, setBusiness] = useState("");
  const [investment, setInvestment] = useState("");
  const [otherIncome, setOtherIncome] = useState("");

  const [lifeInsurance, setLifeInsurance] = useState("");
  const [healthInsurance, setHealthInsurance] = useState("");
  const [homeLoan, setHomeLoan] = useState("");
  const [rent, setRent] = useState("");
  const [donations, setDonations] = useState("");
  const [retirement, setRetirement] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<TaxOptBRfTaxPredictResponseV1 | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const body: TaxOptBRfTaxPredictRequestV1 = {
        tax_year: "2025_26",
        employment_type: employmentType,
        dependents: Math.max(0, Math.min(20, parseInt(dependents || "0", 10))),
        annual_salary_income: salary || "0",
        annual_business_income: business || "0",
        annual_investment_income: investment || "0",
        annual_other_income: otherIncome || "0",
        relief_life_insurance_premium: lifeInsurance || "0",
        relief_health_insurance_premium: healthInsurance || "0",
        relief_home_loan_interest: homeLoan || "0",
        relief_rent: rent || "0",
        relief_charitable_donations: donations || "0",
        relief_retirement_contribution: retirement || "0",
      };
      const data = await postRfTaxPredict(body);
      setResult(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "An error occurred. Please try again.";
      setError(formatUserFacingError(msg));
    } finally {
      setLoading(false);
    }
  }

  const maxShapAbs =
    result
      ? Math.max(...result.shap_explanation.feature_contributions.map((c) => Math.abs(c.shap_value)), 1)
      : 1;

  return (
    <div className="mx-auto max-w-2xl space-y-6 px-4 py-8">
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Calendar className="h-5 w-5 text-primary" aria-hidden />
          <span className="rounded-full bg-amber-100 px-3 py-0.5 text-xs font-semibold text-amber-800">
            File before 30 November 2026
          </span>
        </div>
        <h1 className="text-2xl font-bold tracking-tight">Tax Filing 2025/26</h1>
        <p className="text-sm text-muted-foreground">
          Enter your income and any reliefs you have spent. We estimate your tax for the year ending
          2025/26 and explain what drove the result.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Income</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-2">
              <Label htmlFor={`${formId}-emp`}>Employment type</Label>
              <Select
                id={`${formId}-emp`}
                value={employmentType}
                onChange={(e) => setEmploymentType(e.target.value as TaxOptBEmploymentTypeV1)}
              >
                {EMPLOYMENT_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </Select>
            </div>

            <div className="grid gap-2">
              <Label htmlFor={`${formId}-dep`}>Number of dependents</Label>
              <Input
                id={`${formId}-dep`}
                inputMode="numeric"
                autoComplete="off"
                value={dependents}
                onChange={(e) => setDependents(digitsOnly(e.target.value).slice(0, 2))}
                className="h-10 w-28 tabular-nums"
              />
            </div>

            {(
              [
                { id: "salary", label: "Annual salary income", value: salary, set: setSalary },
                { id: "business", label: "Annual business income", value: business, set: setBusiness },
                { id: "investment", label: "Annual investment income", value: investment, set: setInvestment },
                { id: "other", label: "Other annual income", value: otherIncome, set: setOtherIncome },
              ] as const
            ).map(({ id, label, value, set }) => (
              <div key={id} className="grid gap-2">
                <Label htmlFor={`${formId}-${id}`}>{label}</Label>
                <div className="flex overflow-hidden rounded-md border border-input shadow-sm focus-within:ring-2 focus-within:ring-ring">
                  <span className="flex items-center border-r border-input bg-muted/30 px-3 text-sm text-muted-foreground">
                    LKR
                  </span>
                  <Input
                    id={`${formId}-${id}`}
                    inputMode="numeric"
                    autoComplete="off"
                    placeholder="0"
                    value={formatDisplay(value)}
                    onChange={(e) => set(digitsOnly(e.target.value))}
                    className="h-10 border-0 text-right tabular-nums focus-visible:ring-0 focus-visible:ring-offset-0"
                  />
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Reliefs and deductions</CardTitle>
            <p className="text-xs text-muted-foreground">Enter what you actually paid. Leave blank if none.</p>
          </CardHeader>
          <CardContent className="space-y-4">
            {(
              [
                { id: "life", label: "Life insurance premium paid", value: lifeInsurance, set: setLifeInsurance },
                { id: "health", label: "Health insurance premium paid", value: healthInsurance, set: setHealthInsurance },
                { id: "home", label: "Home loan interest paid", value: homeLoan, set: setHomeLoan },
                { id: "rent", label: "Rent paid", value: rent, set: setRent },
                { id: "donations", label: "Charitable donations made", value: donations, set: setDonations },
                { id: "retirement", label: "Retirement fund contributions", value: retirement, set: setRetirement },
              ] as const
            ).map(({ id, label, value, set }) => (
              <div key={id} className="grid gap-2">
                <Label htmlFor={`${formId}-relief-${id}`}>{label}</Label>
                <div className="flex overflow-hidden rounded-md border border-input shadow-sm focus-within:ring-2 focus-within:ring-ring">
                  <span className="flex items-center border-r border-input bg-muted/30 px-3 text-sm text-muted-foreground">
                    LKR
                  </span>
                  <Input
                    id={`${formId}-relief-${id}`}
                    inputMode="numeric"
                    autoComplete="off"
                    placeholder="0"
                    value={formatDisplay(value)}
                    onChange={(e) => set(digitsOnly(e.target.value))}
                    className="h-10 border-0 text-right tabular-nums focus-visible:ring-0 focus-visible:ring-offset-0"
                  />
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        <Button type="submit" className="w-full" disabled={loading}>
          {loading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
              Calculating…
            </>
          ) : (
            "Calculate my tax"
          )}
        </Button>
      </form>

      {error ? (
        <Card className="border-destructive/30 bg-destructive/5">
          <CardHeader className="p-6 pb-2">
            <CardTitle className="text-base font-semibold text-destructive">Error</CardTitle>
          </CardHeader>
          <CardContent className="px-6 pb-6 pt-0">
            <p className="text-sm text-destructive/90">{error}</p>
          </CardContent>
        </Card>
      ) : null}

      {result ? (
        <div className="space-y-4">
          <Card className="border-primary/20 bg-primary/5">
            <CardContent className="p-6">
              <p className="text-sm font-medium text-muted-foreground">Estimated tax for 2025/26</p>
              <p className="mt-1 text-4xl font-bold tabular-nums tracking-tight text-primary">
                {formatLkrAmount(result.predicted_tax_lkr)}
              </p>
              <div className="mt-4 grid grid-cols-2 gap-4 border-t border-border/40 pt-4 text-sm">
                <div>
                  <p className="text-muted-foreground">Total gross income</p>
                  <p className="font-semibold tabular-nums">{formatLkrAmount(result.total_gross_income_lkr)}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Total relief claimed</p>
                  <p className="font-semibold tabular-nums">{formatLkrAmount(result.total_relief_claimed_lkr)}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">What drove your tax?</CardTitle>
              <p className="text-xs text-muted-foreground">
                Red bars increase your tax; green bars reduce it. Sorted by impact.
              </p>
            </CardHeader>
            <CardContent className="space-y-0.5 pb-5">
              {result.shap_explanation.feature_contributions
                .filter((c) => Math.abs(c.shap_value) > 0.5)
                .map((c) => (
                  <ShapBar key={c.feature_name} contribution={c} maxAbs={maxShapAbs} />
                ))}
            </CardContent>
          </Card>

          <Card className="border-border/30 bg-muted/20">
            <CardContent className="p-4">
              <p className="text-xs leading-relaxed text-muted-foreground">{result.disclaimer}</p>
              <p className="mt-2 text-[10px] text-muted-foreground/60">
                Model: {result.model_id} · Features: {result.feature_version}
              </p>
            </CardContent>
          </Card>
        </div>
      ) : null}
    </div>
  );
}
