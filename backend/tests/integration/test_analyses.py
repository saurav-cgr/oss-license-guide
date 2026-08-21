"""Integration tests for the deterministic scenario-analysis workflow."""

import pytest
from fastapi.testclient import TestClient

from oss_license_guide.api.app import create_app
from oss_license_guide.citations import validate_claims
from oss_license_guide.rules.eligibility import is_eligible
from oss_license_guide.rules.schema import Citation, ObligationClaim, ReviewStatus, Rule


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def analyze(client: TestClient, expression: str, facts: dict) -> dict:
    response = client.post("/api/v1/analyses", json={"expression": expression, "facts": facts})
    assert response.status_code == 200
    return response.json()


def test_mit_internal_use_is_permitted(client: TestClient) -> None:
    body = analyze(client, "MIT", {"action": "use", "distribution": False})
    assert body["outcome"] == "Likely permitted under stated assumptions"
    assert body["rule_id"] == "mit-internal-use"


def test_mit_source_distribution_unmodified_has_obligations(client: TestClient) -> None:
    body = analyze(
        client,
        "MIT",
        {
            "action": "redistribute",
            "distribution": True,
            "distribution_form": "source",
            "recipient": "public",
            "modified": False,
        },
    )
    assert body["outcome"] == "Permitted with listed obligations"
    texts = [claim["text"] for claim in body["obligations"]]
    assert any("license text" in text for text in texts)


def test_apache_binary_distribution_modified_has_obligations(client: TestClient) -> None:
    body = analyze(
        client,
        "Apache-2.0",
        {
            "action": "redistribute",
            "distribution": True,
            "distribution_form": "binary",
            "recipient": "customers",
            "modified": True,
        },
    )
    assert body["outcome"] == "Permitted with listed obligations"
    texts = [claim["text"] for claim in body["obligations"]]
    assert any("NOTICE" in text for text in texts)


def test_evidence_is_included_with_hashes(client: TestClient) -> None:
    body = analyze(
        client,
        "Apache-2.0",
        {
            "action": "redistribute",
            "distribution": True,
            "distribution_form": "binary",
            "recipient": "customers",
            "modified": True,
        },
    )
    assert body["evidence"], "expected evidence entries"
    for entry in body["evidence"]:
        assert entry["source_id"].startswith("spdx:")
        assert entry["hash"]


def test_rendered_contract_includes_required_sections(client: TestClient) -> None:
    body = analyze(client, "MIT", {"action": "use", "distribution": False})
    rendered = body["rendered"]
    assert "Outcome:" in rendered
    assert "Short answer:" in rendered
    assert "Obligations:" in rendered
    assert "Disclaimer:" in rendered
    assert "not legal advice" in body["disclaimer"]


def test_missing_facts_return_insufficient_information(client: TestClient) -> None:
    body = analyze(client, "MIT", {"action": "use"})
    assert body["outcome"] == "Insufficient information"
    assert "distribution" in body["missing_facts"]


def test_unsupported_expression_requires_legal_review(client: TestClient) -> None:
    body = analyze(
        client,
        "GPL-3.0-only",
        {"action": "use", "distribution": False},
    )
    assert body["outcome"] == "Requires legal review"


def test_or_expression_requires_branch_selection(client: TestClient) -> None:
    body = analyze(client, "MIT OR Apache-2.0", {"action": "use", "distribution": False})
    assert body["outcome"] == "Insufficient information"
    assert "selected_branch" in body["missing_facts"]


def test_or_expression_with_selected_branch_evaluates_that_branch(client: TestClient) -> None:
    body = analyze(
        client,
        "MIT OR Apache-2.0",
        {"action": "use", "distribution": False, "selected_branch": "MIT"},
    )
    assert body["outcome"] == "Likely permitted under stated assumptions"
    assert body["rule_id"] == "mit-internal-use"


def test_invalid_expression_abstains(client: TestClient) -> None:
    body = analyze(client, "MIT OR", {"action": "use", "distribution": False})
    assert body["outcome"] == "Insufficient information"


def test_invalid_span_blocks_answer() -> None:
    claim = ObligationClaim(
        text="A claim with a bad span",
        citations=[Citation(source_id="spdx:MIT@3.24.0", span_index=999)],
    )
    from oss_license_guide.sources import load_catalog

    errors = validate_claims([claim], load_catalog())
    assert errors


def test_ineligible_rule_cannot_support_conclusion() -> None:
    draft = Rule(
        rule_id="draft-test",
        license_expression_pattern="MIT",
        outcome="Permitted with listed obligations",
        review_status=ReviewStatus.DRAFT,
    )
    expired = Rule(
        rule_id="expired-test",
        license_expression_pattern="MIT",
        outcome="Permitted with listed obligations",
        review_status=ReviewStatus.EXPIRED,
    )
    reviewed = Rule(
        rule_id="reviewed-test",
        license_expression_pattern="MIT",
        outcome="Permitted with listed obligations",
        review_status=ReviewStatus.MAINTAINER_REVIEWED,
    )
    assert not is_eligible(draft)
    assert not is_eligible(expired)
    assert is_eligible(reviewed)
