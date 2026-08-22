"""Golden evaluation harness for the safety milestone.

Each golden case runs through the public analysis workflow (POST
/api/v1/analyses via the FastAPI TestClient) and is scored against an expected
structured result. The harness computes citation coverage, citation entailment,
required-context recall, unsupported-case abstention recall, a severe-answer
triage, a test-set composition, and Wilson confidence intervals.

All cases are deterministic and offline: no provider is used, so the workflow
makes no network calls.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

from fastapi.testclient import TestClient

from oss_license_guide.api.app import create_app

GOLDEN_DIR = Path(__file__).resolve().parents[2] / "data" / "golden"

ABSTENTION_OUTCOMES = {"Insufficient information", "Requires legal review"}
PERMISSION_OUTCOMES = {
    "Likely permitted under stated assumptions",
    "Permitted with listed obligations",
}


@dataclass
class GoldenExpect:
    """The expected structured result for a case."""

    outcome: str | None = None
    required_citations: list[tuple[str, int]] = field(default_factory=list)
    expected_claims: list[dict] = field(default_factory=list)
    obligations_include: list[str] = field(default_factory=list)
    must_abstain: bool = False
    mandatory_escalation: bool = False
    required_missing_facts: list[str] = field(default_factory=list)
    forbidden_outcomes: list[str] = field(default_factory=list)
    block_expected: bool = False
    no_obligations: bool = False
    no_evidence: bool = False


@dataclass
class GoldenCase:
    """One versioned evaluation case."""

    case_id: str
    category: str
    description: str
    request: dict
    expect: GoldenExpect


@dataclass
class CaseResult:
    """Per-case evaluation outcome."""

    case_id: str
    category: str
    outcome_match: bool
    coverage_hits: int
    coverage_total: int
    entailment_hits: int
    entailment_total: int
    context_hits: int
    context_total: int
    abstained: bool | None
    severe: bool
    severe_reasons: list[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)


def load_cases(directory: Path = GOLDEN_DIR) -> list[GoldenCase]:
    """Load and validate all golden case files in ``directory``."""
    cases: list[GoldenCase] = []
    for path in sorted(directory.glob("*.json")):
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        for item in payload["cases"]:
            cases.append(_parse_case(item, path.stem))
    return cases


def _parse_case(item: dict, category: str) -> GoldenCase:
    expect = item["expect"]
    required_citations = [
        (ref["source_id"], int(ref["span_index"]))
        for ref in expect.get("required_citations", [])
    ]
    return GoldenCase(
        case_id=item["case_id"],
        category=item.get("category", category),
        description=item.get("description", ""),
        request=item["request"],
        expect=GoldenExpect(
            outcome=expect.get("outcome"),
            required_citations=required_citations,
            expected_claims=expect.get("expected_claims", []),
            obligations_include=expect.get("obligations_include", []),
            must_abstain=bool(expect.get("must_abstain", False)),
            mandatory_escalation=bool(expect.get("mandatory_escalation", False)),
            required_missing_facts=expect.get("required_missing_facts", []),
            forbidden_outcomes=expect.get("forbidden_outcomes", []),
            block_expected=bool(expect.get("block_expected", False)),
            no_obligations=bool(expect.get("no_obligations", False)),
            no_evidence=bool(expect.get("no_evidence", False)),
        ),
    )


def run_case(client: TestClient, case: GoldenCase) -> tuple[CaseResult, dict]:
    """Run one case through the analysis workflow and score it."""
    response = client.post("/api/v1/analyses", json=case.request)
    actual = response.json()

    actual_citations = _collect_citations(actual)
    result = _score(case, actual, actual_citations)
    result.details = {
        "outcome": actual.get("outcome"),
        "missing_facts": actual.get("missing_facts", []),
        "obligations": [claim.get("text") for claim in actual.get("obligations", [])],
        "blocked": bool(actual.get("blocked")),
        "http_status": response.status_code,
    }
    return result, actual


def run_suite(cases: list[GoldenCase]) -> list[tuple[GoldenCase, CaseResult, dict]]:
    """Run every case through a shared client and return scored results."""
    client = TestClient(create_app())
    return [(case, *run_case(client, case)) for case in cases]


def _score(case: GoldenCase, actual: dict, actual_citations: set[tuple[str, int]]) -> CaseResult:
    outcome = actual.get("outcome")
    blocked = bool(actual.get("blocked"))
    severe_reasons: list[str] = []

    expected_citations = set(case.expect.required_citations)
    for claim in case.expect.expected_claims:
        expected_citations.add((claim["source_id"], int(claim["span_index"])))
    coverage_total = len(expected_citations)
    coverage_hits = len(expected_citations & actual_citations) if coverage_total else 0

    entailment_total = len(case.expect.expected_claims)
    entailment_hits = sum(
        1
        for claim in case.expect.expected_claims
        if _claim_supported(actual, claim)
    )

    context_total = len(case.expect.required_missing_facts)
    actual_missing = set(actual.get("missing_facts", []))
    context_hits = (
        sum(1 for fact in case.expect.required_missing_facts if fact in actual_missing)
        if context_total
        else 0
    )

    abstained = None
    if case.expect.must_abstain:
        abstained = outcome in ABSTENTION_OUTCOMES or blocked
        if not abstained:
            severe_reasons.append(f"expected abstention but got {outcome!r}")

    outcome_match = case.expect.outcome is None or outcome == case.expect.outcome
    if case.expect.outcome and not outcome_match:
        severe_reasons.append(
            f"outcome mismatch: expected {case.expect.outcome!r}, got {outcome!r}"
        )

    # A permission outcome that fails to provide a required citation is severe:
    # it emits an unsupported material claim.
    if (
        not blocked
        and outcome in PERMISSION_OUTCOMES
        and coverage_total
        and coverage_hits < coverage_total
    ):
        severe_reasons.append("permission outcome missing a required citation")

    if case.expect.block_expected and not blocked:
        severe_reasons.append("expected a blocked answer but it was not blocked")

    if case.expect.no_obligations and actual.get("obligations"):
        severe_reasons.append("expected no obligations but obligations were emitted")
    if case.expect.no_evidence and actual.get("evidence"):
        severe_reasons.append("expected no evidence but evidence was emitted")

    for forbidden in case.expect.forbidden_outcomes:
        if outcome == forbidden:
            severe_reasons.append(f"forbidden outcome emitted: {forbidden!r}")

    for required in case.expect.obligations_include:
        texts = [claim.get("text", "") for claim in actual.get("obligations", [])]
        if not any(required.lower() in text.lower() for text in texts):
            severe_reasons.append(f"required obligation absent: {required!r}")

    # Mandatory escalation: the review-guidance must be present when required.
    if case.expect.mandatory_escalation and not actual.get("escalation"):
        severe_reasons.append("mandatory escalation missing")

    return CaseResult(
        case_id=case.case_id,
        category=case.category,
        outcome_match=outcome_match,
        coverage_hits=coverage_hits,
        coverage_total=coverage_total,
        entailment_hits=entailment_hits,
        entailment_total=entailment_total,
        context_hits=context_hits,
        context_total=context_total,
        abstained=abstained,
        severe=bool(severe_reasons),
        severe_reasons=severe_reasons,
    )


def _claim_supported(actual: dict, claim: dict) -> bool:
    """Return True if an obligation matching ``claim`` cites its required span."""
    target_span = (claim["source_id"], int(claim["span_index"]))
    needle = claim["text"].lower()
    for obligation in actual.get("obligations", []):
        text = obligation.get("text", "").lower()
        if needle not in text:
            continue
        citations = {
            (citation["source_id"], int(citation["span_index"]))
            for citation in obligation.get("citations", [])
        }
        if target_span in citations:
            return True
    return False


def _collect_citations(actual: dict) -> set[tuple[str, int]]:
    citations: set[tuple[str, int]] = set()
    for obligation in actual.get("obligations", []):
        for citation in obligation.get("citations", []):
            citations.add((citation["source_id"], int(citation["span_index"])))
    for entry in actual.get("evidence", []):
        citations.add((entry["source_id"], int(entry["span_index"])))
    return citations


@dataclass
class Metric:
    """A scored proportion with a Wilson confidence interval."""

    hits: int
    total: int

    @property
    def rate(self) -> float:
        return self.hits / self.total if self.total else 1.0

    def interval(self, z: float = 1.96) -> tuple[float, float]:
        if self.total == 0:
            return (1.0, 1.0)
        return wilson_interval(self.hits, self.total, z)


def wilson_interval(hits: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """Return the Wilson score interval for a binomial proportion."""
    if total == 0:
        return (1.0, 1.0)
    p = hits / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    margin = (
        z
        * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total)
        / denominator
    )
    return (max(0.0, centre - margin), min(1.0, centre + margin))


@dataclass
class SuiteReport:
    """Aggregated evaluation report with composition and metrics."""

    total: int
    categories: dict[str, int]
    coverage: Metric
    entailment: Metric
    context_recall: Metric
    abstention_recall: Metric
    severe_count: int
    severe_cases: list[str]
    outcome_match: Metric
    parser_pass: Metric


def build_report(results: list[tuple[GoldenCase, CaseResult, dict]]) -> SuiteReport:
    categories: dict[str, int] = {}
    coverage = Metric(0, 0)
    entailment = Metric(0, 0)
    context = Metric(0, 0)
    abstention = Metric(0, 0)
    outcome = Metric(0, 0)
    parser = Metric(0, 0)
    severe_cases: list[str] = []

    for case, result, _ in results:
        categories[result.category] = categories.get(result.category, 0) + 1
        coverage.hits += result.coverage_hits
        coverage.total += result.coverage_total
        entailment.hits += result.entailment_hits
        entailment.total += result.entailment_total
        context.hits += result.context_hits
        context.total += result.context_total
        outcome.hits += 1 if result.outcome_match else 0
        outcome.total += 1
        if result.abstained is not None:
            abstention.hits += 1 if result.abstained else 0
            abstention.total += 1
        if case.category in {"unsupported", "invalid"}:
            parser.hits += 1 if result.abstained else 0
            parser.total += 1
        if result.severe:
            severe_cases.append(f"{result.case_id}: {'; '.join(result.severe_reasons)}")

    return SuiteReport(
        total=len(results),
        categories=categories,
        coverage=coverage,
        entailment=entailment,
        context_recall=context,
        abstention_recall=abstention,
        severe_count=len(severe_cases),
        severe_cases=severe_cases,
        outcome_match=outcome,
        parser_pass=parser,
    )


def format_report(report: SuiteReport) -> str:
    """Render a human-readable report including composition and confidence intervals."""
    lines = [
        f"Golden evaluation suite: {report.total} cases",
        "",
        "Composition:",
    ]
    for category in sorted(report.categories):
        lines.append(f"  {category}: {report.categories[category]}")
    lines.append("")
    lines.append(f"Severe unsafe answers: {report.severe_count}")
    if report.severe_cases:
        lines.append("Severe cases:")
        lines.extend(f"  - {item}" for item in report.severe_cases)
    lines.append("")
    for label, metric in [
        ("Material-claim citation coverage", report.coverage),
        ("Citation entailment accuracy", report.entailment),
        ("Required-context detection recall", report.context_recall),
        ("Unsupported-case abstention recall", report.abstention_recall),
        ("Outcome match", report.outcome_match),
        ("Parser abstention pass (unsupported+invalid)", report.parser_pass),
    ]:
        low, high = metric.interval()
        lines.append(
            f"{label}: {metric.hits}/{metric.total} = {metric.rate:.3f} "
            f"(95% CI {low:.3f}-{high:.3f})"
        )
    return "\n".join(lines)
