import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { Calculator, FileText, Loader2 } from "lucide-react";

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
  calculateTax,
  type CalculateTaxRequest,
  type CalculateTaxResponse,
} from "../api";
import { formatLkr, toMoneyWire } from "../format-lkr";

type FormState = {
  assessment_year: "2024_25";
  resident_status: "resident" | "non_resident";
  param_set: "current" | "pre_amend_2025";
  employment_income: string;
  business_income: string;
  investment_income: string;
  qualifying_payments: string;
  donations: string;
};

const INITIAL: FormState = {
  assessment_year: "2024_25",
  resident_status: "resident",
  param_set: "current",
  employment_income: "1800000",
  business_income: "0",
  investment_income: "0",
  qualifying_payments: "0",
  donations: "0",
};

function Chip({ children }: { children: string }) {
  return (
    <span className="inline-flex max-w-full truncate rounded-md border bg-muted/60 px-1.5 py-0.5 text-[11px] text-foreground">
      {children}
    </span>
  );
}

function MoneyField({
  id,
  label,
  value,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (next: string) => void;
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      <Input
        id={id}
        inputMode="numeric"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder="0"
      />
    </div>
  );
}

export function AdaptiveTaxCalculatorPage() {
  const [form, setForm] = useState<FormState>(INITIAL);
  const [result, setResult] = useState<CalculateTaxResponse | null>(null);
  const [isCalculating, setIsCalculating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function patch<K extends keyof FormState>(key: K, value: FormState[K]): void {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSubmit(event: FormEvent): Promise<void> {
    event.preventDefault();
    setIsCalculating(true);
    setError(null);
    try {
      const body: CalculateTaxRequest = {
        assessment_year: form.assessment_year,
        resident_status: form.resident_status,
        param_set: form.param_set,
        employment_income: toMoneyWire(form.employment_income),
        business_income: toMoneyWire(form.business_income),
        investment_income: toMoneyWire(form.investment_income),
        qualifying_payments: toMoneyWire(form.qualifying_payments),
        donations: toMoneyWire(form.donations),
        other_reliefs: {},
      };
      const resp = await calculateTax(body);
      setResult(resp);
    } catch (err) {
      setResult(null);
      setError(err instanceof Error ? err.message : "Calculation failed.");
    } finally {
      setIsCalculating(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Tax calculator</h1>
        <p className="text-muted-foreground">
          Phase 3 pure-Python rule engine — KG + param JSON, no GPT. Submit income and
          reliefs to preview final tax with an ordered calculation trace.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Inputs</CardTitle>
          <CardDescription>
            Amounts are annual LKR. Personal relief applies to residents only. Param set
            switches Section 52 cap (pre vs post Act 02/2025).
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={(event) => void handleSubmit(event)}>
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="space-y-2">
                <Label htmlFor="assessment_year">Assessment year</Label>
                <Select
                  id="assessment_year"
                  value={form.assessment_year}
                  onChange={(event) =>
                    patch("assessment_year", event.target.value as FormState["assessment_year"])
                  }
                >
                  <option value="2024_25">2024/25</option>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="resident_status">Resident status</Label>
                <Select
                  id="resident_status"
                  value={form.resident_status}
                  onChange={(event) =>
                    patch("resident_status", event.target.value as FormState["resident_status"])
                  }
                >
                  <option value="resident">Resident</option>
                  <option value="non_resident">Non-resident</option>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="param_set">Param set</Label>
                <Select
                  id="param_set"
                  value={form.param_set}
                  onChange={(event) =>
                    patch("param_set", event.target.value as FormState["param_set"])
                  }
                >
                  <option value="current">Current (Sec 52 cap 1.8M)</option>
                  <option value="pre_amend_2025">Pre-amend 2025 (cap 1.2M)</option>
                </Select>
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              <MoneyField
                id="employment_income"
                label="Employment income"
                value={form.employment_income}
                onChange={(v) => patch("employment_income", v)}
              />
              <MoneyField
                id="business_income"
                label="Business income"
                value={form.business_income}
                onChange={(v) => patch("business_income", v)}
              />
              <MoneyField
                id="investment_income"
                label="Investment income"
                value={form.investment_income}
                onChange={(v) => patch("investment_income", v)}
              />
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <MoneyField
                id="qualifying_payments"
                label="Qualifying payments (Section 52)"
                value={form.qualifying_payments}
                onChange={(v) => patch("qualifying_payments", v)}
              />
              <MoneyField
                id="donations"
                label="Donations"
                value={form.donations}
                onChange={(v) => patch("donations", v)}
              />
            </div>

            <div className="flex flex-wrap gap-2">
              <Button type="submit" disabled={isCalculating}>
                {isCalculating ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Calculator className="h-4 w-4" />
                )}
                Calculate
              </Button>
              <Button
                type="button"
                variant="outline"
                disabled={isCalculating}
                onClick={() => {
                  setForm(INITIAL);
                  setResult(null);
                  setError(null);
                }}
              >
                Reset (ex01)
              </Button>
            </div>

            {error ? <p className="text-sm text-destructive">{error}</p> : null}
          </form>
        </CardContent>
      </Card>

      {result ? (
        <>
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Result</CardTitle>
              <CardDescription>
                Final liability from the deterministic rule engine.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-3xl font-semibold tracking-tight">
                {formatLkr(result.final_tax_lkr)}
              </p>
              {result.calc_id ? (
                <div className="flex flex-wrap items-center gap-2">
                  <Button type="button" asChild>
                    <Link to={`/adaptive-tax/report/${result.calc_id}`}>
                      <FileText className="h-4 w-4" />
                      View report
                    </Link>
                  </Button>
                  <p className="text-xs text-muted-foreground">
                    Opens Phase 4 report with trace, evidence, and grounded narrative (
                    <code>{result.calc_id.slice(0, 8)}…</code>).
                  </p>
                </div>
              ) : null}
              <div className="flex flex-wrap gap-1.5">
                {result.rules_applied.map((rule) => (
                  <Chip key={rule}>{rule}</Chip>
                ))}
              </div>
              {result.rule_source_refs.length > 0 ? (
                <div className="space-y-1">
                  <p className="text-xs font-medium text-muted-foreground">
                    Rule source refs
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {result.rule_source_refs.map((ref) => (
                      <Chip key={`${ref.kind}:${ref.id}`}>
                        {`${ref.kind}:${ref.id}`}
                      </Chip>
                    ))}
                  </div>
                </div>
              ) : null}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Calculation trace</CardTitle>
              <CardDescription>
                Ordered steps with formulas, outputs, and concept / section anchors.
              </CardDescription>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <table className="w-full min-w-[720px] border-collapse text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="py-2 pr-3 font-medium">Step</th>
                    <th className="py-2 pr-3 font-medium">Formula</th>
                    <th className="py-2 pr-3 font-medium">Output</th>
                    <th className="py-2 pr-3 font-medium">Concepts / sections</th>
                    <th className="py-2 font-medium">Rule sources</th>
                  </tr>
                </thead>
                <tbody>
                  {result.calculation_trace.map((step) => (
                    <tr key={step.step_id} className="border-b align-top last:border-0">
                      <td className="py-3 pr-3">
                        <div className="font-medium">{step.step_id}</div>
                        <div className="text-xs text-muted-foreground">
                          {step.description}
                        </div>
                      </td>
                      <td className="py-3 pr-3">
                        <code className="whitespace-pre-wrap text-xs">{step.formula}</code>
                      </td>
                      <td className="py-3 pr-3 whitespace-nowrap font-medium">
                        {/^-?\d+(\.\d+)?$/.test(step.output)
                          ? formatLkr(step.output)
                          : step.output}
                      </td>
                      <td className="py-3 pr-3">
                        <div className="flex flex-wrap gap-1">
                          {step.concept_ids.map((id) => (
                            <Chip key={`c-${step.step_id}-${id}`}>{id}</Chip>
                          ))}
                          {step.section_uids.map((uid) => (
                            <Chip key={`s-${step.step_id}-${uid}`}>
                              {uid.split("::").slice(-1)[0] || uid}
                            </Chip>
                          ))}
                        </div>
                      </td>
                      <td className="py-3">
                        <div className="flex flex-wrap gap-1">
                          {step.rule_source_ids.map((id) => (
                            <Chip key={`r-${step.step_id}-${id}`}>{id}</Chip>
                          ))}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        </>
      ) : null}
    </div>
  );
}
