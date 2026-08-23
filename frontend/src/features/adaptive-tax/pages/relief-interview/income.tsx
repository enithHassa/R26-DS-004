import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";

import {
  getFilingCatalog,
  type FilingCatalogCard,
  type FilingCatalogField,
} from "../../api";
import { CalculatorGroupHead } from "../../components/catalog-card-shell";
import { FieldExplainDrawer } from "../../components/field-explain";
import {
  BusinessIncomeSection,
  EmploymentIncomeSection,
  InvestmentIncomeSection,
  OtherIncomeSection,
  parseLkr,
  type IncomeFormSlice,
} from "./income-cards";
import { useReliefInterview } from "./session";
import {
  catalogYaForInterview,
  isFilingCatalogYa,
  yaDisplay,
  type FilingCatalogYa,
} from "./types";

function seedAmounts(
  card: FilingCatalogCard | null,
  prev: Record<string, string>,
): Record<string, string> {
  const next: Record<string, string> = {};
  for (const field of card?.fields ?? []) {
    const id = field.component_id;
    const prevVal = prev[id];
    if (id === "inv_interest") {
      // Default Interest to 2,000,000 unless the user already entered another amount.
      next[id] =
        prevVal !== undefined && prevVal !== "" && prevVal !== "0"
          ? prevVal
          : "2000000";
    } else {
      next[id] = prevVal ?? "0";
    }
  }
  return next;
}

export function ReliefInterviewIncomePage() {
  const navigate = useNavigate();
  const { session, patchIncome } = useReliefInterview();
  const { assessmentYear, income } = session;

  const [employmentOpen, setEmploymentOpen] = useState(true);
  const [businessOpen, setBusinessOpen] = useState(true);
  const [investmentOpen, setInvestmentOpen] = useState(false);
  const [otherOpen, setOtherOpen] = useState(false);

  const [employmentCard, setEmploymentCard] = useState<FilingCatalogCard | null>(
    null,
  );
  const [businessCard, setBusinessCard] = useState<FilingCatalogCard | null>(null);
  const [investmentCard, setInvestmentCard] = useState<FilingCatalogCard | null>(
    null,
  );
  const [otherCard, setOtherCard] = useState<FilingCatalogCard | null>(null);

  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [actVersionLabel, setActVersionLabel] = useState<string | null>(null);
  const [catalogYaUsed, setCatalogYaUsed] = useState<FilingCatalogYa>("2024_25");
  const [explainField, setExplainField] = useState<FilingCatalogField | null>(
    null,
  );

  const limitedVerification = !isFilingCatalogYa(assessmentYear);

  useEffect(() => {
    let cancelled = false;
    const catalogYa = catalogYaForInterview(assessmentYear);
    setCatalogLoading(true);
    setCatalogYaUsed(catalogYa);

    void getFilingCatalog(catalogYa)
      .then((catalog) => {
        if (cancelled) return;
        setCatalogError(null);
        setActVersionLabel(catalog.act_version_label ?? null);
        const empCard = catalog.cards.find((c) => c.card_id === "employment") ?? null;
        const bizCard = catalog.cards.find((c) => c.card_id === "business") ?? null;
        const invCard = catalog.cards.find((c) => c.card_id === "investment") ?? null;
        const otherCat =
          catalog.cards.find((c) => c.card_id === "other_income") ?? null;
        setEmploymentCard(empCard);
        setBusinessCard(bizCard);
        setInvestmentCard(invCard);
        setOtherCard(otherCat);

        patchIncome((prev) => {
          const employmentAmounts = seedAmounts(empCard, prev.employmentAmounts);
          if (
            Object.values(employmentAmounts).every((v) => parseLkr(v) === 0) &&
            employmentAmounts.emp_salary !== undefined
          ) {
            employmentAmounts.emp_salary = "1600000";
            if (employmentAmounts.emp_bonus !== undefined) {
              employmentAmounts.emp_bonus = "200000";
            }
          }
          return {
            employmentAmounts,
            businessAmounts: seedAmounts(bizCard, prev.businessAmounts),
            investmentAmounts: seedAmounts(invCard, prev.investmentAmounts),
            otherAmounts: seedAmounts(otherCat, prev.otherAmounts),
          };
        });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setCatalogError(
          err instanceof Error ? err.message : "Failed to load filing catalog.",
        );
        patchIncome({
          employmentMode: "total",
          investmentMode: "total",
          otherMode: "total",
        });
      })
      .finally(() => {
        if (!cancelled) setCatalogLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [assessmentYear, patchIncome]);

  function patchForm<K extends keyof IncomeFormSlice>(
    key: K,
    value: IncomeFormSlice[K],
  ): void {
    patchIncome((prev) => ({ form: { ...prev.form, [key]: value } }));
  }

  function onContinue(): void {
    void navigate("/adaptive-tax/relief-interview/reliefs");
  }

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h2 className="text-lg font-semibold">Income</h2>
        <p className="text-sm text-muted-foreground">
          Same Employment / Business / Investment / Other Income cards as the
          Calculator (18 + 4 + 15 + 3 catalog fields). Relief questions come next.
        </p>
      </div>

      {limitedVerification ? (
        <div
          className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-950 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-100"
          role="status"
        >
          <p className="font-medium">Limited verification</p>
          <p className="text-xs opacity-90">
            YA {yaDisplay(assessmentYear)} is outside the filing-catalog enum
            (2024/25–2025/26). Field list is loaded from YA{" "}
            {yaDisplay(catalogYaUsed)} for structure only — not a verified pack for
            this interview year.
          </p>
        </div>
      ) : null}

      {catalogLoading ? (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          Loading filing catalog…
        </p>
      ) : null}

      {catalogError ? (
        <p className="text-xs text-amber-700 dark:text-amber-400">
          Catalog unavailable ({catalogError}). Using single-total income inputs.
        </p>
      ) : null}

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
            actVersionLabel={actVersionLabel}
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
            actVersionLabel={actVersionLabel}
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
            actVersionLabel={actVersionLabel}
            onExplainField={setExplainField}
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
            actVersionLabel={actVersionLabel}
            onExplainField={setExplainField}
          />
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          variant="outline"
          onClick={() => void navigate("/adaptive-tax/relief-interview")}
        >
          Back
        </Button>
        <Button type="button" onClick={onContinue} disabled={catalogLoading}>
          Continue to reliefs
        </Button>
      </div>

      <FieldExplainDrawer
        field={explainField}
        assessmentYear={catalogYaUsed}
        actVersionLabel={actVersionLabel}
        open={explainField !== null}
        onClose={() => setExplainField(null)}
      />
    </div>
  );
}
