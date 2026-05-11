import type { KgJoinFields } from "../types";

export function humanizeSlug(value: string): string {
  return value
    .split(/[-_]+/)
    .filter(Boolean)
    .map((part) => {
      if (/^\d+$/.test(part)) return part;
      if (part.length <= 3) return part.toUpperCase();
      return part.charAt(0).toUpperCase() + part.slice(1);
    })
    .join(" ");
}

export function instrumentLabel(value: string | null | undefined): string | null {
  if (!value) return null;
  const labels: Record<string, string> = {
    base_act: "Principal act",
    amendment_act: "Amendment act",
    consolidated: "Consolidated law",
    guide: "IRD guide",
    regulation: "Regulation",
    circular: "Circular",
  };
  return labels[value] ?? humanizeSlug(value);
}

export function tierLabel(value: string | null | undefined): string | null {
  if (!value) return null;
  const labels: Record<string, string> = {
    A: "Primary legal source",
    B: "Guidance / explanatory material",
    C: "Supporting reference",
  };
  return labels[value.toUpperCase()] ?? `Tier ${value.toUpperCase()}`;
}

export function contentKindLabel(value: string | null | undefined): string | null {
  if (!value) return null;
  const labels: Record<string, string> = {
    text: "Text excerpt",
    table: "Table excerpt",
  };
  return labels[value] ?? humanizeSlug(value);
}

export function retrievalModelLabel(value: string): string {
  const labels: Record<string, string> = {
    "tfidf-baseline": "Keyword similarity search",
    "dense-baseline": "Semantic similarity search",
    "stub-no-corpus": "Demo mode (corpus not loaded)",
  };
  return labels[value] ?? humanizeSlug(value);
}

export function relevanceBand(score: number, maxScore: number): {
  label: string;
  percent: number;
  tone: "strong" | "good" | "moderate" | "low";
} {
  const percent = maxScore > 0 ? Math.round((score / maxScore) * 100) : 0;
  if (percent >= 85) return { label: "Strong match", percent, tone: "strong" };
  if (percent >= 65) return { label: "Good match", percent, tone: "good" };
  if (percent >= 40) return { label: "Moderate match", percent, tone: "moderate" };
  return { label: "Weak match", percent, tone: "low" };
}

export function sourceTitle(fields: KgJoinFields, fallbackId?: string): string {
  if (fields.section_label?.trim()) return fields.section_label.trim();
  if (fields.source_doc_id?.trim()) return humanizeSlug(fields.source_doc_id.trim());
  if (fallbackId?.trim()) return humanizeSlug(fallbackId.trim());
  return "Matched document section";
}

export function sourceSubtitle(fields: KgJoinFields): string | null {
  if (fields.source_doc_id?.trim()) {
    return humanizeSlug(fields.source_doc_id.trim());
  }
  return null;
}

export function intentLabel(value: string | null | undefined): string {
  if (!value?.trim()) return "Not classified";
  return humanizeSlug(value.trim());
}
