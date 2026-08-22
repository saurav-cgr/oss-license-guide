"""Integration tests for SPDX expression parsing through the API boundary."""

import pytest
from fastapi.testclient import TestClient

from oss_license_guide.api.app import create_app

VALID_EXPRESSIONS = [
    ("MIT", "MIT"),
    ("Apache-2.0", "Apache-2.0"),
    ("MIT OR Apache-2.0", "MIT OR Apache-2.0"),
    ("MIT AND Apache-2.0", "MIT AND Apache-2.0"),
    ("GPL-3.0-only", "GPL-3.0-only"),
    ("GPL-3.0-or-later", "GPL-3.0-or-later"),
    ("GPL-2.0+", "GPL-2.0-or-later"),
    ("GPL-2.0-only WITH Classpath-exception-2.0", "GPL-2.0-only WITH Classpath-exception-2.0"),
    ("(MIT OR Apache-2.0) AND GPL-3.0-only", "(MIT OR Apache-2.0) AND GPL-3.0-only"),
    ("MIT OR (Apache-2.0 AND GPL-3.0-only)", "MIT OR (Apache-2.0 AND GPL-3.0-only)"),
    ("LicenseRef-Proprietary", "LicenseRef-Proprietary"),
    (
        "DocumentRef-spdx-tool-1.2:LicenseRef-MIT-Style-2",
        "DocumentRef-spdx-tool-1.2:LicenseRef-MIT-Style-2",
    ),
    ("mit or apache-2.0", "mit OR apache-2.0"),
]

DEPRECATED_EXPRESSIONS = [
    ("GPL-2.0", "GPL-2.0-only"),
    ("LGPL-2.1", "LGPL-2.1-only"),
    ("GPL-3.0", "GPL-3.0-only"),
]

INVALID_EXPRESSIONS = [
    "",
    "   ",
    "MIT OR",
    "AND MIT",
    "(MIT OR Apache-2.0",
    "MIT OR Apache-2.0)",
    "MIT Apache-2.0",
    "LicenseRef-x+",
    "MIT WITH",
    "MIT !",
    "()",
]


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def parse(client: TestClient, expression: str) -> dict:
    response = client.post("/api/v1/expressions/parse", json={"expression": expression})
    assert response.status_code == 200
    return response.json()


def test_grammar_corpus_passes_completely(client: TestClient) -> None:
    for expression, expected_canonical in VALID_EXPRESSIONS:
        body = parse(client, expression)
        assert body["valid"] is True, f"{expression!r} should be valid: {body}"
        assert body["canonical"] == expected_canonical, f"{expression!r} canonical mismatch"
        assert body["structure"] is not None


def test_deprecated_mapping_corpus_passes_completely(client: TestClient) -> None:
    for expression, expected_canonical in DEPRECATED_EXPRESSIONS:
        body = parse(client, expression)
        assert body["valid"] is True
        assert body["canonical"] == expected_canonical
        assert any("deprecated" in warning for warning in body["warnings"])


def test_invalid_expressions_return_diagnostics(client: TestClient) -> None:
    for expression in INVALID_EXPRESSIONS:
        body = parse(client, expression)
        assert body["valid"] is False, f"{expression!r} should be invalid"
        assert body["diagnostics"], f"{expression!r} should carry a diagnostic"
        assert body["canonical"] is None


def test_oversized_expression_returns_422(client: TestClient) -> None:
    response = client.post(
        "/api/v1/expressions/parse",
        json={"expression": "A" * 501},
    )
    assert response.status_code == 422


def test_and_binds_tighter_than_or(client: TestClient) -> None:
    body = parse(client, "MIT OR Apache-2.0 AND GPL-3.0-only")
    assert body["valid"] is True
    structure = body["structure"]
    assert structure["type"] == "or"
    assert structure["left"]["id"] == "MIT"
    assert structure["right"]["type"] == "and"


def test_grouping_is_preserved(client: TestClient) -> None:
    body = parse(client, "(MIT OR Apache-2.0) AND GPL-3.0-only")
    structure = body["structure"]
    assert structure["type"] == "and"
    assert structure["left"]["type"] == "group"


def test_plus_suffix_warns(client: TestClient) -> None:
    body = parse(client, "GPL-2.0+")
    assert body["valid"] is True
    assert body["canonical"] == "GPL-2.0-or-later"
    assert any("+" in warning for warning in body["warnings"])
