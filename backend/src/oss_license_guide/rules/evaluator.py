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
from oss_license_guide.rules.schema import AnalysisOutcome, Citation, ObligationClaim, Rule
from oss_license_guide.scenarios.facts import Action, FactType
from oss_license_guide.scenarios.missing import missing_facts
from oss_license_guide.scenarios.schema import Scenario


@dataclass
class AnalysisResult:
    """Structured outcome of deterministic rule evaluation."""

    outcome: AnalysisOutcome
    canonical: str
    obligations: list[ObligationClaim] = field(default_factory=list)
    permission_citations: list[Citation] = field(default_factory=list)
    missing_facts: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    rule_id: str | None = None
    review_status: str | None = None
    reviewer: str | None = None
    effective_date: str | None = None
    last_verified_at: str | None = None
    rule_version: str | None = None
    content_hash: str | None = None

    @property
    def escalation(self) -> bool:
        return self.outcome in {
            AnalysisOutcome.NOT_SUPPORTED,
            AnalysisOutcome.REQUIRES_LEGAL_REVIEW,
        }


# The only OR branch set with rule-backed MVP coverage.
_SUPPORTED_OR_BRANCHES = {"MIT", "Apache-2.0"}

# The only actions that may produce a substantive conclusion. Modification is
# expressed through the ``modified`` fact under ``redistribute``; every other
# action verb is outside the reviewed rule set and forces abstention.
_SUPPORTED_ACTIONS = {Action.USE.value, Action.REDISTRIBUTE.value}


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
    parse_warnings = list(parse_result.warnings)

    target = _resolve_target(parse_result.structure, scenario, canonical, parse_warnings)
    if isinstance(target, AnalysisResult):
        return target

    missing = [fact.value for fact in missing_facts(scenario)]
    if missing:
        return _insufficient(canonical=canonical, missing_facts=missing, warnings=parse_warnings)

    consistency_warnings = _consistency_warnings(scenario)
    if consistency_warnings:
        return _insufficient(
            canonical=canonical, warnings=parse_warnings + consistency_warnings
        )

    action = scenario.known_value(FactType.ACTION)
    if action not in _SUPPORTED_ACTIONS:
        return AnalysisResult(
            outcome=AnalysisOutcome.REQUIRES_LEGAL_REVIEW,
            canonical=canonical,
            warnings=parse_warnings
            + [f"action {action!r} is not covered by the reviewed MVP rule set"],
        )

    if scenario.known_value(FactType.OUTBOUND_LICENSE) is not None:
        return AnalysisResult(
            outcome=AnalysisOutcome.REQUIRES_LEGAL_REVIEW,
            canonical=canonical,
            warnings=parse_warnings
            + [
                "a stated outbound license implies a combining or relicensing "
                "question that is outside the reviewed MVP rule set"
            ],
        )

    rule = _match_rule(target, scenario, rules)
    if rule is None:
        return AnalysisResult(
            outcome=AnalysisOutcome.REQUIRES_LEGAL_REVIEW,
            canonical=canonical,
            warnings=parse_warnings
            + [f"No reviewed rule covers {target!r} under the stated scenario"],
        )

    return AnalysisResult(
        outcome=AnalysisOutcome(rule.outcome),
        canonical=canonical,
        obligations=list(rule.obligations),
        permission_citations=list(rule.permission_citations),
        rule_id=rule.rule_id,
        review_status=rule.review_status.value,
        reviewer=rule.reviewer,
        effective_date=rule.effective_date,
        last_verified_at=rule.last_verified_at,
        rule_version=rule.rule_version,
        content_hash=rule.content_hash,
        warnings=parse_warnings,
    )


def _resolve_target(
    structure: dict,
    scenario: Scenario,
    canonical: str,
    warnings: list[str],
) -> str | AnalysisResult:
    """Resolve the license whose rules apply, supporting only exact shapes.

    Only a single license and ``MIT OR Apache-2.0`` are evaluated. AND, WITH,
    grouping, and any OR branch that is not a plain license cause abstention.
    Selected branches are compared by their canonical form so deprecated
    spellings do not spuriously fail. Every OR set other than exactly
    {MIT, Apache-2.0} is rejected even when a selected branch is supported.
    """
    branches = _supported_branches(structure)
    if branches is None:
        return AnalysisResult(
            outcome=AnalysisOutcome.REQUIRES_LEGAL_REVIEW,
            canonical=canonical,
            warnings=warnings + ["Only single-license and flat OR expressions are supported"],
        )
    if len(branches) == 1:
        return _canonical_id(branches[0])

    canonical_branches = {_canonical_id(branch) for branch in branches}
    if canonical_branches != _SUPPORTED_OR_BRANCHES:
        return AnalysisResult(
            outcome=AnalysisOutcome.REQUIRES_LEGAL_REVIEW,
            canonical=canonical,
            warnings=warnings
            + [
                "OR expression outside the reviewed MVP coverage "
                "(only MIT OR Apache-2.0 is rule-backed)"
            ],
        )

    selected = scenario.known_value(FactType.SELECTED_BRANCH)
    if selected is None:
        return _insufficient(
            canonical=canonical,
            missing_facts=[FactType.SELECTED_BRANCH.value],
            warnings=warnings,
        )
    selected_canonical = _canonical_id(selected)
    if selected_canonical not in canonical_branches:
        return _insufficient(
            canonical=canonical,
            warnings=warnings
            + [f"{selected!r} is not a branch of {scenario.expression!r}"],
        )
    return selected_canonical


def _supported_branches(structure: dict) -> list[str] | None:
    """Return raw license ids for a supported shape, else None to abstain."""
    node = _strip_groups(structure)
    if node["type"] == "license":
        return [node["id"]]
    if node["type"] != "or":
        return None
    return _pure_or_branches(node)


def _strip_groups(node: dict) -> dict:
    """Remove redundant grouping that wraps an entire expression."""
    while node.get("type") == "group":
        node = node["inner"]
    return node


def _pure_or_branches(node: dict) -> list[str] | None:
    """Return all license ids if ``node`` is a pure OR tree of direct licenses."""
    node = _strip_groups(node)
    if node["type"] == "license":
        return [node["id"]]
    if node["type"] != "or":
        return None
    left = _pure_or_branches(node["left"])
    right = _pure_or_branches(node["right"])
    if left is None or right is None:
        return None
    return left + right


def _canonical_id(identifier: str) -> str:
    """Return the canonical form of a single license identifier."""
    parsed = parse_expression(identifier)
    if parsed.ok and parsed.canonical:
        return parsed.canonical
    return identifier


def _consistency_warnings(scenario: Scenario) -> list[str]:
    """Return warnings for materially contradictory action/distribution facts."""
    action = scenario.known_value(FactType.ACTION)
    distribution = scenario.known_value(FactType.DISTRIBUTION)
    warnings: list[str] = []
    if action == Action.USE.value and distribution is True:
        warnings.append("action 'use' conflicts with distribution=true")
    if action == Action.REDISTRIBUTE.value and distribution is False:
        warnings.append("action 'redistribute' conflicts with distribution=false")
    return warnings


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
