"""Citation resolution against the bundled source catalog.

Citations reference exact source spans by ``source_id`` (for example
``spdx:MIT@3.24.0``) and a deterministic paragraph index. Resolution verifies
that the span exists in the active catalog and that its content hash matches,
so a tampered or drifted source invalidates the citation.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from oss_license_guide.rules.schema import ObligationClaim
from oss_license_guide.sources.catalog import Catalog


@dataclass(frozen=True)
class ResolvedSpan:
    """An exact source span that has been validated against the catalog."""

    source_id: str
    span_index: int
    text: str
    hash: str


def parse_source_id(source_id: str) -> str:
    """Extract the license identifier from a source id like spdx:MIT@3.24.0."""
    value = source_id
    if value.startswith("spdx:"):
        value = value[len("spdx:") :]
    if "@" in value:
        value = value.split("@", 1)[0]
    return value


def resolve_span(source_id: str, span_index: int, catalog: Catalog) -> ResolvedSpan | None:
    """Resolve and validate one citation span, returning None if invalid."""
    record = catalog.lookup(parse_source_id(source_id))
    if record is None or record.text is None:
        return None
    for paragraph in record.paragraphs:
        if paragraph.index != span_index:
            continue
        segment = record.text[paragraph.start : paragraph.end]
        if hashlib.sha256(segment.encode("utf-8")).hexdigest() != paragraph.hash:
            return None
        return ResolvedSpan(
            source_id=source_id,
            span_index=span_index,
            text=segment,
            hash=paragraph.hash,
        )
    return None


def resolve_claims(
    claims: list[ObligationClaim], catalog: Catalog
) -> tuple[list[list[ResolvedSpan]], list[str]]:
    """Resolve every claim's citations; return per-claim spans and errors."""
    resolved: list[list[ResolvedSpan]] = []
    errors: list[str] = []
    for claim in claims:
        spans: list[ResolvedSpan] = []
        for citation in claim.citations:
            span = resolve_span(citation.source_id, citation.span_index, catalog)
            if span is None:
                errors.append(
                    f"Claim {claim.text!r} cites missing or invalid span "
                    f"{citation.source_id}#{citation.span_index}"
                )
            else:
                spans.append(span)
        resolved.append(spans)
    return resolved, errors


def validate_claims(claims: list[ObligationClaim], catalog: Catalog) -> list[str]:
    """Return every citation-coverage and hash-integrity error for ``claims``."""
    _, errors = resolve_claims(claims, catalog)
    for claim in claims:
        if not claim.citations:
            errors.append(f"Claim {claim.text!r} has no source citation")
    return errors
