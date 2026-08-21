"""SPDX catalog lookup and search endpoints."""

from fastapi import APIRouter, HTTPException, Query

from oss_license_guide.sources import load_catalog
from oss_license_guide.sources.catalog import LicenseRecord

router = APIRouter(prefix="/licenses", tags=["licenses"])


def _summary(record: LicenseRecord) -> dict:
    return {
        "id": record.id,
        "name": record.name,
        "deprecated": record.deprecated,
        "osi_approved": record.osi_approved,
        "fsf_libre": record.fsf_libre,
        "is_exception": record.is_exception,
    }


@router.get("")
def list_licenses(
    q: str | None = Query(default=None, description="Optional search query"),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    """Search or list canonical SPDX identifiers and metadata."""
    catalog = load_catalog()
    if q:
        records = catalog.search(q, limit=limit)
    else:
        records = catalog.all_records()[:limit]
    return {
        "version": catalog.version,
        "count": len(records),
        "licenses": [_summary(record) for record in records],
    }


@router.get("/{license_id}")
def get_license(license_id: str) -> dict:
    """Return canonical metadata and exact source text for one identifier."""
    catalog = load_catalog()
    record = catalog.lookup(license_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Unknown SPDX identifier: {license_id}")
    return {
        **_summary(record),
        "see_also": record.see_also,
        "text": record.text,
        "text_hash": record.text_hash,
    }
