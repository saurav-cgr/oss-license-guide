"""Rule eligibility checks.

Only maintainer-reviewed or legally-reviewed rules may support a substantive
demo conclusion. Draft, expired, or superseded rules must force abstention.
"""

from __future__ import annotations

from oss_license_guide.rules.schema import ReviewStatus, Rule

_ELIGIBLE = {ReviewStatus.MAINTAINER_REVIEWED, ReviewStatus.LEGALLY_REVIEWED}


def is_eligible(rule: Rule) -> bool:
    """Return whether ``rule`` may support a substantive conclusion."""
    return rule.review_status in _ELIGIBLE
