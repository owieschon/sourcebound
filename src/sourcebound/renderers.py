from __future__ import annotations

from typing import Any

from sourcebound.errors import ExtractionError
from sourcebound.models import EvidenceValue, RegionBinding


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        text = "true" if value else "false"
    elif isinstance(value, (dict, list)):
        raise ExtractionError("nested values cannot be rendered as Markdown table cells")
    else:
        text = str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def render_markdown_table(evidence: EvidenceValue, binding: RegionBinding) -> str:
    rows = evidence.value
    missing = sorted({column for column in binding.columns for row in rows if column not in row})
    if missing:
        raise ExtractionError(f"binding {binding.id} is missing column(s): {', '.join(missing)}")
    header = "| " + " | ".join(binding.columns) + " |"
    divider = "| " + " | ".join("---" for _ in binding.columns) + " |"
    body = [
        "| " + " | ".join(_cell(row[column]) for column in binding.columns) + " |"
        for row in rows
    ]
    return "\n".join([header, divider, *body])


def _inline_scalar_text(value: Any) -> str:
    if isinstance(value, (dict, list)):
        raise ExtractionError("inline-scalar renderer requires a scalar value")
    if value is None:
        text = ""
    elif isinstance(value, bool):
        text = "true" if value else "false"
    else:
        text = str(value)
    if "\n" in text or "\r" in text:
        raise ExtractionError("inline-scalar renderer requires a single-line value")
    if "sourcebound:begin" in text or "sourcebound:end" in text:
        raise ExtractionError("inline-scalar renderer value must not contain region markers")
    return text


def render(evidence: EvidenceValue, binding: RegionBinding) -> str:
    if binding.renderer == "inline-scalar":
        return _inline_scalar_text(evidence.value)
    if binding.renderer == "markdown-table":
        return render_markdown_table(evidence, binding)
    if binding.renderer == "markdown-list":
        if not isinstance(evidence.value, list) or any(
            isinstance(item, (dict, list)) for item in evidence.value
        ):
            raise ExtractionError("markdown-list evidence must contain scalar items")
        return "\n".join(f"- {_cell(item)}" for item in evidence.value)
    if binding.renderer == "scalar":
        if isinstance(evidence.value, (dict, list)):
            raise ExtractionError("scalar renderer requires a scalar value")
        return _cell(evidence.value)
    if binding.renderer == "markdown-fragment":
        if not isinstance(evidence.value, str) or evidence.kind != "markdown":
            raise ExtractionError("markdown-fragment requires generated Markdown evidence")
        return evidence.value.rstrip()
    if binding.renderer == "fenced-text":
        if not isinstance(evidence.value, str):
            raise ExtractionError("fenced-text renderer requires text evidence")
        fence = "```" + (binding.language or "")
        return f"{fence}\n{evidence.value.rstrip()}\n```"
    raise ExtractionError(f"unsupported renderer: {binding.renderer}")
