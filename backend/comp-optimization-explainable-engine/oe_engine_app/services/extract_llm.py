"""GPT-4o two-pass structured extract. Pass-2 is a verbatim check, not legal advice."""

from __future__ import annotations

import time
from typing import Any, Protocol

from pydantic import BaseModel, Field

from oe_engine_app.services.quote_gate import pass2_window
from oe_engine_app.services.spend import SpendLedger

DEFAULT_MODEL = "gpt-4o"

PASS1_SYSTEM_ACT = """You are a Sri Lankan Inland Revenue Act extraction analyst.

You are given a focus window copied verbatim from ONE official Act PDF.
Extract, from that window ONLY:

1. reliefs — personal relief, deductions, qualifying payments, relief caps.
2. rate_bands — tax rates stated in the window. That includes:
   - progressive income tax slabs (lower, upper, rate), and
   - a specific rate that is not a slab (e.g. a dividend rate) even when
     lower/upper are blank. Still emit it.
   `applies_to` names the taxpayer class copied from the window
   (e.g. "resident or non-resident individual", "a company",
   "Employees' Trust Fund", "a person"). Never guess.

When the Target provision is the Fifth Schedule (or an amendment of it):
- Paragraph 1 lists QUALIFYING PAYMENTS. Emit ONE relief row per distinct
  category or sub-item, even when the word "relief" is absent.
- Paragraph 2 lists RELIEFS. Emit one row per lettered item / dated amount.
- Do not skip paragraph 1 in favour of paragraph 2.
- When one lettered item lists roman sub-items ((i), (ii), (iii)) and each
  sub-item names its own rupee figure, emit ONE row per sub-item. Each row
  quotes only its own sub-item and carries only that sub-item's figure. Never
  merge the sub-items into a single row with one shared or empty amount.

Hard rules for `quote` (a downstream checker re-tests this mechanically):
- `quote` MUST be ONE contiguous run of characters copied from the window,
  character-for-character. Never paraphrase, never repair typos, never reorder,
  never delete words from the middle, never join text across an ellipsis.
- Whitespace inside the quote is normalized before checking.
- Aim for 15-300 characters.

If — and only if — a row comes from a table:
- Use the "Tables on these pages" block, where each line is one table row with
  cells separated by " | ". Quote a whole line from that block (header plus
  that one body row is allowed). Never join two body rows.
- Quote the line exactly as printed in that block, including " | ". Do not
  rebuild the row from the wrapped prose above or below the block.

Amendment Acts still contain extractable rows. If the window substitutes
or inserts a schedule paragraph that states a relief cap, a tax rate, or a
slab, emit those rows from the substituted wording. Wrapping "hereby
amended" sentences and commencement tables are not themselves rows.
When a new First Schedule subparagraph inserts a full taxable-income table,
emit ONE rate_band per body row of that table (lower, upper, rate).
When a Fifth Schedule item states a dated personal-relief amount, emit it.
When the window substitutes a Fifth Schedule paragraph 1 donee or category
item (even with no rupee cap), emit that qualifying-payment row.
When a subsection states that a qualifying payment which cannot be deducted
"shall be carried forward and deducted", emit ONE relief row (cap_amount
empty, unit `text`). Do not skip it because there is no rupee figure.
When a capital allowance is stated as a percent of investment with a USD
threshold, emit it as a relief.

An empty result is valid and expected when the window has no real
extractable relief or rate_band. Never fabricate, infer, or force an entity
into a window to avoid an empty array. A quote-gate rejection must stand.
Preferring a non-empty extract is not a reason to invent content.

Relief fields:
- `paragraph_ref`: schedule paragraph / lettered item (e.g. "2(a)", "1(a)(iia)").
- `eligibility.text`: who qualifies, copied in substance from the window.
- `eligibility.quote`: a contiguous quote backing that eligibility sentence.
- `required_evidence`: documents the Act requires, or [] if none stated.
- `filing_line`: return/schedule line if stated, else "".
- `stacking`: whether this relief stacks with others, if stated, else "".
- `cap_amount`: digits only, no commas or currency symbol. "" if none.
  "not exceeding Rs. X" / "up to Rs. X" is a ceiling: cap_amount is X.
  "not less than Rs. X" / "at least Rs. X" is an entry threshold, not a
  ceiling: leave cap_amount "" and state the threshold in eligibility.text.
- `unit`: exactly `lkr`, `percent`, or `text` (never "currency").
- `compare_group_id`: snake_case stable id (e.g. personal_relief).
- Taxpayer-facing drafts (an auditor will edit these before they appear):
  `question_prompt` is a short question. Do not restate `display_name`. Do
  not copy year of assessment, commencement dates, rupee caps, or eligibility
  from the quote into the question. Dates go in `effective_from`. Caps go in
  `cap_amount`. Good: "What is your personal relief amount?" Bad: "What is
  your personal relief amount for the year of assessment commencing on April
  1, 2026?". Good: "Did you incur qualifying expenditure for digital
  productivity equipment?". `input_kind` is notice (auto-applied, no claim),
  yes_no_amount, amount, or boolean. `help` is one extra hint, or "". It must
  not repeat the question. Never put a rupee amount, percent, rate band, or
  Act quote into display_name, question_prompt, or help.
  Do not emit a second relief for a definition, qualifying-asset example, or
  restated cap of a relief already named in this window. One row per
  compare_group_id per dated amount. Reuse personal_relief /
  digital_productivity_equipment_relief when the same relief is reprinted.
- Numbers: digits only ("1200000", "6").
- `effective_from` / `effective_to`: YYYY-MM-DD when the quote states dates.
  "prior to 1 January 2020" → `effective_to` = 2019-12-31 (open start).
  "commencing on or after" / "commencing from" / "commencing on" /
  "on or after" / "with effect from" a date → `effective_from` that date.
  If no date is stated, use "".
- If a value is not stated, use "" — never guess.
- If one paragraph states two caps or two rates for two parts of the same
  year of assessment (e.g. "Rs. X for first nine months and Rs. Y for second
  three months", or a first-six-months rate and a second-six-months rate),
  emit TWO rows — one per stated amount — each with its own effective_from /
  effective_to for that part of the year. Never average the two figures,
  never drop one of them, never assign a single cap to the whole year.
- If one sentence states two rates for two date ranges (e.g. "40%, prior to
  April 1, 2025; and 45%, with effect from April 1, 2025", or "5% … prior to
  April 1, 2025" and "10% … with effect from April 1, 2025"), emit TWO
  rate_band rows — one per rate — each with its own effective_from /
  effective_to. Never keep only one of the two rates.
- Do not use outside knowledge. The window is the only source.
"""

