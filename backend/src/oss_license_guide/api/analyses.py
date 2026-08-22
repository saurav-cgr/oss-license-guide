"""Scenario analysis endpoint running the bounded deterministic workflow."""

from typing import Any

from fastapi import APIRouter, Header
from pydantic import BaseModel, ConfigDict, Field, field_validator

from oss_license_guide.answering import Answer, build_answer, render
from oss_license_guide.config.settings import get_settings
from oss_license_guide.providers import ExplanationFindings, generate_explanation
from oss_license_guide.rules import evaluate, load_rules
from oss_license_guide.safety import MAX_EXPRESSION_LENGTH
from oss_license_guide.scenarios.facts import (
    Action,
    DistributionForm,
    FactType,
    Provenance,
    Recipient,
)
from oss_license_guide.scenarios.schema import Fact, Scenario
from oss_license_guide.sources import load_catalog

router = APIRouter(prefix="/analyses", tags=["analyses"])


class FactsModel(BaseModel):
    """Structured scenario facts. Omitted or null facts are unknown."""

    action: str | None = None
    distribution: bool | None = None
    distribution_form: str | None = None
    recipient: str | None = None
    modified: bool | None = None
    outbound_license: str | None = None
    selected_branch: str | None = None
    license_file_present: bool | None = None
    copyright_notice_present: bool | None = None
    notice_file_present: bool | None = None

    @field_validator("action")
    @classmethod
    def _validate_action(cls, value: str | None) -> str | None:
        return _validate_enum(value, Action)

    @field_validator("distribution_form")
    @classmethod
    def _validate_form(cls, value: str | None) -> str | None:
        return _validate_enum(value, DistributionForm)

    @field_validator("recipient")
    @classmethod
    def _validate_recipient(cls, value: str | None) -> str | None:
        return _validate_enum(value, Recipient)


QUESTION_MAX_LENGTH = 1000


class AnalysisRequest(BaseModel):
    """Scenario analysis request.

    ``extra="forbid"`` rejects unknown fields (for example a client-supplied
    ``base_url``), because provider endpoints are server-controlled and must
    never be influenced by the request body.
    """

    model_config = ConfigDict(extra="forbid")

    expression: str = Field(min_length=1, max_length=MAX_EXPRESSION_LENGTH)
    facts: FactsModel = FactsModel()
    provider: str | None = None
    model: str | None = None
    question: str | None = Field(
        default=None,
        max_length=QUESTION_MAX_LENGTH,
        description=(
            "Free-text context passed only to an optional model explanation. It "
            "never drives deterministic scenario extraction; conclusions come "
            "solely from the structured facts and versioned rules."
        ),
    )


def _validate_enum(value: str | None, enum_cls: type) -> str | None:
    if value is not None and value not in {member.value for member in enum_cls}:
        raise ValueError(f"invalid value: {value!r}")
    return value


class CitationOut(BaseModel):
    source_id: str
    span_index: int
    text: str
    hash: str
    source_type: str = "spdx"
    source_url: str = ""
    version: str = ""
    retrieved_at: str = ""


class ClaimOut(BaseModel):
    text: str
    citations: list[CitationOut] = []


class RuleReviewOut(BaseModel):
    """Rule provenance surfaced to the client without overstating review.

    ``review_status`` uses the approved review-state vocabulary (for example
    ``maintainer_reviewed``); it must never be described as independent,
    professional, or legal review.
    """

    rule_id: str
    review_status: str
    reviewer: str
    effective_date: str
    last_verified_at: str
    rule_version: str = ""
    content_hash: str = ""


class AnalysisResponse(BaseModel):
    outcome: str
    canonical: str
    short_answer: str
    assumptions: list[str] = []
    obligations: list[ClaimOut] = []
    permission: ClaimOut | None = None
    what_could_change: list[str] = []
    evidence: list[CitationOut] = []
    confidence: dict[str, str] = {}
    escalation: str = ""
    disclaimer: str = ""
    missing_facts: list[str] = []
    warnings: list[str] = []
    rule_id: str | None = None
    rule: RuleReviewOut | None = None
    citation_errors: list[str] = []
    blocked: bool = False
    rendered: str = ""
    explanation: str = ""
    provider: str | None = None
    model: str | None = None
    provider_note: str = ""


