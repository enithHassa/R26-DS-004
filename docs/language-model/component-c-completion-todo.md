# Component C — Completion Todo List

**Student:** IT22896186 (Hewagama S.R)  
**Component:** Intelligent Tax Advisory Language Model  
**Service:** `backend/comp-language-model` (port **8004**)  
**Last updated:** 2026-08-16

Use this checklist to track progress toward a **complete** component aligned with your proposal (SO1–SO6).

**Legend:** ✅ Done · 🟡 Partial · ⬜ Not started

---

## A. Foundation (already complete)

| # | Task | Status | Notes |
|---|------|--------|-------|
| A1 | Repo structure + shared schemas | ✅ | Phase 1 |
| A2 | IRD corpus pipeline (`corpus_v1.jsonl`) | ✅ | Phase 1b — run locally if `data/processed` missing |
| A3 | TF-IDF + dense retrieval baseline | ✅ | Phase 2 M5 gate |
| A4 | Intent classification baseline (TF-IDF centroid) | ✅ | `COMP_LLM_INTENT_BENCHMARK_JSONL` |
| A5 | Evaluation harness + CI smoke tests | ✅ | `scripts/phase2_*`, GitHub Action |
| A6 | FastAPI + API gateway proxy (`/api/v1/llm/**`) | ✅ | Port 8004 → gateway 8000 |
| A7 | Frontend demo pages (NLU + Law query) | ✅ | `/language-model/nlu`, `/language-model/query` |

---

## B. Knowledge graph (Phase 3 — mostly complete)

| # | Task | Status | Notes |
|---|------|--------|-------|
| B1 | Tax KG ontology + ETL specs | ✅ | `knowledge_graph/ontology_v1.json` |
| B2 | Lex Specialis metadata + override paths | ✅ | `lex_specialis_v1.json`, override edges |
| B3 | Neo4j schema + chunk loaders | ✅ | Scripts in `scripts/neo4j_*` |
| B4 | **Seed Neo4j with full corpus** | ⬜ | Run loaders against local Neo4j |
| B5 | Enable graph on API (`COMP_LLM_GRAPH_ENABLED=true`) | 🟡 | Code ready; needs Neo4j + password in `.env` |
| B6 | Graph-first retrieval (Cypher as primary retriever) | ⬜ | Today: chunk search + graph enrichment overlay |

---

## C. Phase 5 — Neuro-symbolic core (implemented in this sprint)

| # | Task | Status | Notes |
|---|------|--------|-------|
| C1 | Query preprocessing (Singlish / informal) | ✅ | `app/services/query_preprocess.py` |
| C2 | Lex Specialis reranking after retrieval | ✅ | `app/services/lex_rank.py` |
| C3 | Symbolic rule engine (personal relief, rates) | ✅ | `reasoning/symbolic_rules_v1.json` + `symbolic_engine.py` |
| C4 | Think Twice validation loop | ✅ | `app/services/think_twice.py` — corrects bad synthesized answers |
| C5 | Proof Map (structured paper trail) | ✅ | Returned on `/query` and `/chat` when enabled |
| C6 | Shared query pipeline | ✅ | `app/services/query_pipeline.py` |
| C7 | Multi-turn chat API (FR9 MVP) | ✅ | `POST /api/v1/chat` + session store |
| C8 | Unit tests for Phase 5/6 | ✅ | `app/tests/test_phase5_phase6.py` |

---

## D. Still required for thesis completion

| # | Task | Status | Priority | Maps to |
|---|------|--------|----------|---------|
| D1 | Fine-tune domain SLM (DistilBERT/RoBERTa) for intent | ⬜ | **High** | SO1 |
| D2 | Entity extraction from queries | ⬜ | High | SO1, FR2 |
| D3 | Graph-first GraphRAG retrieval | ⬜ | **High** | SO2, WP5 |
| D4 | Expand symbolic rules (slabs, WHT, deadlines) | ⬜ | High | SO4 |
| D5 | Full agentic loop (LangGraph/CrewAI regenerate) | ⬜ | **High** | SO4, WP6 |
| D6 | Proof Map UI visualization | ⬜ | Medium | SO5, WP7 |
| D7 | Full chatbot UI (replace demo forms) | ⬜ | Medium | WP9 |
| D8 | Wire Component A/B financial profile into queries | ⬜ | Medium | Dependencies |
| D9 | Hallucination rate evaluation vs baseline LLM | ⬜ | **High** | SO6, WP8 |
| D10 | Legal consistency + traceability accuracy study | ⬜ | **High** | SO6 |
| D11 | Expert-reviewed benchmark expansion | ⬜ | High | WP8 |
| D12 | Thesis chapter + final documentation | ⬜ | High | WP10 |

---

## E. Recommended order (what to do next)

1. **Run & test locally** — follow [`component-c-run-and-test.md`](component-c-run-and-test.md).
2. **Build corpus** — if missing: `scripts/ird_phase1b_finalize.py`.
3. **Seed Neo4j** — enable graph enrichment for demos.
4. **Expand benchmark** — expert-checked `gold_chunk_ids` + intents.
5. **Fine-tune intent SLM** — beat TF-IDF centroid on held-out split.
6. **GraphRAG primary retrieval** — use `nlu_intent_graph_map_v1.json` Cypher templates.
7. **Expand Think Twice** — regenerate with LLM instead of only fallback text.
8. **Proof Map UI** — render `proof_map.steps` in frontend.
9. **Evaluation chapter** — hallucination + legal consistency metrics.
10. **Thesis write-up** — map each SO to implemented artifacts.

---

## F. Environment flags (Component C)

| Variable | Default | Purpose |
|----------|---------|---------|
| `COMP_LLM_CORPUS_JSONL` | — | Path to legal corpus JSONL |
| `COMP_LLM_INTENT_BENCHMARK_JSONL` | — | Intent training/eval benchmark |
| `COMP_LLM_GRAPH_ENABLED` | `false` | Neo4j enrichment |
| `COMP_LLM_ANSWER_SYNTHESIS_ENABLED` | `false` | Gemini plain-language answers |
| `COMP_LLM_GEMINI_API_KEY` | — | Required for synthesis |
| `COMP_LLM_LEX_SPECIALIS_RERANK` | `true` | Tier/instrument boost after retrieval |
| `COMP_LLM_THINK_TWICE_ENABLED` | `true` | Symbolic validation on answers |
| `COMP_LLM_PROOF_MAP_ENABLED` | `true` | Attach Proof Map to responses |

---

## G. Completion criteria (definition of “done”)

Your component is **research-complete** when all of the following are true:

- [ ] User can ask tax questions in natural language (including informal phrasing) via **chat UI**
- [ ] Answers are **grounded** in IRA / IRD sources with **citations**
- [ ] **Lex Specialis** correctly prefers newer/specific law in retrieval
- [ ] **Think Twice** catches and fixes incorrect tax amounts / rates before display
- [ ] **Proof Map** shows auditable path from question → law → validation → answer
- [ ] **Evaluation** shows lower hallucination rate vs general LLM baseline
- [ ] **Integration** optionally uses financial profile from Components A/B
- [ ] **Thesis** documents architecture, experiments, and limitations

**Current estimate:** ~**55–60%** complete after Phase 5/6 MVP (up from ~45–50% before).
