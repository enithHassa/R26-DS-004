# Component C — Intelligent Tax Advisory Language Model

**Student:** Hewagama S.R — IT22896186  
**Project group:** R26-DS-004  
**Component role in the overall system:** Conversational tax advisory interface (Component C of 4)  
**Repo service name:** `backend/comp-language-model` (also called “Component 4” in internal docs)  
**Service version:** `0.1.0`

This document explains **what your component is**, **what the team has already built**, **where you are now**, and **what still needs to be done** to match your proposal and the group presentation. It is written for someone new to the codebase.

---

## 1. The big picture — where your component fits

The full research project is:

> **An Intelligent AI-Driven Decision Support System for Personalized Income Tax Compliance and Advisory in Sri Lanka**

The system has **four research components**:

| # | Component | Owner (presentation) | Role |
|---|-----------|----------------------|------|
| A | Financial Transaction Semantic Reasoning | IT22118936 | Turns raw bank transactions into structured, tax-relevant outputs |
| B | Tax Strategy Optimization | IT22064486 | Optimizes tax-saving strategies using rules + optimization |
| C | **Intelligent Tax Advisory Language Model** | **IT22896186 (you)** | **Conversational, grounded tax Q&A for users** |
| D | Personalized Recommendation Engine | IT22238580 | Ranks strategies and predicts long-term impact |

Your component is the **user-facing conversational brain**. It must:

1. Understand natural-language tax questions (including informal Sri Lankan phrasing).
2. Ground answers in **verified Sri Lankan tax law** (Inland Revenue Act, circulars, IRD guidance).
3. Avoid hallucinations through **neuro-symbolic validation** (your proposal’s core novelty).
4. Show **traceable evidence** (Proof Map / paper trail) so users can trust the advice.
5. Integrate with Components A/B for **personalized context** (income, deductions, etc.).

```text
User question
    │
    ▼
┌─────────────────────────────────────────┐
│  YOUR COMPONENT (Language Model)        │
│  NLU → GraphRAG → Generate → Validate   │
│  → Proof Map → Advisory response        │
└─────────────────────────────────────────┘
    │ uses structured outputs from
    ▼
Component A (transactions) + Component B (strategies)
```

---

## 2. What your proposal says you will build

Your proposal defines a **Neuro-Symbolic Small Language Model (SLM)** — not a generic ChatGPT wrapper.

### 2.1 Main research problem

> How can a Neuro-Symbolic SLM provide reliable, traceable, legally compliant tax advisory by combining GraphRAG, Lex Specialis priority logic, and visual Proof Maps?

### 2.2 Main objective

Design, develop, and validate a system that gives **accurate, personalized, fully traceable** tax guidance grounded in Sri Lankan law hierarchy.

### 2.3 Six specific objectives (SO1–SO6)

| ID | Objective | Proposal meaning |
|----|-----------|------------------|
| **SO1** | Domain-specific SLM + NL preprocessing | Fine-tuned model for Sri Lankan tax syntax, intent, entities, Singlish |
| **SO2** | Tax Knowledge Graph + GraphRAG | Neo4j graph of law relationships; retrieval traverses the graph |
| **SO3** | Lex Specialis priority logic | Newer/specific laws override older general provisions during retrieval |
| **SO4** | Agentic “Think Twice” loop | Draft answer → symbolic rule engine validates → self-correct if wrong |
| **SO5** | Proof Map / traceability | Visual paper trail from user input → law nodes → final advice |
| **SO6** | Experimental validation | Hallucination rate, legal consistency, traceability accuracy vs baselines |

### 2.4 Four architectural layers (from your proposal)

| Layer | Name | Purpose |
|-------|------|---------|
| 1 | Input & contextual preprocessing | Normalize query, extract entities |
| 2 | Cognitive core (NLU + retrieval) | Intent detection + GraphRAG over Tax KG |
| 3 | Reasoning engine | Generate advice + “Think Twice” symbolic validation |
| 4 | Transparent output | Verified answer + Proof Map |

### 2.5 Proposal work packages (WBS WP1–WP10)

