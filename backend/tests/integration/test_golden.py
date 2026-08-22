"""Milestone 7 golden evaluation suite.

Runs the maintainer-reviewed golden cases through the public analysis workflow
and asserts the MVP acceptance targets. Each case goes through the FastAPI
boundary (POST /api/v1/analyses); no internal domain functions are called
directly and no network is used (provider is None).
"""

from collections import Counter

import pytest
from golden_eval import (
    build_report,
    format_report,
    load_cases,
    run_suite,
)

CATEGORY_MINIMUMS = {
    "mit_supported": 10,
    "apache_supported": 15,
    "or_branch": 5,
    "missing_facts": 8,
    "unsupported": 6,
    "invalid": 6,
    "conflicting_or_missing_evidence": 4,
    "adversarial": 6,
}


@pytest.fixture(scope="module")
def suite():
    cases = load_cases()
    results = run_suite(cases)
    return cases, results, build_report(results)


def test_suite_has_required_composition_and_minimums() -> None:
    cases = load_cases()
    counts = Counter(case.category for case in cases)
    assert len(cases) >= 60, f"golden set has {len(cases)} cases"
    for category, minimum in CATEGORY_MINIMUMS.items():
        assert counts[category] >= minimum, f"{category}: {counts[category]} < {minimum}"


def test_no_severe_unsafe_answers(suite) -> None:
    _, _, report = suite
    assert report.severe_count == 0, "Severe unsafe answers:\n" + "\n".join(
        report.severe_cases
    )


def test_citation_coverage_target(suite) -> None:
    _, _, report = suite
    assert report.coverage.total > 0
    assert report.coverage.rate >= 0.99, f"coverage {report.coverage.rate:.3f}"


def test_citation_entailment_target(suite) -> None:
    _, _, report = suite
    assert report.entailment.total > 0
    assert report.entailment.rate >= 0.98, f"entailment {report.entailment.rate:.3f}"


def test_required_context_recall_target(suite) -> None:
    _, _, report = suite
    assert report.context_recall.total > 0
    assert report.context_recall.rate >= 0.95, f"context recall {report.context_recall.rate:.3f}"


def test_unsupported_abstention_recall_target(suite) -> None:
    _, _, report = suite
    assert report.abstention_recall.total > 0
    assert (
        report.abstention_recall.rate >= 0.98
    ), f"abstention recall {report.abstention_recall.rate:.3f}"


def test_parser_abstention_target(suite) -> None:
    _, _, report = suite
    assert report.parser_pass.total > 0
    assert report.parser_pass.rate >= 0.99, f"parser abstention {report.parser_pass.rate:.3f}"


def test_report_includes_composition_and_confidence_intervals(suite) -> None:
    _, _, report = suite
    text = format_report(report)
    assert "Composition" in text
    assert "95% CI" in text
    assert f"Severe unsafe answers: {report.severe_count}" in text
