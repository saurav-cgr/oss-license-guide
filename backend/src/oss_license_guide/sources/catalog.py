"""SPDX catalog models and runtime lookup/search services.

The catalog is a normalized, immutable snapshot of a pinned SPDX release. It is
loaded from a bundled JSON file at application startup; parsing, lookup, and
search never require network access.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

_ACTIVE_VERSION = "3.24.0"
_PACKAGE_ROOT = Path(__file__).resolve().parents[3]
_CATALOG_PATH = _PACKAGE_ROOT / "data" / "sources" / "spdx" / _ACTIVE_VERSION / "catalog.json"


@dataclass(frozen=True)
class ParagraphSpan:
    """A deterministic paragraph span within a license text."""

    index: int
    start: int
    end: int
    hash: str


@dataclass(frozen=True)
class LicenseRecord:
    """Normalized metadata for one SPDX license or exception."""

    id: str
    name: str
    deprecated: bool
    osi_approved: bool
    fsf_libre: bool
    is_exception: bool
    see_also: list[str] = field(default_factory=list)
    text: str | None = None
    text_hash: str | None = None
    paragraphs: list[ParagraphSpan] = field(default_factory=list)


@dataclass
class Catalog:
    """The complete normalized SPDX catalog for one release."""

    version: str
    licenses: dict[str, LicenseRecord]
    exceptions: dict[str, LicenseRecord]

    def lookup(self, identifier: str) -> LicenseRecord | None:
        """Return an exact record for ``identifier`` (case-insensitive)."""
        return self.licenses.get(identifier) or self.exceptions.get(identifier)

    def search(self, query: str, limit: int = 20) -> list[LicenseRecord]:
        """Search by canonical identifier, name, or text keyword."""
        q = query.strip().lower()
        if not q:
            return []

        def matches(record: LicenseRecord) -> bool:
            if q in record.id.lower():
                return True
            if q in record.name.lower():
                return True
            if record.text and q in record.text.lower():
                return True
            return False

        return [record for record in self.all_records() if matches(record)][:limit]

    def all_records(self) -> list[LicenseRecord]:
        records = list(self.licenses.values()) + list(self.exceptions.values())
        return sorted(records, key=lambda record: record.id)


@lru_cache
def load_catalog(path: Path | None = None) -> Catalog:
    """Load the normalized catalog from disk (cached per process)."""
    catalog_path = path or _CATALOG_PATH
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    licenses = {
        item["id"]: _record_from_dict(item)
        for item in data.get("licenses", [])
    }
    exceptions = {
        item["id"]: _record_from_dict(item)
        for item in data.get("exceptions", [])
    }
    return Catalog(version=data.get("version", ""), licenses=licenses, exceptions=exceptions)


def _record_from_dict(item: dict) -> LicenseRecord:
    paragraphs = [
        ParagraphSpan(
            index=span["index"],
            start=span["start"],
            end=span["end"],
            hash=span["hash"],
        )
        for span in item.get("paragraphs", [])
    ]
    return LicenseRecord(
        id=item["id"],
        name=item.get("name", ""),
        deprecated=item.get("deprecated", False),
        osi_approved=item.get("osi_approved", False),
        fsf_libre=item.get("fsf_libre", False),
        is_exception=item.get("is_exception", False),
        see_also=item.get("see_also", []),
        text=item.get("text"),
        text_hash=item.get("text_hash"),
        paragraphs=paragraphs,
    )
