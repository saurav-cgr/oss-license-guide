"""Scenario analysis endpoint running the bounded deterministic workflow."""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from oss_license_guide.rules import evaluate, load_rules
from oss_license_guide.scenarios.facts import FactType, Provenance
from oss_license_guide.scenarios.schema import Fact, Scenario

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


class AnalysisResponse(BaseModel):
    outcome: str
    canonical: str
    obligations: list[str] = []
    missing_facts: list[str] = []
    warnings: list[str] = []
    rule_id: str | None = None
    escalation: bool = False


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
    return AnalysisResponse(
        outcome=result.outcome.value,
        canonical=result.canonical,
        obligations=result.obligations,
        missing_facts=result.missing_facts,
        warnings=result.warnings,
        rule_id=result.rule_id,
        escalation=result.escalation,
    )
