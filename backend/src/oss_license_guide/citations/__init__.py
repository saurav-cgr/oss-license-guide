"""Claim-to-citation validation."""

from oss_license_guide.citations.resolver import (
    ResolvedSpan,
    parse_source_id,
    resolve_claims,
    resolve_span,
    validate_claims,
)

__all__ = [
    "ResolvedSpan",
    "parse_source_id",
    "resolve_claims",
    "resolve_span",
    "validate_claims",
]
