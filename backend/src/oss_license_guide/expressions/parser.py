"""Recursive-descent parser for SPDX license expressions.

Grammar (simplified but faithful to SPDX semantics):

    expression   := disjunction
    disjunction  := conjunction ( OR conjunction )*
    conjunction  := with_expr ( AND with_expr )*
    with_expr    := primary ( WITH exception_id )?
    primary      := '(' expression ')' | license_term
    license_term := identifier ( '+' )? | 'DocumentRef-' id ':' 'LicenseRef-' id

Precedence (tightest first): WITH, AND, OR. Left-associative. Parentheses are
preserved in the AST and override precedence.
"""

from __future__ import annotations

from oss_license_guide.expressions.ast import (
    Conjunction,
    Disjunction,
    Node,
    SimpleLicense,
    Span,
    WithExpr,
)
from oss_license_guide.expressions.errors import ParseError
from oss_license_guide.expressions.lexer import Lexer
from oss_license_guide.expressions.tokens import Token, TokenType

_LICENSE_REF_PREFIX = "LicenseRef-"
_DOCUMENT_REF_PREFIX = "DocumentRef-"


class Parser:
    """Parse a token stream into an expression AST."""

    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.index = 0

    def _peek(self) -> Token:
        return self.tokens[self.index]

    def _advance(self) -> Token:
        token = self.tokens[self.index]
        self.index += 1
        return token

    def _expect(self, token_type: TokenType) -> Token:
        token = self._peek()
        if token.type != token_type:
            raise ParseError(
                f"Expected {token_type.value.lower()}, found {self._describe(token)}",
                self._span(token),
            )
        return self._advance()

    @staticmethod
    def _describe(token: Token) -> str:
        if token.type is TokenType.END:
            return "end of expression"
        return repr(token.value)

    @staticmethod
    def _span(token: Token) -> Span:
        return Span(token.start.offset, token.end.offset, token.start.line, token.start.column)

    def parse(self) -> Node:
        node = self._parse_disjunction()
        token = self._peek()
        if token.type is not TokenType.END:
            raise ParseError(
                f"Unexpected {self._describe(token)} after complete expression",
                self._span(token),
            )
        return node

    def _parse_disjunction(self) -> Node:
        node = self._parse_conjunction()
        while self._peek().type is TokenType.OPERATOR and self._peek().value.upper() == "OR":
            operator = self._advance()
            right = self._parse_conjunction()
            node = Disjunction(node, right, self._span(operator))
        return node

    def _parse_conjunction(self) -> Node:
        node = self._parse_with_expr()
        while self._peek().type is TokenType.OPERATOR and self._peek().value.upper() == "AND":
            operator = self._advance()
            right = self._parse_with_expr()
            node = Conjunction(node, right, self._span(operator))
        return node

    def _parse_with_expr(self) -> Node:
        base = self._parse_primary()
        token = self._peek()
        if token.type is TokenType.OPERATOR and token.value.upper() == "WITH":
            operator = self._advance()
            if not isinstance(base, SimpleLicense):
                raise ParseError(
                    "WITH must follow a single license identifier",
                    self._span(operator),
                )
            exception = self._expect(TokenType.IDENTIFIER)
            return WithExpr(base, exception.value, self._span(operator))
        return base

    def _parse_primary(self) -> Node:
        token = self._peek()
        if token.type is TokenType.LPAREN:
            open_paren = self._advance()
            node = self._parse_disjunction()
            close = self._expect(TokenType.RPAREN)
            return _wrap_in_group(node, open_paren, close)

        return self._parse_license_term()

    def _parse_license_term(self) -> Node:
        token = self._expect(TokenType.IDENTIFIER)
        value = token.value

        if value.startswith(_DOCUMENT_REF_PREFIX):
            self._expect(TokenType.COLON)
            ref = self._expect(TokenType.IDENTIFIER)
            if not ref.value.startswith(_LICENSE_REF_PREFIX):
                raise ParseError(
                    f"Expected LicenseRef- after DocumentRef-, found {ref.value!r}",
                    self._span(ref),
                )
            combined = f"{value}:{ref.value}"
            return SimpleLicense(combined, False, self._span(token))

        or_later = False
        if self._peek().type is TokenType.PLUS:
            plus = self._advance()
            if value.startswith(_LICENSE_REF_PREFIX):
                raise ParseError(
                    "The + suffix is not allowed on LicenseRef identifiers",
                    self._span(plus),
                )
            or_later = True

        return SimpleLicense(value, or_later, self._span(token))


def _wrap_in_group(node: Node, open_paren: Token, close_paren: Token) -> Node:
    """Tag a node so rendering can reproduce explicit parentheses.

    Grouping is preserved structurally by the tree; the span is widened to
    include the parentheses so diagnostics and rendering remain faithful.
    """
    start = open_paren.start.offset
    end = close_paren.end.offset
    return _Grouped(node, Span(start, end, open_paren.start.line, open_paren.start.column))


class _Grouped(Node):
    """Internal wrapper marking an explicitly parenthesized sub-expression."""

    __slots__ = ("inner", "span")

    def __init__(self, inner: Node, span: Span) -> None:
        self.inner = inner
        self.span = span


def parse_expression(text: str) -> Node:
    """Parse ``text`` into an expression AST, raising on invalid input."""
    tokens = Lexer(text).tokenize()
    return Parser(tokens).parse()
