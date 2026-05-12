"""SHAP explainability for Function 3 ML ranking — TreeExplainer for sklearn Pipelines."""

from __future__ import annotations

from typing import Any

import numpy as np
import shap


def compute_shap_values(
    estimator: Any,
    X: np.ndarray,
) -> tuple[np.ndarray, float]:
    """Return ``(shap_values, base_value)`` for the full passing-strategy matrix.

    ``estimator`` is a sklearn Pipeline (SimpleImputer → StandardScaler → tree model).
    TreeExplainer is applied to the final step; X is transformed through all prior steps
    before SHAP computation so values are in the model's native feature space.

    Returns:
        shap_values: ndarray of shape (n_strategies, n_features)
        base_value:  float — expected model output over the training background
    """
    # Separate preprocessing steps from final tree model
    has_pipeline = hasattr(estimator, "steps")
    if has_pipeline:
        final_model = estimator[-1]
        X_transformed = estimator[:-1].transform(X)
    else:
        final_model = estimator
        X_transformed = X

    explainer = shap.TreeExplainer(final_model)
    shap_vals = explainer.shap_values(X_transformed)

    # shap_vals may be a list (multi-output) — take first element if so
    if isinstance(shap_vals, list):
        shap_vals = shap_vals[0]

    base_value = float(
        explainer.expected_value[0]
        if hasattr(explainer.expected_value, "__len__")
        else explainer.expected_value
    )
    return np.asarray(shap_vals, dtype=np.float64), base_value


__all__ = ["compute_shap_values"]
