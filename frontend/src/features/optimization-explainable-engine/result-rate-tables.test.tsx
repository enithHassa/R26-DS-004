import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { CalculateResponse, SlabLine } from "./api";
import { ResultRateTables } from "./result-rate-tables";

function slab(patch: Partial<SlabLine>): SlabLine {
  return {
    band_index: 1,
    lower: 0,
    upper: 1_000_000,
    rate_percent: 6,
    slice: 500_000,
    tax: 30_000,
    band_label: "Ordinary first",
    quote: "",
    source_doc_id: "oee-act-02-2025",
    ...patch,
  };
}

const ordinary: CalculateResponse = {
  assessment_year: "2025_26",
  gross_income: 3_800_000,
  total_reliefs: 1_800_000,
  taxable_income: 2_000_000,
  tax_payable: 390_000,
  relief_lines: [],
  slab_lines: [slab({})],
  terminal_benefit_tax: 120_000,
  terminal_benefit_lines: [
    {
      type: "retiring_gratuity",
      amount: 12_000_000,
      tax: null,
      slab_lines: [],
    },
  ],
};

describe("ResultRateTables", () => {
  it("binds the ordinary table to slab_lines and the terminal table to terminal_benefit_lines", () => {
    render(<ResultRateTables result={ordinary} />);
    const ordinaryTable = screen.getByRole("heading", { name: "Rate bands (this YA)" })
      .parentElement as HTMLElement;
    expect(ordinaryTable).toHaveTextContent("Ordinary first");
    expect(ordinaryTable).toHaveTextContent("6%");
    expect(ordinaryTable).not.toHaveTextContent("Retiring gratuity");

    const terminalHeading = screen.getByRole("heading", { name: "Terminal-benefit tax" });
    const terminalSection = terminalHeading.parentElement as HTMLElement;
    expect(terminalSection).toHaveTextContent("Retiring gratuity");
    expect(terminalSection).toHaveTextContent("LKR 12,000,000");
    expect(terminalSection).toHaveTextContent("Total terminal benefits");
    expect(terminalSection).toHaveTextContent("Terminal-benefit tax");
    expect(terminalSection).toHaveTextContent("LKR 120,000");
    expect(terminalSection).not.toHaveTextContent("Ordinary first");
    expect(terminalSection).not.toHaveTextContent("Terminal 0%");
  });

  it("hides the terminal section when terminal_benefit_lines is empty", () => {
    render(
      <ResultRateTables
        result={{ ...ordinary, terminal_benefit_lines: [], terminal_benefit_tax: 0 }}
      />,
    );
    expect(screen.queryByRole("heading", { name: "Terminal-benefit tax" })).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Rate bands (this YA)" })).toBeInTheDocument();
  });
});
