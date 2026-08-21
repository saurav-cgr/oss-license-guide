"""Missing-fact detection for scenarios.

The detector returns every material fact that is absent. It never supplies a
favorable default: an unknown fact is reported as missing so the caller can ask
a focused question or return conditional branches.
"""

from __future__ import annotations

from oss_license_guide.expressions.service import parse_expression
from oss_license_guide.scenarios.facts import Action, FactType
from oss_license_guide.scenarios.schema import Scenario


def missing_facts(scenario: Scenario) -> list[FactType]:
    """Return the ordered list of material facts missing from ``scenario``."""
    missing: list[FactType] = []

    for fact_type in (FactType.ACTION, FactType.DISTRIBUTION):
        if not _is_known(scenario, fact_type):
            missing.append(fact_type)

    distributing = scenario.known_value(FactType.DISTRIBUTION)
    if distributing is True:
        for fact_type in (FactType.DISTRIBUTION_FORM, FactType.RECIPIENT, FactType.MODIFIED):
            if not _is_known(scenario, fact_type):
                missing.append(fact_type)

    action = scenario.known_value(FactType.ACTION)
    if action in {Action.AGGREGATE, Action.LINK, Action.SUBLICENSE}:
        if not _is_known(scenario, FactType.OUTBOUND_LICENSE):
            missing.append(FactType.OUTBOUND_LICENSE)

    if _is_disjunction(scenario.expression):
        if not _is_known(scenario, FactType.SELECTED_BRANCH):
            missing.append(FactType.SELECTED_BRANCH)

    return missing


def _is_known(scenario: Scenario, fact_type: FactType) -> bool:
    fact = scenario.get(fact_type)
    return fact is not None and fact.known


def _is_disjunction(expression: str) -> bool:
    result = parse_expression(expression)
    if not result.ok or result.structure is None:
        return False
    return result.structure.get("type") == "or"
