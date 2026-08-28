import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { TerminalBenefitLadder } from "./api";
import { TerminalBenefitExplainPanel } from "./terminal-benefit-explain";

function band(lower: number, upper: number | null, rate: number, label: string) {
  return { band_index: 1, lower, upper, rate_percent: rate, band_label: label };
}

function ladder(patch: Partial<TerminalBenefitLadder>): TerminalBenefitLadder {
  return {
    compare_group_id: "terminal_benefit_tax_rate",
    qualifying_income_types: ["commuted_pension", "retiring_gratuity"],
    bands: [],
    quote: "",
    ...patch,
  };
}

const act24 = "Inland Revenue Act No. 24 of 2017";
const act10 = "Inland Revenue (Amendment) Act No. 10 of 2021";

describe("TerminalBenefitExplainPanel", () => {
  it("shows a fallback when no ladders are returned", () => {
    render(<TerminalBenefitExplainPanel assessmentYear="2025_26" ladders={[]} />);
    expect(
      screen.getByText(
        "No promoted terminal-benefit rule is currently available for this assessment year.",
      ),
    ).toBeInTheDocument();
  });

  it("renders the exact API quote and does not invent one when missing", () => {
    render(
      <TerminalBenefitExplainPanel
        assessmentYear="2025_26"
        ladders={[
          ladder({
            act_name: act10,
            quote: "EXACT-QUOTE-FROM-EXTRACTION",
            period_from: "2025-04-01",
            period_to: "2026-03-31",
          }),
        ]}
      />,
    );
    expect(screen.getByText(/EXACT-QUOTE-FROM-EXTRACTION/)).toBeInTheDocument();

    render(
      <TerminalBenefitExplainPanel
        assessmentYear="2025_26"
        ladders={[ladder({ act_name: act10, quote: "" })]}
      />,
    );
    expect(screen.getByText("Act quotation is not currently available.")).toBeInTheDocument();
    expect(screen.queryByText(/Qualifying terminal benefits —/)).not.toBeInTheDocument();
  });

  it("resolves 2018/19 from Act 24 with both employment-period conditions", () => {
    render(
      <TerminalBenefitExplainPanel
        assessmentYear="2018_19"
        ladders={[
          ladder({
            act_name: act24,
            employment_period_condition: "upto_20_years",
            period_from: "2018-04-01",
            period_to: "2019-03-31",
            quote: "Not exceeding Rs. 2,000,000 | 0%",
            bands: [band(0, 2_000_000, 0, "Not exceeding 2,000,000")],
          }),
          ladder({
            act_name: act24,
            employment_period_condition: "over_20_years",
            period_from: "2018-04-01",
            period_to: "2019-03-31",
            quote: "Not exceeding Rs. 5,000,000 | 0%",
            bands: [band(0, 5_000_000, 0, "Not exceeding 5,000,000")],
          }),
        ]}
      />,
    );
    expect(screen.getByText("Terminal-benefit rule for YA 2018/19")).toBeInTheDocument();
    expect(screen.getAllByText(act24).length).toBeGreaterThan(0);
    expect(screen.getByText("20 years or less")).toBeInTheDocument();
    expect(screen.getByText("More than 20 years")).toBeInTheDocument();
    expect(screen.queryByText(act10)).not.toBeInTheDocument();
    expect(
      screen.queryByText("Terminal-benefit rates changed during this assessment year."),
    ).not.toBeInTheDocument();
  });

  it("shows two 2019/20 periods from API dates and never a blended ladder heading", () => {
    render(
      <TerminalBenefitExplainPanel
        assessmentYear="2019_20"
        ladders={[
          ladder({
            act_name: act24,
            employment_period_condition: "upto_20_years",
            period_from: "2019-04-01",
            period_to: "2019-12-31",
            quote: "pre-2020 quote",
            bands: [band(0, 2_000_000, 0, "Pre 0%")],
          }),
          ladder({
            act_name: act10,
            employment_period_condition: "not_applicable",
            period_from: "2020-01-01",
            period_to: "2020-03-31",
            quote: "from-2020 quote",
            bands: [band(0, 10_000_000, 0, "Post 0%"), band(10_000_000, 20_000_000, 6, "Post 6%")],
          }),
        ]}
      />,
    );
    expect(
      screen.getByText("Terminal-benefit rates changed during this assessment year."),
    ).toBeInTheDocument();
    expect(screen.getAllByText("1 April 2019 – 31 December 2019").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("1 January 2020 – 31 March 2020").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(act24)).toBeInTheDocument();
    expect(screen.getByText(act10)).toBeInTheDocument();
    expect(screen.getByText(/pre-2020 quote/)).toBeInTheDocument();
    expect(screen.getByText(/from-2020 quote/)).toBeInTheDocument();
    expect(screen.getByText(/Pre 0%/)).toBeInTheDocument();
    expect(screen.getByText(/Post 0%/)).toBeInTheDocument();
    expect(screen.queryByText(/blended/i)).not.toBeInTheDocument();
  });

  it("renders 2020/21 Act 10 names and bands from the payload", () => {
    render(
      <TerminalBenefitExplainPanel
        assessmentYear="2020_21"
        ladders={[
          ladder({
            act_name: act10,
            period_from: "2020-04-01",
            period_to: "2021-03-31",
            quote: "act-10-2020-21-quote",
            bands: [
              band(0, 10_000_000, 0, "First"),
              band(10_000_000, 20_000_000, 6, "Second"),
              band(20_000_000, null, 12, "Third"),
            ],
          }),
        ]}
      />,
    );
    expect(screen.getByText("Terminal-benefit rule for YA 2020/21")).toBeInTheDocument();
    expect(screen.getByText(act10)).toBeInTheDocument();
    expect(screen.getByText(/act-10-2020-21-quote/)).toBeInTheDocument();
    expect(screen.getByText(/6%/)).toBeInTheDocument();
    expect(screen.getByText(/12%/)).toBeInTheDocument();
    expect(screen.queryByText("0/6/12")).not.toBeInTheDocument();
  });

  it("renders 2025/26 from the year payload without a React year-to-rate map", () => {
    render(
      <TerminalBenefitExplainPanel
        assessmentYear="2025_26"
        ladders={[
          ladder({
            act_name: act10,
            period_from: "2025-04-01",
            period_to: "2026-03-31",
            quote: "year-view-quote-2025",
            bands: [band(0, 10_000_000, 0, "Zero band"), band(10_000_000, 20_000_000, 6, "Six band")],
          }),
        ]}
      />,
    );
    expect(screen.getByText("Terminal-benefit rule for YA 2025/26")).toBeInTheDocument();
    expect(screen.getByText(act10)).toBeInTheDocument();
    expect(screen.getByText(/year-view-quote-2025/)).toBeInTheDocument();
    expect(screen.getByText(/Zero band/)).toBeInTheDocument();
    expect(screen.queryByText("0/6/12")).not.toBeInTheDocument();
  });
});
