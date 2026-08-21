"""SPDX expression parsing endpoint."""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from oss_license_guide.expressions.service import parse_expression

router = APIRouter(prefix="/expressions", tags=["expressions"])


class ParseRequest(BaseModel):
    expression: str = Field(..., description="SPDX license expression to parse")


class SpanModel(BaseModel):
    start: int
    end: int
    line: int
    column: int


class DiagnosticModel(BaseModel):
    message: str
    span: SpanModel


class ParseResponse(BaseModel):
    valid: bool
    original: str
    canonical: str | None = None
    warnings: list[str] = []
    structure: dict[str, Any] | None = None
    diagnostics: list[DiagnosticModel] = []


@router.post("/parse", response_model=ParseResponse)
def parse(request: ParseRequest) -> ParseResponse:
    """Validate and preserve an SPDX expression without guessing a meaning."""
    result = parse_expression(request.expression)
    diagnostics = [
        DiagnosticModel(
            message=diagnostic.message,
            span=SpanModel(
                start=diagnostic.span.start,
                end=diagnostic.span.end,
                line=diagnostic.span.line,
                column=diagnostic.span.column,
            ),
        )
        for diagnostic in result.diagnostics
    ]
    return ParseResponse(
        valid=result.ok,
        original=result.original,
        canonical=result.canonical,
        warnings=result.warnings,
        structure=result.structure,
        diagnostics=diagnostics,
    )
