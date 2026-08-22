"""Load versioned rule records from the bundled data directory."""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

from oss_license_guide.rules.schema import Citation, ObligationClaim, ReviewStatus, Rule

_PACKAGE_ROOT = Path(__file__).resolve().parents[3]
_RULES_DIR = _PACKAGE_ROOT / "data" / "rules"


@lru_cache
def load_rules(directory: Path | None = None) -> list[Rule]:
    """Load every rule from the JSON files under the rules directory."""
    rules_dir = directory or _RULES_DIR
    rules: list[Rule] = []
    if not rules_dir.is_dir():
        return rules
    for rule_file in sorted(rules_dir.glob("*.json")):
        rules.extend(_rules_from_file(rule_file))
    return rules


def _rules_from_file(path: Path) -> list[Rule]:
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data if isinstance(data, list) else data.get("rules", [])
    return [_rule_from_dict(entry) for entry in entries]


def _rule_from_dict(entry: dict) -> Rule:
    return Rule(
        rule_id=entry["rule_id"],
        license_expression_pattern=entry["license_expression_pattern"],
        scenario_preconditions=entry.get("scenario_preconditions", {}),
        outcome=entry.get("outcome", ""),
        obligations=_obligations_from_dict(entry.get("obligations", [])),
        permission_citations=_citations_from_dict(entry.get("permission_citations", [])),
        exceptions=entry.get("exceptions", []),
        direction=entry.get("direction", ""),
        source_ids=entry.get("source_ids", []),
        review_status=ReviewStatus(entry.get("review_status", "draft")),
        reviewer=entry.get("reviewer", ""),
        effective_date=entry.get("effective_date", ""),
        last_verified_at=entry.get("last_verified_at", ""),
        rule_version=entry.get("rule_version", ""),
        content_hash=_content_hash(entry),
    )


def _content_hash(entry: dict) -> str:
    """Return a stable content hash identifying this exact rule revision.

    The hash covers the full rule record except any pre-existing
    ``content_hash`` key, using canonical (sorted-key) JSON so the same logical
    rule always hashes identically regardless of formatting or key order.
    """
    payload = {key: value for key, value in entry.items() if key != "content_hash"}
    canonical = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _obligations_from_dict(items: list[dict]) -> list[ObligationClaim]:
    claims: list[ObligationClaim] = []
    for item in items:
        if isinstance(item, str):
            claims.append(ObligationClaim(text=item))
            continue
        claims.append(
            ObligationClaim(
                text=item["text"],
                citations=_citations_from_dict(item.get("citations", [])),
            )
        )
    return claims


def _citations_from_dict(items: list[dict]) -> list[Citation]:
    return [
        Citation(
            source_id=cite["source_id"],
            span_index=cite["span_index"],
            expected_hash=cite.get("expected_hash", ""),
        )
        for cite in items
    ]
