"""SPDX license expression parsing and canonicalization.

This package implements a minimal, deterministic SPDX expression parser.
It depends only on the Python standard library and never on external services.
"""

from oss_license_guide.expressions.service import ParseResult, parse_expression

__all__ = ["ParseResult", "parse_expression"]
