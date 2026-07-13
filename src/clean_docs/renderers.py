from __future__ import annotations

from typing import Any

from clean_docs.errors import ExtractionError
from clean_docs.models import EvidenceValue, RegionBinding


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
