"""Versioned deterministic rule evaluation."""

from oss_license_guide.rules.eligibility import is_eligible
from oss_license_guide.rules.evaluator import AnalysisResult, evaluate
from oss_license_guide.rules.loader import load_rules
from oss_license_guide.rules.schema import AnalysisOutcome, ReviewStatus, Rule

__all__ = [
    "AnalysisOutcome",
    "AnalysisResult",
    "ReviewStatus",
    "Rule",
    "evaluate",
    "is_eligible",
    "load_rules",
]
