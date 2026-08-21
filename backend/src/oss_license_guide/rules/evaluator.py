"""Deterministic scenario rule evaluation.

The evaluator applies eligible, versioned rules to a scenario. It never asks a
language model to decide a rule. Missing facts, unsupported expressions, and
ineligible rules force abstention with a structured outcome.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from oss_license_guide.expressions.service import parse_expression
from oss_license_guide.rules.eligibility import is_eligible
from oss_license_guide.rules.schema import AnalysisOutcome, Rule
from oss_license_guide.scenarios.facts import FactType
from oss_license_guide.scenarios.missing import missing_facts
from oss_license_guide.scenarios.schema import Scenario


@dataclass
class AnalysisResult:
    """Structured outcome of deterministic rule evaluation."""

    outcome: AnalysisOutcome
    canonical: str
    obligations: list[str] = field(default_factory=list)
    missing_facts: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    rule_id: str | None = None

    @property
    def escalation(self) -> bool:
        return self.outcome in {
            AnalysisOutcome.NOT_SUPPORTED,
            AnalysisOutcome.REQUIRES_LEGAL_REVIEW,
        }


def evaluate(scenario: Scenario, rules: list[Rule]) -> AnalysisResult:
    """Evaluate ``scenario`` against ``rules`` deterministically."""
    parse_result = parse_expression(scenario.expression)
    if not parse_result.ok or parse_result.structure is None:
        message = (
            parse_result.diagnostics[0].message
            if parse_result.diagnostics
            else "Invalid expression"
        )
        return _insufficient(canonical=scenario.expression, warnings=[message])

    canonical = parse_result.canonical or scenario.expression
    target = _resolve_target(parse_result.structure, scenario)
    if isinstance(target, AnalysisResult):
        return target

    missing = [fact.value for fact in missing_facts(scenario)]
    if missing:
        return _insufficient(canonical=canonical, missing_facts=missing)

    rule = _match_rule(target, scenario, rules)
    if rule is None:
        return AnalysisResult(
            outcome=AnalysisOutcome.REQUIRES_LEGAL_REVIEW,
            canonical=canonical,
            warnings=[f"No reviewed rule covers {target!r} under the stated scenario"],
        )

    return AnalysisResult(
        outcome=AnalysisOutcome(rule.outcome),
        canonical=canonical,
        obligations=list(rule.obligations),
        rule_id=rule.rule_id,
    )


def _resolve_target(structure: dict, scenario: Scenario) -> str | AnalysisResult:
    """Resolve the license whose rules should apply, handling OR branches."""
    if structure.get("type") != "or":
        return _collect_primary_license(structure)

    branches = _collect_license_ids(structure)
    selected = scenario.known_value(FactType.SELECTED_BRANCH)
    if selected is None:
        return _insufficient(
            canonical=scenario.expression,
            missing_facts=[FactType.SELECTED_BRANCH.value],
        )
    if selected not in branches:
        return _insufficient(
            canonical=scenario.expression,
            warnings=[f"{selected!r} is not a branch of {scenario.expression!r}"],
        )
    return selected


def _collect_primary_license(structure: dict) -> str:
    ids = _collect_license_ids(structure)
    return ids[0] if ids else ""


def _collect_license_ids(structure: dict) -> list[str]:
    ids: list[str] = []

    def walk(node: dict) -> None:
        node_type = node.get("type")
        if node_type == "license":
            ids.append(node["id"])
        else:
            for key in ("left", "right", "base", "inner"):
                child = node.get(key)
                if isinstance(child, dict):
                    walk(child)

    walk(structure)
    return ids


def _match_rule(target: str, scenario: Scenario, rules: list[Rule]) -> Rule | None:
    for rule in rules:
        if not is_eligible(rule):
            continue
        if rule.license_expression_pattern != target:
            continue
        if _preconditions_match(rule, scenario):
            return rule
    return None


def _preconditions_match(rule: Rule, scenario: Scenario) -> bool:
    for key, expected in rule.scenario_preconditions.items():
        actual = scenario.known_value(FactType(key))
        if actual is None or _norm(actual) != _norm(expected):
            return False
    return True


def _norm(value: object) -> object:
    return value.value if isinstance(value, Enum) else value


def _insufficient(
    canonical: str,
    missing_facts: list[str] | None = None,
    warnings: list[str] | None = None,
) -> AnalysisResult:
    return AnalysisResult(
        outcome=AnalysisOutcome.INSUFFICIENT_INFORMATION,
        canonical=canonical,
        missing_facts=missing_facts or [],
        warnings=warnings or [],
    )
