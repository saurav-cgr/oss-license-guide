"""Load versioned rule records from the bundled data directory."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from oss_license_guide.rules.schema import ReviewStatus, Rule

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
        obligations=entry.get("obligations", []),
        exceptions=entry.get("exceptions", []),
        direction=entry.get("direction", ""),
        source_ids=entry.get("source_ids", []),
        review_status=ReviewStatus(entry.get("review_status", "draft")),
        reviewer=entry.get("reviewer", ""),
        effective_date=entry.get("effective_date", ""),
        last_verified_at=entry.get("last_verified_at", ""),
    )