PASS1_SYSTEM_GUIDE = """You extract taxpayer-facing help from an Inland Revenue Guide.

You are given a focus window copied verbatim from ONE official Guide PDF.
Emit guide_help rows only. These notes are labelled "Guide" in the interview.
They NEVER set a cap, rate, or slab. The Act year tables already hold those
numbers. Never emit relief or rate_band kinds. Never emit cap_amount.

From the window ONLY, explain how a resident individual uses a relief that
the window actually discusses. Pair each row to one of these compare_group_id
values (exact spelling):

- personal_relief
- employment_income_relief
- rental_income_relief
- senior_citizen_interest_income_relief
- foreign_currency_income_relief
- donation_to_charitable_institution
- donation_to_government_or_approved_fund
- solar_panel_relief
- qualifying_payment_carry_forward
- capital_allowance

If the window is an example or a "how to apply" paragraph, still emit a help
row for the relief it illustrates. One row per compare_group_id per window is
enough; do not duplicate the same group with the same quote.

Hard rules for `quote` (a downstream checker re-tests this mechanically):
- `quote` MUST be ONE contiguous run of characters copied from the window,
  character-for-character. Never paraphrase, never repair typos, never reorder,
  never delete words from the middle.
- Whitespace inside the quote is normalized before checking.
- Aim for 15-300 characters.

`help`: 1-4 sentences a taxpayer can use. If a rupee figure appears in the
window, you MAY repeat it inside help/quote as wording, and you MUST say that
the Guide is describing the figure — it is not the engine cap. Do not present
a Guide rupee figure as the current legal cap.
`eligibility.text`: who qualifies, in substance from the window.
`eligibility.quote`: a contiguous quote backing that sentence.
`required_evidence`: only documents the window names (invoice, declaration,
certificate). If none are named, use []. Never invent a document.

Do NOT emit:
- company, partnership, trust, NGO, or unit-trust help
- First Schedule rate tables or progressive slabs as if they were current caps
- terminal-benefit / employment-commutation tables
- withholding / transfer-pricing / assessment procedure notes

An empty result is valid when the window has no individual-relief help.
Never fabricate. Do not use outside knowledge.
"""

