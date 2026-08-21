"""Domain guardrails and input limits applied at the API boundary."""

from __future__ import annotations

MAX_EXPRESSION_LENGTH = 500


def validate_expression(expression: str) -> list[str]:
    """Return input-limit violations for an expression, or an empty list."""
    errors: list[str] = []
    if not expression or not expression.strip():
        errors.append("expression must not be empty")
    if len(expression) > MAX_EXPRESSION_LENGTH:
        errors.append(f"expression exceeds {MAX_EXPRESSION_LENGTH} characters")
    return errors
