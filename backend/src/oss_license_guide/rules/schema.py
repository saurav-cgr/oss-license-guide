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
    """A reference to one exact source span, pinned to the approved hash.

    ``expected_hash`` records the sha256 of the exact text span that a reviewer
    approved. Resolution rejects the citation if the active catalog's span hash
    differs, so regenerated or drifted source text cannot silently change the
    evidence supporting an existing reviewed rule.
    """

    source_id: str
    span_index: int
    expected_hash: str = ""


@dataclass(frozen=True)
class ObligationClaim:
    """A material obligation claim linked to supporting source spans."""

    text: str
    citations: list[Citation] = field(default_factory=list)


@dataclass(frozen=True)
class Rule:
    """A single versioned rule record.

    ``rule_version`` is a maintainer-assigned immutable revision identifier.
    ``content_hash`` is computed from the rule's canonical serialization so a
    response can identify the exact approved revision it evaluated.
    """

    rule_id: str
    license_expression_pattern: str
    scenario_preconditions: dict[str, Any] = field(default_factory=dict)
    outcome: str = ""
    obligations: list[ObligationClaim] = field(default_factory=list)
    permission_citations: list[Citation] = field(default_factory=list)
    exceptions: list[str] = field(default_factory=list)
    direction: str = ""
    source_ids: list[str] = field(default_factory=list)
    review_status: ReviewStatus = ReviewStatus.DRAFT
    reviewer: str = ""
    effective_date: str = ""
    last_verified_at: str = ""
    rule_version: str = ""
    content_hash: str = ""
