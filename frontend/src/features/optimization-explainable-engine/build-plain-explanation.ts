import type { CalculateResponse, ReliefLine, SlabLine } from "./api";
import { formatLkr, yaDisplay } from "./format-lkr";

export type PlainExplanationBlock = {
  heading: string;
  lines: string[];
};

export type PlainExplanation = {
  headline: string;
  summary: string;
  blocks: PlainExplanationBlock[];
};

function appliedReliefs(lines: ReliefLine[]): ReliefLine[] {
  return lines.filter((line) => line.applied > 0);
}

function usedBands(lines: SlabLine[]): SlabLine[] {
  return lines.filter((line) => line.slice > 0);
}

function taxedBands(lines: SlabLine[]): SlabLine[] {
  return lines.filter((line) => line.tax > 0);
}

function reliefKidLine(line: ReliefLine): string {
  const name = line.display_name;
  const amount = formatLkr(line.applied);
  const group = line.compare_group_id ?? "";

  if (group === "personal_relief") {
    return `Personal relief — a basic amount every taxpayer can keep tax-free. We took off ${amount}.`;
  }
  if (group === "solar_panel_relief") {
    return `Solar panel relief — money back for installing solar panels. You claimed some of this, so we took off ${amount}.`;
  }
  if (group.includes("provincial") || name.toLowerCase().includes("provincial council")) {
    return `Provincial Council donation — you gave to a Provincial Council fund, so ${amount} comes off your income.`;
  }
  if (name.toLowerCase().includes("digital") || name.toLowerCase().includes("productivity")) {
    return `Digital equipment relief — spending on approved digital tools can reduce tax. We took off ${amount}.`;
  }
  if (group === "senior_citizen_interest_relief") {
    return `Senior citizen interest relief — extra help on bank interest for senior citizens. We took off ${amount}.`;
  }
  if (group === "foreign_currency_income_relief") {
    return `Foreign currency income relief — some earnings in foreign currency can be sheltered. We took off ${amount}.`;
  }
  if (group === "rental_income_relief" || group === "rent_relief") {
    return `Rent relief — help linked to rental income. We took off ${amount}.`;
  }

  if (line.claim > 0 && line.claim !== line.applied) {
    return `${name} — you asked for ${formatLkr(line.claim)}, and the rules allowed ${amount} this time.`;
  }
  return `${name} — the rules let you take ${amount} off your income.`;
}

function simpleBandStep(band: SlabLine, stepNumber: number): string {
  const slice = formatLkr(band.slice);
  const tax = formatLkr(band.tax);
  const rate = band.rate_percent;
  const label = band.band_label?.trim();

  if (label) {
    return `Step ${stepNumber}: ${slice} falls in “${label}”. Tax at ${rate}% on that slice is ${tax}.`;
  }
  return `Step ${stepNumber}: ${slice} is taxed at ${rate}%, which is ${tax}.`;
}

