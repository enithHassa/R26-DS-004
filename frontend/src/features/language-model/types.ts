/** Mirrors backend `app/schemas/nlu_v1.py`, `query_v1.py`, `chat_v1.py`, `proof_map_v1.py`, `graph_v1.py`. */

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

// ── Phase 4: Knowledge Graph types ──────────────────────────────────────────

export interface ConceptNode {
  concept_id: string;
  canonical_name?: string | null;
  aliases?: string[];
  notes?: string | null;
}

export interface ReliefNode {
  relief_id: string;
  display_name?: string | null;
  statutory_label?: string | null;
  description?: string | null;
  source_doc_id?: string | null;
}

export interface RateBandNode {
  rate_band_id: string;
  band_label?: string | null;
  band_type?: string | null;
  lower_bound?: number | null;
  upper_bound?: number | null;
  rate_percent?: number | null;
  currency?: string | null;
  effective_start_date?: string | null;
  effective_end_date?: string | null;
}

export interface ProcedureMilestoneNode {
  milestone_id: string;
  milestone_kind?: string | null;
  display_name?: string | null;
  description?: string | null;
  due_day?: number | null;
  due_month?: number | null;
  recurrence?: string | null;
  applies_to?: string[];
}

export interface TaxpayerProfileNode {
  profile_type: string;
  display_name?: string | null;
  description?: string | null;
}

export interface LexNote {
  winner_section_uid: string;
  overridden_section_uid: string;
  authority_class?: string | null;
  note?: string | null;
}

export interface GraphContext {
  concepts: ConceptNode[];
  reliefs: ReliefNode[];
  rate_bands: RateBandNode[];
  procedure_milestones: ProcedureMilestoneNode[];
  taxpayer_profiles: TaxpayerProfileNode[];
  superseded_by: string[];
  lex_notes: LexNote[];
  graph_model: string;
}

// ── NLU contracts ─────────────────────────────────────────────────────────

export interface NLUParseResponse {
  utterance: string;
  intent: string | null;
  predicted_intent: string | null;
  intent_model: string | null;
  retrieval_hits: RetrievalHit[];
  model: string;
  corpus_loaded: boolean;
  graph_context?: GraphContext | null;
  domain_status?: string | null;
  domain_message?: string | null;
}

// ── Query / Citation contracts ─────────────────────────────────────────────

export interface QueryRequest {
  question: string;
  top_k?: number | null;
  synthesize_answer?: boolean;
  assessment_year_hint?: string | null;
  include_proof_map?: boolean;
}

export interface Citation extends KgJoinFields {
  chunk_id: string;
  score: number;
  text: string;
}

// ── Phase 5: Proof Map ─────────────────────────────────────────────────────

export type ProofStepKind =
  | "user_query"
  | "retrieval"
  | "knowledge_graph"
  | "evidence"
  | "symbolic_validation"
  | "advisory_output";

export interface ProofMapStep {
  step_id: string;
  kind: ProofStepKind;
  label: string;
  detail?: string | null;
  metadata?: Record<string, unknown> | null;
}

export interface ProofMap {
  steps: ProofMapStep[];
  evidence_refs: string[];
  validation_status: string;
  rule_engine_version: string;
}

export interface QueryResponse {
  question: string;
  normalized_question?: string | null;
  top_k: number;
  citations: Citation[];
  retrieval_model: string;
  graph_context?: GraphContext | null;
  plain_answer?: string | null;
  answer_provider?: string | null;
  answer_model?: string | null;
  domain_status?: string | null;
  domain_message?: string | null;
  validation_status?: string | null;
  proof_map?: ProofMap | null;
}

// ── Phase 6: Chat contracts ─────────────────────────────────────────────────

export interface ChatRequest {
  message: string;
  session_id?: string | null;
  top_k?: number | null;
  synthesize_answer?: boolean;
  assessment_year_hint?: string | null;
  /** Caller's users.id — persists the conversation per-user when set. */
  user_id?: string | null;
  /** Caller's financial_profiles.id — enables answers about their own taxpayer record. */
  profile_id?: string | null;
}

export interface TaxpayerContext {
  used: boolean;
  profile_id?: string | null;
  taxpayer_name?: string | null;
  tax_year?: string | null;
  fields_used?: string[];
  kg_consistency?: string | null;
  note?: string | null;
}

export interface ChatSessionSummary {
  session_id: string;
  title?: string | null;
  archived: boolean;
  created_at: string;
  last_message_at: string;
  message_count: number;
}

export interface ChatHistoryMessage {
  role: "user" | "assistant";
  content: string;
  created_at: string;
  query_result?: QueryResponse | null;
  proof_map?: ProofMap | null;
  taxpayer_context?: TaxpayerContext | null;
}

export interface ChatSessionDetail {
  session_id: string;
  title?: string | null;
  archived: boolean;
  created_at: string;
  last_message_at: string;
  messages: ChatHistoryMessage[];
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  created_at?: string | null;
}

export interface ChatResponse {
  session_id: string;
  turn_index: number;
  user_message: string;
  assistant_message: string;
  query_result: QueryResponse;
  proof_map?: ProofMap | null;
  history_length: number;
  taxpayer_context?: TaxpayerContext | null;
  persisted?: boolean;
}