| WP | Work package | Proposal deliverable |
|----|--------------|---------------------|
| WP1 | Requirement analysis | Scoped problem + plan |
| WP2 | Literature review | Research gap justification |
| WP3 | Tax Knowledge Graph + Lex Specialis | Neo4j graph with legal hierarchy |
| WP4 | Domain SLM fine-tuning + NLU | Intent/entity model on local tax language |
| WP5 | GraphRAG + priority logic | Graph-aware retrieval |
| WP6 | Think Twice + symbolic rules | Hallucination prevention |
| WP7 | Proof Map visualization | Auditable reasoning UI |
| WP8 | Evaluation | Metrics vs baseline LLMs |
| WP9 | Prototype + API | Working chatbot + FastAPI |
| WP10 | Thesis documentation | Final report |

**Timeline (proposal Gantt):** M1–M2 planning, M3–M4 graph/data, **M5–M7 core engine**, M8–M9 validation + proof maps, M10–M12 integration + thesis (deadline **March 2026**).

---

## 3. What exists in the repository today

The monorepo is organized so **your component spans several folders**, not only `backend/comp-language-model`.

### 3.1 Folder map (your areas of ownership)

| Path | What it is |
|------|------------|
| `backend/comp-language-model/` | **Your FastAPI microservice** (port **8004**) |
| `backend/api-gateway/` | Proxies `/api/v1/llm/**` → your service |
| `frontend/src/features/language-model/` | Dashboard UI for NLU + law query |
| `data/raw/ird/`, `data/processed/ird/` | IRD legal corpus (PDFs → JSONL; local, gitignored) |
| `knowledge_graph/` | Tax KG ontology, Neo4j schema, ETL, Lex Specialis specs |
| `scripts/ird_*`, `scripts/neo4j_*`, `scripts/phase2_*` | Corpus pipeline, KG loaders, evaluation |
| `evaluation/` | Benchmarks, frozen API contracts, experiment logs |
| `nlu/`, `retrieval/`, `reasoning/`, `ui/` | Workspace placeholders / future artifacts |
| `models/language-model/` | Planned location for SLM checkpoints |
| `docs/PHASES_RUNBOOK.md` | **Team runbook** — copy-paste commands for every phase |

### 3.2 Your backend service — live API endpoints

Service entry: `backend/comp-language-model/app/main.py`

| Endpoint | Purpose |
|----------|---------|
| `GET /health`, `GET /ready` | Health checks |
| `POST /api/v1/nlu/parse` | Intent prediction + retrieval hits + optional Neo4j context |
| `POST /api/v1/query` | Law-grounded citations + optional plain-language answer (Gemini) |

Via API gateway (port 8000):

- `POST /api/v1/llm/nlu/parse`
- `POST /api/v1/llm/query`

### 3.3 Key backend modules (what each file does)

| Module | Role |
|--------|------|
| `services/tfidf_chunk_index.py` | **Default retrieval** — TF-IDF over legal text chunks |
| `services/dense_chunk_index.py` | Optional **semantic retrieval** (sentence-transformers) |
| `services/intent_tfidf_centroid.py` | **Intent baseline** — TF-IDF centroid classifier |
| `services/corpus_chunk_texts.py` | Loads chunk text for citation excerpts |
| `services/corpus_chunk_kg_join.py` | Maps chunks → KG metadata (`section_uid`, `tier`, etc.) |
| `services/graph_service.py` | **Neo4j enrichment** — concepts, reliefs, rate bands, Lex overrides |
| `services/domain_gate.py` | Blocks off-topic / weak-match questions |
| `services/answer_synthesis.py` | Optional **Gemini** plain-language summary (grounded in citations) |

Configuration: `app/config.py` (env vars prefixed `COMP_LLM_*`, `NEO4J_*`).

### 3.4 Frontend (what you can demo today)

Under `frontend/src/features/language-model/`:

| Page | Route | What it shows |
|------|-------|---------------|
| NLU parse | `/language-model/nlu` | Predicted intent, retrieval hits, graph context panel |
| Law query | `/language-model/query` | Citations, relevance scores, optional synthesized answer, graph link map |

This is **not yet a multi-turn chatbot UI** — it is an **engineering demo** of retrieval + enrichment.

### 3.5 Data & knowledge base pipeline (Phase 1b + Phase 3)

**Already implemented as scripts + specs:**

