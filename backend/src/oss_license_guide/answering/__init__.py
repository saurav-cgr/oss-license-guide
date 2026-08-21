"""Structured answer assembly and deterministic fallback rendering."""

from oss_license_guide.answering.answer import DISCLAIMER, Answer, ClaimView, EvidenceEntry
from oss_license_guide.answering.builder import build_answer
from oss_license_guide.answering.render import render

__all__ = [
    "Answer",
    "ClaimView",
    "DISCLAIMER",
    "EvidenceEntry",
    "build_answer",
    "render",
]
