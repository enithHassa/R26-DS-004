"""Curated, well-established Sri Lankan IRD procedural facts.

Retrieval over the corpus sometimes returns passages that confirm a rule exists
but omit the concrete figure or date (e.g. the return-filing deadline). These
notes fill only those stable, non-controversial procedural gaps so the synthesis
model can give a direct answer instead of "the sources do not state a date".

They are injected into the synthesis prompt as clearly-labelled reference notes,
NOT as retrieved citations, and each carries its statutory anchor. Keep this list
small and uncontroversial — anything year-sensitive or contested belongs in the
corpus, not here.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReferenceFact:
    triggers: tuple[str, ...]
    text: str


_FACTS: tuple[ReferenceFact, ...] = (
    ReferenceFact(
        triggers=(
            "return deadline",
            "return due",
            "file a return",
            "filing deadline",
            "when is the tax return",
            "when to file",
            "due date for the return",
            "submit the return",
            "lodge the return",
        ),
        text=(
            "Return-of-income filing deadline (Inland Revenue Act No. 24 of 2017, s. 93): "
            "a person required to file must furnish the return not later than eight months "
            "after the end of the year of assessment. The year of assessment ends on 31 "
            "March, so the annual return is due by 30 November of that year. IRD may grant "
            "an extension only on a written application made before the due date."
        ),
    ),
    ReferenceFact(
        triggers=(
            "balance tax",
            "when to pay tax",
            "payment deadline",
            "when is tax due",
            "self assessment instal",
            "quarterly instal",
            "instalment",
            "final payment of tax",
        ),
        text=(
            "Income tax payment dates (Inland Revenue Act No. 24 of 2017, s. 90-92): tax is "
            "paid in four self-assessment instalments on or before 15 August, 15 November, "
            "15 February and 15 May, covering the three-month periods of the year of "
            "assessment. Any balance (final) tax is payable on or before 30 September "
            "following the end of that year of assessment."
        ),
    ),
    ReferenceFact(
        triggers=(
            "year of assessment",
            "tax year",
            "assessment year",
        ),
        text=(
            "Year of assessment (Inland Revenue Act No. 24 of 2017, s. 20): the twelve-month "
            "period from 1 April to 31 March of the following year."
        ),
    ),
)


def reference_notes_for(question: str) -> str | None:
    """Return curated reference notes whose triggers appear in the question."""
    q = (question or "").lower()
    hits = [f.text for f in _FACTS if any(t in q for t in f.triggers)]
    if not hits:
        return None
    return "\n".join(f"- {h}" for h in hits)
