import type {
  CalculationTraceStep,
  EvidenceSourceQuote,
  ExplainStep,
  ExplainTaxResponse,
  GraphModifiesEdge,
  RuleSourceRef,
  StoredCalculation,
} from "./api";
import { cappedNote, mentionPersonalRelief } from "./build-taxpayer-summary";
import { formatLkr } from "./format-lkr";
import { sourceDocPlainName, stepLabel } from "./taxpayer-labels";

const INSUFFICIENT_EVIDENCE_MESSAGE =
  "We couldn't confirm the exact legal wording for this step, so no explanation is shown here — the calculated amount itself is unaffected and still comes from the deterministic rule engine.";

const EVIDENCE_UNAVAILABLE = "Evidence unavailable for this step";

export type ReportNarrativeCitation = {
  quote: string;
  section: string;
  actName: string | null;
};

const CAP_DEDUCT_PAIRS: ReadonlyArray<readonly [string, string]> = [
  ["cap_solar_panel_relief", "deduct_solar_panel_relief"],
  ["cap_rent_relief", "deduct_rent_relief"],
];

export type ReportNarrativeStep = {
  label: string;
  sentence: string;
  sectionTag: string | null;
  citation: ReportNarrativeCitation | null;
};

export type ReportNarrativeView = {
  summary: string | null;
  steps: ReportNarrativeStep[];
  insufficientEvidence: boolean;
  insufficientEvidenceMessage: string | null;
  lawChanges: string[];
};

function findTraceStep(
  trace: CalculationTraceStep[],
  stepId: string,
): CalculationTraceStep | undefined {
  return trace.find((step) => step.step_id === stepId);
}

function isUsableDescription(description: string | undefined, stepId: string): boolean {
  const text = (description ?? "").trim();
  if (!text) return false;
  if (text === stepId) return false;
  if (text.startsWith("qp_category:")) return false;
  return true;
}

