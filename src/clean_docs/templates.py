"""Render documentation around a complete task contract."""

from __future__ import annotations

from dataclasses import dataclass

from clean_docs.errors import ConfigurationError


TASK_SECTIONS = (
    "Intended reader",
    "Value",
    "Prerequisites",
    "Procedure",
    "Limits",
    "Next step",
)


@dataclass(frozen=True)
class TaskPage:
    title: str
    intended_reader: str
    value: str
    prerequisites: tuple[str, ...]
    procedure: tuple[str, ...]
    limits: tuple[str, ...]
    next_step: str


def _text(value: str, field: str) -> str:
    if not value.strip():
        raise ConfigurationError(f"task page {field} must be non-empty")
    return value.strip()


def _items(values: tuple[str, ...], field: str) -> tuple[str, ...]:
    if not values or any(not value.strip() for value in values):
        raise ConfigurationError(f"task page {field} must contain non-empty items")
    return tuple(value.strip() for value in values)


def render_task_markdown(page: TaskPage) -> str:
    """Render a task page only when every required reader slot is populated."""
    title = _text(page.title, "title")
    intended_reader = _text(page.intended_reader, "intended reader")
    value = _text(page.value, "value")
    prerequisites = _items(page.prerequisites, "prerequisites")
    procedure = _items(page.procedure, "procedure")
    limits = _items(page.limits, "limits")
    next_step = _text(page.next_step, "next step")
    lines = [
        f"# {title}",
        "",
        "## Intended reader",
        "",
        intended_reader,
        "",
        "## Value",
        "",
        value,
        "",
        "## Prerequisites",
        "",
        *(f"- {item}" for item in prerequisites),
        "",
        "## Procedure",
        "",
        *(f"{index}. {item}" for index, item in enumerate(procedure, start=1)),
        "",
        "## Limits",
        "",
        *(f"- {item}" for item in limits),
        "",
        "## Next step",
        "",
        next_step,
    ]
    return "\n".join(lines) + "\n"


def validate_task_markdown(content: str) -> None:
    """Reject task documentation that omits or reorders a required slot."""
    observed = tuple(
        line.removeprefix("## ").strip()
        for line in content.splitlines()
        if line.startswith("## ")
    )
    positions = []
    for section in TASK_SECTIONS:
        try:
            positions.append(observed.index(section))
        except ValueError as exc:
            raise ConfigurationError(f"task page is missing section: {section}") from exc
    if positions != sorted(positions):
        raise ConfigurationError("task page sections are out of order")
