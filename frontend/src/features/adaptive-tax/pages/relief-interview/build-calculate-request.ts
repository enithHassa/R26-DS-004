/**
 * Build CalculateTaxRequest from Relief Interview session income + relief answers.
 */

import type { CalculateTaxRequest, FilingLine } from "../../api";
import { toMoneyWire } from "../../format-lkr";
import { parseLkr } from "./income-cards";
import {
  isExpenditureReliefAvailableForYa,
  isExpenditureReliefGroup,
} from "./expenditure-relief";
import { isBankMergerQpGroup } from "./bank-merger-qp";
import { isEntityCharityDonationGroup } from "./entity-charity-donation";
import type { ReliefAnswer } from "./catalog-types";
import type { ApprovedEntry } from "./catalog-types";
import type { FilingCatalogYa, ReliefInterviewIncomeState } from "./types";

function linesFromAmounts(
  mode: "components" | "total" | "net" | "breakdown",
  amounts: Record<string, string>,
  allowed?: Set<string>,
): FilingLine[] {
  if (mode === "total") return [];
  return Object.entries(amounts)
    .filter(([id, amount]) => {
      if (allowed && !allowed.has(id)) return false;
      return parseLkr(amount) > 0;
    })
    .map(([component_id, amount]) => ({
      component_id,
      amount: toMoneyWire(amount),
    }));
}

function otherFilingLines(income: ReliefInterviewIncomeState): FilingLine[] {
  if (income.otherMode !== "components") return [];
  const lines: FilingLine[] = [];
  const residual = parseLkr(income.otherAmounts.oth_residual ?? "0");
  if (residual > 0) {
    lines.push({
      component_id: "oth_residual",
      amount: toMoneyWire(income.otherAmounts.oth_residual ?? "0"),
    });
  }
  for (const row of income.otherCustomRows) {
    if (parseLkr(row.amount) <= 0) continue;
    lines.push({
      component_id: "oth_custom",
      amount: toMoneyWire(row.amount),
      label_override: row.label.trim() || undefined,
    });
  }
  const fwh = parseLkr(income.otherAmounts.oth_final_withholding ?? "0");
  if (fwh > 0) {
    lines.push({
      component_id: "oth_final_withholding",
      amount: toMoneyWire(income.otherAmounts.oth_final_withholding ?? "0"),
    });
  }
  return lines;
}

function businessLines(income: ReliefInterviewIncomeState): FilingLine[] {
  if (income.businessMode === "net") {
    return linesFromAmounts("net", income.businessAmounts, new Set(["biz_net_profits"]));
  }
  return linesFromAmounts(
    "breakdown",
    income.businessAmounts,
    new Set(["biz_gross", "biz_deductions", "biz_capital_allowances"]),
  );
}

export function buildCalculateRequestFromSession(args: {
  assessmentYear: FilingCatalogYa;
  income: ReliefInterviewIncomeState;
  answers: ReliefAnswer[];
  entries: ApprovedEntry[];
}): CalculateTaxRequest {
  const { assessmentYear, income, answers, entries } = args;
  const form = income.form;
  const byId = new Map(entries.map((e) => [e.entry_id, e]));

  let solar = "0";
  let rent = "0";
  let senior = "0";
  let qualifyingPayments = 0;
  let donations = 0;
  /** Collapse filing_line answers that share an engine component_id (e.g. ¶1(b) funds). */
  const filingLineTotals = new Map<string, number>();

  for (const ans of answers) {
    if (ans.skipped) continue;
    if (isBankMergerQpGroup(ans.compare_group_id)) continue;
    if (isEntityCharityDonationGroup(ans.compare_group_id)) continue;
    const entry = byId.get(ans.entry_id);
    if (!entry?.engine_binding) continue;
    const binding = entry.engine_binding;
    const amount =
      ans.amount != null && parseLkr(ans.amount) > 0
        ? toMoneyWire(ans.amount)
        : "0";
    if (binding.kind === "solar_panel_relief") {
      if (ans.affirmed !== false && parseLkr(amount) > 0) solar = amount;
    } else if (binding.kind === "rent_relief") {
      if (ans.affirmed !== false && parseLkr(amount) > 0) rent = amount;
    } else if (binding.kind === "senior_citizen_interest_relief") {
      if (ans.affirmed === true && parseLkr(amount) > 0) senior = amount;
    } else if (binding.kind === "qualifying_payments") {
      if (ans.affirmed !== false && parseLkr(amount) > 0) {
        qualifyingPayments += parseLkr(amount);
      }
    } else if (binding.kind === "donations") {
      if (ans.affirmed !== false && parseLkr(amount) > 0) {
        donations += parseLkr(amount);
      }
    } else if (binding.kind === "filing_line" && binding.component_id) {
      if (ans.affirmed === false) continue;
      if (
        isExpenditureReliefGroup(ans.compare_group_id) &&
        !isExpenditureReliefAvailableForYa(assessmentYear)
      ) {
        continue;
      }
      const n = parseLkr(amount);
      if (n > 0) {
        filingLineTotals.set(
          binding.component_id,
          (filingLineTotals.get(binding.component_id) ?? 0) + n,
        );
      }
    }
    // binding.kind === "none": intentional no-op (informational / out-of-scope rows)
  }

  const extraLines: FilingLine[] = [...filingLineTotals.entries()].map(
    ([component_id, total]) => ({
      component_id,
      amount: toMoneyWire(String(total)),
    }),
  );

  const bizLines = businessLines(income);
  const useBizCatalog = bizLines.length > 0;

  const filingLines: FilingLine[] = [
    ...linesFromAmounts(income.employmentMode, income.employmentAmounts),
    ...bizLines,
    ...linesFromAmounts(income.investmentMode, income.investmentAmounts),
    ...otherFilingLines(income),
    ...extraLines,
  ];

  return {
    assessment_year: assessmentYear,
    resident_status: "resident",
    param_set: "current",
    employment_income:
      income.employmentMode === "components" ? "0" : toMoneyWire(form.employment_income),
    employment_final_withholding:
      income.employmentMode === "components"
        ? "0"
        : toMoneyWire(form.employment_final_withholding),
    business_income:
      useBizCatalog || income.businessMode === "breakdown"
        ? "0"
        : toMoneyWire(form.business_income),
    business_gross:
      useBizCatalog || income.businessMode === "net" ? "0" : toMoneyWire(form.business_gross),
    business_deductions:
      useBizCatalog || income.businessMode === "net"
        ? "0"
        : toMoneyWire(form.business_deductions),
    capital_allowances:
      useBizCatalog || income.businessMode === "net"
        ? "0"
        : toMoneyWire(form.capital_allowances),
    investment_income:
      income.investmentMode === "components" ? "0" : toMoneyWire(form.investment_income),
    investment_final_withholding:
      income.investmentMode === "components"
        ? "0"
        : toMoneyWire(form.investment_final_withholding),
    other_income: income.otherMode === "components" ? "0" : toMoneyWire(form.other_income),
    other_final_withholding:
      income.otherMode === "components" ? "0" : toMoneyWire(form.other_final_withholding),
    qualifying_payments: toMoneyWire(String(qualifyingPayments)),
    donations: toMoneyWire(String(donations)),
    apit_already_paid: "0",
    solar_panel_relief: solar,
    rent_relief: rent,
    senior_citizen_interest_relief: senior,
    filing_lines: filingLines,
  };
}

