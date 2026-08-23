# Component 3 — Results & Discussion (ICAC draft, one column)

> **Status:** Prose + interim figures ready. Metric cells in Table II are placeholders until Phase-6 JSON is produced (do **not** paste the old ~99.9% anecdote).

---

### B. *Personalized Recommendation*

Eligible Sri Lankan tax strategies are generated from a ten-entry rule catalog conditioned on the taxpayer profile, then ranked by a hybrid stack: LightGBM LambdaMART learning-to-rank, a multi-label adoption proxy, and linear multi-objective fusion, with multi-year outcomes projected by Monte Carlo simulation. Offline comparison is defined over catalog/rule priority, feasibility-only ranking, classical pair regressors, and the deployed LambdaMART configuration, reporting NDCG@5, NDCG@10, MAP@5, Precision@5, and adoption F1 (Table II). Fig. 3 shows the fusion weights used at inference; Fig. 4 summarizes the ablation order from rules through full hybrid impact.

**TABLE II. RANKING AND ADOPTION METRICS (SHARED EVAL PROTOCOL)**

| Method | NDCG@5 | NDCG@10 | MAP@5 | P@5 | Adoption F1 |
|--------|-------:|--------:|------:|----:|------------:|
| Catalog / rule priority | — | — | — | — | — |
| Feasibility-only | — | — | — | — | — |
| Pair regressor (HGB / RF) | — | — | — | — | — |
| LambdaMART + adoption + fusion (ours) | — | — | — | — | — |

*Em dashes: fill from `reports/phase6_eval.json` after a leakage-aware re-run; do not use prior near-perfect scores.*

1) **Baseline vs learned ranking.** Rule and feasibility baselines provide eligible shortlists but do not optimize graded relevance across profile–strategy pairs; LambdaMART is the selected ranker for ordered recommendations under the planned offline protocol (NDCG/MAP/P@K).

2) **Hybrid fusion.** Final scores combine normalized tax savings, adoption probability, feasibility, and a risk penalty with weights 0.40 / 0.30 / 0.20 / 0.10 (Fig. 3), so recommendations balance fiscal gain against uptake and compliance risk rather than savings alone.

3) **Pipeline and evaluation honesty.** Ablation arms follow rules → feasibility → LambdaMART → adoption/fusion → Monte Carlo impact (Fig. 4). Experiments use synthetic Sri Lankan–like profiles; adoption labels are eligibility proxies rather than observed behaviour, and early near-ceiling ranking scores are treated as label-leakage risk—not as evidence of real-world predictive skill—pending an independent relevance protocol.

---

**Fig. 3.** Multi-objective fusion weights used by the recommendation scorer (savings, adoption, feasibility, risk penalty).

**Fig. 4.** Hybrid recommendation pipeline shown in ablation order from rule eligibility to Monte Carlo impact.

**Assets:** `models/personalized-recommendation/evaluation/figures/fig1_fusion_weights.*`, `fig2_hybrid_ablation_stages.*`
