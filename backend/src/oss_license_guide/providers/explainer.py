"""Bounded explanation generation over deterministic findings.

The model explains already-approved structured findings only. It never creates
obligations or citations, and its output must match a strict schema. Any failure
(missing key, invalid output, auth, rate limit, timeout) degrades to the
deterministic response with a non-secret note. At most one repair attempt is
made for an invalid structured explanation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from oss_license_guide.config.settings import Settings
from oss_license_guide.providers.protocol import (
    ProviderError,
    ProviderOutputError,
    ProviderRequest,
)
from oss_license_guide.providers.registry import available_models, get_adapter, is_allowed

# Keys the model must never emit: they would inject authoritative content.
_FORBIDDEN_KEYS = {
    "claims",
    "obligations",
    "citations",
    "outcome",
    "score",
    "confidence",
    "rule_id",
}

_SYSTEM_PROMPT = (
    "You are a cautious legal-information assistant. You restate already-approved "
    "structured findings. You never add obligations, permissions, change outcomes, "
    "create citations, or give legal advice. Answer only from the provided findings. "
    "Output a single JSON object with exactly one field named \"elaboration\" "
    "containing a short plain-language restatement (2-3 sentences) of the outcome "
    "and any listed obligations. Do not introduce any requirement, prohibition, "
    "grant, payment, or liability. Do not include any other fields."
)


_INVALID_OUTPUT_NOTE = "Model explanation unavailable; deterministic result shown."


@dataclass
class ExplanationFindings:
    """Non-secret structured content passed to the model."""

    outcome: str
    canonical: str
    short_answer: str
    assumptions: list[str] = field(default_factory=list)
    obligations: list[dict] = field(default_factory=list)
    what_could_change: list[str] = field(default_factory=list)
    escalation: str = ""
    question: str = ""


@dataclass
class ExplanationResult:
    """Outcome of an explanation attempt; always deterministic-safe."""

    explanation: str = ""
    provider: str = ""
    model: str = ""
    note: str = ""
    token_counts: dict[str, int] = field(default_factory=dict)


def generate_explanation(
    *,
    provider: str,
    model: str,
    api_key: str | None,
    findings: ExplanationFindings,
    settings: Settings,
) -> ExplanationResult:
    """Generate a validated explanation, degrading safely on any failure."""
    if not is_allowed(provider, settings):
        return ExplanationResult(
            provider=provider,
            note=f"Provider {provider!r} is not available; deterministic result shown.",
        )

    if model not in available_models(provider):
        return ExplanationResult(
            provider=provider,
            model=model,
            note=(
                f"Requested model {model!r} is not allowlisted for {provider!r}; "
                "deterministic result shown."
            ),
        )

    key = _resolve_key(provider, api_key, settings)
    if not key:
        return ExplanationResult(
            provider=provider,
            model=model,
            note=(
                "Provide a provider API key to enable a model explanation; "
                "the deterministic result is shown."
            ),
        )

    try:
        adapter = get_adapter(provider, settings)
    except ProviderError as error:
        return ExplanationResult(provider=provider, model=model, note=_note_for(error))

    request = _build_request(provider, model, key, findings, settings)

    elaboration, response, error = _attempt(adapter, request, settings, findings)
    if elaboration is None and error is None and settings.provider_max_repairs > 0:
        elaboration, response, error = _attempt(
            adapter, _repair_request(request, ""), settings, findings
        )

    if elaboration is not None:
        explanation = _assemble_deterministic(findings)
        if elaboration:
            explanation += "\n\n" + elaboration
        return ExplanationResult(
            explanation=explanation,
            provider=provider,
            model=model,
            token_counts=response.token_counts if response else {},
        )
    return ExplanationResult(
        provider=provider,
        model=model,
        note=_note_for(error) if error else _INVALID_OUTPUT_NOTE,
    )


def _build_request(
    provider: str,
    model: str,
    api_key: str,
    findings: ExplanationFindings,
    settings: Settings,
) -> ProviderRequest:
    return ProviderRequest(
        provider=provider,
        model=model,
        api_key=api_key,
        system_prompt=_SYSTEM_PROMPT,
        user_prompt=_user_prompt(findings),
        max_tokens=settings.provider_max_tokens,
        timeout_seconds=settings.provider_timeout_seconds,
    )


def _attempt(
    adapter: object,
    request: ProviderRequest,
    settings: Settings,
    findings: ExplanationFindings,
) -> tuple[str | None, object | None, ProviderError | None]:
    """Run one generation attempt.

    Returns ``(explanation, response, error)``. Invalid output yields
    ``(None, None, None)`` so the caller may retry; other provider failures
    yield an error for immediate fallback.
    """
    try:
        response = adapter.generate(request)  # type: ignore[attr-defined]
    except ProviderOutputError:
        return None, None, None
    except ProviderError as error:
        return None, None, error
    explanation = _validate(response.text, settings, findings)
    if explanation is None:
        return None, None, None
    return explanation, response, None


def _resolve_key(provider: str, api_key: str | None, settings: Settings) -> str | None:
    if api_key:
        return api_key
    # Development-only key: only used when explicitly enabled; never on a public
    # path that lacks a user credential.
    if settings.allow_dev_provider_key and provider == "gemini" and settings.gemini_api_key:
        return settings.gemini_api_key
    return None


def _user_prompt(findings: ExplanationFindings) -> str:
    lines = [
        f"Outcome: {findings.outcome}",
        f"Expression: {findings.canonical}",
        f"Short answer: {findings.short_answer}",
        "",
        "Assumptions:",
    ]
    lines.extend(f"- {item}" for item in findings.assumptions or ["None stated"])
    lines.append("")
    lines.append("Obligations (deterministic, source-backed):")
    if findings.obligations:
        for obligation in findings.obligations:
            text = obligation.get("text", "")
            refs = obligation.get("citations", [])
            ref_text = ", ".join(f"{c.get('source_id')} span {c.get('span_index')}" for c in refs)
            lines.append(f"- {text}" + (f" ({ref_text})" if ref_text else ""))
    else:
        lines.append("- None")
    lines.append("")
    lines.append("What could change this:")
    lines.extend(f"- {item}" for item in findings.what_could_change)
    lines.append("")
    lines.append(f"Review guidance: {findings.escalation}")
    if findings.question:
        lines.append("")
        lines.append(f"User's question (for context only): {findings.question}")
    lines.append("")
    lines.append('Respond with JSON: {"elaboration": "<your restatement>"}')
    return "\n".join(lines)


def _assemble_deterministic(findings: ExplanationFindings) -> str:
    """Assemble a plain-language explanation from validated deterministic fragments.

    Every claim in this text is derived from the reviewed structured findings;
    no language-model content contributes a new obligation, permission, or
    conclusion here.
    """
    lines = [f"{findings.outcome}. {findings.short_answer}"]
    if findings.obligations:
        lines.append("Obligations:")
        lines.extend(f"- {obligation['text']}" for obligation in findings.obligations)
    lines.append(findings.escalation)
    return "\n".join(lines)


def _normalize(value: str) -> str:
    """Lowercase and collapse whitespace for containment comparison."""
    return " ".join(value.lower().split())


def _sentences(value: str) -> list[str]:
    """Split ``value`` into trimmed sentences."""
    return [part for part in re.split(r"(?<=[.!?])\s+", value.strip()) if part.strip()]


def _derivable_from_findings(value: str, findings: ExplanationFindings) -> bool:
    """Return True if every sentence is a fragment of the deterministic text.

    A model sentence is accepted only when its normalized text is a contiguous
    substring of the normalized deterministic explanation assembled from the
    structured findings. This rejects any new permission, obligation, payment,
    or liability wording the model might invent, regardless of phrasing.
    """
    pool = _normalize(_assemble_deterministic(findings))
    for sentence in _sentences(value):
        normalized = _normalize(sentence.rstrip(".!?"))
        if normalized and normalized not in pool:
            return False
    return True


def _repair_request(request: ProviderRequest, prior: str) -> ProviderRequest:
    import oss_license_guide.providers.gemini as gemini_mod
    import oss_license_guide.providers.openai as openai_mod

    parser = gemini_mod.parse_json if request.provider == "gemini" else openai_mod.parse_json
    detail = "the output was not parseable"
    try:
        parsed = parser(prior)
        detail = "the output contained unexpected fields" if not isinstance(parsed, dict) else (
            "the output was missing a valid \"elaboration\" string"
        )
    except ProviderOutputError:
        detail = "the output was not parseable JSON"
    corrective = (
        f"\n\nYour previous response was rejected: {detail}. "
        'Respond again with ONLY a JSON object: {"elaboration": "<2-3 sentence restatement>"}. '
        "No other fields, no extra text, and do not introduce any requirement or obligation."
    )
    return ProviderRequest(
        provider=request.provider,
        model=request.model,
        api_key=request.api_key,
        system_prompt=request.system_prompt,
        user_prompt=request.user_prompt + corrective,
        max_tokens=request.max_tokens,
        timeout_seconds=request.timeout_seconds,
    )


def _validate(
    text: str,
    settings: Settings,
    findings: ExplanationFindings,
) -> str | None:
    """Return a screened elaboration string, or None if the output is invalid.

    The model contributes only a bounded ``elaboration`` slot. Any output that
    fails JSON shape, carries forbidden keys, is oversized, or is not derivable
    from the deterministic findings is rejected, so new uncited permissions or
    obligations can never reach the display.
    """
    import oss_license_guide.providers.gemini as gemini_mod
    import oss_license_guide.providers.openai as openai_mod

    for parser in (openai_mod.parse_json, gemini_mod.parse_json):
        try:
            payload = parser(text)
            break
        except ProviderOutputError:
            payload = None
    if not isinstance(payload, dict):
        return None
    if _FORBIDDEN_KEYS & set(payload):
        return None
    value = payload.get("elaboration")
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value:
        return None
    if len(value) > settings.provider_max_output_chars:
        return None
    if not _derivable_from_findings(value, findings):
        return None
    return value


def _note_for(error: ProviderError) -> str:
    message = str(error)
    # Never echo provider-supplied content that might contain credentials.
    prefix = message.split("(")[0].strip()
    return "Model explanation unavailable; deterministic result shown. " + prefix
