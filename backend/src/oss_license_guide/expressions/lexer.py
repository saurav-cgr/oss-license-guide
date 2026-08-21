"""Tokenizer for SPDX license expressions.

The lexer produces a flat token stream. Operator keywords (``AND``, ``OR``,
``WITH``) are recognized case-insensitively; every other identifier-style run
becomes an ``IDENTIFIER`` token. Whitespace is insignificant.
"""

from __future__ import annotations

from oss_license_guide.expressions.ast import Span
from oss_license_guide.expressions.errors import LexError
from oss_license_guide.expressions.tokens import Position, Token, TokenType

_OPERATORS = {"AND", "OR", "WITH"}
_ID_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-.")


class Lexer:
    """Convert source text into a list of tokens ending with an END token."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.offset = 0
        self.line = 1
        self.column = 1

    def _position(self) -> Position:
        return Position(offset=self.offset, line=self.line, column=self.column)

    def _advance(self) -> str:
        char = self.text[self.offset]
        self.offset += 1
        if char == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return char

    def _skip_whitespace(self) -> None:
        while self.offset < len(self.text) and self.text[self.offset].isspace():
            self._advance()

    def tokenize(self) -> list[Token]:
        tokens: list[Token] = []
        while True:
            self._skip_whitespace()
            if self.offset >= len(self.text):
                pos = self._position()
                tokens.append(Token(TokenType.END, "", pos, pos))
                return tokens

            start = self._position()
            char = self.text[self.offset]

            if char == "(":
                self._advance()
                tokens.append(Token(TokenType.LPAREN, char, start, self._position()))
            elif char == ")":
                self._advance()
                tokens.append(Token(TokenType.RPAREN, char, start, self._position()))
            elif char == "+":
                self._advance()
                tokens.append(Token(TokenType.PLUS, char, start, self._position()))
            elif char == ":":
                self._advance()
                tokens.append(Token(TokenType.COLON, char, start, self._position()))
            elif char in _ID_CHARS:
                tokens.append(self._identifier(start))
            else:
                self._advance()
                span = Span(start.offset, self.offset, start.line, start.column)
                raise LexError(f"Unexpected character {char!r}", span)

    def _identifier(self, start: Position) -> Token:
        while self.offset < len(self.text) and self.text[self.offset] in _ID_CHARS:
            self._advance()
        end = self._position()
        value = self.text[start.offset : end.offset]
        token_type = TokenType.OPERATOR if value.upper() in _OPERATORS else TokenType.IDENTIFIER
        return Token(token_type, value, start, end)