PASS1_SYSTEM_CONSOLIDATED = """You extract cross-check facts from a Consolidated Act PDF.

You are given a focus window copied verbatim from ONE official Consolidated PDF.
Emit consolidated_fact rows only. These facts are a mismatch cross-check against
already-compiled Act year tables. They are NEVER year-table caps. Never emit
relief or rate_band kinds.

From the window ONLY, extract individual-facing facts that have a stated rupee
cap, a percent relief, or an individual progressive rate ladder:

- personal_relief (Fifth Schedule paragraph 2(a) dated amounts)
- donation_to_charitable_institution (individual 75,000 cap in paragraph 1(a)(iia))
- employment_income_relief
- rental_income_relief (value is the percent digits only, e.g. "25")
- senior_citizen_interest_income_relief
- foreign_currency_income_relief
- solar_panel_relief
- qualifying_payment_carry_forward (only if the window states a qualifying
  payment that cannot be deducted shall be carried forward)
- first_schedule_rates (individual progressive ladder only)

Hard rules for `quote` (a downstream checker re-tests this mechanically):
- `quote` MUST be ONE contiguous run of characters copied from the window,
  character-for-character. Never paraphrase, never repair typos, never reorder,
  never delete words from the middle, never join text across an ellipsis.
- Whitespace inside the quote is normalized before checking.
- Aim for 15-300 characters.
- If — and only if — a row comes from a table: quote a whole line from the
  "Tables on these pages" block, cells separated by " | ". Never join two
  body rows. Do not rebuild the row from wrapped prose.

`year` is always `YYYY_YY` for a Sri Lanka year of assessment (April–March).
Engine years you may emit: 2018_19, 2019_20, 2020_21, 2021_22, 2022_23,
2023_24, 2024_25, 2025_26. Never emit 2026_27 — there is no YA 2026/27
catalog. Emit ONE fact per (compare_group_id, year).
Map date phrases to those years:
- "year of assessment prior to January 1, 2020" → 2018_19 and 2019_20
- "commencing on or after January 1, 2020, but prior to April 1, 2022"
  → 2020_21 and 2021_22
- the year of assessment commencing on April 1, 2022 (including "first nine
  months" / "second three months") → 2022_23 only
- "commencing on or after April 1, 2023, but prior to April 1, 2025"
  → 2023_24 and 2024_25
- "commencing on or after April 1, 2025" → 2025_26 only (not 2026_27)
- "commencing on or after April 1, 2018 but ... prior to January 1, 2020"
  (First Schedule individual ladder) → 2018_19 and 2019_20
If one paragraph states two personal-relief amounts for two parts of the same
year of assessment, emit ONE personal_relief fact for that year using the
first-period amount (e.g. Rs. 2,250,000 for 2022_23). Never average, never
emit 300,000 as a separate year.
If a continuing undated individual cap is stated with no end date (charitable
donation 75,000; rental 25 percent), emit that fact for each engine year
2018_19 through 2025_26.
If a relief is expressly ended ("prior to January 1, 2020", "up to December 31,
2019"), emit it only for the years that phrase covers — do not copy it forward.

`value`:
- Rupee caps: digits only, no commas or "Rs." ("1800000", "75000").
- Percents: digits only ("25").
- first_schedule_rates: join the individual slab percents for THAT dated
  ladder with commas and no spaces, e.g. "4,8,12,16,20,24" or
  "6,12,18,24,30,36" or "6,18,24,30,36". One fact per year in that ladder's
  date range, same joined value on each.

Do NOT emit:
- company, partnership, trust, NGO, unit-trust, or Employees' Trust Fund rates
- terminal-benefit / "Total Income from Employment" tables (0/5/10)
- withholding, dividend, or other overlay rates
- entity (non-individual) donation caps
- Act `relief` / `rate_band` rows

An empty result is valid when the window has no such fact. Never fabricate,
infer, or force a fact into a window. Do not use outside knowledge.
"""

