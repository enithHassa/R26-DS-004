import { describe, expect, it } from "vitest";

import { buildCalculateRequest } from "./build-calculate-request";
import { hydrateTerminalBenefits, newTerminalBenefitRow } from "./terminal-benefits";
import { createDefaultSession, type TerminalBenefitRow } from "./types";

function row(patch: Partial<TerminalBenefitRow>): TerminalBenefitRow {
  return { ...newTerminalBenefitRow(), id: patch.id ?? "tb-1", ...patch };
}

describe("buildCalculateRequest terminal_benefits", () => {
  it("omits terminal fields when the taxpayer answers No", () => {
    const session = createDefaultSession();
    session.income.hasTerminalBenefits = false;
    session.income.terminalBenefits = [
      row({ type: "retiring_gratuity", amount: "12000000" }),
    ];
    const request = buildCalculateRequest(session);
    expect(request.income.terminal_benefits).toBeUndefined();
    expect(request.income.terminal_benefit_amount).toBeUndefined();
    expect(request.income.terminal_benefit_type).toBeUndefined();
  });

  it("sends two complete rows with only fields relevant to 2025/26", () => {
    const session = createDefaultSession();
    session.assessmentYear = "2025_26";
    session.income.hasTerminalBenefits = true;
    session.income.terminalBenefits = [
      row({
        id: "a",
        type: "retiring_gratuity",
        amount: "12000000",
        employmentPeriodOver20Years: true,
        terminalBenefitPeriod: "pre_2020",
      }),
      row({
        id: "b",
        type: "commuted_pension",
        amount: "1000000",
        lossOfOfficeSchemeApproved: true,
      }),
    ];
    const request = buildCalculateRequest(session);
    expect(request.income.terminal_benefits).toEqual([
      { type: "retiring_gratuity", amount: 12_000_000 },
      { type: "commuted_pension", amount: 1_000_000 },
    ]);
  });

  it("includes 2019/20 period, >20 years, and loss-of-office scheme only when relevant", () => {
    const session = createDefaultSession();
    session.assessmentYear = "2019_20";
    session.income.hasTerminalBenefits = true;
    session.income.terminalBenefits = [
      row({
        id: "a",
        type: "retiring_gratuity",
        amount: "2500000",
        terminalBenefitPeriod: "pre_2020",
        employmentPeriodOver20Years: true,
      }),
      row({
        id: "b",
        type: "loss_of_office_compensation",
        amount: "3000000",
        terminalBenefitPeriod: "from_2020_01_01",
        lossOfOfficeSchemeApproved: true,
        employmentPeriodOver20Years: true,
      }),
    ];
    const request = buildCalculateRequest(session);
    expect(request.income.terminal_benefits).toEqual([
      {
        type: "retiring_gratuity",
        amount: 2_500_000,
        terminal_benefit_period: "pre_2020",
        employment_period_over_20_years: true,
      },
      {
        type: "loss_of_office_compensation",
        amount: 3_000_000,
        terminal_benefit_period: "from_2020_01_01",
        loss_of_office_scheme_approved: true,
      },
    ]);
  });

  it("hydrates a legacy scalar session into one row", () => {
    const hydrated = hydrateTerminalBenefits({
      terminalBenefitType: "retiring_gratuity",
      terminalBenefitAmount: "12000000",
      employmentPeriodOver20Years: true,
      lossOfOfficeSchemeApproved: false,
      terminalBenefitPeriod: "from_2020_01_01",
    });
    expect(hydrated.hasTerminalBenefits).toBe(true);
    expect(hydrated.terminalBenefits).toHaveLength(1);
    expect(hydrated.terminalBenefits[0]?.type).toBe("retiring_gratuity");
    expect(hydrated.terminalBenefits[0]?.amount).toBe("12000000");
  });
});
