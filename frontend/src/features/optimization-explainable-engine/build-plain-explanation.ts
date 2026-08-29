import type { CalculateResponse, ReliefLine, SlabLine } from "./api";
import { formatLkr, yaDisplay } from "./format-lkr";
import { sortReliefLinesForDisplay } from "./sort-reliefs";
import { activeSlabLines, ordinaryTaxFromSlabs } from "./tax-buildup";

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

function reliefKidLine(line: ReliefLine): string {
  const name = line.display_name;
  const amount = formatLkr(line.applied);
  const group = line.compare_group_id ?? "";

  if (group === "personal_relief") {
    return `Personal relief — this is the basic tax-free allowance for the year. The Act lets every qualifying individual keep ${amount} of income free of tax before the rate bands start.`;
  }
  if (group === "solar_panel_relief") {
    return `Solar panel relief — spending on approved solar installations can reduce taxable income. Based on what you claimed, ${amount} came off this year’s calculation.`;
  }
  if (group.includes("provincial") || name.toLowerCase().includes("provincial council")) {
    return `Provincial Council donation — gifts to an approved Provincial Council fund can reduce taxable income. Your claim removed ${amount}.`;
  }
  if (name.toLowerCase().includes("digital") || name.toLowerCase().includes("productivity")) {
    return `Digital / productivity equipment relief — approved spending on digital tools can reduce tax. We took off ${amount} under the rules for this year.`;
  }
  if (group === "senior_citizen_interest_relief") {
    return `Senior citizen interest relief — extra shelter on qualifying bank interest for senior citizens. Applied amount: ${amount}.`;
  }
  if (group === "foreign_currency_income_relief") {
    return `Foreign currency income relief — some foreign-currency earnings can be sheltered under the Act. Applied amount: ${amount}.`;
  }
  if (group === "rental_income_relief" || group === "rent_relief") {
    return `Rent relief — a share of rental income can come off under the rental relief rule. Applied amount: ${amount}.`;
  }

  if (line.claim > 0 && line.claim !== line.applied) {
    return `${name} — you asked for ${formatLkr(line.claim)}; the published cap and formula for this year allowed ${amount}.`;
  }
  return `${name} — under the published rules for this year, ${amount} comes off your income.`;
}

function simpleBandStep(band: SlabLine, stepNumber: number): string {
  const slice = formatLkr(band.slice);
  const tax = formatLkr(band.tax);
  const rate = band.rate_percent;
  const label = band.band_label?.trim();

  if (label) {
    return `Step ${stepNumber}: ${slice} of taxable income is in “${label}” (${rate}%) → tax ${tax}.`;
  }
  return `Step ${stepNumber}: ${slice} taxed at ${rate}% → ${tax}.`;
}