PASS2_SYSTEM = """You verify quote fidelity for a legal extraction pipeline.

You are given a source text window and a candidate quote. Answer one question:
does the candidate quote appear as a CONTIGUOUS SUBSTRING of the source window,
ignoring only whitespace differences (tabs, line breaks, repeated spaces)?

- verbatim: true if every character appears, in the same order, with nothing
  deleted from the middle.
- A quote that starts or stops mid-sentence is still verbatim.
- verbatim is false if words were reordered, omitted from the middle,
  paraphrased, or stitched together from separate table cells.
- closest_quote: if false, copy the closest genuinely contiguous passage from
  the window; otherwise "".
- note: one short sentence explaining the decision.
Do not speculate about legal meaning.
"""


class Pass1Eligibility(BaseModel):
    text: str
    quote: str


class Pass1Relief(BaseModel):
    compare_group_id: str
    display_name: str
    paragraph_ref: str
    section_ref: str
    act_name: str
    cap_amount: str
    unit: str
    quote: str
    eligibility: Pass1Eligibility
    required_evidence: list[str] = Field(default_factory=list)
    filing_line: str
    stacking: str
    effective_from: str
    effective_to: str
    question_prompt: str = ""
    help: str = ""
    input_kind: str = "notice"


class Pass1RateBand(BaseModel):
    band_index: int
    band_label: str
    lower: str
    upper: str
    rate_percent: str
    applies_to: str
    section_ref: str
    act_name: str
    effective_from: str
    effective_to: str = ""
    quote: str
    compare_group_id: str


class Pass1GuideHelp(BaseModel):
    compare_group_id: str
    display_name: str
    help: str
    eligibility: Pass1Eligibility
    required_evidence: list[str] = Field(default_factory=list)
    section_ref: str
    quote: str


class Pass1Fact(BaseModel):
    compare_group_id: str
    year: str
    value: str
    quote: str
    section_ref: str


class Pass1ActPayload(BaseModel):
    reliefs: list[Pass1Relief]
    rate_bands: list[Pass1RateBand]


class Pass1GuidePayload(BaseModel):
    guide_help: list[Pass1GuideHelp]


class Pass1ConsolidatedPayload(BaseModel):
    consolidated_facts: list[Pass1Fact]


class QuoteCheck(BaseModel):
    verbatim: bool
    closest_quote: str
    note: str


class ExtractLLM(Protocol):
    def pass1_act(
        self,
        *,
        act_title: str,
        source_doc_id: str,
        target: str,
        focus_text: str,
    ) -> Pass1ActPayload: ...

    def pass1_guide(
        self,
        *,
        act_title: str,
        source_doc_id: str,
        target: str,
        focus_text: str,
    ) -> Pass1GuidePayload: ...

    def pass1_consolidated(
        self,
        *,
        act_title: str,
        source_doc_id: str,
        target: str,
        focus_text: str,
    ) -> Pass1ConsolidatedPayload: ...

    def pass2(self, *, quote: str, focus_text: str) -> QuoteCheck: ...


def _parse(client: Any, **kwargs: Any) -> Any:
    try:
        return client.chat.completions.parse(**kwargs)
    except AttributeError:
        return client.beta.chat.completions.parse(**kwargs)


def _call_with_retry(client: Any, model: str, **kwargs: Any) -> Any:
    delay = 2.0
    last: Exception | None = None
    for _ in range(4):
        try:
            return _parse(client, model=model, temperature=0, **kwargs)
        except Exception as exc:  # noqa: BLE001
            last = exc
            message = str(exc).lower()
            if "insufficient_quota" in message or "billing" in message:
                raise RuntimeError(f"OPENAI_CREDITS_EXHAUSTED: {exc}") from exc
            if "401" in message or "unauthorized" in message or "invalid_api_key" in message:
                raise RuntimeError(f"OPENAI_AUTH_FAILED: {exc}") from exc
            time.sleep(delay)
            delay *= 2
    raise RuntimeError(f"OpenAI call failed after retries: {last}")


