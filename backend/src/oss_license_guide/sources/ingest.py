"""Explicit SPDX catalog ingestion command.

This is an administrative one-off command, never run during normal API request
execution. It validates a pinned SPDX JSON snapshot, copies it as an immutable
raw snapshot, produces a normalized runtime catalog with deterministic citation
spans, and writes a manifest plus a change report against the previous release.

Usage:

    uv run python -m oss_license_guide.sources.ingest \\
        --version 3.24.0 --source /path/to/spdx/json

The source directory must contain ``licenses.json``, ``exceptions.json``, and an
optional ``details/`` folder with one ``<SPDX-ID>.json`` file per license whose
full text should be included in the catalog.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_PACKAGE_ROOT = Path(__file__).resolve().parents[3]
_DATA_ROOT = _PACKAGE_ROOT / "data" / "sources" / "spdx"

_SOURCE_URL = "https://github.com/spdx/license-list-data"


@dataclass
class IngestReport:
    """Summary of an ingestion run."""

    version: str
    licenses: int = 0
    exceptions: int = 0
    details: int = 0
    changes: dict[str, list[str]] = field(default_factory=dict)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_index(data: Any, kind: str, required: set[str]) -> None:
    if not isinstance(data, dict) or kind not in data or not isinstance(data[kind], list):
        raise ValueError(f"{kind}.json is missing the {kind!r} array")
    for entry in data[kind]:
        if not isinstance(entry, dict) or not required.issubset(entry):
            raise ValueError(f"{kind}.json contains an invalid entry: {entry!r}")


def _paragraph_spans(text: str) -> list[dict[str, Any]]:
    """Split text into paragraphs and assign deterministic hashed spans."""
    spans: list[dict[str, Any]] = []
    start = 0
    index = 0
    for paragraph in text.split("\n\n"):
        end = start + len(paragraph)
        if paragraph.strip():
            digest = hashlib.sha256(paragraph.encode("utf-8")).hexdigest()
            spans.append({"index": index, "start": start, "end": end, "hash": digest})
            index += 1
        start = end + 2  # account for the "\n\n" separator
    return spans


def _record_from_detail(identifier: str, detail: dict[str, Any] | None) -> dict[str, Any]:
    if detail is None:
        return {
            "id": identifier,
            "name": "",
            "deprecated": False,
            "osi_approved": False,
            "fsf_libre": False,
            "see_also": [],
            "text": None,
            "text_hash": None,
            "paragraphs": [],
        }
    text = detail.get("licenseText") or ""
    return {
        "id": identifier,
        "name": detail.get("name", ""),
        "deprecated": detail.get("isDeprecatedLicenseId", False),
        "osi_approved": detail.get("isOsiApproved", False),
        "fsf_libre": detail.get("isFsfLibre", False),
        "see_also": detail.get("seeAlsos", []),
        "text": text or None,
        "text_hash": hashlib.sha256(text.encode("utf-8")).hexdigest() if text else None,
        "paragraphs": _paragraph_spans(text) if text else [],
    }


def _copy_raw_snapshot(source: Path, version: str) -> dict[str, str]:
    snapshot = _DATA_ROOT / version / "raw"
    snapshot.mkdir(parents=True, exist_ok=True)

    hashes: dict[str, str] = {}
    for filename in ("licenses.json", "exceptions.json"):
        shutil.copyfile(source / filename, snapshot / filename)
        hashes[filename] = _sha256(snapshot / filename)

    details_dir = snapshot / "details"
    if (source / "details").is_dir():
        details_dir.mkdir(exist_ok=True)
        for detail_file in sorted((source / "details").glob("*.json")):
            shutil.copyfile(detail_file, details_dir / detail_file.name)
            hashes[f"details/{detail_file.name}"] = _sha256(details_dir / detail_file.name)
    return hashes


def _load_details(source: Path) -> dict[str, dict[str, Any]]:
    details_dir = source / "details"
    if not details_dir.is_dir():
        return {}
    loaded: dict[str, dict[str, Any]] = {}
    for detail_file in details_dir.glob("*.json"):
        loaded[detail_file.stem] = _load_json(detail_file)
    return loaded


def _change_report(version: str, catalog: dict[str, Any]) -> dict[str, list[str]]:
    previous_path = _previous_catalog(version)
    if previous_path is None:
        return {"added": [entry["id"] for entry in catalog["licenses"]]}

    previous = _load_json(previous_path)
    previous_ids = {entry["id"] for entry in previous["licenses"]}
    current_ids = {entry["id"] for entry in catalog["licenses"]}
    return {
        "added": sorted(current_ids - previous_ids),
        "removed": sorted(previous_ids - current_ids),
    }


def _previous_catalog(version: str) -> Path | None:
    for candidate in sorted(_DATA_ROOT.iterdir(), reverse=True):
        if candidate.name == version:
            continue
        catalog = candidate / "catalog.json"
        if catalog.is_file():
            return catalog
    return None


def ingest(version: str, source: Path) -> IngestReport:
    """Run the full ingestion pipeline for one SPDX release."""
    licenses_data = _load_json(source / "licenses.json")
    exceptions_data = _load_json(source / "exceptions.json")

    _validate_index(licenses_data, "licenses", {"licenseId", "isDeprecatedLicenseId"})
    _validate_index(exceptions_data, "exceptions", {"licenseExceptionId", "isDeprecatedLicenseId"})

    details = _load_details(source)
    hashes = _copy_raw_snapshot(source, version)

    license_ids = [entry["licenseId"] for entry in licenses_data["licenses"]]
    licenses = [
        _record_from_detail(identifier, details.get(identifier))
        for identifier in license_ids
    ]

    exception_ids = [entry["licenseExceptionId"] for entry in exceptions_data["exceptions"]]
    exceptions = [
        _record_from_detail(identifier, details.get(identifier))
        for identifier in exception_ids
    ]

    catalog = {"version": version, "licenses": licenses, "exceptions": exceptions}
    catalog_path = _DATA_ROOT / version / "catalog.json"
    catalog_text = json.dumps(catalog, indent=2, ensure_ascii=False) + "\n"
    catalog_path.write_text(catalog_text, encoding="utf-8")

    manifest = {
        "version": version,
        "source": f"{_SOURCE_URL}/releases/tag/v{version}",
        "retrieved_at": datetime.now(UTC).isoformat(),
        "raw_hashes": hashes,
    }
    (_DATA_ROOT / version / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    changes = _change_report(version, catalog)
    return IngestReport(
        version=version,
        licenses=len(licenses),
        exceptions=len(exceptions),
        details=len(details),
        changes=changes,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest a pinned SPDX release into the catalog")
    parser.add_argument("--version", required=True, help="SPDX license-list version, e.g. 3.24.0")
    parser.add_argument(
        "--source", required=True, type=Path, help="Directory with SPDX JSON snapshot"
    )
    args = parser.parse_args()

    missing = not (args.source / "licenses.json").is_file() or not (
        args.source / "exceptions.json"
    ).is_file()
    if missing:
        sys.exit("Source directory must contain licenses.json and exceptions.json")

    report = ingest(args.version, args.source)
    print(
        f"Ingested SPDX {report.version}: "
        f"{report.licenses} licenses, {report.exceptions} exceptions, {report.details} details"
    )
    if report.changes:
        added = len(report.changes.get("added", []))
        removed = len(report.changes.get("removed", []))
        print(f"Added: {added} | Removed: {removed}")


if __name__ == "__main__":
    main()
