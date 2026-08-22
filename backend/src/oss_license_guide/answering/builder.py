"""Assemble a structured answer from rule evaluation results.

Findings are assembled deterministically: obligations and their citations come
from the matched rule, never from a language model. Citation validation runs
here; any invalid or missing span blocks the substantive answer.
"""

from __future__ import annotations

from oss_license_guide.answering.answer import Answer, ClaimView, EvidenceEntry
from oss_license_guide.citations.resolver import ResolvedSpan, resolve_claims, validate_claims
from oss_license_guide.rules.evaluator import AnalysisResult
from oss_license_guide.rules.schema import AnalysisOutcome, ObligationClaim
from oss_license_guide.scenarios.schema import Scenario
from oss_license_guide.sources.catalog import Catalog


def build_answer(result: AnalysisResult, scenario: Scenario, catalog: Catalog) -> Answer:
    """Build a complete structured answer for ``result`` under ``scenario``."""
    obligations, citation_errors = _build_obligations(result, catalog)
    citation_errors.extend(validate_claims(result.obligations, catalog))

    permission, permission_errors = _build_permission(result, catalog)
    citation_errors.extend(permission_errors)

    views = obligations + ([permission] if permission is not None else [])

    answer = Answer(
        outcome=result.outcome.value,
        canonical=result.canonical,
        short_answer=_short_answer(result),
        assumptions=_assumptions(scenario),
        obligations=obligations,
        what_could_change=_what_could_change(result, scenario),
        evidence=_evidence(views),
        confidence=_confidence(result),
        escalation=_escalation(result),
        missing_facts=result.missing_facts,
        warnings=result.warnings,
        rule_id=result.rule_id,
        review_status=result.review_status,
        reviewer=result.reviewer,
        effective_date=result.effective_date,
        last_verified_at=result.last_verified_at,
        rule_version=result.rule_version,
        content_hash=result.content_hash,
        permission=permission,
        citation_errors=sorted(set(citation_errors)),
    )
    if answer.blocked:
        # A blocked answer must abstain, never retain a permission outcome.
        answer.outcome = _BLOCKED_OUTCOME
        answer.short_answer = _BLOCKED_SHORT_ANSWER
    return answer


_BLOCKED_OUTCOME = "Requires legal review"
_BLOCKED_SHORT_ANSWER = (
    "Analysis blocked because the supporting evidence could not be validated; "
    "no substantive conclusion is shown."
)


def _build_permission(
    result: AnalysisResult, catalog: Catalog
) -> tuple[ClaimView | None, list[str]]:
    """Represent and validate the material permission claim behind the outcome.

    Every permission outcome must be supported by a pinned source span, so a
    permission conclusion is never emitted with zero evidence.
    """
    errors: list[str] = []
    if result.outcome not in {
        AnalysisOutcome.LIKELY_PERMITTED,
        AnalysisOutcome.PERMITTED_WITH_OBLIGATIONS,
    }:
        return None, errors

    citations = list(result.permission_citations)
    claim = ObligationClaim(text=_permission_text(result), citations=citations)
    spans_per_claim, resolve_errors = resolve_claims([claim], catalog)
    errors.extend(resolve_errors)
    if not citations:
        errors.append(
            f"Permission outcome {result.outcome.value!r} has no source citation"
        )
    if citations and not spans_per_claim[0]:
        errors.append(
            f"Permission outcome {result.outcome.value!r} has no valid source citation"
        )
    view = ClaimView(
        text=claim.text,
        citations=[_evidence_entry(span) for span in spans_per_claim[0]],
    )
    return view, errors


def _permission_text(result: AnalysisResult) -> str:
    return f"Permission to use {result.canonical} under the stated scenario"


def _build_obligations(
    result: AnalysisResult, catalog: Catalog
) -> tuple[list[ClaimView], list[str]]:
    spans_per_claim, errors = resolve_claims(result.obligations, catalog)
    views: list[ClaimView] = []
    for claim, spans in zip(result.obligations, spans_per_claim):
        citations = [_evidence_entry(span) for span in spans]
        views.append(ClaimView(text=claim.text, citations=citations))
    return views, errors


def _evidence_entry(span: ResolvedSpan) -> EvidenceEntry:
    return EvidenceEntry(
        source_id=span.source_id,
        span_index=span.span_index,
        text=span.text,
        hash=span.hash,
        source_type=span.source_type,
        source_url=span.source_url,
        version=span.version,
        retrieved_at=span.retrieved_at,
    )


def _evidence(obligations: list[ClaimView]) -> list[EvidenceEntry]:
    seen: set[tuple[str, int]] = set()
    entries: list[EvidenceEntry] = []
    for claim in obligations:
        for citation in claim.citations:
            key = (citation.source_id, citation.span_index)
            if key not in seen:
                seen.add(key)
                entries.append(citation)
    return entries


def _short_answer(result: AnalysisResult) -> str:
    target = result.canonical
    if result.outcome is AnalysisOutcome.LIKELY_PERMITTED:
        return f"Under the stated scenario, {target} is likely permitted."
    if result.outcome is AnalysisOutcome.PERMITTED_WITH_OBLIGATIONS:
        return f"{target} is permitted provided the listed obligations are satisfied."
    if result.outcome is AnalysisOutcome.INSUFFICIENT_INFORMATION:
        return "Insufficient information to reach a conclusion; provide the missing facts."
    if result.outcome is AnalysisOutcome.NOT_SUPPORTED:
        return "The stated outbound-license goal is not supported by this outcome."
    return "This scenario requires review by qualified legal counsel."


def _assumptions(scenario: Scenario) -> list[str]:
    assumptions: list[str] = []
    for fact_type, fact in scenario.facts.items():
        if fact.known:
            assumptions.append(f"{fact_type.value} = {_fmt(fact.value)}")
    return assumptions


def _fmt(value: object) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _what_could_change(result: AnalysisResult, scenario: Scenario) -> list[str]:
    if result.missing_facts:
        return [f"Providing a value for: {fact}" for fact in result.missing_facts]
    return [
        "A different scenario fact could change this result.",
        "Whether any distribution occurs is material to this result.",
        "Judicial or agency interpretation of the license could differ.",
    ]


def _confidence(result: AnalysisResult) -> dict[str, str]:
    rule_coverage = "High" if result.rule_id else "Low"
    scenario_completeness = "High" if not result.missing_facts else "Low"
    expression = "Low" if result.outcome is AnalysisOutcome.INSUFFICIENT_INFORMATION else "High"
    return {
        "expression_parsing": expression,
        "rule_coverage": rule_coverage,
        "scenario_completeness": scenario_completeness,
    }


def _escalation(result: AnalysisResult) -> str:
    if result.escalation:
        return (
            "Qualified legal review is recommended because this outcome depends on "
            "interpretation or rule coverage that is not fully supported."
        )
    return (
        "No automatic escalation is triggered by this outcome; it is based on "
        "reviewed rules for the stated scenario. Because this is educational "
        "guidance, have qualified counsel review any decision with material legal "
        "or business impact."
    )
