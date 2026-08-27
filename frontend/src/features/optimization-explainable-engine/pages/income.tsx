import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Info } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import { CalculatorGroupHead } from "../catalog-card-shell";
import { FieldExplainDrawer } from "../field-explain";
import { formatLkr, formatMoneyInput, parseLkr } from "../format-lkr";
import {
  businessIncomeLkr,
  employmentIncomeLkr,
  interestScheduleTotals,
  investmentIncomeLkr,
  otherIncomeLkr,
  totalIncomeLkr,
} from "../income-aggregate";
import {
  BusinessIncomeSection,
  EmploymentIncomeSection,
  InvestmentIncomeSection,
  OtherIncomeSection,
} from "../income-cards";
import { INCOME_CATALOG_BADGE, incomeCatalogCard, type IncomeCatalogField } from "../income-catalog";
import { useInterview } from "../session";
import type { IncomeFormSlice, InterestScheduleLine } from "../types";

function newLine(): InterestScheduleLine {
  return {
    id: `wht-${Date.now()}`,
    label: "Bank interest",
    interest: "0",
    wht: "0",
  };
}

export function InterviewIncomePage() {
  const navigate = useNavigate();
  const { session, patchIncome } = useInterview();
  const { income } = session;

  const employmentCard = incomeCatalogCard("employment");
  const businessCard = incomeCatalogCard("business");
  const investmentCard = incomeCatalogCard("investment");
  const otherCard = incomeCatalogCard("other_income");

  const [employmentOpen, setEmploymentOpen] = useState(true);
  const [businessOpen, setBusinessOpen] = useState(true);
  const [investmentOpen, setInvestmentOpen] = useState(true);
  const [otherOpen, setOtherOpen] = useState(false);
  const [explainField, setExplainField] = useState<IncomeCatalogField | null>(null);

  const total = totalIncomeLkr(income);
  const employment = employmentIncomeLkr(income);
  const business = businessIncomeLkr(income);
  const investment = investmentIncomeLkr(income);
  const other = otherIncomeLkr(income);
  const schedule = interestScheduleTotals(income);

  function patchForm<K extends keyof IncomeFormSlice>(
    key: K,
    value: IncomeFormSlice[K],
  ): void {
    patchIncome((prev) => ({ form: { ...prev.form, [key]: value } }));
  }

  function setSchedule(next: InterestScheduleLine[]): void {
    const interest = next.reduce((sum, line) => sum + parseLkr(line.interest), 0);
    patchIncome((prev) => ({
      interestSchedule: next,
      investmentAmounts: {
        ...prev.investmentAmounts,
        inv_interest: String(interest),
      },
    }));
  }

  function patchLine(id: string, field: keyof InterestScheduleLine, raw: string): void {
    const value = field === "label" ? raw : formatMoneyInput(raw);
    setSchedule(
      (income.interestSchedule ?? []).map((line) =>
        line.id === id ? { ...line, [field]: value } : line,
      ),
    );
  }

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h2 className="text-lg font-semibold">Income</h2>
        <p className="text-sm text-muted-foreground">
          Name and TIN are for this session only. Catalog cards cover Sections 5–8.
          Interest rows follow the WHT schedule — withheld tax becomes a credit on Result,
          not a reduction of assessable income.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1">
          <Label htmlFor="oe-engine-name">Name</Label>
          <Input
            id="oe-engine-name"
            value={income.taxpayerName}
            onChange={(event) => patchIncome({ taxpayerName: event.target.value })}
            placeholder="Taxpayer name"
            autoComplete="name"
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="oe-engine-tin">TIN</Label>
          <Input
            id="oe-engine-tin"
            value={income.tin}
            onChange={(event) => patchIncome({ tin: event.target.value })}
            placeholder="Taxpayer identification number"
            autoComplete="off"
          />
        </div>
      </div>

      <div className="space-y-4">
        <CalculatorGroupHead
          title="Income heads"
          description="Catalog cards for Sections 5–8 — assessable income components."
        />
        <div className="space-y-3">
          <EmploymentIncomeSection
            card={employmentCard}
            mode={income.employmentMode}
            onModeChange={(mode) => patchIncome({ employmentMode: mode })}
            fields={employmentCard?.fields ?? []}
            amounts={income.employmentAmounts}
            onAmountChange={(id, v) =>
              patchIncome((prev) => ({
                employmentAmounts: { ...prev.employmentAmounts, [id]: v },
              }))
            }
            form={income.form}
            onPatch={patchForm}
            open={employmentOpen}
            onToggle={() => setEmploymentOpen((v) => !v)}
            actVersionLabel={INCOME_CATALOG_BADGE}
            onExplainField={setExplainField}
          />

          <BusinessIncomeSection
            card={businessCard}
            mode={income.businessMode}
            onModeChange={(mode) => patchIncome({ businessMode: mode })}
            fields={businessCard?.fields ?? []}
            amounts={income.businessAmounts}
            onAmountChange={(id, v) =>
              patchIncome((prev) => ({
                businessAmounts: { ...prev.businessAmounts, [id]: v },
              }))
            }
            form={income.form}
            onPatch={patchForm}
            open={businessOpen}
            onToggle={() => setBusinessOpen((v) => !v)}
            actVersionLabel={INCOME_CATALOG_BADGE}
            onExplainField={setExplainField}
          />

          <InvestmentIncomeSection
            card={investmentCard}
            mode={income.investmentMode}
            onModeChange={(mode) => patchIncome({ investmentMode: mode })}
            fields={investmentCard?.fields ?? []}
            amounts={income.investmentAmounts}
            onAmountChange={(id, v) =>
              patchIncome((prev) => ({
                investmentAmounts: { ...prev.investmentAmounts, [id]: v },
              }))
            }
            form={income.form}
            onPatch={patchForm}
            open={investmentOpen}
            onToggle={() => setInvestmentOpen((v) => !v)}
            actVersionLabel={INCOME_CATALOG_BADGE}
            onExplainField={setExplainField}
            scheduleInterestLkr={schedule.interest}
            interestSchedule={
              <InterestSchedule
                lines={income.interestSchedule ?? []}
                totals={schedule}
                explainField={
                  investmentCard?.fields.find((f) => f.component_id === "inv_interest") ??
                  null
                }
                onExplain={setExplainField}
                onAdd={() => setSchedule([...(income.interestSchedule ?? []), newLine()])}
                onPatchLine={patchLine}
                onRemove={(id) =>
                  setSchedule((income.interestSchedule ?? []).filter((row) => row.id !== id))
                }
              />
            }
          />

          <OtherIncomeSection
            card={otherCard}
            mode={income.otherMode}
            onModeChange={(mode) => patchIncome({ otherMode: mode })}
            fields={otherCard?.fields ?? []}
            amounts={income.otherAmounts}
            onAmountChange={(id, v) =>
              patchIncome((prev) => ({
                otherAmounts: { ...prev.otherAmounts, [id]: v },
              }))
            }
            customRows={income.otherCustomRows}
            onCustomRowsChange={(rows) => patchIncome({ otherCustomRows: rows })}
            form={income.form}
            onPatch={patchForm}
            open={otherOpen}
            onToggle={() => setOtherOpen((v) => !v)}
            actVersionLabel={INCOME_CATALOG_BADGE}
            onExplainField={setExplainField}
          />
        </div>
      </div>

      <div className="space-y-1">
        <p className="text-sm text-muted-foreground">
          Assessable income (before reliefs):{" "}
          <span className="font-medium text-foreground">{formatLkr(String(total))}</span>
        </p>
        <p className="text-xs text-muted-foreground">
          Employment {formatLkr(employment)} · Business {formatLkr(business)} · Investment{" "}
          {formatLkr(investment)} · Other {formatLkr(other)}
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          variant="outline"
          onClick={() => void navigate("/optimization-explainable-engine/acts")}
        >
          Back
        </Button>
        <Button
          type="button"
          onClick={() => void navigate("/optimization-explainable-engine/reliefs")}
        >
          Continue to reliefs
        </Button>
      </div>

      <FieldExplainDrawer
        field={explainField}
        actVersionLabel={INCOME_CATALOG_BADGE}
        open={explainField !== null}
        onClose={() => setExplainField(null)}
      />
    </div>
  );
}