1. **IRD corpus ingestion** — PDF/HTML → `corpus_v1.jsonl` with metadata (tier, instrument type, section labels).
2. **Source manifest** — `evaluation/ird/source_manifest_filled.csv` (committed snapshot).
3. **Tax Knowledge Graph ontology** — `knowledge_graph/ontology_v1.json` (8 node types, relationship types).
4. **Lex Specialis metadata** — authority classes, override paths, precedence rules.
5. **Neo4j loaders** — chunk nodes, curated edges, consolidated view anchors.
6. **NLU → graph maps** — entity and intent mapping JSON specs.
7. **Dense embedding bundles** — precomputed vectors for faster retrieval startup.

Runbook for all commands: **`docs/PHASES_RUNBOOK.md`**.

### 3.6 Evaluation infrastructure (Phase 2 — largely complete)

| Artifact | Purpose |
|----------|---------|
| `evaluation/phase2_task_registry.json` | Defines eval tasks (retrieval, intent, joint) |
| `evaluation/benchmark_seed_template.jsonl` | Seed benchmark rows |
| `evaluation/frozen/phase2_M5_baseline.json` | **Frozen production baseline** (TF-IDF + centroid intent) |
| `scripts/phase2_eval_*.py` | Retrieval, intent, joint metrics |
| `scripts/phase2_experiment_run.py` | Logs experiment runs to `phase2_runs.jsonl` |
| `.github/workflows/phase2-smoke.yml` | CI regression smoke tests |

**Frozen baseline (M5 gate):** TF-IDF passage retrieval + TF-IDF centroid intent over `corpus_v1`. Dense retrieval is implemented but **not promoted** as the shipping baseline until new experiment runs beat it.

---

## 4. Build status — honest assessment

Status is mapped to **your proposal objectives** and **internal repo phases**.

### 4.1 Summary scorecard

| Area | Proposal target | Repo reality | Status |
|------|-----------------|--------------|--------|
| Legal corpus & source governance | IRA + IRD docs ingested | Full pipeline + manifest; data is local | **~85%** |
| Tax Knowledge Graph (SO2) | Neo4j graph with law topology | Ontology, ETL, loaders, Lex metadata complete; **graph must be seeded on Neo4j** | **~75%** |
| NLU / domain SLM (SO1) | Fine-tuned BERT/Llama SLM | TF-IDF intent centroid + domain gate; **no fine-tuned SLM yet** | **~30%** |
| GraphRAG retrieval (SO2/SO5) | Graph traversal drives retrieval | Chunk TF-IDF/dense retrieval + **post-retrieval** graph enrichment | **~45%** |
| Lex Specialis in retrieval (SO3) | Priority ranking at retrieval time | Partial — in GraphService Cypher + KG metadata, not primary ranker | **~40%** |
| Think Twice + symbolic engine (SO4) | Agentic self-correction | `reasoning/` folder is **placeholder only** | **~5%** |
| Proof Map (SO5) | Visual auditable paper trail | Citations + graph panels in UI; **no dedicated Proof Map module** | **~35%** |
| Conversational chatbot | Multi-turn advisory UI | Two demo pages; **no chat session / memory API** | **~25%** |
| Answer generation | Grounded SLM responses | Optional Gemini summary over citations; **not your fine-tuned SLM** | **~30%** |
| Evaluation (SO6) | Hallucination, legal consistency, traceability | Phase 2 retrieval/intent/joint metrics; **missing proposal-specific legal eval** | **~40%** |
| API + integration (WP9) | FastAPI prototype | Service + gateway + frontend demo | **~70%** |
| Personalization (Comp A/B) | User financial profile in answers | **Not wired** into your API yet | **~0%** |

**Overall component completion (engineering vs proposal vision): ~45–50%**

You have a **strong foundation** (corpus, KG specs, retrieval API, eval harness, UI skeleton). The **research differentiators** from your proposal — neuro-symbolic validation, fine-tuned SLM, true GraphRAG ranking, Proof Maps, and formal legal evaluation — are **mostly still ahead**.

### 4.2 What is **done** (you can claim these in progress reports)

#### Phase 1 — Foundation ✅
- Repo structure, shared traceability schemas, service skeleton, health endpoints.

#### Phase 1b — IRD corpus pipeline ✅
- Download/manifest workflow, PDF/HTML extraction, QA reports, SQLite mirror.