def _build_scenario(request: AnalysisRequest) -> Scenario:
    scenario = Scenario(expression=request.expression)
    for fact_type in FactType:
        value: Any = getattr(request.facts, fact_type.value, None)
        if value is not None:
            scenario.facts[fact_type] = Fact(value=value, provenance=Provenance.USER_PROVIDED)
    return scenario


@router.post("", response_model=AnalysisResponse)
def analyze(
    request: AnalysisRequest,
    x_model_key: str | None = Header(default=None),
) -> AnalysisResponse:
    """Run the bounded scenario-analysis workflow with an optional explanation."""
    scenario = _build_scenario(request)
    result = evaluate(scenario, load_rules())
    answer = build_answer(result, scenario, load_catalog())

    explanation, provider_note = _explain(request, x_model_key, answer)

    obligations = [] if answer.blocked else [_claim_out(claim) for claim in answer.obligations]
    permission = (
        None if answer.blocked or answer.permission is None else _claim_out(answer.permission)
    )
    evidence = [] if answer.blocked else [_citation_out(c) for c in answer.evidence]

    return AnalysisResponse(
        outcome=answer.outcome,
        canonical=answer.canonical,
        short_answer=answer.short_answer,
        assumptions=answer.assumptions,
        obligations=obligations,
        permission=permission,
        what_could_change=answer.what_could_change,
        evidence=evidence,
        confidence=answer.confidence,
        escalation=answer.escalation,
        disclaimer=answer.disclaimer,
        missing_facts=answer.missing_facts,
        warnings=answer.warnings,
        rule_id=answer.rule_id,
        rule=_rule_review_out(answer),
        citation_errors=answer.citation_errors,
        blocked=answer.blocked,
        rendered=render(answer),
        explanation=explanation,
        provider=request.provider,
        model=request.model or "",
        provider_note=provider_note,
    )


def _explain(request: AnalysisRequest, x_model_key: str | None, answer: Answer) -> tuple[str, str]:
    """Generate a bounded model explanation, degrading safely to deterministic."""
    if not request.provider or answer.blocked:
        return "", ""
    result = generate_explanation(
        provider=request.provider,
        model=request.model or "",
        api_key=x_model_key,
        findings=_findings(answer, request.question),
        settings=get_settings(),
    )
    return result.explanation, result.note


def _findings(answer: Answer, question: str | None) -> ExplanationFindings:
    """Build non-secret model findings from the deterministic answer."""
    return ExplanationFindings(
        outcome=answer.outcome,
        canonical=answer.canonical,
        short_answer=answer.short_answer,
        assumptions=list(answer.assumptions),
        question=question or "",
        obligations=[
            {
                "text": claim.text,
                "citations": [
                    {
                        "source_id": citation.source_id,
                        "span_index": citation.span_index,
                        "text": citation.text,
                    }
                    for citation in claim.citations
                ],
            }
            for claim in answer.obligations
        ],
        what_could_change=list(answer.what_could_change),
        escalation=answer.escalation,
    )


def _claim_out(claim: Any) -> ClaimOut:
    return ClaimOut(text=claim.text, citations=[_citation_out(c) for c in claim.citations])


def _citation_out(citation: Any) -> CitationOut:
    return CitationOut(
        source_id=citation.source_id,
        span_index=citation.span_index,
        text=citation.text,
        hash=citation.hash,
        source_type=citation.source_type,
        source_url=citation.source_url,
        version=citation.version,
        retrieved_at=citation.retrieved_at,
    )


def _rule_review_out(answer: Answer) -> RuleReviewOut | None:
    if not answer.rule_id:
        return None
    return RuleReviewOut(
        rule_id=answer.rule_id,
        review_status=answer.review_status or "",
        reviewer=answer.reviewer or "",
        effective_date=answer.effective_date or "",
        last_verified_at=answer.last_verified_at or "",
        rule_version=answer.rule_version or "",
        content_hash=answer.content_hash or "",
    )

