"""Token definitions for the SPDX expression lexer."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TokenType(Enum):
    """The kinds of tokens produced by the lexer."""

    IDENTIFIER = "IDENTIFIER"
    OPERATOR = "OPERATOR"
    LPAREN = "LPAREN"
    RPAREN = "RPAREN"
    PLUS = "PLUS"
    COLON = "COLON"
    END = "END"


@dataclass(frozen=True)
class Position:
    """A zero-based offset plus one-based line and column in the source text."""

    offset: int
    line: int
    column: int


@dataclass(frozen=True)
class Token:
    """A single lexical token with its source span."""

    type: TokenType
    value: str
    start: Position
    end: Position
