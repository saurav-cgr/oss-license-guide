"""Canonicalization of SPDX expression trees.

The canonicalizer normalizes version suffixes and deprecated identifiers into
their modern SPDX form while leaving the original input untouched. It never
drops grouping or converts unknown identifiers into a normalized license.
"""

from __future__ import annotations

from typing import Any

from oss_license_guide.expressions.ast import (
    Conjunction,
    Disjunction,
    Node,
    SimpleLicense,
    WithExpr,
)
from oss_license_guide.expressions.parser import _Grouped

# Seed mapping of common deprecated SPDX identifiers to their canonical
# ``-only`` form. The complete, versioned mapping arrives with the SPDX
# catalog ingestion pipeline; this covers the identifiers used by the parser
# corpus and the MVP rule set.
_DEPRECATED_ONLY = {
    "AGPL-1.0": "AGPL-1.0-only",
    "AGPL-3.0": "AGPL-3.0-only",
    "GFDL-1.1": "GFDL-1.1-only",
    "GFDL-1.2": "GFDL-1.2-only",
    "GFDL-1.3": "GFDL-1.3-only",
    "GPL-1.0": "GPL-1.0-only",
    "GPL-2.0": "GPL-2.0-only",
    "GPL-3.0": "GPL-3.0-only",
    "LGPL-2.0": "LGPL-2.0-only",
    "LGPL-2.1": "LGPL-2.1-only",
    "LGPL-3.0": "LGPL-3.0-only",
}

_DEPRECATED_OR_LATER = {
    "AGPL-1.0": "AGPL-1.0-or-later",
    "AGPL-3.0": "AGPL-3.0-or-later",
    "GPL-1.0": "GPL-1.0-or-later",
    "GPL-2.0": "GPL-2.0-or-later",
    "GPL-3.0": "GPL-3.0-or-later",
    "LGPL-2.0": "LGPL-2.0-or-later",
    "LGPL-2.1": "LGPL-2.1-or-later",
    "LGPL-3.0": "LGPL-3.0-or-later",
}


def _canonical_license(license: SimpleLicense, warnings: list[str]) -> str:
    if license.or_later:
        if license.value in _DEPRECATED_OR_LATER:
            replacement = _DEPRECATED_OR_LATER[license.value]
            warnings.append(
                f"{license.value}+ is a deprecated spelling; use {replacement} instead"
            )
            return replacement
        warnings.append("The '+' suffix is deprecated; prefer '-or-later' instead")
        return f"{license.value}-or-later"
    if license.value in _DEPRECATED_ONLY:
        replacement = _DEPRECATED_ONLY[license.value]
        warnings.append(
            f"{license.value} is a deprecated SPDX identifier; use {replacement} instead"
        )
        return replacement
    return license.value


def render(node: Node, warnings: list[str]) -> str:
    """Render an AST node to its canonical string form."""
    if isinstance(node, _Grouped):
        return f"({render(node.inner, warnings)})"
    if isinstance(node, SimpleLicense):
        return _canonical_license(node, warnings)
    if isinstance(node, WithExpr):
        return f"{render(node.base, warnings)} WITH {node.exception}"
    if isinstance(node, Conjunction):
        return f"{render(node.left, warnings)} AND {render(node.right, warnings)}"
    if isinstance(node, Disjunction):
        return f"{render(node.left, warnings)} OR {render(node.right, warnings)}"
    raise TypeError(f"Unknown node type: {type(node).__name__}")


def structure(node: Node) -> dict[str, Any]:
    """Convert an AST node into a JSON-serializable structure."""
    if isinstance(node, _Grouped):
        return {"type": "group", "inner": structure(node.inner)}
    if isinstance(node, SimpleLicense):
        return {
            "type": "license",
            "id": node.value,
            "or_later": node.or_later,
        }
    if isinstance(node, WithExpr):
        return {
            "type": "with",
            "base": structure(node.base),
            "exception": node.exception,
        }
    if isinstance(node, Conjunction):
        return {"type": "and", "left": structure(node.left), "right": structure(node.right)}
    if isinstance(node, Disjunction):
        return {"type": "or", "left": structure(node.left), "right": structure(node.right)}
    raise TypeError(f"Unknown node type: {type(node).__name__}")


def canonicalize(node: Node) -> tuple[str, list[str]]:
    """Return the canonical string and any normalization warnings."""
    warnings: list[str] = []
    canonical = render(node, warnings)
    return canonical, warnings
