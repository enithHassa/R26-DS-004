import { describe, expect, it } from "vitest";

import { formatLkr, formatMoneyInput, parseLkr, roundLkr } from "./format-lkr";

describe("format-lkr (2 decimal LKR)", () => {
  it("roundLkr keeps two decimal places", () => {
    expect(roundLkr(10.456)).toBe(10.46);
    expect(roundLkr(10.454)).toBe(10.45);
  });

  it("formatMoneyInput allows cents while typing", () => {
    expect(formatMoneyInput("1800000.5")).toBe("1,800,000.5");
    expect(formatMoneyInput("1800000.50")).toBe("1,800,000.50");
    expect(formatMoneyInput("1800000.")).toBe("1,800,000.");
    expect(formatMoneyInput("1800000.999")).toBe("1,800,000.99");
  });

  it("parseLkr reads comma-formatted decimals", () => {
    expect(parseLkr("1,800,000.50")).toBe(1_800_000.5);
    expect(parseLkr("40,000.25")).toBe(40_000.25);
  });

  it("formatLkr shows up to two decimals", () => {
    expect(formatLkr(1_800_000)).toBe("LKR 1,800,000");
    expect(formatLkr(1_800_000.5)).toBe("LKR 1,800,000.5");
    expect(formatLkr("40000.25")).toBe("LKR 40,000.25");
  });
});
