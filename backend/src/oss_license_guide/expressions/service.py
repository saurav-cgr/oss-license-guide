"""Application service for parsing SPDX expressions.

This is the framework-independent entry point used by the API layer. It
validates input, lexes and parses, then canonicalizes. Invalid expressions
produce structured diagnostics rather than a guessed normalization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from oss_license_guide.expressions.ast import Span
from oss_license_guide.expressions.canonicalizer import canonicalize, structure
from oss_license_guide.expressions.errors import ExpressionDiagnostic, LexError, ParseError
from oss_license_guide.expressions.parser import parse_expression as _parse


@dataclass
class ParseResult:
    """Outcome of parsing a single SPDX expression."""

    ok: bool
    original: str
    canonical: str | None = None
    warnings: list[str] = field(default_factory=list)
    structure: dict[str, Any] | None = None
    diagnostics: list[ExpressionDiagnostic] = field(default_factory=list)


def parse_expression(text: str) -> ParseResult:
    """Parse and canonicalize ``text`` into a :class:`ParseResult`."""
    if not text or not text.strip():
        diagnostic = ExpressionDiagnostic("Expression is empty", Span(0, 0, 1, 1))
        return ParseResult(ok=False, original=text, diagnostics=[diagnostic])

    try:
        tree = _parse(text)
    except (LexError, ParseError) as error:
        return ParseResult(ok=False, original=text, diagnostics=[error.diagnostic()])

    canonical, warnings = canonicalize(tree)
    return ParseResult(
        ok=True,
        original=text,
        canonical=canonical,
        warnings=warnings,
        structure=structure(tree),
    )