#### Phase 2 — Retrieval + NLU baseline ✅ (M5 gate accepted)
- TF-IDF and dense chunk retrieval.
- TF-IDF centroid intent classification.
- Joint intent + retrieval evaluation scripts.
- `POST /api/v1/nlu/parse` and `POST /api/v1/query` with citation excerpts.
- Frozen API JSON schemas + contract tests.
- CI smoke tests + handoff report generator.
- Domain gate (off-topic filtering).

#### Phase 3 — Knowledge graph engineering ✅ (specs + loaders)
- Ontology v1.2.0, ETL bundles, Lex Specialis tagging.
- Neo4j constraints/indexes, chunk loader, curated edge loader.
- NLU entity/intent → graph mapping specs.
- Node embedding bundle pipeline.
- API returns KG join metadata on citations.

#### Phase 4 (partial) — Graph enrichment on API 🟡
- `GraphService` connects to Neo4j when `COMP_LLM_GRAPH_ENABLED=true`.
- Enriches NLU/query responses with concepts, reliefs, rate bands, Lex override notes.
- Frontend graph context / link map visualization.

#### Phase 4 (partial) — Optional answer synthesis 🟡
- Gemini-based plain answer when `synthesize_answer=true` and API key configured.
- Still **retrieval-grounded**, not the full Think Twice pipeline.

### 4.3 What is **not done** (gaps vs your proposal)

| Gap | Why it matters for your thesis |
|-----|--------------------------------|
| **Fine-tuned domain SLM (SO1)** | Core claim: specialized model beats general LLMs on Sri Lankan tax syntax |
| **True GraphRAG as primary retriever (SO2)** | Today retrieval is flat chunk search; graph is enrichment overlay |
| **Lex Specialis ranking in retrieval (SO3)** | Must automatically prefer 2025 amendments over 2017 base act |
| **Symbolic rule engine (SO4)** | Hard-coded tax brackets/procedures to catch math/legal errors |
| **Agentic “Think Twice” loop (SO4)** | Critic agent + regenerate until rule-compliant — **main novelty** |
| **Proof Map generator (SO5)** | Structured auditable path, not just citations list |
| **Multi-turn conversational API (FR9)** | Session memory for follow-up questions |
| **Singlish / multilingual preprocessing (FR1)** | Proposal explicitly mentions mixed-language queries |
| **Integration with Component A/B profile** | Personalized advice needs income/deduction context |
| **Proposal evaluation metrics (SO6)** | Hallucination rate, legal consistency score, traceability accuracy, adversarial tests |
| **Full chatbot UX** | Proposal describes primary conversational interface |

### 4.4 Internal roadmap not yet started (from runbook)

The team runbook lists future phases explicitly:

- **Phase 5** — Symbolic / Think Twice
- **Phase 6** — Proof map / UI

The `reasoning/` directory currently contains only a one-line README.

---

## 5. How the current system works (end-to-end)

Understanding the **actual** pipeline today helps you explain demos and plan upgrades.

```text
                    POST /api/v1/query  (or /nlu/parse)
                              │
                              ▼
                    ┌─────────────────┐
                    │  Domain gate    │  off-topic / weak match → empty response
                    └────────┬────────┘
                             │ in_domain
                             ▼
                    ┌─────────────────┐
                    │ Retrieval index │  TF-IDF or dense vectors over corpus_v1.jsonl
                    └────────┬────────┘
                             │ top-k chunk_ids + scores
                             ▼
                    ┌─────────────────┐
                    │ Citation build  │  chunk text + section_uid, tier, etc.
                    └────────┬────────┘
                             │
              ┌──────────────┴──────────────┐
              │ COMP_LLM_GRAPH_ENABLED      │
              ▼                             │
     ┌─────────────────┐                   │
     │ GraphService    │  Neo4j: concepts, reliefs, lex_notes, superseded_by
     │ (optional)      │                   │
     └────────┬────────┘                   │
              │                             │
              └──────────────┬──────────────┘
                             │
              ┌──────────────┴──────────────┐
              │ synthesize_answer=true      │
              ▼                             │
     ┌─────────────────┐                   │
     │ Gemini summary  │  optional; uses citations + graph context only
     └────────┬────────┘                   │
              │                             │
              └──────────────┬──────────────┘
                             ▼
                    JSON response to UI / gateway
```

**Important:** This is **retrieve-then-enrich**, not yet **graph-first GraphRAG** with **symbolic validation**.

---

## 6. How to run your component locally

All commands from repo root. See **`docs/PHASES_RUNBOOK.md`** for full detail.

