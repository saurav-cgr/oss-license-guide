"""Integration tests for the SPDX ingestion pipeline.

Tests run against a temporary data root and a minimal crafted SPDX snapshot so
they stay offline and deterministic. They cover the no-op re-ingestion, stale
snapshot detection, and completeness enforcement added to ``sources.ingest``.
"""

from __future__ import annotations

import json

import pytest

from oss_license_guide.sources import ingest as ingest_mod


@pytest.fixture
def source(tmp_path):
    """Create a minimal, complete SPDX source directory."""
    src = tmp_path / "source"
    details = src / "details"
    exceptions = src / "exceptions"
    details.mkdir(parents=True)
    exceptions.mkdir(parents=True)

    (src / "licenses.json").write_text(
        json.dumps(
            {
                "licenses": [
                    {
                        "licenseId": "MIT",
                        "name": "MIT License",
                        "isDeprecatedLicenseId": False,
                        "isOsiApproved": True,
                        "seeAlso": ["https://example.test/mit"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (src / "exceptions.json").write_text(
        json.dumps(
            {
                "exceptions": [
                    {
                        "licenseExceptionId": "Example-exception",
                        "name": "Example Exception",
                        "isDeprecatedLicenseId": False,
                        "seeAlso": ["https://example.test/exc"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (details / "MIT.json").write_text(
        json.dumps({"licenseText": "Permission is hereby granted.\n\nUse it."}),
        encoding="utf-8",
    )
    (exceptions / "Example-exception.json").write_text(
        json.dumps({"licenseExceptionText": "An exception applies here."}),
        encoding="utf-8",
    )
    return src


@pytest.fixture
def data_root(tmp_path, monkeypatch):
    """Redirect the module data root to a temporary directory."""
    root = tmp_path / "data"
    monkeypatch.setattr(ingest_mod, "_DATA_ROOT", root / "sources" / "spdx")
    return ingest_mod._DATA_ROOT


def _catalog(version: str) -> dict:
    return json.loads((ingest_mod._DATA_ROOT / version / "catalog.json").read_text())


def _manifest(version: str) -> dict:
    return json.loads((ingest_mod._DATA_ROOT / version / "manifest.json").read_text())


def test_ingest_produces_complete_catalog(source, data_root) -> None:
    report = ingest_mod.ingest("3.24.0", source)
    assert report.licenses == 1
    assert report.exceptions == 1
    catalog = _catalog("3.24.0")
    assert catalog["licenses"][0]["name"] == "MIT License"
    assert catalog["licenses"][0]["text"] is not None
    assert catalog["exceptions"][0]["is_exception"] is True
    assert catalog["exceptions"][0]["text"] is not None


def test_identical_reingestion_is_a_noop(source, data_root) -> None:
    ingest_mod.ingest("3.24.0", source)
    manifest_before = _manifest("3.24.0")
    catalog_before = _catalog("3.24.0")

    ingest_mod.ingest("3.24.0", source)

    assert _manifest("3.24.0")["retrieved_at"] == manifest_before["retrieved_at"]
    assert _catalog("3.24.0") == catalog_before


def test_incomplete_details_snapshot_is_rejected(source, data_root) -> None:
    (source / "exceptions" / "Example-exception.json").unlink()
    with pytest.raises(ValueError, match="incomplete details"):
        ingest_mod.ingest("3.24.0", source)


def test_stale_extra_snapshot_file_is_detected(source, data_root) -> None:
    ingest_mod.ingest("3.24.0", source)
    stale = ingest_mod._DATA_ROOT / "3.24.0" / "raw" / "details" / "Stale.json"
    stale.write_text("{}", encoding="utf-8")
    with pytest.raises(FileExistsError, match="absent from the source"):
        ingest_mod.ingest("3.24.0", source)
