import type { CalculateResponse, ReliefLine, SlabLine } from "./api";
import { parseLkr } from "./format-lkr";
import type { InterviewSession } from "./types";

export type ScenarioCitation = {
  entry_id?: string;
  display_name?: string;
  act_name: string;
  section_ref: string;
  source_doc_id: string;
  quote: string;
};

function citationKey(line: {
  source_doc_id?: string;
  section_ref?: string;
  quote?: string;
  entry_id?: string;
}): string {
  return [
    line.entry_id ?? "",
    line.source_doc_id ?? "",
    line.section_ref ?? "",
    (line.quote ?? "").slice(0, 120),
  ].join("|");
}

function reliefIsInScenario(line: ReliefLine, session?: InterviewSession): boolean {
  if (line.applied <= 0) return false;
  if (!session?.reliefAnswers.length) return true;

  const answer = session.reliefAnswers.find((item) => item.entry_id === line.entry_id);
  if (!answer) return true;
  if (answer.skipped) return false;
  const amount = parseLkr(answer.amount ?? "0");
  return amount > 0 || answer.affirmed === true;
}

function slabIsInScenario(band: SlabLine): boolean {
  return band.tax > 0 || band.slice > 0;
}

function lineToCitation(
  line: ReliefLine | SlabLine,
  displayName?: string,
): ScenarioCitation | null {
  const quote = (line.quote ?? "").trim();
  if (!quote) return null;
  return {
    entry_id: "entry_id" in line ? line.entry_id : undefined,
    display_name: displayName,
    act_name: line.act_name ?? "",
    section_ref: line.section_ref ?? "",
    source_doc_id: line.source_doc_id ?? "",
    quote,
  };
}

/**
 * Legal sources for this scenario only: reliefs the user claimed that actually
 * applied, plus rate bands that were used in the tax calculation.
 */
export function buildScenarioCitations(
  result: CalculateResponse,
  session?: InterviewSession,
): ScenarioCitation[] {
  const out: ScenarioCitation[] = [];
  const seen = new Set<string>();

  for (const line of result.relief_lines ?? []) {
    if (!reliefIsInScenario(line, session)) continue;
    const cite = lineToCitation(line, line.display_name);
    if (!cite) continue;
    const key = citationKey(cite);
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(cite);
  }

  for (const band of result.slab_lines ?? []) {
    if (!slabIsInScenario(band)) continue;
    const label = band.band_label?.trim() || `Rate band ${band.band_index}`;
    const cite = lineToCitation(band, label);
    if (!cite) continue;
    const key = citationKey(cite);
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(cite);
  }

  return out;
}
