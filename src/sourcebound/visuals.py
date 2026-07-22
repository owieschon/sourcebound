from __future__ import annotations

import hashlib
import html
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from sourcebound.errors import ConfigurationError
from sourcebound.models import VisualProjection


VISUAL_SCHEMA = "sourcebound.visual.v1"
VISUAL_KEYS = {
    "schema",
    "id",
    "kind",
    "src",
    "src_dark",
    "width",
    "height",
    "alt",
    "caption",
    "description",
    "annotations",
}
ANNOTATION_KEYS = {"id", "x", "y", "title", "description"}
IDENTIFIER = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*")
REMOTE_SOURCE = re.compile(r"https://", re.IGNORECASE)


@dataclass(frozen=True)
class VisualAnnotation:
    id: str
    x: float
    y: float
    title: str
    description: str


@dataclass(frozen=True)
class VisualRecord:
    id: str
    kind: str
    src: str
    src_dark: str | None
    width: int
    height: int
    alt: str
    caption: str
    description: str
    annotations: tuple[VisualAnnotation, ...]
    digest: str


def _mapping(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigurationError(f"{where} must be a mapping")
    return value


def _keys(value: dict[str, Any], allowed: set[str], where: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ConfigurationError(f"{where} has unknown key(s): {', '.join(unknown)}")


def _identifier(value: Any, where: str) -> str:
    if not isinstance(value, str) or IDENTIFIER.fullmatch(value) is None:
        raise ConfigurationError(f"{where} must be a kebab-case identifier")
    return value


def _text(value: Any, where: str, *, one_line: bool = False) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"{where} must be non-empty text")
    result = value.strip()
    if one_line and ("\n" in result or "\r" in result):
        raise ConfigurationError(f"{where} must be one line")
    return result


def _dimension(value: Any, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ConfigurationError(f"{where} must be a positive integer")
    return value


def _coordinate(value: Any, where: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not 0 <= float(value) <= 100
    ):
        raise ConfigurationError(f"{where} must be a number from 0 through 100")
    return float(value)


def _source(value: Any, where: str) -> str:
    source = _text(value, where, one_line=True)
    if any(character.isspace() for character in source) or any(
        character in source for character in "<>()"
    ):
        raise ConfigurationError(
            f"{where} must not contain whitespace or Markdown link delimiters"
        )
    if REMOTE_SOURCE.match(source):
        return source
    path = Path(source)
    if path.is_absolute() or ".." in path.parts:
        raise ConfigurationError(f"{where} must be HTTPS or repository-relative")
    return path.as_posix()


def load_visual_record(path: Path, expected_id: str) -> VisualRecord:
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise ConfigurationError(f"cannot read visual record {path}: {exc}") from exc
    try:
        if path.suffix.lower() == ".json":
            raw = json.loads(content)
        else:
            raw = yaml.safe_load(content)
    except (json.JSONDecodeError, yaml.YAMLError, UnicodeError) as exc:
        raise ConfigurationError(f"invalid visual record {path}: {exc}") from exc
    data = _mapping(raw, f"visual record {path}")
    _keys(data, VISUAL_KEYS, f"visual record {path}")
    if data.get("schema") != VISUAL_SCHEMA:
        raise ConfigurationError(
            f"visual record {path} must use schema {VISUAL_SCHEMA}"
        )
    record_id = _identifier(data.get("id"), f"visual record {path}.id")
    if record_id != expected_id:
        raise ConfigurationError(
            f"visual projection id {expected_id!r} does not match record id {record_id!r}"
        )
    kind = data.get("kind")
    if kind not in {"diagram", "screenshot"}:
        raise ConfigurationError(
            f"visual record {path}.kind must be diagram or screenshot"
        )
    annotations_raw = data.get("annotations", [])
    if not isinstance(annotations_raw, list):
        raise ConfigurationError(f"visual record {path}.annotations must be a list")
    annotations: list[VisualAnnotation] = []
    annotation_ids: set[str] = set()
    for index, raw_annotation in enumerate(annotations_raw):
        where = f"visual record {path}.annotations[{index}]"
        item = _mapping(raw_annotation, where)
        _keys(item, ANNOTATION_KEYS, where)
        annotation_id = _identifier(item.get("id"), f"{where}.id")
        if annotation_id in annotation_ids:
            raise ConfigurationError(f"duplicate visual annotation id: {annotation_id}")
        annotation_ids.add(annotation_id)
        annotations.append(
            VisualAnnotation(
                annotation_id,
                _coordinate(item.get("x"), f"{where}.x"),
                _coordinate(item.get("y"), f"{where}.y"),
                _text(item.get("title"), f"{where}.title", one_line=True),
                _text(item.get("description"), f"{where}.description"),
            )
        )
    src_dark_raw = data.get("src_dark")
    return VisualRecord(
        id=record_id,
        kind=kind,
        src=_source(data.get("src"), f"visual record {path}.src"),
        src_dark=(
            _source(src_dark_raw, f"visual record {path}.src_dark")
            if src_dark_raw is not None
            else None
        ),
        width=_dimension(data.get("width"), f"visual record {path}.width"),
        height=_dimension(data.get("height"), f"visual record {path}.height"),
        alt=_text(data.get("alt"), f"visual record {path}.alt", one_line=True),
        caption=_text(
            data.get("caption"), f"visual record {path}.caption", one_line=True
        ),
        description=_text(
            data.get("description"), f"visual record {path}.description"
        ),
        annotations=tuple(annotations),
        digest=hashlib.sha256(content).hexdigest(),
    )


def _asset(root: Path, output: Path, source: str) -> str:
    if REMOTE_SOURCE.match(source):
        return source
    asset = root / source
    try:
        asset.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ConfigurationError(f"visual asset escapes the repository: {source}") from exc
    if not asset.is_file():
        raise ConfigurationError(f"visual asset does not exist: {source}")
    return os.path.relpath(asset, (root / output).parent).replace(os.sep, "/")


def _attribute(value: str) -> str:
    return html.escape(value, quote=True)


def _html_text(value: str) -> str:
    return html.escape(value).replace("\n", "<br />\n")


def _style(output: Path, html_value: str, mdx_value: str) -> str:
    if output.suffix.lower() == ".mdx":
        return f"style={{{{{mdx_value}}}}}"
    return f'style="{html_value}"'


def render_human_visual(
    root: Path,
    projection: VisualProjection,
    record: VisualRecord,
) -> str:
    src = _asset(root, projection.human_output, record.src)
    dark = (
        _asset(root, projection.human_output, record.src_dark)
        if record.src_dark
        else None
    )
    visual_id = f"visual-{record.id}"
    receipt = (
        f"generated by Sourcebound from {projection.source.as_posix()}; "
        f"sha256: {record.digest}"
    )
    comment = (
        f"{{/* {receipt} */}}"
        if projection.human_output.suffix.lower() == ".mdx"
        else f"<!-- {receipt} -->"
    )
    role_marker = (
        "{/* sourcebound:role reference */}"
        if projection.human_output.suffix.lower() == ".mdx"
        else "<!-- sourcebound:role reference -->"
    )
    lines = [
        comment,
        role_marker,
        f'<figure id="{visual_id}" data-sourcebound-visual="{VISUAL_SCHEMA}">',
        "  <div "
        + _style(
            projection.human_output,
            "position: relative; display: inline-block; max-width: 100%;",
            " position: 'relative', display: 'inline-block', maxWidth: '100%' ",
        )
        + ">",
        "    <picture>",
    ]
    if dark:
        source_set = "srcSet" if projection.human_output.suffix.lower() == ".mdx" else "srcset"
        lines.append(
            f'      <source media="(prefers-color-scheme: dark)" '
            f'{source_set}="{_attribute(dark)}" />'
        )
    image_style = _style(
        projection.human_output,
        "display: block; max-width: 100%; height: auto;",
        " display: 'block', maxWidth: '100%', height: 'auto' ",
    )
    lines.extend([
        f'      <img src="{_attribute(src)}" alt="{_attribute(record.alt)}" '
        f'width="{record.width}" height="{record.height}" '
        f"{image_style} />",
        "    </picture>",
    ])
    for number, annotation in enumerate(record.annotations, start=1):
        anchor = f"{visual_id}-annotation-{annotation.id}"
        marker_style = _style(
            projection.human_output,
            f"position: absolute; left: {annotation.x:g}%; top: {annotation.y:g}%; "
            "transform: translate(-50%, -50%); display: inline-flex; "
            "align-items: center; justify-content: center; width: 1.75rem; "
            "height: 1.75rem; border: 2px solid currentColor; border-radius: 999px; "
            "background: Canvas; color: CanvasText; font-weight: 700;",
            " position: 'absolute', "
            f"left: '{annotation.x:g}%', top: '{annotation.y:g}%', "
            "transform: 'translate(-50%, -50%)', display: 'inline-flex', "
            "alignItems: 'center', justifyContent: 'center', width: '1.75rem', "
            "height: '1.75rem', border: '2px solid currentColor', "
            "borderRadius: '999px', background: 'Canvas', color: 'CanvasText', "
            "fontWeight: 700 ",
        )
        lines.append(
            f'    <a href="#{anchor}" aria-label="{number}: '
            f'{_attribute(annotation.title)}" {marker_style}>{number}</a>'
        )
    lines.extend([
        "  </div>",
        f"  <figcaption>{_html_text(record.caption)}</figcaption>",
        f'  <p><strong>Description:</strong> {_html_text(record.description)}</p>',
    ])
    if record.annotations:
        lines.append('  <ol aria-label="Annotation key">')
        for annotation in record.annotations:
            anchor = f"{visual_id}-annotation-{annotation.id}"
            lines.append(
                f'    <li id="{anchor}"><strong>{_html_text(annotation.title)}</strong>: '
                f'{_html_text(annotation.description)}</li>'
            )
        lines.append("  </ol>")
    lines.extend(["</figure>", ""])
    return "\n".join(lines)


def render_agent_visual(
    root: Path,
    projection: VisualProjection,
    record: VisualRecord,
) -> str:
    src = _asset(root, projection.agent_output, record.src)
    lines = [
        f"# Visual: {record.id}",
        "",
        f"- Schema: `{VISUAL_SCHEMA}`",
        f"- Kind: `{record.kind}`",
        f"- Canonical record: `{projection.source.as_posix()}`",
        f"- Record sha256: `{record.digest}`",
        f"- Source image: [{record.src}]({src})",
    ]
    if record.src_dark:
        dark = _asset(root, projection.agent_output, record.src_dark)
        lines.append(f"- Dark source image: [{record.src_dark}]({dark})")
    lines.extend([
        f"- Intrinsic size: {record.width} × {record.height}",
        f"- Alternative text: {record.alt}",
        f"- Caption: {record.caption}",
        "",
        "## Complete text equivalent",
        "",
        record.description,
    ])
    if record.annotations:
        lines.extend(["", "## Annotations", ""])
        for number, annotation in enumerate(record.annotations, start=1):
            lines.extend([
                f"{number}. **{annotation.title}** "
                f"(`x={annotation.x:g}%`, `y={annotation.y:g}%`)",
                f"   {annotation.description}",
            ])
    lines.append("")
    return "\n".join(lines)
