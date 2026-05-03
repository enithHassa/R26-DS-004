"""ML package for Component 3 — Personalized Recommendation & Predictive Impact.

This package is the home of every model artifact that belongs to Component 3:
synthetic data generation, feature engineering, learning-to-rank training,
offline evaluation, and Monte Carlo impact simulation.

It is intentionally separate from the FastAPI service under
``backend/comp-personalized-recommendation``. The service imports trained
artifacts from :data:`ComponentSettings.COMP_RECOMMENDATION_ARTIFACTS_DIR`
at runtime; the service package itself never contains model training code.
"""
