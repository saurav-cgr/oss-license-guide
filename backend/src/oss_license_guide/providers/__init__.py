"""LLM provider adapters behind a small structured-generation protocol.

Public API for the analysis workflow: ``generate_explanation``, provider
allowlist checks, and model metadata.
"""

from oss_license_guide.providers.explainer import (
    ExplanationFindings,
    ExplanationResult,
    generate_explanation,
)
from oss_license_guide.providers.protocol import ProviderError
from oss_license_guide.providers.registry import available_models, is_allowed

__all__ = [
    "ExplanationFindings",
    "ExplanationResult",
    "ProviderError",
    "available_models",
    "generate_explanation",
    "is_allowed",
]
