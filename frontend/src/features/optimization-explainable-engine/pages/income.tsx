import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Info, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ActiveProfileBanner } from "@/components/auditor/active-profile-banner";
import { useActiveAuditorProfile } from "@/hooks/use-active-auditor-profile";
import { useOeSnapshotPersistence } from "@/hooks/use-oe-snapshot";
import { getProfileMonthlyTaxableIncome } from "@/features/personalized-recommendation/api/profiles";
import { profileToAuditorSummary } from "@/lib/profile-bridge/profile-summary";
import { profileToInterviewIncome } from "@/lib/profile-bridge/tax-return-to-oe-income";
import { mergeBreakdownIntoIncome } from "@/lib/profile-bridge/transaction-summary-to-oe-income";
import { normalizeDocumentTaxYear } from "@/lib/profile-bridge/tax-year-bridge";
import { useAuditorWorkspaceStore } from "@/store/auditor-workspace-store";

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
import { TerminalBenefitExplainDrawer } from "../terminal-benefit-explain";
import { TerminalBenefitSection } from "../terminal-benefit-section";
import {
  hasPublishedIncomeDocsSnapshot,
  importIncomeDocs,
  IncomeDocsCategoryPanel,
} from "../income-docs";
import {
  terminalBenefitsBlockContinue,
  terminalBenefitsTotalLkr,
} from "../terminal-benefits";
import type { IncomeFormSlice, InterestScheduleLine } from "../types";
import { getProfile } from "@/features/personalized-recommendation/api/profiles";
import { useQuery } from "@tanstack/react-query";

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
  const { session, patchIncome, replaceIncome, replaceSession } = useInterview();
  const { income } = session;
  const profileQuery = useActiveAuditorProfile();
  const activeProfileId = useAuditorWorkspaceStore((s) => s.activeProfileId);
  const profileSummary = useAuditorWorkspaceStore((s) => s.profileSummary);
  const { saveDraft, loadLatestDraft, saveState, draftState, canPersist, errorMessage } =
    useOeSnapshotPersistence(activeProfileId);
  const pendingTransactionBreakdown = useAuditorWorkspaceStore(
    (s) => s.pendingTransactionBreakdown,
  );
  const setPendingTransactionBreakdown = useAuditorWorkspaceStore(
    (s) => s.setPendingTransactionBreakdown,
  );
  const [profileLoadState, setProfileLoadState] = useState<"idle" | "loading" | "done">("idle");
  const [monthlyLoadState, setMonthlyLoadState] = useState<"idle" | "loading" | "done" | "error">("idle");
  const [monthlyLoadMessage, setMonthlyLoadMessage] = useState<string | null>(null);

  const employmentCard = incomeCatalogCard("employment");
  const businessCard = incomeCatalogCard("business");
  const investmentCard = incomeCatalogCard("investment");
  const otherCard = incomeCatalogCard("other_income");

  const [employmentOpen, setEmploymentOpen] = useState(true);
  const [businessOpen, setBusinessOpen] = useState(true);
  const [investmentOpen, setInvestmentOpen] = useState(true);
  const [otherOpen, setOtherOpen] = useState(false);
  const [terminalOpen, setTerminalOpen] = useState(false);
  const [terminalExplainOpen, setTerminalExplainOpen] = useState(false);
  const [explainField, setExplainFieldState] = useState<IncomeCatalogField | null>(null);

  function setExplainField(field: IncomeCatalogField | null): void {
    setTerminalExplainOpen(false);
    setExplainFieldState(field);
  }

  const publishedDocsQuery = useQuery({
    queryKey: ["profile", activeProfileId, "income-docs"],
    queryFn: () => getProfile(activeProfileId!),
    enabled: Boolean(activeProfileId),
    retry: false,
  });

  useEffect(() => {
    if (!activeProfileId || !publishedDocsQuery.data) return;
    const stored = publishedDocsQuery.data.tax_return_detail as
      | { incomeDocumentsByYear?: Parameters<typeof importIncomeDocs>[1] }
      | undefined;
    const published = stored?.incomeDocumentsByYear;
    if (hasPublishedIncomeDocsSnapshot(published)) {
      importIncomeDocs(activeProfileId, published);
    }
  }, [activeProfileId, publishedDocsQuery.data]);

  // Keep Name / TIN in sync with the auditor's active taxpayer (including switches).
  useEffect(() => {
    let name = "";
    let tin = "";

    if (!activeProfileId) {
      name = "";
      tin = "";
    } else if (profileQuery.data) {
      const summary = profileToAuditorSummary(profileQuery.data);
      name = summary.fullName || "";
      tin = summary.tin || "";
    } else if (profileSummary?.id === activeProfileId) {
      name = profileSummary.fullName || "";
      tin = profileSummary.tin || "";
    } else {
      return;
    }

    if (income.taxpayerName === name && income.tin === tin) return;
    patchIncome({ taxpayerName: name, tin });
  }, [
    activeProfileId,
    profileQuery.data,
    profileSummary,
    income.taxpayerName,
    income.tin,
    patchIncome,
  ]);

  const total = totalIncomeLkr(income);
  const employment = employmentIncomeLkr(income);
  const business = businessIncomeLkr(income);
  const investment = investmentIncomeLkr(income);
  const other = otherIncomeLkr(income);
  const schedule = interestScheduleTotals(income);
  const terminalAmount = income.hasTerminalBenefits
    ? terminalBenefitsTotalLkr(income.terminalBenefits)
    : 0;
  const terminalIncomplete = terminalBenefitsBlockContinue(
    income.hasTerminalBenefits,
    income.terminalBenefits,
    session.assessmentYear,
  );

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

  function loadFromTaxReturnProfile(): void {
    if (!profileQuery.data) return;
    setProfileLoadState("loading");
    const mapped = profileToInterviewIncome(profileQuery.data);
    replaceIncome(mapped.income, mapped.assessmentYear);
    setProfileLoadState("done");
  }

  function mergeTransactionTotals(): void {
    if (!pendingTransactionBreakdown?.length) return;
    const merged = mergeBreakdownIntoIncome(income, pendingTransactionBreakdown);
    replaceIncome(merged);
    setPendingTransactionBreakdown(null);
  }

  async function mergeSavedMonthlyTotals(): Promise<void> {
    if (!activeProfileId) return;
    setMonthlyLoadState("loading");
    setMonthlyLoadMessage(null);
    try {
      const taxYear = normalizeDocumentTaxYear(profileSummary?.taxYear);
      const response = await getProfileMonthlyTaxableIncome(activeProfileId, taxYear);
      const byClass = new Map<string, number>();
      for (const line of response.lines) {
        const amount = Number(line.taxable_amount_lkr);
        if (!Number.isFinite(amount) || amount <= 0) continue;
        byClass.set(line.class_key, (byClass.get(line.class_key) ?? 0) + amount);
      }
      const breakdown = [...byClass.entries()].map(([classKey, amount]) => ({
        classKey,
        amount,
      }));
      if (!breakdown.length) {
        setMonthlyLoadState("error");
        setMonthlyLoadMessage(
          taxYear
            ? `No saved taxable credits for tax year ${taxYear}. Classify documents first.`
            : "No saved taxable credits for this profile. Classify documents first.",
        );
        return;
      }
      const merged = mergeBreakdownIntoIncome(income, breakdown);
      replaceIncome(merged);
      setMonthlyLoadState("done");
      setMonthlyLoadMessage(`Merged ${breakdown.length} income bucket(s) from saved bank data.`);
    } catch {
      setMonthlyLoadState("error");
      setMonthlyLoadMessage("Could not load monthly bank totals.");
    }
  }

  async function handleLoadSavedDraft(): Promise<void> {
    const loaded = await loadLatestDraft(session.assessmentYear);
    if (loaded) replaceSession(loaded);
  }

  return (
    <div className="space-y-6">
      <ActiveProfileBanner moduleLabel="Optimization income" />

      {canPersist ? (
        <div className="flex flex-wrap items-center gap-2 rounded-md border bg-muted/30 p-3">
          <p className="flex-1 text-sm text-muted-foreground">
            Save or reload the interview draft (income + reliefs) for the locked taxpayer profile.
          </p>
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={draftState === "loading"}
            onClick={() => void handleLoadSavedDraft()}
          >
            {draftState === "loading" ? (
              <>
                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" aria-hidden />
                Loading…
              </>
            ) : (
              "Load saved draft"
            )}
          </Button>
          <Button
            type="button"
            size="sm"
            variant="secondary"
            disabled={saveState === "loading"}
            onClick={() => void saveDraft(session)}
          >
            {saveState === "loading" ? (
              <>
                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" aria-hidden />
                Saving…
              </>
            ) : saveState === "done" ? (
              "Draft saved"
            ) : (
              "Save draft"
            )}
          </Button>
        </div>
      ) : null}
      {errorMessage ? <p className="text-sm text-destructive">{errorMessage}</p> : null}

      <div className="flex flex-wrap items-center gap-2 rounded-md border bg-muted/30 p-3">
        <p className="flex-1 text-sm text-muted-foreground">
          Pre-fill user-side income from the selected taxpayer&apos;s Tax Return Profile
          (employment, FDs, dividends, business, rents).
        </p>
        <Button
          type="button"
          size="sm"
          variant="secondary"
          disabled={!profileQuery.data || profileQuery.isLoading || profileLoadState === "loading"}
          onClick={loadFromTaxReturnProfile}
        >
          {profileLoadState === "loading" ? (
            <>
              <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" aria-hidden />
              Loading…
            </>
          ) : (
            "Load from Tax Return Profile"
          )}
        </Button>
        <Button
          type="button"
          size="sm"
          variant="secondary"
          disabled={!activeProfileId || monthlyLoadState === "loading"}
          onClick={() => void mergeSavedMonthlyTotals()}
        >
          {monthlyLoadState === "loading" ? (
            <>
              <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" aria-hidden />
              Loading…
            </>
          ) : (
            "Merge saved monthly bank totals"
          )}
        </Button>
      </div>
      {monthlyLoadMessage ? (
        <p
          className={
            monthlyLoadState === "error"
              ? "text-sm text-destructive"
              : "text-sm text-muted-foreground"
          }
        >
          {monthlyLoadMessage}
        </p>
      ) : null}

      {pendingTransactionBreakdown && pendingTransactionBreakdown.length > 0 ? (
        <div className="flex flex-wrap items-center gap-2 rounded-md border border-primary/30 bg-primary/5 p-3">
          <p className="flex-1 text-sm">
            Transaction classification totals ready ({pendingTransactionBreakdown.length}{" "}
            bucket{pendingTransactionBreakdown.length === 1 ? "" : "s"}).
          </p>
          <Button type="button" size="sm" onClick={mergeTransactionTotals}>
            Merge transaction totals
          </Button>
        </div>
      ) : null}

      <div className="space-y-1">
        <h2 className="text-lg font-semibold">Income</h2>
        <p className="text-sm text-muted-foreground">
          Name and TIN sync from the active taxpayer profile when one is selected.
          Catalog cards cover Sections 5–8. Interest rows follow the WHT schedule —
          withheld tax becomes a credit on Result, not a reduction of assessable income.
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
            apitAlreadyPaid={income.apitAlreadyPaid ?? "0"}
            onApitChange={(v) => patchIncome({ apitAlreadyPaid: v })}
            open={employmentOpen}
            onToggle={() => setEmploymentOpen((v) => !v)}
            actVersionLabel={INCOME_CATALOG_BADGE}
            onExplainField={setExplainField}
          />
          <IncomeDocsCategoryPanel
            profileId={activeProfileId}
            assessmentYear={session.assessmentYear}
            categoryId="employment"
            mode="auditor"
            defaultOpen={false}
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
          <IncomeDocsCategoryPanel
            profileId={activeProfileId}
            assessmentYear={session.assessmentYear}
            categoryId="business"
            mode="auditor"
            defaultOpen={false}
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
          <IncomeDocsCategoryPanel
            profileId={activeProfileId}
            assessmentYear={session.assessmentYear}
            categoryId="investment"
            mode="auditor"
            defaultOpen={false}
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
          <IncomeDocsCategoryPanel
            profileId={activeProfileId}
            assessmentYear={session.assessmentYear}
            categoryId="other_income"
            mode="auditor"
            defaultOpen={false}
          />

          <TerminalBenefitSection
            open={terminalOpen}
            onToggle={() => setTerminalOpen((v) => !v)}
            actVersionLabel={INCOME_CATALOG_BADGE}
            onExplain={() => {
              setExplainField(null);
              setTerminalExplainOpen(true);
            }}
          />
          <IncomeDocsCategoryPanel
            profileId={activeProfileId}
            assessmentYear={session.assessmentYear}
            categoryId="terminal_benefits"
            mode="auditor"
            defaultOpen={false}
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
          {terminalAmount > 0
            ? ` · Terminal benefits ${formatLkr(terminalAmount)}`
            : ""}
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
          disabled={terminalIncomplete}
          onClick={() => void navigate("/optimization-explainable-engine/reliefs")}
        >
          Continue to reliefs
        </Button>
      </div>
      {terminalIncomplete ? (
        <p className="text-sm text-destructive" role="alert">
          Complete each retirement & terminal benefit (type, amount
          {session.assessmentYear === "2019_20" ? ", 2019/20 period" : ""}
          {income.terminalBenefits.some((row) => row.type === "loss_of_office_compensation")
            ? ", and the uniform-scheme confirmation for loss of office"
            : ""}
          ) before continuing.
        </p>
      ) : null}

      <FieldExplainDrawer
        field={explainField}
        actVersionLabel={INCOME_CATALOG_BADGE}
        open={explainField !== null}
        onClose={() => setExplainFieldState(null)}
      />
      <TerminalBenefitExplainDrawer
        assessmentYear={session.assessmentYear}
        actVersionLabel={INCOME_CATALOG_BADGE}
        open={terminalExplainOpen}
        onClose={() => setTerminalExplainOpen(false)}
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
