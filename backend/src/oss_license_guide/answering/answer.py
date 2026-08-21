"""Structured answer contract shared by the deterministic renderer."""

from __future__ import annotations

from dataclasses import dataclass, field

DISCLAIMER = (
    "Informational guidance only, not legal advice. "
    "Have qualified counsel review decisions with material legal or business impact."
)


@dataclass(frozen=True)
class EvidenceEntry:
    """A validated source span supporting a claim."""

    source_id: str
    span_index: int
    text: str
    hash: str


@dataclass(frozen=True)
class ClaimView:
    """A material claim with its resolved evidence spans."""

    text: str
    citations: list[EvidenceEntry] = field(default_factory=list)


@dataclass
class Answer:
    """The full structured answer conforming to the product output contract."""

    outcome: str
    canonical: str
    short_answer: str
    assumptions: list[str] = field(default_factory=list)
    obligations: list[ClaimView] = field(default_factory=list)
    what_could_change: list[str] = field(default_factory=list)
    evidence: list[EvidenceEntry] = field(default_factory=list)
    confidence: dict[str, str] = field(default_factory=dict)
    escalation: str = ""
    disclaimer: str = DISCLAIMER
    missing_facts: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    rule_id: str | None = None
    citation_errors: list[str] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        """An answer is blocked when citation validation failed."""
        return bool(self.citation_errors)
