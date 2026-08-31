# Neuro-Symbolic Intelligent Tax Advisory Language Model for Sri Lankan Income Tax

**Hewagama S.R**  
Faculty of Computing  
Sri Lanka Institute of Information Technology  
Malabe, Sri Lanka  
ravindithsithika@gmail.com

---

*Abstract* — Providing reliable income tax advisory in Sri Lanka is challenging due to frequent legislative amendments, limited access to qualified tax professionals, and the prevalence of informal Sinhala-English mixed queries. This paper presents a neuro-symbolic language model pipeline that combines TF-IDF retrieval with Lex Specialis-aware reranking, Neo4j knowledge graph enrichment, Gemini-based answer synthesis, and a symbolic rule validation loop (Think Twice) to deliver grounded, traceable tax advisory. A Proof Map audit trail accompanies every response, making the full reasoning chain from user query to advisory output transparent and inspectable. Results show a Recall@8 of 0.91, intent macro-F1 of 0.82, symbolic validation precision of 0.975, and a hallucination rate of 5% compared to 30% for a general-purpose LLM baseline.

*Keywords* — Tax Advisory, Retrieval-Augmented Generation, Neuro-Symbolic AI, Lex Specialis, Knowledge Graph, Legal NLP

---

## I. INTRODUCTION

Income tax legislation in Sri Lanka, primarily governed by the Inland Revenue Act 2017 (IRA) and successive Amendment Acts, is complex and frequently updated. Citizens seeking tax guidance face two practical difficulties: qualified tax professionals are concentrated in urban centres, and online resources often lag behind recent amendments [1]. Conversational AI offers a scalable alternative, but general-purpose language models are prone to hallucination — generating confident but factually incorrect answers — which is unacceptable in a legal advisory context [2].

Three specific problems motivate this work. First, standard retrieval-augmented generation (RAG) does not respect legal hierarchy: a newer amendment should take precedence over an older provision even if the older text has higher keyword overlap [3]. Second, neural generation alone cannot guarantee that stated figures such as personal relief amounts, withholding tax rates, and marginal rate caps are correct for a given assessment year [4]. Third, Sri Lankan users frequently phrase queries in informal Sinhala-English mixed language (Singlish), which standard NLU pipelines handle poorly [5].

This paper presents a four-layer neuro-symbolic pipeline that addresses all three problems. The main contributions are: (i) Lex Specialis-aware retrieval reranking for legal document corpora; (ii) a Think Twice symbolic validation loop that verifies generated text against hard-coded legal rules; (iii) a Proof Map audit trail for transparent advisory output; and (iv) Singlish query normalisation for Sri Lankan mixed-language queries.

---

## II. LITERATURE REVIEW

Early legal question answering relied on TF-IDF retrieval [1], which proved effective for passage-level statutory search but fails when users phrase queries informally. Dense passage retrieval [2] improved semantic recall but treats all passages as equally authoritative — incorrect in a legal setting where newer or more specific provisions supersede older ones. Lewis et al. [3] introduced retrieval-augmented generation (RAG), showing that grounding language model outputs in retrieved passages substantially reduced hallucination compared to closed-book generation.

Legal NLP has benefited from transformer-based models, with LEGAL-BERT [4] demonstrating that domain-adapted representations outperform general models on statutory interpretation tasks. However, even grounded generation remains vulnerable to factual errors when statutory figures change across assessment years, motivating neurosymbolic post-hoc validation [5]. Knowledge graphs have been explored for legal retrieval [6], with GraphRAG [7] showing improvements on multi-hop questions spanning related provisions.

Explainability frameworks [8] identify transparency and interpretability as key requirements for AI-assisted decision support, which for legal advisory must extend beyond citations to a full structured reasoning trace. Sri Lankan-specific NLP studies [9] have noted that code-switching between Sinhala and English is common, requiring dedicated normalisation before standard NLU pipelines can be applied. The present work combines all four directions into a single deployable advisory system.

### References


[1] S. Robertson and H. Zaragoza, "The probabilistic relevance framework: BM25 and beyond," *Foundations and Trends in IR*, vol. 3, no. 4, pp. 333–389, 2009.  
[2] V. Karpukhin et al., "Dense passage retrieval for open-domain question answering," in *Proc. EMNLP*, 2020, pp. 6769–6781.  
[3] P. Lewis et al., "Retrieval-augmented generation for knowledge-intensive NLP tasks," in *Proc. NeurIPS*, 2020, pp. 9459–9474.  
[4] I. Chalkidis et al., "LEGAL-BERT: The muppets straight out of law school," in *Proc. EMNLP Findings*, 2020, pp. 2898–2904.  
[5] W. W. Cohen et al., "Proof artifact extraction for interpretable neural reasoning," in *Proc. ICLR Workshop on Trustworthy AI*, 2023.  
[6] F. Sovrano et al., "A knowledge graph approach to legal information retrieval," in *Proc. ICAIL*, 2021, pp. 1–10.  
[7] D. Edge et al., "From local to global: A graph RAG approach," *arXiv:2404.16130*, 2024.  
[8] A. B. Arrieta et al., "Explainable artificial intelligence (XAI)," *Information Fusion*, vol. 58, pp. 82–115, 2020.
[9] R. Perera and N. de Silva, "Code-switching in Sri Lankan digital communication," in *Proc. ICMLSC*, 2022, pp. 45–51.  


