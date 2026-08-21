"""Versioned scenario schema.

A scenario bundles an exact license expression with a set of facts, each of
which carries explicit provenance. Domain logic never assumes a value for a
fact marked unknown.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from oss_license_guide.scenarios.facts import FactType, Provenance


@dataclass
class Fact:
    """A single scenario fact with explicit provenance."""

    value: Any = None
    provenance: Provenance = Provenance.UNKNOWN

    @property
    def known(self) -> bool:
        """A fact is known only when it has a value and provenance."""
        return self.value is not None and self.provenance is not Provenance.UNKNOWN


@dataclass
class Scenario:
    """A stated use scenario for a license expression."""

    expression: str
    facts: dict[FactType, Fact] = field(default_factory=dict)

    def get(self, fact_type: FactType) -> Fact | None:
        return self.facts.get(fact_type)

    def known_value(self, fact_type: FactType) -> Any:
        """Return the value of a known fact, or None if unknown."""
        fact = self.facts.get(fact_type)
        if fact is None or not fact.known:
            return None
        return fact.value
