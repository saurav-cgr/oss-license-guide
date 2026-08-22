"""Explicit SPDX catalog ingestion command.

This is an administrative one-off command, never run during normal API request
execution. It validates a pinned SPDX JSON snapshot, copies it as an immutable
raw snapshot, produces a normalized runtime catalog with deterministic citation
spans, and writes a manifest plus a change report against the previous release.

Usage:

    uv run python -m oss_license_guide.sources.ingest \\
        --version 3.24.0 --source /path/to/spdx/json

The source directory must contain ``licenses.json``, ``exceptions.json``, and a
``details/`` folder with one ``<SPDX-ID>.json`` file per license AND exception
whose full text must be included in the catalog. Ingestion fails if any
identifier lacks a detail file, so the committed runtime catalog always carries
complete canonical text and citation spans for every record.
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


def _record_from_detail(
    identifier: str,
    detail: dict[str, Any] | None,
    index_entry: dict[str, Any] | None,
    is_exception: bool,
) -> dict[str, Any]:
    """Build a normalized catalog record from a detail file and index entry.

    Metadata (name, deprecated, OSI, FSF, see-also) comes from the detail file
    when present, falling back to the index entry so records without detail
    files keep their index metadata instead of being empty stubs.
    """
    index = index_entry or {}
    detail = detail or {}
    text_key = "licenseExceptionText" if is_exception else "licenseText"
    text = detail.get(text_key) or ""
    return {
        "id": identifier,
        "name": detail.get("name") or index.get("name", ""),
        "deprecated": bool(
            detail.get("isDeprecatedLicenseId", index.get("isDeprecatedLicenseId", False))
        ),
        "osi_approved": bool(
            detail.get("isOsiApproved", index.get("isOsiApproved", False))
        ),
        "fsf_libre": bool(detail.get("isFsfLibre", False)),
        "is_exception": is_exception,
        "see_also": detail.get("seeAlso") or index.get("seeAlso") or [],
        "text": text or None,
        "text_hash": hashlib.sha256(text.encode("utf-8")).hexdigest() if text else None,
        "paragraphs": _paragraph_spans(text) if text else [],
    }


def _raw_files(source: Path) -> list[tuple[str, Path]]:
    """Return the (relative_path, source_path) pairs that form a raw snapshot."""
    files: list[tuple[str, Path]] = [
        ("licenses.json", source / "licenses.json"),
        ("exceptions.json", source / "exceptions.json"),
    ]
    for directory in ("details", "exceptions"):
        detail_dir = source / directory
        if detail_dir.is_dir():
            for detail_file in sorted(detail_dir.glob("*.json")):
                files.append((f"{directory}/{detail_file.name}", detail_file))
    return files


def _copy_raw_snapshot(source: Path, version: str) -> dict[str, str]:
    """Copy the raw snapshot, failing on re-ingest of an existing version.

    Source snapshots are immutable: if the version directory already exists,
    every file's hash must match the source, otherwise the run fails rather
    than silently overwriting previously versioned content.
    """
    snapshot = _DATA_ROOT / version / "raw"
    files = _raw_files(source)

    if snapshot.exists():
        incoming = {rel for rel, _src in files}
        existing = {
            str(path.relative_to(snapshot))
            for path in snapshot.rglob("*")
            if path.is_file()
        }
        stale = existing - incoming
        if stale:
            raise FileExistsError(
                f"version {version!r} has snapshot files absent from the source: "
                f"{sorted(stale)!r}"
            )
        hashes: dict[str, str] = {}
        for rel, src in files:
            dest = snapshot / rel
            if not dest.is_file():
                raise FileExistsError(
                    f"version {version!r} already exists but is missing {rel!r}"
                )
            if _sha256(dest) != _sha256(src):
                raise FileExistsError(
                    f"version {version!r} already exists with different content for {rel!r}"
                )
            hashes[rel] = _sha256(dest)
        return hashes

    snapshot.mkdir(parents=True)
    hashes: dict[str, str] = {}
    for rel, src in files:
        dest = snapshot / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        hashes[rel] = _sha256(dest)
    return hashes


def _load_details(source: Path) -> dict[str, dict[str, Any]]:
    """Load license and exception detail files, keyed by SPDX identifier.

    The official SPDX release keeps license details under ``details/`` and
    exception details under ``exceptions/``; both use the identifier as the
    file stem and are merged into one lookup.
    """
    loaded: dict[str, dict[str, Any]] = {}
    for directory in ("details", "exceptions"):
        details_dir = source / directory
        if details_dir.is_dir():
            for detail_file in details_dir.glob("*.json"):
                loaded[detail_file.stem] = _load_json(detail_file)
    return loaded


def _change_report(version: str, catalog: dict[str, Any]) -> dict[str, list[str]]:
    """Report added/removed/changed records against the previous release.

    Uses semantic-version ordering to select the predecessor and compares
    content (text hash and metadata), including exception records, not just
    license IDs.
    """
    previous_path = _previous_catalog(version)
    if previous_path is None:
        all_ids = {e["id"] for e in catalog["licenses"]} | {e["id"] for e in catalog["exceptions"]}
        return {"added": sorted(all_ids)}

    previous = _load_json(previous_path)
    prev_licenses = {e["id"]: e for e in previous["licenses"]}
    current_licenses = {e["id"]: e for e in catalog["licenses"]}
    prev_exceptions = {e["id"]: e for e in previous.get("exceptions", [])}
    current_exceptions = {e["id"]: e for e in catalog.get("exceptions", [])}

    previous_ids = set(prev_licenses) | set(prev_exceptions)
    current_ids = set(current_licenses) | set(current_exceptions)

    report: dict[str, list[str]] = {}
    added = sorted(current_ids - previous_ids)
    removed = sorted(previous_ids - current_ids)
    changed = sorted(
        {
            record_id
            for record_id in current_ids & previous_ids
            if _record_changed(
                prev_licenses.get(record_id) or prev_exceptions.get(record_id),
                current_licenses.get(record_id) or current_exceptions.get(record_id),
            )
        }
    )
    if added:
        report["added"] = added
    if removed:
        report["removed"] = removed
    if changed:
        report["changed"] = changed
    return report


def _record_changed(previous: dict[str, Any], current: dict[str, Any]) -> bool:
    if previous is None or current is None:
        return True
    return (
        previous.get("text_hash") != current.get("text_hash")
        or previous.get("name") != current.get("name")
        or bool(previous.get("deprecated")) != bool(current.get("deprecated"))
        or bool(previous.get("osi_approved")) != bool(current.get("osi_approved"))
        or bool(previous.get("is_exception")) != bool(current.get("is_exception"))
    )


def _version_key(version: str) -> tuple[int, ...]:
    """Return a sortable semantic-version key for a directory name."""
    key: list[int] = []
    for part in version.split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        key.append(int(digits) if digits else 0)
    return tuple(key)


def _previous_catalog(version: str) -> Path | None:
    current_key = _version_key(version)
    best: Path | None = None
    best_key: tuple[int, ...] | None = None
    for candidate in _DATA_ROOT.iterdir():
        if not candidate.is_dir() or candidate.name == version:
            continue
        catalog = candidate / "catalog.json"
        if not catalog.is_file():
            continue
        key = _version_key(candidate.name)
        if key < current_key and (best_key is None or key > best_key):
            best = catalog
            best_key = key
    return best


def ingest(version: str, source: Path) -> IngestReport:
    """Run the full ingestion pipeline for one SPDX release."""
    licenses_data = _load_json(source / "licenses.json")
    exceptions_data = _load_json(source / "exceptions.json")

    _validate_index(licenses_data, "licenses", {"licenseId", "isDeprecatedLicenseId"})
    _validate_index(exceptions_data, "exceptions", {"licenseExceptionId", "isDeprecatedLicenseId"})

    details = _load_details(source)

    license_index = {entry["licenseId"]: entry for entry in licenses_data["licenses"]}
    license_ids = [entry["licenseId"] for entry in licenses_data["licenses"]]
    exception_index = {
        entry["licenseExceptionId"]: entry for entry in exceptions_data["exceptions"]
    }
    exception_ids = [entry["licenseExceptionId"] for entry in exceptions_data["exceptions"]]

    missing_details = sorted({*license_ids, *exception_ids} - set(details))
    if missing_details:
        raise ValueError(
            f"incomplete details snapshot: {len(missing_details)} identifiers lack a detail file"
        )

    hashes = _copy_raw_snapshot(source, version)

    licenses = [
        _record_from_detail(
            identifier, details.get(identifier), license_index.get(identifier), False
        )
        for identifier in license_ids
    ]
    exceptions = [
        _record_from_detail(
            identifier, details.get(identifier), exception_index.get(identifier), True
        )
        for identifier in exception_ids
    ]

    catalog = {"version": version, "licenses": licenses, "exceptions": exceptions}
    catalog_path = _DATA_ROOT / version / "catalog.json"
    catalog_text = json.dumps(catalog, indent=2, ensure_ascii=False) + "\n"

    changes = _change_report(version, catalog)

    # Identical re-ingestion is a no-op: the versioned catalog, manifest, and
    # ``retrieved_at`` are preserved instead of being silently rewritten.
    if catalog_path.is_file() and catalog_path.read_text(encoding="utf-8") == catalog_text:
        return IngestReport(
            version=version,
            licenses=len(licenses),
            exceptions=len(exceptions),
            details=len(details),
            changes=changes,
        )

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
