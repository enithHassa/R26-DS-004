"""Phase 6 seed gates: CLI flags, spend prior, hard stop, no 401 retry."""

from __future__ import annotations

from pathlib import Path

import pytest

from oe_engine_app.cli import main
from oe_engine_app.services.extract import run_extract
from oe_engine_app.services.extract_llm import _call_with_retry
from oe_engine_app.services.spend import (
    PHASE6_HARD_STOP_USD,
    SpendLedger,
    load_phase6_prior,
)


def test_full_extract_requires_seed_or_schema_validate() -> None:
    with pytest.raises(RuntimeError, match="or --seed"):
        run_extract(
            None,  # type: ignore[arg-type]
            source_doc_id="oee-act-14-2023",
            llm=None,
            ledger=SpendLedger(),
            dry_run=False,
            schema_validate=False,
            seed=False,
        )


def test_cli_extract_without_flags_is_blocked() -> None:
    assert main(["extract", "--source-doc-id", "oee-act-14-2023"]) == 2


def test_load_phase6_prior_sums_this_run_only(tmp_path: Path) -> None:
    log = tmp_path / "spend_log.jsonl"
    log.write_text(
        "\n".join(
            [
                '{"budget":"phase3_schema_validation","this_run_usd":0.13,"total_usd":0.13}',
                '{"budget":"phase6_seed","this_run_usd":1.25,"prior_usd":0,"total_usd":1.25}',
                '{"budget":"phase6_seed","this_run_usd":0.40,"prior_usd":1.25,"total_usd":1.65}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    assert load_phase6_prior(log) == pytest.approx(1.65)


def test_phase6_hard_stop_raises() -> None:
    ledger = SpendLedger(budget="phase6_seed", prior_usd=PHASE6_HARD_STOP_USD - 0.001)
    with pytest.raises(RuntimeError, match="hard stop"):
        ledger.record(
            label="over",
            model="gpt-4o",
            prompt_tokens=1_000_000,
            completion_tokens=0,
        )


def test_this_run_usd_excludes_prior() -> None:
    ledger = SpendLedger(budget="phase6_seed", prior_usd=2.0)
    ledger.record(label="a", model="gpt-4o", prompt_tokens=0, completion_tokens=0)
    assert ledger.this_run_usd == 0.0
    assert ledger.total_usd == pytest.approx(2.0)


class _BoomCompletions:
    def parse(self, **_kwargs: object) -> object:
        raise RuntimeError("Error code: 401 - Unauthorized")


class _BoomClient:
    def __init__(self) -> None:
        chat = type("Chat", (), {"completions": _BoomCompletions()})()
        self.chat = chat


def test_401_does_not_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr(
        "oe_engine_app.services.extract_llm.time.sleep",
        lambda seconds: sleeps.append(seconds),
    )
    with pytest.raises(RuntimeError, match="OPENAI_AUTH_FAILED"):
        _call_with_retry(_BoomClient(), "gpt-4o", messages=[])
    assert sleeps == []