function InterestSchedule({
  lines,
  totals,
  explainField,
  onExplain,
  onAdd,
  onPatchLine,
  onRemove,
}: {
  lines: InterestScheduleLine[];
  totals: { interest: number; wht: number };
  explainField: IncomeCatalogField | null;
  onExplain: (field: IncomeCatalogField) => void;
  onAdd: () => void;
  onPatchLine: (id: string, field: keyof InterestScheduleLine, raw: string) => void;
  onRemove: (id: string) => void;
}) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold">Interest schedule (WHT)</h3>
            {explainField ? (
              <button
                type="button"
                className="inline-flex items-center gap-0.5 text-[10px] text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
                onClick={() => onExplain(explainField)}
                aria-label="Explain interest"
              >
                <Info className="h-3 w-3" aria-hidden />
                Explain
              </button>
            ) : null}
          </div>
          <p className="text-[11px] text-muted-foreground">
            Sec 7(2)(a) · include — gross interest is assessable income. WHT deducted is a
            tax credit on Result, not a reduction of income.
          </p>
        </div>
        <Button type="button" size="sm" variant="outline" onClick={onAdd}>
          Add line
        </Button>
      </div>
      <div className="overflow-x-auto rounded-md border">
        <table className="w-full min-w-[28rem] text-left text-sm">
          <thead className="bg-muted/40 text-xs text-muted-foreground">
            <tr>
              <th className="px-3 py-2 font-medium">Source</th>
              <th className="px-3 py-2 font-medium">Gross interest</th>
              <th className="px-3 py-2 font-medium">WHT deducted</th>
              <th className="px-3 py-2 font-medium"> </th>
            </tr>
          </thead>
          <tbody>
            {lines.map((line) => (
              <tr key={line.id} className="border-t">
                <td className="px-3 py-2">
                  <Input
                    aria-label="Interest source"
                    value={line.label}
                    onChange={(event) => onPatchLine(line.id, "label", event.target.value)}
                  />
                </td>
                <td className="px-3 py-2">
                  <Input
                    inputMode="numeric"
                    aria-label="Gross interest"
                    value={formatMoneyInput(line.interest)}
                    onChange={(event) => onPatchLine(line.id, "interest", event.target.value)}
                  />
                </td>
                <td className="px-3 py-2">
                  <Input
                    inputMode="numeric"
                    aria-label="WHT deducted"
                    value={formatMoneyInput(line.wht)}
                    onChange={(event) => onPatchLine(line.id, "wht", event.target.value)}
                  />
                </td>
                <td className="px-3 py-2">
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    onClick={() => onRemove(line.id)}
                  >
                    Remove
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-muted-foreground">
        Interest {formatLkr(totals.interest)} · WHT credit {formatLkr(totals.wht)}
      </p>
    </div>
  );
}