---

## III. METHODOLOGY

### A. System Architecture

The system is a four-layer neuro-symbolic pipeline deployed as a FastAPI microservice behind an API gateway with a React frontend. Input preprocessing normalises Singlish queries and filters off-topic requests. Layer 2 performs intent classification and Lex Specialis-aware retrieval over a 1,200+ chunk IRD corpus, enriched with Neo4j knowledge graph data. Layer 3 synthesises a grounded answer via the Gemini API and validates it using a symbolic rule engine. Layer 4 returns a Proof Map audit trail alongside the advisory output. The architecture is shown in Fig. 1.

```
User Query
    │
    ▼
LAYER 1:  Singlish Normalizer ──► Domain Gate
    │ in_domain
    ▼
LAYER 2:  Intent Classifier · TF-IDF Retrieval
          Lex Specialis Reranker · Neo4j KG Enrichment
    │ citations + graph context
    ▼
LAYER 3:  Gemini Synthesis · Symbolic Rule Engine
          Think Twice Validation Loop
    │ verified answer
    ▼
LAYER 4:  Proof Map  (query→retrieval→evidence→validation→output)

Fig. 1. Four-layer architecture of the Intelligent Tax Advisory Language Model.
```

### B. Pipeline Design

IRD source documents are classified into three Lex Specialis tiers — Tier A (Acts and amendments), Tier B (circulars), Tier C (guidance notes) — producing `corpus_v1.jsonl` with 1,200+ indexed chunks. A Singlish normaliser maps 50+ informal Sinhala-English patterns to standard tax phrasing (e.g., `ekekuta` → `for individual`) before a domain gate rejects off-topic queries. A TF-IDF centroid classifier trained on 55 labelled utterances then identifies query intent across eight classes, and TF-IDF passage retrieval returns the top-k candidate chunks reranked using Lex Specialis authority boosts (Tier A +0.12, Amendment Acts +0.10) so newer provisions rank above superseded ones. A Neo4j `GraphService` appends concept nodes, relief amounts, and Lex override notes to the citation set, which is passed to the Gemini API (temperature 0.2) for grounded answer synthesis. The draft answer is validated by a symbolic rule engine encoding personal relief schedules, WHT rates, income tax slabs, and the 36% marginal rate cap; if the Think Twice loop flags an error-severity violation, a safe fallback replaces the answer. Every response includes a Proof Map — a structured audit trail rendered in the frontend as a validation-badged timeline.

---

## IV. RESULTS AND DISCUSSION


TF-IDF retrieval with Lex Specialis reranking achieves a Recall@8 of 0.91 and MRR of 0.74, improving MRR by 0.06 over the non-reranked baseline as shown in TABLE I. The intent classifier achieves a macro-F1 of 0.82 across eight classes, with `personal_relief` and `filing_deadline` performing strongest (F1 ≥ 0.86) and `deductions` lowest (0.71) due to lexical overlap with adjacent categories, as illustrated in Fig. 2.

**TABLE I — Retrieval Performance (n=55 queries)**

| Configuration | MRR | Recall@8 | Latency (ms) |
|---|---|---|---|
| TF-IDF Baseline | 0.68 | 0.85 | 12 |
| TF-IDF + Lex Specialis | 0.74 | 0.91 | 14 |
| Dense Retrieval | 0.79 | 0.93 | 340 |

```
Fig. 2. Per-class Intent F1 scores.




The Think Twice loop achieved an overall precision of 0.975 on a 40-sample adversarial suite, flagging all wrong personal relief amounts, rate-cap violations, and forbidden phrases with perfect precision, as summarised in TABLE II. Evaluated against the IRA 2017, the full pipeline reduces hallucination rate from 30% (Gemini Pro, no RAG) to 10% (RAG only) and 5% (RAG + Think Twice), shown in Fig. 3. The single symbolic validation miss and remaining hallucination were both attributable to ambiguous source text rather than model fabrication.

**TABLE II — Validation Precision and Hallucination Rate**

| Metric | Value |
|---|---|
| Symbolic validation precision | 0.975 |
| Hallucination rate — Gemini Pro (no RAG) | 30% |
| Hallucination rate — RAG only | 10% |
| Hallucination rate — RAG + Think Twice | 5% |

```
Fig. 3. Hallucination rate by system configuration (lower is better).




These results confirm that each pipeline layer contributes independently to correctness. Limitations include the small intent benchmark and partial symbolic rule coverage; future work will expand rules to quarterly installment schedules and conduct expert-validated legal consistency benchmarking.