/** Simplified income totals for the Phase 8 catalog rate engine. */
export function buildCatalogEngineRequestFromSession(args: {
  assessmentYear: string;
  income: ReliefInterviewIncomeState;
  answers: ReliefAnswer[];
  entries: ApprovedEntry[];
}): {
  assessment_year: string;
  employment_income: string;
  business_income: string;
  investment_income: string;
  other_income: string;
  solar_panel_relief: string;
  rent_relief: string;
  senior_citizen_interest_relief: string;
  claims: Array<{ compare_group_id: string; amount: string }>;
} {
  const { assessmentYear, income, answers, entries } = args;
  const form = income.form;
  const byId = new Map(entries.map((e) => [e.entry_id, e]));

  const sumAmounts = (amounts: Record<string, string>) =>
    Object.values(amounts).reduce((acc, v) => acc + parseLkr(v), 0);

  const employment =
    income.employmentMode === "components"
      ? sumAmounts(income.employmentAmounts)
      : parseLkr(form.employment_income);

  let business = 0;
  if (income.businessMode === "net") {
    business = parseLkr(income.businessAmounts.biz_net_profits ?? form.business_income);
  } else if (income.businessMode === "breakdown") {
    business = Math.max(
      0,
      parseLkr(income.businessAmounts.biz_gross ?? "0") -
        parseLkr(income.businessAmounts.biz_deductions ?? "0") -
        parseLkr(income.businessAmounts.biz_capital_allowances ?? "0"),
    );
  } else {
    business = parseLkr(form.business_income);
  }

  const investment =
    income.investmentMode === "components"
      ? sumAmounts(income.investmentAmounts)
      : parseLkr(form.investment_income);

  let other = 0;
  if (income.otherMode === "components") {
    other += parseLkr(income.otherAmounts.oth_residual ?? "0");
    for (const row of income.otherCustomRows) other += parseLkr(row.amount);
  } else {
    other = parseLkr(form.other_income);
  }

  let solar = 0;
  let rent = 0;
  let senior = 0;
  const claims: Array<{ compare_group_id: string; amount: string }> = [];
  for (const ans of answers) {
    if (ans.skipped) continue;
    if (isBankMergerQpGroup(ans.compare_group_id)) continue;
    if (isEntityCharityDonationGroup(ans.compare_group_id)) continue;
    if (ans.affirmed === false) continue;
    const amount = ans.amount != null && parseLkr(ans.amount) > 0 ? parseLkr(ans.amount) : 0;
    const entry = byId.get(ans.entry_id);
    if (entry?.engine_binding?.kind === "solar_panel_relief") {
      solar = amount;
    } else if (entry?.engine_binding?.kind === "rent_relief") {
      rent = amount;
    } else if (entry?.engine_binding?.kind === "senior_citizen_interest_relief") {
      if (ans.affirmed === true) senior = amount;
    }
    if (amount > 0 || entry?.auto_applied) {
      claims.push({
        compare_group_id: ans.compare_group_id,
        amount: toMoneyWire(String(amount)),
      });
    }
  }

  return {
    assessment_year: assessmentYear,
    employment_income: toMoneyWire(String(employment)),
    business_income: toMoneyWire(String(business)),
    investment_income: toMoneyWire(String(investment)),
    other_income: toMoneyWire(String(other)),
    solar_panel_relief: toMoneyWire(String(solar)),
    rent_relief: toMoneyWire(String(rent)),
    senior_citizen_interest_relief: toMoneyWire(String(senior)),
    claims,
  };
}
