#!/usr/bin/env python3
"""Backfill the approved reviewed span hash into every rule citation.

Each rule citation must pin the sha256 of the exact text span a reviewer
approved, so that regenerated or drifted source text cannot silently change the
evidence supporting a reviewed rule. This script reads the active catalog's
paragraph hashes and writes ``expected_hash`` into every citation object under
``data/rules/*.json``.

Idempotent and offline: it only reads the bundled catalog and rewrites rule
files that already carry a ``source_id`` + ``span_index``. Golden expectation
fixtures are intentionally left untouched, because the golden harness compares
spans, not pinned hashes.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_ACTIVE_VERSION = "3.24.0"
_CATALOG = _REPO_ROOT / "backend" / "data" / "sources" / "spdx" / _ACTIVE_VERSION / "catalog.json"
_RULES_DIR = _REPO_ROOT / "backend" / "data" / "rules"


def _parse_source_id(source_id: str) -> tuple[str, str]:
    value = source_id
    if value.startswith("spdx:"):
        value = value[len("spdx:") :]
    if "@" in value:
        ident, version = value.split("@", 1)
        return ident, version
    return value, ""


def _span_hash_lookup(catalog: dict) -> dict[str, dict[int, str]]:
    """Return {record_id: {span_index: hash}} for licenses and exceptions."""
    lookup: dict[str, dict[int, str]] = {}
    for group in ("licenses", "exceptions"):
        for item in catalog.get(group, []):
            paragraphs = {
                span["index"]: span["hash"]
                for span in item.get("paragraphs", [])
            }
            lookup[item["id"]] = paragraphs
    return lookup


_REVIEWED_STATUSES = {"maintainer_reviewed", "legally_reviewed"}


def _citation_nodes(node: object) -> list[dict]:
    """Return every citation dict (source_id + span_index) under ``node``."""
    found: list[dict] = []
    if isinstance(node, dict):
        if "source_id" in node and "span_index" in node:
            found.append(node)
        for value in node.values():
            found.extend(_citation_nodes(value))
    elif isinstance(node, list):
        for value in node:
            found.extend(_citation_nodes(value))
    return found


def _backfill_file(path: Path, lookup: dict[str, dict[int, str]]) -> tuple[int, list[str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rules = data if isinstance(data, list) else data.get("rules", [])
    changed = 0
    errors: list[str] = []

    for rule in rules:
        if not isinstance(rule, dict):
            continue
        rule_id = rule.get("rule_id", "<unknown>")
        reviewed = rule.get("review_status") in _REVIEWED_STATUSES
        for node in _citation_nodes(rule):
            ident, version = _parse_source_id(node["source_id"])
            if version and version != _ACTIVE_VERSION:
                errors.append(
                    f"{path.name}: {rule_id} cites {node['source_id']} at "
                    f"version {version!r}, not active {_ACTIVE_VERSION!r}"
                )
                continue
            span = int(node["span_index"])
            span_hash = lookup.get(ident, {}).get(span)
            if not span_hash:
                continue
            current = node.get("expected_hash", "")
            if reviewed:
                # Never mutate a reviewed rule's pinned evidence; a changed hash
                # would silently re-approve different source text.
                if current and current != span_hash:
                    errors.append(
                        f"{path.name}: refusing to change reviewed rule {rule_id} "
                        f"citation {node['source_id']}#{span}"
                    )
                elif not current:
                    errors.append(
                        f"{path.name}: refusing to backfill an unpinned citation on "
                        f"reviewed rule {rule_id} ({node['source_id']}#{span})"
                    )
                continue
            if current != span_hash:
                node["expected_hash"] = span_hash
                changed += 1

    if changed:
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return changed, errors


def main() -> int:
    catalog = json.loads(_CATALOG.read_text(encoding="utf-8"))
    lookup = _span_hash_lookup(catalog)
    total = 0
    errors: list[str] = []
    for path in sorted(_RULES_DIR.glob("*.json")):
        changed, file_errors = _backfill_file(path, lookup)
        total += changed
        errors.extend(file_errors)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"Updated {total} citation hashes across {_RULES_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
