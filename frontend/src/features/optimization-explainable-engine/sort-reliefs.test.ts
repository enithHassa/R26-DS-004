import { describe, expect, it } from "vitest";

import { sortReliefsForInterview } from "./sort-reliefs";
import type { ReliefEntry } from "./types";

function entry(
  compare_group_id: string,
  display_name: string,
  sort_order: number,
): ReliefEntry {
  return {
    entry_id: compare_group_id,
    compare_group_id,
    display_name,
    question_prompt: display_name,
    sort_order,
    input_kind: "amount",
    unit: "lkr",
    cap_amount: "0",
  };
}

describe("sortReliefsForInterview", () => {
  it("puts known reliefs first in the demo order", () => {
    const mixed = [
      entry("qp_samurdhi_shop", "Samurdhi shop contribution", 10),
      entry("donation_to_government_or_approved_fund", "Donation to government", 20),
      entry("solar_panel_relief", "Solar Panel Expenditure", 30),
      entry("rental_income_relief", "Rental income relief", 40),
      entry("personal_relief", "Personal Relief", 50),
      entry("donation_to_charitable_institution", "Donation to approved charitable", 60),
      entry("expenditure_cinema", "Cinema upgrade", 5),
    ];
    const ordered = sortReliefsForInterview(mixed).map((e) => e.compare_group_id);
    expect(ordered.slice(0, 5)).toEqual([
      "personal_relief",
      "solar_panel_relief",
      "rental_income_relief",
      "donation_to_charitable_institution",
      "donation_to_government_or_approved_fund",
    ]);
    expect(ordered.slice(5)).toEqual(["expenditure_cinema", "qp_samurdhi_shop"]);
  });
});