function escapeRegex(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function ratePercent(rate: string | undefined): string | null {
  const n = parseFloat(rate ?? "");
  if (!Number.isFinite(n)) return null;
  return String(Math.round(n * 100));
}

function resolveLabel(stepId: string, trace: CalculationTraceStep): string | null {
  const mapped = stepLabel(stepId);
  if (mapped) {
    if (/^slab_band_\d+$/.test(stepId)) {
      const percent = ratePercent(trace.inputs.rate);
      return percent != null ? `${mapped} (${percent}% band)` : mapped;
    }
    return mapped;
  }
  if (isUsableDescription(trace.description, stepId)) return trace.description.trim();
  return null;
}

function deJargon(text: string, traceOutput: string, knownIds: string[]): string {
  let s = text;
  s = s.replace(/`[^`]*`/g, "");
  s = s.replace(
    /\byielding\s+-?\d[\d,]*(?:\.\d+)?/gi,
    `giving ${formatLkr(traceOutput)}`,
  );
  s = s.replace(/\s*\(sections?:\s*[^)]+\)/gi, "");
  s = s.replace(/\bKG-applicable\b/gi, "applicable");
  s = s.replace(/\s+via\s+qualifying_payment_cap\b/gi, "");
  for (const id of knownIds) {
    if (!id || id.length < 4) continue;
    s = s.replace(new RegExp(`\\b${escapeRegex(id)}\\b`, "g"), "");
  }
  return s.replace(/\s{2,}/g, " ").trim();
}

function sentenceHasTraceAmount(sentence: string, amountText: string): boolean {
  if (!amountText || amountText === "—") return false;
  return sentence.includes(amountText);
}

function ensureTraceAmount(sentence: string, amountText: string): string {
  const trimmed = sentence.replace(/\.+$/, "").trim();
  if (!amountText || amountText === "—") {
    return /[.!?]$/.test(sentence.trim()) ? sentence.trim() : `${trimmed}.`;
  }
  if (!trimmed) return amountText.endsWith(".") ? amountText : `${amountText}.`;
  if (sentenceHasTraceAmount(trimmed, amountText)) {
    return /[.!?]$/.test(sentence.trim()) ? sentence.trim() : `${trimmed}.`;
  }
  return `${trimmed} — ${amountText}.`;
}

function capClause(trace: CalculationTraceStep): string | null {
  const claimed = trace.inputs.claimed ?? trace.inputs.effective_claim;
  const allowed = trace.inputs.allowed;
  if (!cappedNote(claimed, allowed) || !claimed || !allowed) return null;
  return `Only ${formatLkr(allowed)} of ${formatLkr(claimed)} claimed was allowed`;
}

function sectionFromUid(uid: string): string | null {
  const slug = uid.includes("::") ? uid.split("::").slice(-1)[0] ?? "" : uid;
  if (!slug || slug.startsWith("ird-")) return null;
  if (slug === "first_schedule") return "First Schedule";
  if (slug === "fifth_schedule") return "Fifth Schedule";
  const m = slug.match(/^section[_\s-]*(\d+[a-z]?)$/i);
  if (m) return `Section ${m[1]}`;
  return null;
}

function sectionTag(
  trace: CalculationTraceStep,
  narrative: string,
  citation: ReportNarrativeCitation | null,
): string | null {
  const fromDesc = (trace.description || "").match(
    /(?:sec(?:tion)?\.?\s*)(\d+[a-z]?)(?:\s*\((\d+[a-z]?)\))?/i,
  );
  if (fromDesc) {
    return fromDesc[2]
      ? `Section ${fromDesc[1]}(${fromDesc[2]})`
      : `Section ${fromDesc[1]}`;
  }
  const fromNarrative = narrative.match(/\(sections?:\s*([^)]+)\)/i);
  if (fromNarrative) {
    const first = fromNarrative[1].split(",")[0]?.trim();
    if (first && !first.includes("::") && !first.startsWith("ird-")) return first;
  }
  if (citation?.section) {
    const sec = citation.section.trim();
    if (/^\d/.test(sec)) return `Section ${sec}`;
    if (!sec.includes("::") && !sec.startsWith("ird-")) return sec;
  }
  for (const uid of trace.section_uids) {
    const label = sectionFromUid(uid);
    if (label) return label;
  }
  return null;
}

const YEAR_SUFFIX_ID = /_20\d{2}_\d{2}$/;

function actNameForId(id: string, refs: RuleSourceRef[]): string | null {
  const row = refs.find((item) => item.id === id);
  return sourceDocPlainName(row?.source_doc_id) ?? null;
}

function quoteForId(
  id: string,
  refs: RuleSourceRef[],
  quotes: EvidenceSourceQuote[],
): ReportNarrativeCitation | null {
  const actName = actNameForId(id, refs);
  const ref = refs.find((row) => row.id === id && row.source_quote);
  if (ref?.source_quote) {
    return {
      quote: ref.source_quote,
      section: ref.section || "",
      actName,
    };
  }
  const quote = quotes.find((row) => row.rule_source_id === id && row.source_quote);
  if (quote?.source_quote) {
    return {
      quote: quote.source_quote,
      section: quote.section || "",
      actName,
    };
  }
  return null;
}

function lookupCitation(
  trace: CalculationTraceStep,
  refs: RuleSourceRef[],
  quotes: EvidenceSourceQuote[],
): ReportNarrativeCitation | null {
  const ids = trace.rule_source_ids.filter((id): id is string => Boolean(id));
  if (ids.length === 0) return null;

  const yearId = ids.find((id) => YEAR_SUFFIX_ID.test(id));
  if (yearId) {
    const yearHit = quoteForId(yearId, refs, quotes);
    if (yearHit) return yearHit;
  }

  const primary = ids[0];
  if (primary && primary !== yearId) {
    return quoteForId(primary, refs, quotes);
  }
  return null;
}

function extractMoneyFigures(text: string): string[] {
  return text.match(/\d{1,3}(?:,\d{3})+|\d{4,}/g) ?? [];
}

function plainSectionFromEdge(edge: GraphModifiesEdge): string | null {
  const label = (edge.section_label || "").trim();
  if (label && !label.includes("::") && !label.startsWith("ird-")) return label;
  return sectionFromUid(edge.section_uid);
}

function lawChangeSentences(edges: GraphModifiesEdge[]): string[] {
  const out: string[] = [];
  for (const edge of edges) {
    const source = sourceDocPlainName(edge.amendment_source_doc_id);
    const section = plainSectionFromEdge(edge);
    const when = edge.effective_from?.trim() || null;
    const note = edge.source_note || "";
    const figures = extractMoneyFigures(note);
    const parts: string[] = [];

    if (figures.length >= 2) {
      const fromAmt = formatLkr(figures[0].replace(/,/g, ""));
      const toAmt = formatLkr(figures[1].replace(/,/g, ""));
      let sentence = `The qualifying-payment limit was raised from ${fromAmt} to ${toAmt}`;
      if (source) sentence += ` by ${source}`;
      if (when) sentence += `, effective ${when}`;
      sentence += ". This calculation uses the updated figure.";
      parts.push(sentence);
    } else if (source && section && when) {
      parts.push(`An amendment in ${source} changed ${section}, effective ${when}.`);
    } else if (source && section) {
      parts.push(`An amendment in ${source} changed ${section}.`);
    } else if (section && when) {
      parts.push(`An amendment changed ${section}, effective ${when}.`);
    } else if (section) {
      parts.push(`An amendment changed ${section}.`);
    } else if (when) {
      parts.push(`An amendment took effect ${when}.`);
    } else if (source) {
      parts.push(`An amendment in ${source} applies to this calculation.`);
    }
    out.push(...parts);
  }
  return out;
}

function deJargonSummary(text: string, finalTax: string, knownIds: string[]): string {
  let s = deJargon(text, finalTax, knownIds);
  s = s.replace(/\b-?\d[\d,]*(?:\.\d+)?\s*LKR\b/gi, formatLkr(finalTax));
  return s.replace(/\s{2,}/g, " ").trim();
}

function pairFor(stepId: string): { capId: string; deductId: string } | null {
  for (const [capId, deductId] of CAP_DEDUCT_PAIRS) {
    if (stepId === capId || stepId === deductId) return { capId, deductId };
  }
  return null;
}

function schedulePhrase(
  cap: CalculationTraceStep,
  citation: ReportNarrativeCitation | null,
): string | null {
  const desc = cap.description || "";
  if (/fifth schedule/i.test(desc)) return "Fifth Schedule";
  const sectionMatch = desc.match(/section\s+(\d+[a-z]?)/i);
  if (sectionMatch) return `Section ${sectionMatch[1]}`;
  return sectionTag(cap, "", citation);
}

function mergeCapDeductSentence(
  cap: CalculationTraceStep,
  deduct: CalculationTraceStep,
  citation: ReportNarrativeCitation | null,
): string {
  const claimed =
    cap.inputs.claimed ??
    cap.inputs.effective_claim ??
    deduct.inputs.claimed ??
    deduct.inputs.effective_claim;
  const allowed = cap.inputs.allowed ?? deduct.inputs.allowed;
  const capAmt = cap.inputs.cap ?? cap.inputs.sec52_cap ?? cap.inputs.ceiling;
  const schedule = schedulePhrase(cap, citation);

  if (cappedNote(claimed, allowed) && claimed && allowed && capAmt) {
    const capBit = schedule
      ? `after the ${schedule} cap of ${formatLkr(capAmt)}`
      : `after the cap of ${formatLkr(capAmt)}`;
    return `You claimed ${formatLkr(claimed)}; ${capBit}, ${formatLkr(allowed)} was allowed and deducted.`;
  }
  return `You claimed ${formatLkr(claimed)}, and ${formatLkr(allowed)} was allowed and deducted.`;
}

function canNarrateStep(
  stepId: string,
  explained: ExplainStep[],
  trace: CalculationTraceStep[],
  personalTrace: CalculationTraceStep | undefined,
): boolean {
  if (stepId === "apply_personal_relief" && !mentionPersonalRelief(personalTrace)) {
    return false;
  }
  const entry = explained.find((row) => row.step_id === stepId);
  if (!entry) return false;
  if ((entry.narrative || "").trim() === EVIDENCE_UNAVAILABLE) return false;
  if (stepId.startsWith("unresolved_")) return false;
  const matched = findTraceStep(trace, stepId);
  if (!matched) return false;
  return Boolean(resolveLabel(stepId, matched));
}

function buildSingleNarrativeStep(
  explained: ExplainStep,
  matched: CalculationTraceStep,
  knownIds: string[],
  refs: RuleSourceRef[],
  quotes: EvidenceSourceQuote[],
): ReportNarrativeStep | null {
  const label = resolveLabel(explained.step_id, matched);
  if (!label) return null;

  let sentence = deJargon(explained.narrative || "", matched.output, knownIds);
  const extra = capClause(matched);
  if (extra && !sentence.toLowerCase().includes("only ")) {
    sentence = `${sentence.replace(/\.+$/, "")}. ${extra}`;
  }
  sentence = ensureTraceAmount(sentence, formatLkr(matched.output));

  const citation = lookupCitation(matched, refs, quotes);
  return {
    label,
    sentence,
    sectionTag: sectionTag(matched, explained.narrative || "", citation),
    citation,
  };
}

export function buildReportNarrative(
  stored: StoredCalculation,
  explanation?: ExplainTaxResponse,
): ReportNarrativeView {
  const empty: ReportNarrativeView = {
    summary: null,
    steps: [],
    insufficientEvidence: true,
    insufficientEvidenceMessage: INSUFFICIENT_EVIDENCE_MESSAGE,
    lawChanges: [],
  };

  if (!explanation || explanation.insufficient_evidence) {
    return empty;
  }

  const trace = stored.response.calculation_trace ?? [];
  const refs = stored.response.rule_source_refs ?? [];
  const quotes = explanation.evidence?.source_quotes ?? [];
  const knownIds = [
    ...trace.map((step) => step.step_id),
    ...explanation.steps_explained.map((step) => step.step_id),
  ];
  const personalTrace = findTraceStep(trace, "apply_personal_relief");
  const explainedSteps = explanation.steps_explained;
  const consumed = new Set<string>();
  const steps: ReportNarrativeStep[] = [];

  for (const explained of explainedSteps) {
    const stepId = explained.step_id;
    if (consumed.has(stepId)) continue;
    if (stepId === "apply_personal_relief" && !mentionPersonalRelief(personalTrace)) {
      continue;
    }
    if ((explained.narrative || "").trim() === EVIDENCE_UNAVAILABLE) continue;
    if (stepId.startsWith("unresolved_")) continue;

    const matched = findTraceStep(trace, stepId);
    if (!matched) continue;

    const pair = pairFor(stepId);
    const partnerId = pair
      ? stepId === pair.capId
        ? pair.deductId
        : pair.capId
      : null;
    if (
      pair &&
      partnerId &&
      canNarrateStep(stepId, explainedSteps, trace, personalTrace) &&
      canNarrateStep(partnerId, explainedSteps, trace, personalTrace)
    ) {
      const capTrace = findTraceStep(trace, pair.capId);
      const deductTrace = findTraceStep(trace, pair.deductId);
      const label = resolveLabel(stepId, matched);
      if (capTrace && deductTrace && label) {
        consumed.add(partnerId);
        const citation = lookupCitation(capTrace, refs, quotes);
        steps.push({
          label,
          sentence: mergeCapDeductSentence(capTrace, deductTrace, citation),
          sectionTag: sectionTag(capTrace, "", citation),
          citation,
        });
        continue;
      }
    }

    const single = buildSingleNarrativeStep(explained, matched, knownIds, refs, quotes);
    if (single) steps.push(single);
  }

  const summaryRaw = (explanation.summary || "").trim();
  const summary = summaryRaw
    ? deJargonSummary(summaryRaw, stored.response.final_tax_lkr, knownIds)
    : null;

  return {
    summary: summary || null,
    steps,
    insufficientEvidence: false,
    insufficientEvidenceMessage: null,
    lawChanges: lawChangeSentences(explanation.evidence?.graph_modifies ?? []),
  };
}