export function buildPlainExplanation(result: CalculateResponse): PlainExplanation {
  const ya = yaDisplay(result.assessment_year);
  const reliefs = sortReliefLinesForDisplay(appliedReliefs(result.relief_lines ?? []));
  const bands = activeSlabLines(result.slab_lines ?? []);
  const ordinaryTax = ordinaryTaxFromSlabs(result.slab_lines);
  const terminalTax = result.terminal_benefit_tax ?? 0;

  const blocks: PlainExplanationBlock[] = [];

  // Year + gross live in the headline/summary — walkthrough starts where tax actually changes.
  if (reliefs.length > 0) {
    const terminalAmount = result.terminal_benefit_amount ?? 0;
    const ordinaryIncome = Math.max(0, result.gross_income - terminalAmount);
    const reliefIntro =
      terminalAmount > 0
        ? `You reported ${formatLkr(result.gross_income)} in YA ${ya}, including ${formatLkr(terminalAmount)} of qualifying terminal benefits (taxed separately). Reliefs only reduce ordinary income of ${formatLkr(ordinaryIncome)}. Together they remove ${formatLkr(result.total_reliefs)}.`
        : `You earned ${formatLkr(result.gross_income)} in YA ${ya}. Before tax rates apply, the law allows certain “reliefs” — think of them as approved reductions. Together they remove ${formatLkr(result.total_reliefs)} from what would otherwise be taxed.`;
    const reliefClose =
      terminalAmount > 0
        ? `After reliefs on ordinary income: ${formatLkr(ordinaryIncome)} − ${formatLkr(result.total_reliefs)} = ${formatLkr(result.taxable_income)} left for ordinary rate bands (terminal benefits stay on their own ladder).`
        : `Put together: ${formatLkr(result.gross_income)} earnings − ${formatLkr(result.total_reliefs)} reliefs = ${formatLkr(result.taxable_income)} left to put through the rate bands.`;
    blocks.push({
      heading: "What came off your income?",
      lines: [
        reliefIntro,
        ...reliefs.map((line) => reliefKidLine(line)),
        reliefClose,
      ],
    });
  } else {
    const terminalAmount = result.terminal_benefit_amount ?? 0;
    blocks.push({
      heading: "What came off your income?",
      lines: [
        terminalAmount > 0
          ? `You reported ${formatLkr(result.gross_income)} in YA ${ya} (including ${formatLkr(terminalAmount)} terminal benefits) and claimed no reliefs on ordinary income.`
          : `You earned ${formatLkr(result.gross_income)} in YA ${ya} and claimed no reliefs in this scenario.`,
        `That means ${formatLkr(result.taxable_income)} goes into the ordinary tax rate steps below.`,
      ],
    });
  }

  if (bands.length > 0) {
    const bandLines = bands.map((band, index) => simpleBandStep(band, index + 1));
    const parts = bands.map((band) => formatLkr(band.tax));
    const sumLine =
      terminalTax > 0
        ? `Ordinary bands add up to ${formatLkr(ordinaryTax)}. Terminal-benefit tax adds ${formatLkr(terminalTax)}. Together: ${formatLkr(ordinaryTax)} + ${formatLkr(terminalTax)} = ${formatLkr(result.tax_payable)} tax payable.`
        : `Add every band: ${parts.join(" + ")} = ${formatLkr(ordinaryTax)} tax payable.`;
    blocks.push({
      heading: "How the tax is added up",
      lines: [
        `Only the ${formatLkr(result.taxable_income)} taxable amount is taxed — not your full earnings. Sri Lanka uses progressive “stairs”: the first slice of taxable income is taxed at one rate, the next slice at a higher rate, and so on.`,
        ...bandLines,
        sumLine,
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
        "A qualifying terminal benefit (for example certain end-of-employment payments) is taxed on its own ladder, separate from ordinary salary. That keeps those amounts from being piled onto your normal rate bands.",
        ...terminalBands.map((band, index) => simpleBandStep(band, index + 1)),
        `That extra tax is ${formatLkr(terminalTax)}, and it is already included in the ${formatLkr(result.tax_payable)} tax payable total.`,
      ],
    });
  }

  blocks.push({
    heading: "The bottom line",
    lines: [
      (() => {
        const apit = result.apit_credit ?? 0;
        const wht = result.wht_credit ?? 0;
        if (apit <= 0 && wht <= 0) {
          return `After ${formatLkr(result.tax_payable)} tax on this scenario, about ${formatLkr(result.gross_income - result.tax_payable)} of your ${formatLkr(result.gross_income)} earnings remains before other payments or credits.`;
        }
        const parts: string[] = [];
        if (apit > 0) parts.push(`APIT of ${formatLkr(apit)}`);
        if (wht > 0) parts.push(`WHT of ${formatLkr(wht)}`);
        return `Tax before credits is ${formatLkr(result.tax_payable)}. ${parts.join(" and ")} already paid is credited against that bill, leaving ${formatLkr(result.balance_payable ?? result.tax_payable)} to pay${(result.tax_refund ?? 0) > 0 ? ` (or a refund of ${formatLkr(result.tax_refund)})` : ""}.`;
      })(),
      "These figures use the official Act / Gazette rules loaded for this year — the same engine numbers shown on My Tax Result. The Act quotes below show where each main step comes from.",
    ],
  });

  const reliefCount = reliefs.length;
  const summary =
    reliefCount > 0
      ? `YA ${ya}: you earned ${formatLkr(result.gross_income)}, used ${reliefCount} relief${reliefCount === 1 ? "" : "s"} to bring taxable income down to ${formatLkr(result.taxable_income)}, and owe ${formatLkr(result.tax_payable)} in tax.`
      : `YA ${ya}: you earned ${formatLkr(result.gross_income)}, had no reliefs, and owe ${formatLkr(result.tax_payable)} in tax.`;

  return {
    headline: `Your tax for ${ya} is ${formatLkr(result.tax_payable)}.`,
    summary,
    blocks,
  };
}
