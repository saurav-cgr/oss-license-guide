"""Diagnostics for SPDX expression parsing."""

from __future__ import annotations

from dataclasses import dataclass

from oss_license_guide.expressions.ast import Span


@dataclass(frozen=True)
class ExpressionDiagnostic:
    """A location-aware parse or normalization problem."""

    message: str
    span: Span


@dataclass(frozen=True)
class LexError(Exception):
    """Raised when the lexer encounters an illegal character."""

    message: str
    span: Span

    def diagnostic(self) -> ExpressionDiagnostic:
        return ExpressionDiagnostic(self.message, self.span)


@dataclass(frozen=True)
class ParseError(Exception):
    """Raised when the token stream is not a valid SPDX expression."""

    message: str
    span: Span

    def diagnostic(self) -> ExpressionDiagnostic:
        return ExpressionDiagnostic(self.message, self.span)
