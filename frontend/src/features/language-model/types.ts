/** Mirrors backend `app/schemas/nlu_v1.py` and `query_v1.py` (JSON field names). */

/** Phase 3 Step 15 — optional Neo4j / ETL join hints from corpus JSONL. */
export interface KgJoinFields {
  source_doc_id?: string | null;
  section_uid?: string | null;
  section_label?: string | null;
  tier?: string | null;
  instrument_type?: string | null;
  content_kind?: string | null;
}

export interface RetrievalHit extends KgJoinFields {
  chunk_id: string;
  score: number;
}

export interface NLUParseRequest {
  utterance: string;
  top_k?: number | null;
  intent_hint?: string | null;
}

export interface NLUParseResponse {
  utterance: string;
  intent: string | null;
  predicted_intent: string | null;
  intent_model: string | null;
  retrieval_hits: RetrievalHit[];
  model: string;
  corpus_loaded: boolean;
}

export interface QueryRequest {
  question: string;
  top_k?: number | null;
}

export interface Citation extends KgJoinFields {
  chunk_id: string;
  score: number;
  text: string;
}

export interface QueryResponse {
  question: string;
  top_k: number;
  citations: Citation[];
  retrieval_model: string;
}
