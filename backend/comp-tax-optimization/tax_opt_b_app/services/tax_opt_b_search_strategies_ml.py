"""Function 3 — ML-assisted ordering over **legal** strategy search results only."""

from __future__ import annotations

from pathlib import Path

from tax_opt_b_app.services.tax_opt_b_ml_features_v1 import (
    build_ml_feature_matrix_v1,
    build_ml_feature_matrix_v2,
)
from tax_opt_b_app.services.tax_opt_b_financial_strategy_presets import (
    relief_max_claim_amounts_by_code,
)
from tax_opt_b_app.services.tax_opt_b_ml_ranking import (
    MlFeatureVersionMismatchError,
    file_sha256_hex,
    load_ml_bundle_summary,
    load_ml_estimator,
    measure_predict_latency_ms,
)
from tax_opt_b_app.services.tax_opt_b_rules_loader import TaxOptBRulePack
from tax_opt_b_app.services.tax_opt_b_search_strategies import (
    apply_top_k_with_baseline_sticky,
    assemble_search_strategies_response,
    build_search_response_rows,
    evaluate_search_passing_rows,
    find_baseline_passing_row,
    rule_sort_key_for_passing_row,
    sort_passing_rows_rule_only,
)
from tax_opt_b_app.tax_opt_b_schemas_search_v1 import (
    TaxOptBSearchMlMetaV1,
    TaxOptBSearchStrategiesMlRankRequestV1,
    TaxOptBSearchStrategiesResponseV1,
    TaxOptBSearchStrategyRowV1,
)

COMPLIANCE_ASSERTION = (
    "All listed strategies passed deterministic Sri Lankan rules compliance and tax computation "
    "before ML-assisted reordering. Machine learning did not add candidates, change relief amounts, "
    "or replace rule-based tax outcomes."
)


def _artifacts_directory(body: TaxOptBSearchStrategiesMlRankRequestV1, default_root: Path) -> Path:
    raw = body.model_bundle_path
    if raw is None or not str(raw).strip():
        return default_root
    return Path(raw).expanduser().resolve()


def search_strategies_ml_rank(
    body: TaxOptBSearchStrategiesMlRankRequestV1,
    pack: TaxOptBRulePack,
    *,
    default_artifacts_root: Path,
    rules_version_label: str | None = None,
    preloaded_summary: object | None = None,
    preloaded_estimator: object | None = None,
) -> TaxOptBSearchStrategiesResponseV1:
    """Enumerate and tax-evaluate all grid points, then reorder **passing** rows with ML scores."""

    art_dir = _artifacts_directory(body, default_artifacts_root)
    summary = preloaded_summary if preloaded_summary is not None else load_ml_bundle_summary(art_dir)
    if body.feature_version is not None and body.feature_version != summary.feature_version:
        msg = (
            f"feature_version mismatch: request={body.feature_version!r} "
            f"artifact={summary.feature_version!r}"
        )
        raise MlFeatureVersionMismatchError(msg)

    estimator = preloaded_estimator if preloaded_estimator is not None else load_ml_estimator(art_dir, summary)

    evaluation = evaluate_search_passing_rows(body, pack, rules_version_label=rules_version_label)
    gross = evaluation.profile.annual_gross_income

    passing_sorted = sort_passing_rows_rule_only(
        list(evaluation.passing_rows),
        rank_by=body.rank_by,
        gross=gross,
    )
    if len(passing_sorted) > body.max_ml_candidates:
        msg = (
            f"{len(passing_sorted)} passing strategies exceed max_ml_candidates={body.max_ml_candidates}; "
            "raise the cap or narrow the grid."
        )
        raise ValueError(msg)

    rule_rank_by_id = {row[0].candidate_id: i + 1 for i, row in enumerate(passing_sorted)}
    baseline_row = find_baseline_passing_row(passing_sorted, evaluation.baseline_candidate_id)
    baseline_tax = baseline_row[2] if baseline_row is not None else None

    if summary.inference_matrix_layout == "v2_14_utility":
        claimed_amounts = relief_max_claim_amounts_by_code(evaluation.profile, evaluation.pack)
        X = build_ml_feature_matrix_v2(
            evaluation,
            passing_sorted,
            baseline_tax=baseline_tax,
            claimed_amounts=claimed_amounts,
        )
    else:
        X = build_ml_feature_matrix_v1(
            evaluation,
            passing_sorted,
            baseline_tax=baseline_tax,
            matrix_layout=summary.inference_matrix_layout,
        )
    scores_vec, latency_ms = measure_predict_latency_ms(estimator, X)
    score_by_id = {row[0].candidate_id: float(scores_vec[i]) for i, row in enumerate(passing_sorted)}

    ml_sorted = sorted(
        passing_sorted,
        key=lambda row: (
            -score_by_id[row[0].candidate_id],
            rule_sort_key_for_passing_row(row, body.rank_by, gross),
        ),
    )

    top = apply_top_k_with_baseline_sticky(
        ml_sorted,
        top_k=body.top_k,
        baseline_candidate_id=evaluation.baseline_candidate_id,
        baseline_row=baseline_row,
    )
    top.sort(
        key=lambda row: (
            -score_by_id[row[0].candidate_id],
            rule_sort_key_for_passing_row(row, body.rank_by, gross),
        ),
    )

    rows_out, top_rank_explanation = build_search_response_rows(
        top,
        evaluation=evaluation,
        rank_by=body.rank_by,
        include_result_detail=body.include_result_detail,
        baseline_tax=baseline_tax,
        baseline_row=baseline_row,
    )

    patched: list[TaxOptBSearchStrategyRowV1] = []
    for r in rows_out:
        rid = rule_rank_by_id[r.candidate_id]
        ms = score_by_id[r.candidate_id]
        patched.append(
            r.model_copy(
                update={
                    "rule_only_rank": rid,
                    "ml_score": f"{ms:.12g}",
                    "ml_assist_rank": r.rank,
                    "deterministic_rank": rid,
                },
            ),
        )

    est_path = (art_dir / summary.model_joblib).resolve()
    digest: str | None = summary.artifact_sha256 or file_sha256_hex(est_path)

    ml_meta = TaxOptBSearchMlMetaV1(
        model_id=summary.model_id,
        feature_version=summary.feature_version,
        training_timestamp=summary.training_timestamp,
        artifact_sha256=digest,
        artifact_path_used=str((art_dir / summary.model_joblib).resolve()),
        synthetic_training_data_disclaimer=summary.synthetic_training_data_disclaimer,
        compliance_assertion=COMPLIANCE_ASSERTION,
        inference_latency_ms=latency_ms,
        utility_alpha=summary.utility_alpha,
        optimization_objective_label=(
            f"Pareto utility (α={summary.utility_alpha}: {int(summary.utility_alpha * 100)}% tax savings, "
            f"{int((1 - summary.utility_alpha) * 100)}% liquidity efficiency)"
            if summary.utility_alpha is not None else None
        ),
    )

    return assemble_search_strategies_response(
        evaluation=evaluation,
        passing_sorted_rule=passing_sorted,
        rows_out=patched,
        top_rank_explanation=top_rank_explanation,
        rank_by=body.rank_by,
        baseline_row=baseline_row,
        baseline_tax=baseline_tax,
        rules_version_label=rules_version_label,
        optimization_mode="ml_assisted_grid_ranking",
        optimization_objective=(
            f"pareto_utility;alpha={summary.utility_alpha};rule_tie_break={body.rank_by}"
            if summary.inference_matrix_layout == "v2_14_utility"
            else f"ml_assisted_priority;rule_tie_break={body.rank_by}"
        ),
        ml_meta=ml_meta,
    )