export function buildPlainExplanation(result: CalculateResponse): PlainExplanation {
  const ya = yaDisplay(result.assessment_year);
  const reliefs = appliedReliefs(result.relief_lines ?? []);
  const bands = usedBands(result.slab_lines ?? []);
  const payingBands = taxedBands(result.slab_lines ?? []);

  const blocks: PlainExplanationBlock[] = [];

  blocks.push({
    heading: "What year is this?",
    lines: [
      `This is for the tax year ${ya} (year of assessment ${ya}).`,
      "Think of it like a report card for one full year of earnings — we add up what you made, then see how much tax is due.",
    ],
  });

  blocks.push({
    heading: "How much did you make?",
    lines: [
      `You told us you earned ${formatLkr(result.gross_income)} in total.`,
      "That is the starting number — all the income we use before any tax breaks.",
    ],
  });

  if (reliefs.length > 0) {
    blocks.push({
      heading: "What came off your income?",
      lines: [
        `Tax rules allow certain “reliefs” — they work like discounts. Together they remove ${formatLkr(result.total_reliefs)} from what would otherwise be taxed.`,
        "Here is each one that applied to you:",
        ...reliefs.map((line) => reliefKidLine(line)),
        `Add those up: ${formatLkr(result.gross_income)} minus ${formatLkr(result.total_reliefs)} leaves ${formatLkr(result.taxable_income)}.`,
      ],
    });
  } else {
    blocks.push({
      heading: "What came off your income?",
      lines: [
        "You did not use any reliefs in this scenario.",
        `So the full ${formatLkr(result.gross_income)} is still there to be taxed.`,
      ],
    });
  }

  blocks.push({
    heading: "What is left to tax?",
    lines: [
      `${formatLkr(result.taxable_income)} is the part of your income that tax is calculated on.`,
      "Only this leftover amount goes through the tax rate steps below — not the whole original income.",
    ],
  });

  if (payingBands.length > 0) {
    const bandLines = payingBands.map((band, index) => simpleBandStep(band, index + 1));
    const parts = payingBands.map((band) => formatLkr(band.tax));
    const ordinaryTax = payingBands.reduce((sum, band) => sum + band.tax, 0);
    blocks.push({
      heading: "How the tax is added up",
      lines: [
        "Tax is not one flat percentage on everything. It works like stairs — a small slice at a low rate, then the next slice at a higher rate, and so on.",
        ...bandLines,
        (result.terminal_benefit_tax ?? 0) > 0
          ? `Ordinary income tax on those steps is ${formatLkr(ordinaryTax)}.`
          : `Add those steps: ${parts.join(" + ")} = ${formatLkr(result.tax_payable)}.`,
      ],
    });
  } else if (bands.length > 0) {
    blocks.push({
      heading: "How the tax is added up",
      lines: [
        "Your income fell into the rate bands for this year, but the tax due worked out to zero.",
        `Tax payable: ${formatLkr(result.tax_payable)}.`,
      ],
    });
  } else {
    blocks.push({
      heading: "How the tax is added up",
      lines: [`Your tax payable is ${formatLkr(result.tax_payable)}.`],
    });
  }

  const terminalBands = usedBands(result.terminal_benefit_slab_lines ?? []);
  if (terminalBands.length > 0) {
    blocks.push({
      heading: "Terminal-benefit tax",
      lines: [
        "A qualifying terminal benefit is taxed on its own ladder, separate from ordinary salary.",
        ...terminalBands.map((band, index) => simpleBandStep(band, index + 1)),
        `That extra tax is ${formatLkr(result.terminal_benefit_tax ?? 0)}, included in the ${formatLkr(result.tax_payable)} total.`,
      ],
    });
  }

  blocks.push({
    heading: "The bottom line",
    lines: [
      result.wht_credit
        ? `Tax before credits is ${formatLkr(result.tax_payable)}. WHT already paid of ${formatLkr(result.wht_credit)} is credited, leaving ${formatLkr(result.balance_payable ?? result.tax_payable)} to pay${(result.tax_refund ?? 0) > 0 ? ` (or a refund of ${formatLkr(result.tax_refund)})` : ""}.`
        : `You keep ${formatLkr(result.gross_income - result.tax_payable)} after paying ${formatLkr(result.tax_payable)} in tax (before any other payments or credits).`,
      "These numbers come from the official rules loaded for this year — the same calculation shown in the tables above.",
    ],
  });

  const reliefCount = reliefs.length;
  const summary =
    reliefCount > 0
      ? `You earned ${formatLkr(result.gross_income)}, used ${reliefCount} relief${reliefCount === 1 ? "" : "s"} to bring taxable income down to ${formatLkr(result.taxable_income)}, and owe ${formatLkr(result.tax_payable)} in tax.`
      : `You earned ${formatLkr(result.gross_income)}, had no reliefs, and owe ${formatLkr(result.tax_payable)} in tax.`;

  return {
    headline: `Your tax for ${ya} is ${formatLkr(result.tax_payable)}.`,
    summary,
    blocks,
  };
}
