"""Function 3 — ML-assisted strategy ranking (post-compliance legal set only)."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Request, status
from starlette.status import HTTP_424_FAILED_DEPENDENCY

from tax_opt_b_app.config import get_component_settings
from tax_opt_b_app.routers.tax_opt_b_compliance import _maybe_search_explanations, _rules_pack_for_request
from tax_opt_b_app.services.tax_opt_b_financial_inputs_mapper import validate_relief_codes_used
from tax_opt_b_app.services.tax_opt_b_ml_ranking import (
    MlArtifactChecksumError,
    MlArtifactNotFoundError,
    MlFeatureVersionMismatchError,
)
from tax_opt_b_app.services.tax_opt_b_search_strategies_ml import search_strategies_ml_rank
from tax_opt_b_app.tax_opt_b_schemas_search_v1 import (
    TaxOptBSearchStrategiesMlRankRequestV1,
    TaxOptBSearchStrategiesResponseV1,
)

router = APIRouter(tags=["tax-opt-b-strategies-ml"])


@router.post(
    "/ml-rank",
    response_model=TaxOptBSearchStrategiesResponseV1,
    summary="ML-assisted rank over legal candidates (Function 3)",
)
def search_strategies_ml_rank_route(
    request: Request,
    body: TaxOptBSearchStrategiesMlRankRequestV1,
) -> TaxOptBSearchStrategiesResponseV1:
    pack = _rules_pack_for_request(request, body.tax_year)
    unknown = validate_relief_codes_used(body, pack.allowed_relief_codes)
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "Unknown or disallowed relief_code in deductions or investments "
                f"(not in active rules pack): {', '.join(repr(c) for c in unknown)}"
            ),
        )

    try:
        comp = get_component_settings()
        resp = search_strategies_ml_rank(
            body,
            pack,
            default_artifacts_root=comp.COMP_ML_ARTIFACTS_PATH,
            rules_version_label=comp.COMP_OPTIMIZATION_RULES_VERSION,
        )
    except MlArtifactNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except MlArtifactChecksumError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except MlFeatureVersionMismatchError as exc:
        raise HTTPException(
            status_code=HTTP_424_FAILED_DEPENDENCY,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    explanation_detail: Literal["summary", "detailed"] = body.explanation_detail
    return _maybe_search_explanations(
        resp,
        include_explanations=body.include_explanations,
        explanation_detail=explanation_detail,
    )
