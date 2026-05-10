"""Protocol for deterministic explanation providers (template today; ML later)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Protocol, runtime_checkable

if TYPE_CHECKING:
    from tax_opt_b_app.tax_opt_b_schemas_compare_v1 import TaxOptBCompareStrategiesResponseV1
    from tax_opt_b_app.tax_opt_b_schemas_explainability_v1 import TaxOptBExplanationBundleV1
    from tax_opt_b_app.tax_opt_b_schemas_tax_computation_v1 import TaxOptBComputeTaxResponseV1


ExplanationDetail = Literal["summary", "detailed"]


@runtime_checkable
class ExplanationProviderV1(Protocol):
    """Produces user-facing narratives from existing engine DTOs."""

    @property
    def engine_id(self) -> str: ...

    def explain_compute_response(
        self,
        resp: TaxOptBComputeTaxResponseV1,
        *,
        detail: ExplanationDetail = "summary",
    ) -> TaxOptBExplanationBundleV1: ...

    def explain_compare_response(
        self,
        resp: TaxOptBCompareStrategiesResponseV1,
        *,
        detail: ExplanationDetail = "summary",
    ) -> TaxOptBExplanationBundleV1: ...


__all__ = ["ExplanationDetail", "ExplanationProviderV1"]