class OpenAIExtractLLM:
    def __init__(
        self,
        client: Any,
        *,
        model: str = DEFAULT_MODEL,
        ledger: SpendLedger | None = None,
    ) -> None:
        self._client = client
        self.model = model
        self.ledger = ledger or SpendLedger()

    def _complete(self, *, label: str, messages: list[dict[str, str]], response_format: type) -> Any:
        completion = _call_with_retry(
            self._client,
            self.model,
            messages=messages,
            response_format=response_format,
        )
        usage = getattr(completion, "usage", None)
        self.ledger.record(
            label=label,
            model=self.model,
            prompt_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
            completion_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
        )
        message = completion.choices[0].message
        if getattr(message, "refusal", None):
            raise RuntimeError(f"{label} refused: {message.refusal}")
        return message.parsed

    def pass1_act(
        self,
        *,
        act_title: str,
        source_doc_id: str,
        target: str,
        focus_text: str,
    ) -> Pass1ActPayload:
        user = (
            f"Act: {act_title}\n"
            f"source_doc_id: {source_doc_id}\n"
            f"Target provision: {target}\n\n"
            "Extract reliefs and rate_bands from the focus window below.\n"
            "Copy every `quote` verbatim from this window.\n\n"
            "--- BEGIN FOCUS WINDOW ---\n"
            f"{focus_text}\n"
            "--- END FOCUS WINDOW ---\n"
        )
        parsed = self._complete(
            label=f"pass1_act:{source_doc_id}:{target}",
            messages=[
                {"role": "system", "content": PASS1_SYSTEM_ACT},
                {"role": "user", "content": user},
            ],
            response_format=Pass1ActPayload,
        )
        return parsed or Pass1ActPayload(reliefs=[], rate_bands=[])

    def pass1_guide(
        self,
        *,
        act_title: str,
        source_doc_id: str,
        target: str,
        focus_text: str,
    ) -> Pass1GuidePayload:
        user = (
            f"Guide: {act_title}\n"
            f"source_doc_id: {source_doc_id}\n"
            f"Target provision: {target}\n\n"
            "Extract guide_help from the focus window below.\n"
            "Copy every `quote` verbatim from this window.\n"
            "Never emit a cap_amount.\n\n"
            "--- BEGIN FOCUS WINDOW ---\n"
            f"{focus_text}\n"
            "--- END FOCUS WINDOW ---\n"
        )
        parsed = self._complete(
            label=f"pass1_guide:{source_doc_id}:{target}",
            messages=[
                {"role": "system", "content": PASS1_SYSTEM_GUIDE},
                {"role": "user", "content": user},
            ],
            response_format=Pass1GuidePayload,
        )
        return parsed or Pass1GuidePayload(guide_help=[])

    def pass1_consolidated(
        self,
        *,
        act_title: str,
        source_doc_id: str,
        target: str,
        focus_text: str,
    ) -> Pass1ConsolidatedPayload:
        user = (
            f"Consolidated: {act_title}\n"
            f"source_doc_id: {source_doc_id}\n"
            f"Target provision: {target}\n\n"
            "Extract consolidated_facts from the focus window below.\n"
            "Copy every `quote` verbatim from this window.\n\n"
            "--- BEGIN FOCUS WINDOW ---\n"
            f"{focus_text}\n"
            "--- END FOCUS WINDOW ---\n"
        )
        parsed = self._complete(
            label=f"pass1_consolidated:{source_doc_id}:{target}",
            messages=[
                {"role": "system", "content": PASS1_SYSTEM_CONSOLIDATED},
                {"role": "user", "content": user},
            ],
            response_format=Pass1ConsolidatedPayload,
        )
        return parsed or Pass1ConsolidatedPayload(consolidated_facts=[])

    def pass2(self, *, quote: str, focus_text: str) -> QuoteCheck:
        tightened = pass2_window(quote, focus_text)
        user = (
            "--- BEGIN SOURCE WINDOW ---\n"
            f"{tightened}\n"
            "--- END SOURCE WINDOW ---\n\n"
            f"Candidate quote:\n{quote}\n"
        )
        parsed = self._complete(
            label="pass2",
            messages=[
                {"role": "system", "content": PASS2_SYSTEM},
                {"role": "user", "content": user},
            ],
            response_format=QuoteCheck,
        )
        return parsed or QuoteCheck(verbatim=False, closest_quote="", note="no parse")