### 6.1 One-time setup

```powershell
python -m venv .venv-backend
.\.venv-backend\Scripts\Activate.ps1
pip install -r backend/requirements.txt
copy .env.example .env
# Edit .env: corpus path, optional Neo4j password, optional Gemini key
```

Build corpus (if not already on disk):

```powershell
.\.venv-backend\Scripts\python.exe scripts/ird_phase1b_finalize.py `
  --manifest evaluation/ird/source_manifest_filled.csv `
  --files-root data/raw/ird/downloads `
  --corpus-jsonl data/processed/ird/corpus_v1.jsonl `
  --sqlite-db data/processed/ird/corpus_v1.sqlite `
  --qa-out data/processed/ird/extraction_qa_report.md `
  --skip-missing
```

### 6.2 Start your service (port 8004)

```powershell
$env:PYTHONPATH = "backend/comp-language-model;$PWD"
$env:COMP_LLM_CORPUS_JSONL = "data/processed/ird/corpus_v1.jsonl"
$env:COMP_LLM_INTENT_BENCHMARK_JSONL = "evaluation/benchmark_seed_template.jsonl"
# Optional Neo4j:
# $env:COMP_LLM_GRAPH_ENABLED = "true"
# $env:NEO4J_PASSWORD = "<password>"
.\.venv-backend\Scripts\python.exe -m uvicorn app.main:app `
  --app-dir backend/comp-language-model --reload --host 127.0.0.1 --port 8004
```

Test:

```powershell
curl -s -X POST http://127.0.0.1:8004/api/v1/query `
  -H "Content-Type: application/json" `
  -d "{\"question\":\"What is personal relief?\",\"top_k\":5}"
```

### 6.3 Start gateway + frontend (full UI demo)

```powershell
# Terminal 1 — gateway
$env:PYTHONPATH = "$PWD"
.\.venv-backend\Scripts\python.exe -m uvicorn app.main:app --app-dir backend/api-gateway --host 127.0.0.1 --port 8000

# Terminal 2 — frontend
cd frontend
npm install
npm run dev
```

