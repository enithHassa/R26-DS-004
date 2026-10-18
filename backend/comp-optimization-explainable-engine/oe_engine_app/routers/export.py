"""POST /export/tax-return — multi-sheet Excel tax computation workbook."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import Response

from oe_engine_app.schemas.tax_return_export import TaxReturnExportRequest
from oe_engine_app.services.tax_return_export import build_tax_return_workbook

router = APIRouter(tags=["export"])

_XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.post("/export/tax-return")
def post_export_tax_return(body: TaxReturnExportRequest) -> Response:
    """Build a tax-return-style workbook from Profile + Comp1 + OE calculate data."""
    payload = build_tax_return_workbook(body)
    ya = (
        body.header.assessment_year_label
        or str(body.calculate_result.get("assessment_year") or "YA")
    ).replace("/", "-").replace(" ", "_")
    name = (body.header.full_name or "taxpayer").strip().replace(" ", "_")[:40]
    filename = f"Tax_Computation_{name}_{ya}.xlsx"
    return Response(
        content=payload,
        media_type=_XLSX_MEDIA,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
