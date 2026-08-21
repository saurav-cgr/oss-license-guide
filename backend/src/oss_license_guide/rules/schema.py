"""Versioned deterministic rule records.

A rule encodes the maintainer-reviewed outcome and obligations for one license
expression pattern under stated scenario preconditions. Review status gates
whether a rule may support a substantive conclusion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ReviewStatus(StrEnum):
    """Approval state of a rule version."""

    DRAFT = "draft"
    MAINTAINER_REVIEWED = "maintainer_reviewed"
    LEGALLY_REVIEWED = "legally_reviewed"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"


class AnalysisOutcome(StrEnum):
    """The only user-facing outcomes the MVP is allowed to produce."""

    LIKELY_PERMITTED = "Likely permitted under stated assumptions"
    PERMITTED_WITH_OBLIGATIONS = "Permitted with listed obligations"
    NOT_SUPPORTED = "Not supported under stated outbound-license goal"
    INSUFFICIENT_INFORMATION = "Insufficient information"
    REQUIRES_LEGAL_REVIEW = "Requires legal review"


@dataclass(frozen=True)
class Citation:
    """A reference to one exact source span."""

    source_id: str
    span_index: int


@dataclass(frozen=True)
class ObligationClaim:
    """A material obligation claim linked to supporting source spans."""

    text: str
    citations: list[Citation] = field(default_factory=list)


@dataclass(frozen=True)
class Rule:
    """A single versioned rule record."""

    rule_id: str
    license_expression_pattern: str
    scenario_preconditions: dict[str, Any] = field(default_factory=dict)
    outcome: str = ""
    obligations: list[ObligationClaim] = field(default_factory=list)
    exceptions: list[str] = field(default_factory=list)
    direction: str = ""
    source_ids: list[str] = field(default_factory=list)
    review_status: ReviewStatus = ReviewStatus.DRAFT
    reviewer: str = ""
    effective_date: str = ""
    last_verified_at: str = ""