Open: [http://127.0.0.1:5173/language-model/query](http://127.0.0.1:5173/language-model/query)

### 6.4 Run tests

```powershell
$env:PYTHONPATH = "backend/comp-language-model;$PWD"
.\.venv-backend\Scripts\python.exe -m pytest backend/comp-language-model/app/tests -q
```

Expect **21+ passing** tests; some dense-retrieval tests skip without `sentence-transformers`. A few stub tests may fail if environment differs — install optional deps from `backend/requirements-retrieval-dense.txt` if needed.

---

## 7. What you still need to build (prioritized roadmap)

Aligned with your proposal WBS and the gaps above. Order reflects **thesis novelty first**, then integration polish.

### Priority 1 — Core research differentiators (thesis-critical)

| # | Task | Maps to | Suggested approach in this repo |
|---|------|---------|--------------------------------|
| 1 | **Symbolic rule engine** | SO4, WP6 | Implement under `reasoning/` — Python rules for tax slabs, procedural steps; shared with Component B where possible |
| 2 | **Think Twice agentic loop** | SO4, WP6 | LangGraph/CrewAI: draft (Gemini or SLM) → extract claims → rule engine validates → regenerate |
| 3 | **Graph-first retrieval upgrade** | SO2, SO3, WP5 | Use `nlu_intent_graph_map_v1.json` Cypher templates + Lex precedence in ranker; not only post-hoc enrichment |
| 4 | **Fine-tuned intent/entity SLM** | SO1, WP4 | Train small classifier (DistilBERT/RoBERTa) on expanded benchmark in `nlu/`; replace TF-IDF centroid |
| 5 | **Proof Map module** | SO5, WP7 | Structured JSON trace + UI component in `frontend/` and `ui/` specs — path: query → chunks → sections → instruments → rule checks |

### Priority 2 — Product completeness

| # | Task | Maps to |
|---|------|---------|
| 6 | **Multi-turn chat API** | FR9 — session store, conversation history in prompts |
| 7 | **Singlish / normalization pipeline** | SO1, FR1 — preprocessing before NLU |
| 8 | **Full chatbot UI** | WP9 — replace two demo pages with conversational interface + Proof Map side panel |
| 9 | **Wire Component A/B context** | Dependencies in proposal — accept financial profile in query request |

### Priority 3 — Evaluation & thesis evidence (SO6, WP8)

| # | Task | Metrics from proposal |
|---|------|----------------------|
| 10 | **Hallucination rate study** | Compare your pipeline vs raw Gemini / ChatGPT on held-out legal Qs |
| 11 | **Legal consistency scoring** | Expert-reviewed answer set |
| 12 | **Traceability accuracy** | Does Proof Map cite the correct IRA section? |
| 13 | **Adversarial + multi-turn tests** | Edge cases, conflicting law scenarios |
| 14 | **Document experiment runs** | Append to `evaluation/phase2_runs.jsonl` + thesis tables |

### Priority 4 — Operations

| # | Task |
|---|------|
| 15 | Seed production Neo4j from full corpus + curated override edges |
| 16 | Promote dense retrieval (or graph retriever) via new M5 gate if metrics improve |
| 17 | Finalize WP10 thesis chapter aligning **built artifacts ↔ SO1–SO6** |

---

## 8. Mapping proposal functional requirements → repo

From your proposal Table 4 (FR1–FR10):

| FR | Requirement | Current status |
|----|-------------|----------------|
| FR1 | English + Singlish query input | Partial — free text accepted; no Singlish normalizer |
| FR2 | SLM intent + entity extraction | Partial — TF-IDF intent only; entities not extracted |
| FR3 | GraphRAG retrieval | Partial — chunk retrieval + graph enrichment |
| FR4 | Lex Specialis priority | Partial — in GraphService, not full retrieval ranker |
| FR5 | Conversational advisory generation | Partial — optional Gemini summary |
| FR6 | Think Twice loop | **Not implemented** |
| FR7 | Symbolic rule validation | **Not implemented** |
| FR8 | Proof Map generation | Partial — citations + graph link map |
| FR9 | Conversational context / memory | **Not implemented** |
| FR10 | Verified output + evidence nodes | Partial — citations + graph_context in API |

---

## 9. Dependencies on teammates

Your component **consumes** (does not replace):

| From | Data / service | Status |
|------|----------------|--------|
| Component A | Categorized transactions, taxable income inference | Separate service `comp-transaction-sementic` (port 8001) |
| Component B | Tax strategies, symbolic rules | `comp-tax-optimization` (port 8002) — potential shared rule engine |
| Shared | API gateway, PostgreSQL, frontend shell | Gateway live; DB used by other components |

For personalized advice, you will eventually pass user profile fields into your query pipeline — **this integration is not built yet**.

---

## 10. Key documents to read next

| Document | Why read it |
|----------|-------------|
| `docs/PHASES_RUNBOOK.md` | Every command for corpus, eval, Neo4j, API |
| `docs/language-model_phase1_architecture.md` | Phase 1 contracts and traceability |
| `docs/PHASE2_PLAN.md` | Evaluation tasks and milestones |
| `knowledge_graph/README.md` | KG ontology and loader overview |
| `evaluation/frozen/phase2_M5_baseline.json` | What “production baseline” means today |
| Your proposal PDF | SO1–SO6, architecture figure, WBS, Gantt |

---

## 11. Elevator pitch (for viva / demo)

> **Built:** We ingest Sri Lankan IRD legal sources into a versioned corpus, retrieve grounded law passages with TF-IDF/dense search, classify tax intent with a reproducible baseline, enrich answers from a Neo4j Tax Knowledge Graph with Lex Specialis override notes, expose everything through a FastAPI service and dashboard, and measure retrieval/intent quality with frozen benchmarks and CI smoke tests.

> **Still building:** A fine-tuned Sri Lankan tax SLM, graph-first GraphRAG ranking, an agentic Think Twice loop with a symbolic rule engine, visual Proof Maps, multi-turn conversational UX, personalized integration with transaction/strategy components, and formal hallucination/legal-consistency evaluation — which together deliver the neuro-symbolic, traceable advisory system promised in the research proposal.

---

## 12. Changelog

| Date | Notes |
|------|-------|
| 2026-08-15 | Initial guide created from proposal PDFs + repo inspection (`comp-language-model` v0.1.0, Phases 1–3 complete, Phase 4 partial). |

---

*Maintainer: Component C (IT22896186). Update this file when you complete Think Twice, Proof Maps, SLM fine-tuning, or promote a new retrieval baseline.*
