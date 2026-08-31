# Adaptive Tax RAG — Acceptance checklist (Phases 5–11)

Status as of corpus rebuild + Phase 11 scaffold. Wire into live calculate is **out of scope**.

## Architecture terminology

| | |
|---|---|
| **CURRENT** | RAG → evidence + explain \| Rule Engine → calculate |
| **FUTURE** | RAG → LegalRuleEvidence → human approval → Rule Engine |
| **Not this phase** | Calling this “RAG calculation”; auto-merge into param packs; Neo4j executable edges from RAG; GPT rewriting calculator logic |

## Checklist

| # | Deliverable | Status |
|---|---|---|
| 1 | Before/after section metadata coverage | Done — see [`rag_legal_coverage.md`](rag_legal_coverage.md) (18.33% → 99.5% `section_ref`) |
| 2 | Chunk counts before/after | Done — 1260 → 3421 |
| 3 | Coverage Sec 2/5/6/7/8/11/16/52/89 + First Schedule | Done — all PASS (operative + YA) |
| 4 | YA 2024/25 vs 2025/26 coverage | Done — per-section YA counts in coverage report |
| 5 | Retrieval + citation-correctness per required section (incl. Sec 52(4) when cited) | Done — citation PASS/FAIL in coverage; gold eval in [`RESULTS.md`](RESULTS.md) |
| 6 | Example retrieved chunks for Sec 5 and Sec 52 / 52(4) (split continuity) | Done — examples in coverage report |
| 7 | Guide / Master excluded | Done — blocked from explain Chroma |
| 8 | Corpus build completed without GPT; GPT enrich not auto-run | Done — `gpt_assisted=0`; enrich script manual-only |
| 9 | Full relevant pytest | Run component tests for adaptive-tax Phase 7–11 |
| 10 | Calculate behavior unchanged; Rule Engine sole calculator | Done — architecture guard + calc tests |
| 11 | Continuations retain `section_ref` / `paragraph_ref` / `parent_provision_id` | Done — corpus + Chroma metadata |
| 12 | YA precedence beats raw similarity | Done — `legal_authority` ranking |
| 13 | Gold set P@3 / R@3 before vs after | Done — **13.33% / 36%** → **52% / 72%** |
| 14 | LegalRuleEvidence schema = structured legal evidence (not RAG calc); non-executable; human-approval path documented; no silent RAG→calc | Done — Phase 11a schema, 11b stub review, 11c optional bundle candidates |

## Phase 11 path (documented stub)

```text
RAG finds provision
  → LegalRuleEvidence (structured legal evidence)
  → Human/admin validation
  → RAG-grounded rule candidate approved
  → (future) Incorporated into calculation engine
```

Code:

- Schema: `backend/comp-adaptive-tax/adaptive_tax_app/schemas/legal_rule_evidence.py`
- Approval stub: `.../services/legal_rule_evidence_review.py`
- Explain emission: `.../services/legal_rule_evidence_emit.py` → `EvidenceBundle.legal_rule_evidence`

## Explicitly out of scope (stop here)

- Live `POST /calculate` wiring of approved candidates
- Default GPT enrich in corpus rebuild (run later manually only if `needs_review` remain)
