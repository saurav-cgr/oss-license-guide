"""SPDX expression abstract syntax tree nodes.

Nodes are immutable and each carries a source span so that diagnostics can
point at the exact offending text. The AST preserves grouping, operators, and
version suffixes exactly as written.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Span:
    """A source span, in character offsets plus human-readable location."""

    start: int
    end: int
    line: int
    column: int


class Node:
    """Base class for expression tree nodes."""

    span: Span


@dataclass(frozen=True)
class SimpleLicense(Node):
    """A single license or reference identifier.

    ``value`` is the raw identifier text (for example ``MIT``,
    ``GPL-3.0-or-later``, or ``LicenseRef-custom``). ``or_later`` is true when
    the source used the trailing ``+`` form.
    """

    value: str
    or_later: bool
    span: Span


@dataclass(frozen=True)
class WithExpr(Node):
    """A base license modified by an exception, such as ``GPL-2.0-only WITH
    Classpath-exception-2.0``."""

    base: SimpleLicense
    exception: str
    span: Span


@dataclass(frozen=True)
class Conjunction(Node):
    """An ``AND`` combining two sub-expressions, where all terms apply."""

    left: Node
    right: Node
    span: Span


@dataclass(frozen=True)
class Disjunction(Node):
    """An ``OR`` combining two sub-expressions, where a choice applies."""

    left: Node
    right: Node
    span: Span
