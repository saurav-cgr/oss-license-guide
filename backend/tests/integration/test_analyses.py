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
            "license_file_present": True,
            "copyright_notice_present": True,
            "notice_file_present": False,
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
            "license_file_present": True,
            "copyright_notice_present": True,
            "notice_file_present": True,
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
            "license_file_present": True,
            "copyright_notice_present": True,
            "notice_file_present": True,
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


def test_and_expression_abstains_not_first_license(client: TestClient) -> None:
    body = analyze(
        client,
        "MIT AND GPL-2.0-only",
        {"action": "use", "distribution": False},
    )
    assert body["outcome"] in {"Insufficient information", "Requires legal review"}
    assert body["rule_id"] is None


def test_with_expression_abstains_not_first_license(client: TestClient) -> None:
    body = analyze(
        client,
        "MIT WITH Classpath-exception-2.0",
        {"action": "use", "distribution": False},
    )
    assert body["outcome"] in {"Insufficient information", "Requires legal review"}
    assert body["rule_id"] is None


def test_grouped_or_requires_branch_not_collapse(client: TestClient) -> None:
    body = analyze(
        client,
        "(MIT OR Apache-2.0)",
        {"action": "use", "distribution": False, "selected_branch": "MIT"},
    )
    assert body["outcome"] == "Likely permitted under stated assumptions"
    assert body["rule_id"] == "mit-internal-use"


def test_compound_or_abstains(client: TestClient) -> None:
    body = analyze(
        client,
        "MIT OR (Apache-2.0 OR GPL-2.0-only)",
        {"action": "use", "distribution": False},
    )
    assert body["outcome"] in {"Insufficient information", "Requires legal review"}
    assert body["rule_id"] is None


def test_or_branch_compared_canonically(client: TestClient) -> None:
    # The deprecated branch GPL-2.0 canonicalizes to GPL-2.0-only; selecting
    # GPL-2.0-only must not be rejected as "not a branch". GPL is still outside
    # the MVP rule set, so the answer must abstain rather than claim permission.
    body = analyze(
        client,
        "GPL-2.0 OR MIT",
        {"action": "use", "distribution": False, "selected_branch": "GPL-2.0-only"},
    )
    assert body["outcome"] in {"Insufficient information", "Requires legal review"}
    assert body["rule_id"] is None


def test_contradictory_use_with_distribution_abstains(client: TestClient) -> None:
    body = analyze(
        client,
        "MIT",
        {
            "action": "use",
            "distribution": True,
            "distribution_form": "source",
            "recipient": "public",
            "modified": False,
        },
    )
    assert body["outcome"] in {"Insufficient information", "Requires legal review"}


def test_link_with_outbound_license_abstains(client: TestClient) -> None:
    body = analyze(
        client,
        "MIT",
        {"action": "link", "distribution": False, "outbound_license": "MIT"},
    )
    assert body["outcome"] in {"Insufficient information", "Requires legal review"}
    assert body["rule_id"] is None


def test_sublicense_with_outbound_license_abstains(client: TestClient) -> None:
    body = analyze(
        client,
        "MIT",
        {
            "action": "sublicense",
            "distribution": True,
            "distribution_form": "source",
            "recipient": "public",
            "modified": False,
            "outbound_license": "MIT",
        },
    )
    assert body["outcome"] in {"Insufficient information", "Requires legal review"}
    assert body["rule_id"] is None


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


def test_unsupported_or_set_abstains_even_with_supported_branch(
    client: TestClient,
) -> None:
    body = analyze(
        client,
        "MIT OR GPL-3.0-only",
        {"action": "use", "distribution": False, "selected_branch": "MIT"},
    )
    assert body["outcome"] == "Requires legal review"
    assert body["rule_id"] is None


def test_three_way_or_expression_abstains(client: TestClient) -> None:
    body = analyze(
        client,
        "MIT OR Apache-2.0 OR GPL-3.0-only",
        {"action": "use", "distribution": False, "selected_branch": "MIT"},
    )
    assert body["outcome"] == "Requires legal review"
    assert body["rule_id"] is None


def test_grouped_or_branch_evaluates_like_flat_or(client: TestClient) -> None:
    body = analyze(
        client,
        "(MIT) OR Apache-2.0",
        {"action": "use", "distribution": False, "selected_branch": "MIT"},
    )
    assert body["outcome"] == "Likely permitted under stated assumptions"
    assert body["rule_id"] == "mit-internal-use"


def test_modify_action_abstains(client: TestClient) -> None:
    body = analyze(client, "MIT", {"action": "modify", "distribution": False})
    assert body["outcome"] == "Requires legal review"
    assert body["rule_id"] is None


def test_aggregate_action_abstains(client: TestClient) -> None:
    body = analyze(
        client,
        "MIT",
        {
            "action": "aggregate",
            "distribution": True,
            "distribution_form": "source",
            "recipient": "public",
            "modified": False,
            "outbound_license": "MIT",
            "license_file_present": True,
            "copyright_notice_present": True,
            "notice_file_present": False,
        },
    )
    assert body["outcome"] == "Requires legal review"
    assert body["rule_id"] is None


def test_outbound_license_abstains_even_for_redistribute(client: TestClient) -> None:
    body = analyze(
        client,
        "MIT",
        {
            "action": "redistribute",
            "distribution": True,
            "distribution_form": "source",
            "recipient": "public",
            "modified": False,
            "outbound_license": "MIT",
            "license_file_present": True,
            "copyright_notice_present": True,
            "notice_file_present": False,
        },
    )
    assert body["outcome"] == "Requires legal review"
    assert body["rule_id"] is None


def test_permission_claim_is_cited_in_response(client: TestClient) -> None:
    body = analyze(client, "MIT", {"action": "use", "distribution": False})
    permission = body["permission"]
    assert permission is not None
    assert "Permission to use MIT" in permission["text"]
    assert permission["citations"], "permission claim must carry a citation"
    assert permission["citations"][0]["source_id"].startswith("spdx:MIT")


def test_rule_version_and_content_hash_are_exposed(client: TestClient) -> None:
    body = analyze(client, "MIT", {"action": "use", "distribution": False})
    rule = body["rule"]
    assert rule is not None
    assert rule["rule_id"] == "mit-internal-use"
    assert rule["content_hash"]
    assert body["rule_id"] == "mit-internal-use"


def test_deprecated_identifier_canonicalizes_with_warning(client: TestClient) -> None:
    body = analyze(client, "GPL-2.0", {"action": "use", "distribution": False})
    assert body["canonical"] == "GPL-2.0-only"
    assert any("deprecated" in warning for warning in body["warnings"])
    assert body["outcome"] == "Requires legal review"


def test_question_does_not_change_deterministic_result(client: TestClient) -> None:
    base = analyze(client, "MIT", {"action": "use", "distribution": False})
    with_question = client.post(
        "/api/v1/analyses",
        json={
            "expression": "MIT",
            "facts": {"action": "use", "distribution": False},
            "question": "Can we use this internally without distributing it?",
        },
    ).json()
    assert with_question["outcome"] == base["outcome"]
    assert with_question["obligations"] == base["obligations"]
    assert with_question["rule_id"] == base["rule_id"]
    assert with_question["permission"] == base["permission"]
