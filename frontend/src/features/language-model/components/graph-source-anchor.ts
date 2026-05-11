import type { Citation, KgJoinFields, RetrievalHit } from "../types";
import { sourceSubtitle, sourceTitle } from "./language-model-display";

export interface GraphSourceAnchor {
  rank: number;
  chunkId: string;
  title: string;
  subtitle: string | null;
  sectionUid: string | null;
  sourceDocId: string | null;
}

function toAnchor(
  rank: number,
  chunkId: string,
  fields: KgJoinFields,
): GraphSourceAnchor {
  const title = sourceTitle(fields, chunkId);
  const subtitle = sourceSubtitle(fields);
  return {
    rank,
    chunkId,
    title,
    subtitle: subtitle && subtitle !== title ? subtitle : null,
    sectionUid: fields.section_uid?.trim() || null,
    sourceDocId: fields.source_doc_id?.trim() || null,
  };
}

export function anchorsFromRetrievalHits(hits: RetrievalHit[]): GraphSourceAnchor[] {
  return hits.map((hit, index) => toAnchor(index + 1, hit.chunk_id, hit));
}

export function anchorsFromCitations(citations: Citation[]): GraphSourceAnchor[] {
  return citations.map((citation, index) => toAnchor(index + 1, citation.chunk_id, citation));
}
