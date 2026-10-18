# Component 3 — Results & Discussion (ICAC draft, one column)

> **Status:** Prose + interim figures ready. Table II is now populated from `reports/phase6_eval.json` (val split, n=1,500 profiles, 10 strategies). **Caveat:** this run predates the leakage-aware re-run flagged below — the near-ceiling ranking scores should be treated as an upper bound pending an independent relevance protocol, not as confirmed real-world predictive skill.

---

### B. *Personalized Recommendation*

Eligible Sri Lankan tax strategies are generated from a ten-entry rule catalog conditioned on the taxpayer profile, then ranked by a hybrid stack: LightGBM LambdaMART learning-to-rank, a multi-label adoption proxy, and linear multi-objective fusion, with multi-year outcomes projected by Monte Carlo simulation. Offline comparison is defined over catalog/rule priority, feasibility-only ranking, classical pair regressors, and the deployed LambdaMART configuration, reporting NDCG@5, NDCG@10, MAP@5, Precision@5, and adoption F1 (Table II). Fig. 3 shows the fusion weights used at inference; Fig. 4 summarizes the ablation order from rules through full hybrid impact.

**TABLE II. RANKING AND ADOPTION METRICS (SHARED EVAL PROTOCOL)**

| Method | NDCG@5 | NDCG@10 | MAP@5 | P@5 | Adoption F1 |
|--------|-------:|--------:|------:|----:|------------:|
| Catalog / rule priority | 0.690 | 0.773 | 0.756 | 0.368 | n/a¹ |
| Feasibility-only | 0.968 | 0.971 | 0.991 | 0.535 | n/a¹ |
| Pair regressor (HGB / RF)² | 0.992 | 0.994 | 0.986 | 0.531 | n/a¹ |
| LambdaMART + adoption + fusion (ours) | 0.990 | 0.992 | 0.985 | 0.530 | 0.772³ |

*Source: `reports/phase6_eval.json` (val split, n=1,500 profiles, 10 strategies), mapped as: Catalog/rule priority → "Catalog priority (rules)"; Feasibility-only → "Feasibility heuristic"; Pair regressor → "HistGradientBoosting pair regressor"; LambdaMART + fusion → "LightGBM LambdaMART (retrained)".*

¹ No adoption-classifier counterpart exists for this arm in the current JSON, so Adoption F1 cannot be reported without fabricating a figure.
² Only an HGB run is persisted in this evaluation; no separate RandomForest arm was found on disk (RF is imported in `scripts/evaluate_phase4_model_comparison.py` but not saved as a scored result).
³ Macro-F1 taken from the paired "LightGBM adoption (retrained)" classifier arm, not from the ranking arm itself — the current JSON does not compute a single fused Adoption F1 for the LambdaMART ranking row.

**Caveat (unresolved):** the ranking metrics above (NDCG/MAP/P@5) are near-ceiling and, per this file's own prior note, predate a leakage-aware re-run. Treat as provisional until that re-run is completed and confirms the scores are not an artefact of label leakage.

1) **Baseline vs learned ranking.** Rule and feasibility baselines provide eligible shortlists but do not optimize graded relevance across profile–strategy pairs; LambdaMART is the selected ranker for ordered recommendations under the planned offline protocol (NDCG/MAP/P@K).

2) **Hybrid fusion.** Final scores combine normalized tax savings, adoption probability, feasibility, and a risk penalty with weights 0.40 / 0.30 / 0.20 / 0.10 (Fig. 3), so recommendations balance fiscal gain against uptake and compliance risk rather than savings alone.

3) **Pipeline and evaluation honesty.** Ablation arms follow rules → feasibility → LambdaMART → adoption/fusion → Monte Carlo impact (Fig. 4). Experiments use synthetic Sri Lankan–like profiles; adoption labels are eligibility proxies rather than observed behaviour, and early near-ceiling ranking scores are treated as label-leakage risk—not as evidence of real-world predictive skill—pending an independent relevance protocol.

---

**Fig. 3.** Multi-objective fusion weights used by the recommendation scorer (savings, adoption, feasibility, risk penalty).

**Fig. 4.** Hybrid recommendation pipeline shown in ablation order from rule eligibility to Monte Carlo impact.

**Assets:** `models/personalized-recommendation/evaluation/figures/fig1_fusion_weights.*`, `fig2_hybrid_ablation_stages.*`
