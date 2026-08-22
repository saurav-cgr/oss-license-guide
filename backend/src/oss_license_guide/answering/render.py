"""Deterministic plain-language renderer for the answer contract.

This renderer satisfies the product output contract without any language model.
If an answer is blocked by citation validation, it renders an abstention notice.
"""

from __future__ import annotations

from oss_license_guide.answering.answer import Answer


def render(answer: Answer) -> str:
    """Render ``answer`` to the plain-language output contract."""
    lines: list[str] = [f"Outcome: {answer.outcome}"]

    if answer.blocked:
        lines.append("Short answer:")
        lines.append("Analysis blocked because citation validation failed.")
        lines.append("Citation errors:")
        lines.extend(f"- {error}" for error in answer.citation_errors)
    else:
        lines.append(f"Short answer: {answer.short_answer}")

        lines.append("Assumptions:")
        lines.extend(f"- {assumption}" for assumption in answer.assumptions or ["None stated"])

        lines.append("Permissions:")
        if answer.permission is not None:
            refs = ", ".join(
                f"{c.source_id} span {c.span_index}" for c in answer.permission.citations
            )
            lines.append(
                f"- {answer.permission.text}" + (f" ({refs})" if refs else " (no citation)")
            )
        else:
            lines.append("- None")

        lines.append("Obligations:")
        if answer.obligations:
            for claim in answer.obligations:
                refs = ", ".join(f"{c.source_id} span {c.span_index}" for c in claim.citations)
                lines.append(f"- {claim.text}" + (f" ({refs})" if refs else " (no citation)"))
        else:
            lines.append("- None")

        lines.append("What could change this answer:")
        lines.extend(f"- {item}" for item in answer.what_could_change)

        lines.append("Evidence:")
        for entry in answer.evidence:
            snippet = _one_line(entry.text)
            lines.append(f"- {entry.source_id} span {entry.span_index}: {snippet}")
        if not answer.evidence:
            lines.append("- None")

        lines.append("Confidence:")
        lines.append(f"- Expression parsing: {answer.confidence.get('expression_parsing', 'Low')}")
        lines.append(f"- Rule coverage: {answer.confidence.get('rule_coverage', 'Low')}")
        lines.append(
            f"- Scenario completeness: {answer.confidence.get('scenario_completeness', 'Low')}"
        )

        lines.append(f"Escalation: {answer.escalation}")

    lines.append(f"Disclaimer: {answer.disclaimer}")
    return "\n".join(lines)


def _one_line(text: str, limit: int = 120) -> str:
    compact = " ".join(text.split())
    return compact if len(compact) <= limit else compact[: limit - 1] + "…"
