"""Scenario analysis endpoint running the bounded deterministic workflow."""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from oss_license_guide.answering import build_answer, render
from oss_license_guide.rules import evaluate, load_rules
from oss_license_guide.scenarios.facts import FactType, Provenance
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


class AnalysisRequest(BaseModel):
    expression: str
    facts: FactsModel = FactsModel()


class CitationOut(BaseModel):
    source_id: str
    span_index: int
    text: str
    hash: str


class ClaimOut(BaseModel):
    text: str
    citations: list[CitationOut] = []


class AnalysisResponse(BaseModel):
    outcome: str
    canonical: str
    short_answer: str
    assumptions: list[str] = []
    obligations: list[ClaimOut] = []
    what_could_change: list[str] = []
    evidence: list[CitationOut] = []
    confidence: dict[str, str] = {}
    escalation: str = ""
    disclaimer: str = ""
    missing_facts: list[str] = []
    warnings: list[str] = []
    rule_id: str | None = None
    citation_errors: list[str] = []
    blocked: bool = False
    rendered: str = ""


def _build_scenario(request: AnalysisRequest) -> Scenario:
    scenario = Scenario(expression=request.expression)
    for fact_type in FactType:
        value: Any = getattr(request.facts, fact_type.value, None)
        if value is not None:
            scenario.facts[fact_type] = Fact(value=value, provenance=Provenance.USER_PROVIDED)
    return scenario


@router.post("", response_model=AnalysisResponse)
def analyze(request: AnalysisRequest) -> AnalysisResponse:
    """Run the deterministic scenario-analysis workflow."""
    scenario = _build_scenario(request)
    result = evaluate(scenario, load_rules())
    answer = build_answer(result, scenario, load_catalog())

    obligations = [] if answer.blocked else [_claim_out(claim) for claim in answer.obligations]
    evidence = [] if answer.blocked else [_citation_out(c) for c in answer.evidence]

    return AnalysisResponse(
        outcome=answer.outcome,
        canonical=answer.canonical,
        short_answer=answer.short_answer,
        assumptions=answer.assumptions,
        obligations=obligations,
        what_could_change=answer.what_could_change,
        evidence=evidence,
        confidence=answer.confidence,
        escalation=answer.escalation,
        disclaimer=answer.disclaimer,
        missing_facts=answer.missing_facts,
        warnings=answer.warnings,
        rule_id=answer.rule_id,
        citation_errors=answer.citation_errors,
        blocked=answer.blocked,
        rendered=render(answer),
    )


def _claim_out(claim: Any) -> ClaimOut:
    return ClaimOut(text=claim.text, citations=[_citation_out(c) for c in claim.citations])


def _citation_out(citation: Any) -> CitationOut:
    return CitationOut(
        source_id=citation.source_id,
        span_index=citation.span_index,
        text=citation.text,
        hash=citation.hash,
    )

