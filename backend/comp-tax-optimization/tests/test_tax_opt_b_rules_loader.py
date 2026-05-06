"""Loader validation: parse errors, malformed structures, file I/O edge cases."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from tax_opt_b_app.services.tax_opt_b_rules_loader import (
    load_tax_opt_b_rules,
    parse_tax_opt_b_rules_dict,
)


def _minimal_valid_raw() -> dict:
    return {
        "schema_version": "1",
        "assessment_year": "2024_25",
        "currency": "LKR",
        "thresholds": {
            "personal_relief_annual": 1_200_000,
            "apit_slabs": [{"upper": 100, "rate": 0.06}, {"upper": None, "rate": 0.36}],
            "deductions": {
                "life_insurance_premium_cap_annual": 100_000,
                "charitable_donations_cap_pct_of_taxable": "0.33",
                "retirement_contribution_cap_pct_of_income": "0.15",
                "retirement_contribution_cap_annual": 600_000,
            },
        },
        "allowed_relief_codes": ["life_insurance_premium"],
        "rules": [
            {"rule_id": "y1", "type": "tax_year_match", "description": "", "reference": ""},
            {"rule_id": "u1", "type": "unknown_relief_code", "description": "", "reference": ""},
            {
                "rule_id": "c1",
                "type": "deduction_cap",
                "description": "",
                "reference": "ref",
                "message": "over",
                "relief_code": "life_insurance_premium",
                "cap_field": "life_insurance_premium_cap_annual",
            },
        ],
    }


def test_parse_rejects_missing_assessment_year() -> None:
    with pytest.raises(ValueError, match="assessment_year"):
        parse_tax_opt_b_rules_dict(
            {
                "schema_version": "1",
                "currency": "LKR",
                "thresholds": {
                    "personal_relief_annual": 1,
                    "apit_slabs": [{"upper": 1, "rate": 0.1}],
                    "deductions": {"x": 1},
                },
                "allowed_relief_codes": ["a"],
                "rules": [{"rule_id": "r1", "type": "tax_year_match", "reference": ""}],
            }
        )


def test_parse_rejects_empty_rules() -> None:
    with pytest.raises(ValueError, match="rules"):
        parse_tax_opt_b_rules_dict(
            {
                "schema_version": "1",
                "assessment_year": "2024_25",
                "currency": "LKR",
                "thresholds": {
                    "personal_relief_annual": 1,
                    "apit_slabs": [{"upper": 1, "rate": 0.1}],
                    "deductions": {"x": Decimal("1")},
                },
                "allowed_relief_codes": ["a"],
                "rules": [],
            }
        )


def test_parse_rejects_empty_allowed_relief_codes() -> None:
    raw = _minimal_valid_raw()
    raw["allowed_relief_codes"] = []
    with pytest.raises(ValueError, match="allowed_relief_codes"):
        parse_tax_opt_b_rules_dict(raw)


def test_parse_rejects_rule_row_missing_rule_id() -> None:
    raw = _minimal_valid_raw()
    raw["rules"] = [
        {"type": "tax_year_match", "description": "", "reference": ""},
    ]
    with pytest.raises(ValueError, match="rule_id"):
        parse_tax_opt_b_rules_dict(raw)


def test_parse_rejects_rule_row_missing_type() -> None:
    raw = _minimal_valid_raw()
    raw["rules"] = [
        {"rule_id": "x1", "description": "", "reference": ""},
    ]
    with pytest.raises(ValueError, match="type"):
        parse_tax_opt_b_rules_dict(raw)


def test_parse_rejects_rule_row_not_mapping() -> None:
    raw = _minimal_valid_raw()
    raw["rules"] = ["not-a-dict"]
    with pytest.raises(ValueError, match=r"rules\[0\]"):
        parse_tax_opt_b_rules_dict(raw)


def test_parse_rejects_root_not_mapping() -> None:
    with pytest.raises(TypeError, match="mapping"):
        parse_tax_opt_b_rules_dict([])  # type: ignore[arg-type]


def test_parse_minimal_pack_roundtrip() -> None:
    pack = parse_tax_opt_b_rules_dict(_minimal_valid_raw(), path=None)
    assert pack.assessment_year == "2024_25"
    assert pack.allowed_relief_codes == frozenset({"life_insurance_premium"})
    assert pack.thresholds.deductions["life_insurance_premium_cap_annual"] == Decimal("100000")


def test_load_tax_opt_b_rules_rejects_non_mapping_yaml(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text("- not: a mapping root\n", encoding="utf-8")
    with pytest.raises(ValueError, match="mapping"):
        load_tax_opt_b_rules(path)


def test_load_tax_opt_b_rules_file_not_found(tmp_path: Path) -> None:
    missing = tmp_path / "nope.yaml"
    with pytest.raises(FileNotFoundError):
        load_tax_opt_b_rules(missing)


def test_load_tax_opt_b_rules_invalid_thresholds(tmp_path: Path) -> None:
    path = tmp_path / "bad2.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "schema_version": "1",
                "assessment_year": "2024_25",
                "currency": "LKR",
                "thresholds": {},
                "allowed_relief_codes": ["x"],
                "rules": [{"rule_id": "r", "type": "tax_year_match", "description": "", "reference": ""}],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="personal_relief_annual"):
        load_tax_opt_b_rules(path)


def test_evaluate_compliance_pure_no_http() -> None:
    """Engine uses only injected pack (no file I/O inside evaluate)."""
    from tax_opt_b_app.services.tax_opt_b_compliance_engine import evaluate_compliance
    from tax_opt_b_app.tax_opt_b_schemas_profile_v1 import TaxOptBProfileV1
    from tax_opt_b_app.tax_opt_b_schemas_strategy_v1 import TaxOptBStrategyProposalV1

    pack = parse_tax_opt_b_rules_dict(_minimal_valid_raw(), path=None)
    profile = TaxOptBProfileV1(tax_year="2024_25", annual_gross_income=Decimal("1000000"))
    strategy = TaxOptBStrategyProposalV1.model_validate(
        {"claims": [{"relief_code": "life_insurance_premium", "claimed_amount_annual": "50000"}]}
    )
    result = evaluate_compliance(profile, strategy, pack)
    assert result.passed is True
    assert result.violations == []
