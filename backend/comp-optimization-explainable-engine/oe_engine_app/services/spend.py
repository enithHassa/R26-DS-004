"""USD spend logger. Phase 6 seed caps do not apply to Phase 3 schema-validation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.shared.config.settings import PROJECT_ROOT

# gpt-4o list prices (USD per 1M tokens) — used for live logging, not billing.
GPT4O_INPUT_PER_M = 2.50
GPT4O_OUTPUT_PER_M = 10.00
PHASE6_SOFT_CAP_USD = 15.0
PHASE6_HARD_STOP_USD = 40.0


@dataclass
class SpendEvent:
    label: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    usd: float
    budget: str


@dataclass
class SpendLedger:
    budget: str = "phase3_schema_validation"
    prior_usd: float = 0.0
    events: list[SpendEvent] = field(default_factory=list)

    @property
    def this_run_usd(self) -> float:
        return sum(event.usd for event in self.events)

    @property
    def total_usd(self) -> float:
        return self.prior_usd + self.this_run_usd

    def record(
        self,
        *,
        label: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> SpendEvent:
        usd = (
            prompt_tokens / 1_000_000.0 * GPT4O_INPUT_PER_M
            + completion_tokens / 1_000_000.0 * GPT4O_OUTPUT_PER_M
        )
        event = SpendEvent(
            label=label,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            usd=usd,
            budget=self.budget,
        )
        self.events.append(event)
        print(
            f"spend {label}: ${usd:.4f}  "
            f"(prompt={prompt_tokens} completion={completion_tokens})  "
            f"running=${self.total_usd:.4f}  budget={self.budget}",
            flush=True,
        )
        self.assert_phase6_caps()
        return event

    def assert_phase6_caps(self) -> None:
        if self.budget != "phase6_seed":
            return
        if self.total_usd >= PHASE6_HARD_STOP_USD:
            raise RuntimeError(
                f"Phase 6 hard stop ${PHASE6_HARD_STOP_USD:.0f} reached "
                f"(running ${self.total_usd:.4f})"
            )

    def dump(self, path: Path | None = None) -> Path:
        out = path or (
            PROJECT_ROOT / "data" / "processed" / "opt-explain-engine" / "spend_log.jsonl"
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "at": datetime.now(timezone.utc).isoformat(),
            "budget": self.budget,
            "this_run_usd": round(self.this_run_usd, 6),
            "prior_usd": round(self.prior_usd, 6),
            "total_usd": round(self.total_usd, 6),
            "events": [
                {
                    "label": e.label,
                    "model": e.model,
                    "prompt_tokens": e.prompt_tokens,
                    "completion_tokens": e.completion_tokens,
                    "usd": round(e.usd, 6),
                }
                for e in self.events
            ],
        }
        with out.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload) + "\n")
        return out


def default_spend_log() -> Path:
    return PROJECT_ROOT / "data" / "processed" / "opt-explain-engine" / "spend_log.jsonl"


def load_phase6_prior(path: Path | None = None) -> float:
    log = path or default_spend_log()
    if not log.is_file():
        return 0.0
    total = 0.0
    for line in log.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("budget") != "phase6_seed":
            continue
        if "this_run_usd" in rec:
            total += float(rec["this_run_usd"] or 0)
            continue
        events = rec.get("events") or []
        total += sum(float(item.get("usd") or 0) for item in events)
    return total
