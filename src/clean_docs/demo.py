"""Generate one static, accessible demonstration from recorded fixture evidence."""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from clean_docs.errors import ConfigurationError


EVIDENCE_KEYS = {
    "schema", "title", "intended_reader", "value", "prerequisites", "states", "limits",
    "next_step",
}
STATE_KEYS = {"id", "label", "steps"}
STEP_KEYS = {"command", "exit_code", "output"}
NEXT_STEP_KEYS = {"label", "href"}
STATE_IDS = ("before", "drift", "repaired")


@dataclass(frozen=True)
class DemoStep:
    command: str
    exit_code: int
    output: str


@dataclass(frozen=True)
class DemoState:
    id: str
    label: str
    steps: tuple[DemoStep, ...]


@dataclass(frozen=True)
class DemoEvidence:
    title: str
    intended_reader: str
    value: str
    prerequisites: tuple[str, ...]
    states: tuple[DemoState, ...]
    limits: tuple[str, ...]
    next_step_label: str
    next_step_href: str
    digest: str


def _mapping(raw: Any, where: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ConfigurationError(f"{where} must be a mapping")
    return raw


def _exact(data: dict[str, Any], keys: set[str], where: str) -> None:
    if set(data) != keys:
        raise ConfigurationError(f"{where} must contain exactly: {', '.join(sorted(keys))}")


def _text(raw: Any, where: str) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise ConfigurationError(f"{where} must be non-empty text")
    return raw.strip()


def _strings(raw: Any, where: str) -> tuple[str, ...]:
    if not isinstance(raw, list) or not raw or not all(
        isinstance(value, str) and value.strip() for value in raw
    ):
        raise ConfigurationError(f"{where} must be a non-empty string list")
    return tuple(value.strip() for value in raw)


def load_demo_evidence(path: Path) -> DemoEvidence:
    try:
        content = path.read_bytes()
        raw = json.loads(content)
    except OSError as exc:
        raise ConfigurationError(f"cannot read demo evidence {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigurationError(f"invalid demo evidence JSON: {exc}") from exc
    root = _mapping(raw, "demo evidence")
    _exact(root, EVIDENCE_KEYS, "demo evidence")
    if root["schema"] != "clean-docs.demo-evidence.v1":
        raise ConfigurationError("demo evidence has an unsupported schema")
    raw_states = root["states"]
    if not isinstance(raw_states, list) or len(raw_states) != 3:
        raise ConfigurationError("demo evidence must contain before, drift, and repaired states")
    states = []
    for index, raw_state in enumerate(raw_states):
        where = f"demo evidence.states[{index}]"
        state = _mapping(raw_state, where)
        _exact(state, STATE_KEYS, where)
        if state["id"] != STATE_IDS[index]:
            raise ConfigurationError(
                "demo evidence states must be ordered before, drift, repaired"
            )
        raw_steps = state["steps"]
        if not isinstance(raw_steps, list) or not raw_steps:
            raise ConfigurationError(f"{where}.steps must be a non-empty list")
        steps = []
        for step_index, raw_step in enumerate(raw_steps):
            step_where = f"{where}.steps[{step_index}]"
            step = _mapping(raw_step, step_where)
            _exact(step, STEP_KEYS, step_where)
            exit_code = step["exit_code"]
            if not isinstance(exit_code, int) or exit_code < 0:
                raise ConfigurationError(f"{step_where}.exit_code must be a non-negative integer")
            steps.append(DemoStep(
                command=_text(step["command"], f"{step_where}.command"),
                exit_code=exit_code,
                output=_text(step["output"], f"{step_where}.output"),
            ))
        states.append(DemoState(
            id=state["id"],
            label=_text(state["label"], f"{where}.label"),
            steps=tuple(steps),
        ))
    next_step = _mapping(root["next_step"], "demo evidence.next_step")
    _exact(next_step, NEXT_STEP_KEYS, "demo evidence.next_step")
    href = _text(next_step["href"], "demo evidence.next_step.href")
    if href.startswith(("http://", "//")):
        raise ConfigurationError("demo next step must be local or use HTTPS")
    return DemoEvidence(
        title=_text(root["title"], "demo evidence.title"),
        intended_reader=_text(root["intended_reader"], "demo evidence.intended_reader"),
        value=_text(root["value"], "demo evidence.value"),
        prerequisites=_strings(root["prerequisites"], "demo evidence.prerequisites"),
        states=tuple(states),
        limits=_strings(root["limits"], "demo evidence.limits"),
        next_step_label=_text(next_step["label"], "demo evidence.next_step.label"),
        next_step_href=href,
        digest=hashlib.sha256(content).hexdigest(),
    )


class _StructureParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.lang = ""
        self.in_title = False
        self.title = ""
        self.headings: list[int] = []
        self.ids: set[str] = set()
        self.fragments: list[str] = []
        self.labelled_by: list[str] = []
        self.skip_main = False
        self.main = False
        self.scripts = 0
        self.external_resources: list[str] = []
        self.images_without_alt = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        if tag == "html":
            self.lang = values.get("lang", "")
        if tag == "title":
            self.in_title = True
        if tag == "main" and values.get("id") == "main":
            self.main = True
        if tag == "script":
            self.scripts += 1
        if tag == "img" and "alt" not in values:
            self.images_without_alt += 1
        if tag in {"link", "img", "script", "iframe"}:
            resource = values.get("href") or values.get("src")
            if resource and resource.startswith(("http://", "https://", "//")):
                self.external_resources.append(resource)
        if tag.startswith("h") and len(tag) == 2 and tag[1].isdigit():
            self.headings.append(int(tag[1]))
        if identifier := values.get("id"):
            self.ids.add(identifier)
        if labelled_by := values.get("aria-labelledby"):
            self.labelled_by.extend(labelled_by.split())
        href = values.get("href", "")
        if href == "#main":
            self.skip_main = True
        if href.startswith("#") and len(href) > 1:
            self.fragments.append(href[1:])

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title += data


def validate_static_html(content: str) -> None:
    parser = _StructureParser()
    parser.feed(content)
    failures = []
    if parser.lang != "en":
        failures.append("html lang must be en")
    if not parser.title.strip():
        failures.append("title must be non-empty")
    if not parser.main:
        failures.append("main landmark must have id main")
    if not parser.skip_main:
        failures.append("skip link must target #main")
    if parser.headings.count(1) != 1:
        failures.append("page must contain one h1")
    if parser.headings and any(
        current > previous + 1
        for previous, current in zip(parser.headings, parser.headings[1:])
    ):
        failures.append("heading levels must not skip")
    missing = sorted((set(parser.fragments) | set(parser.labelled_by)) - parser.ids)
    if missing:
        failures.append("missing referenced id(s): " + ", ".join(missing))
    if parser.scripts:
        failures.append("scripts are not allowed")
    if parser.external_resources:
        failures.append("external runtime resources are not allowed")
    if parser.images_without_alt:
        failures.append("every image must have alt text")
    if failures:
        raise ConfigurationError("static demo structure failed: " + "; ".join(failures))


def _link(output: Path, target: str) -> str:
    if target.startswith("https://"):
        return target
    path, separator, fragment = target.partition("#")
    relative = os.path.relpath(path, output.parent).replace(os.sep, "/")
    return relative + (f"#{fragment}" if separator else "")


def render_static_demo(evidence: DemoEvidence, output: Path) -> str:
    esc = html.escape

    def preformatted(value: str) -> str:
        escaped = esc(value)
        return re.sub(
            r" +(?=\n|$)",
            lambda match: "&#32;" * len(match.group(0)),
            escaped,
        )

    prerequisite_items = "".join(f"<li>{esc(item)}</li>" for item in evidence.prerequisites)
    limit_items = "".join(f"<li>{esc(item)}</li>" for item in evidence.limits)
    state_cards = []
    for state in evidence.states:
        steps = []
        for step in state.steps:
            steps.append(
                '<div class="step">'
                f'<p><code>{esc(step.command)}</code> <span>exit {step.exit_code}</span></p>'
                f'<pre aria-label="Output from {esc(step.command)}"><code>{preformatted(step.output)}</code></pre>'
                "</div>"
            )
        state_cards.append(
            f'<article class="state {esc(state.id)}" aria-labelledby="state-{esc(state.id)}">'
            f'<h3 id="state-{esc(state.id)}">{esc(state.label)}</h3>'
            + "".join(steps)
            + "</article>"
        )
    next_href = _link(output, evidence.next_step_href)
    content = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(evidence.title)}</title>
  <style>
    :root {{ color-scheme: light; --ink: #18211b; --muted: #58635b; --paper: #f7f5ef; --line: #c9cec8; --good: #286344; --bad: #a43f32; --repair: #7a5717; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: var(--paper); color: var(--ink); font: 17px/1.55 ui-monospace, SFMono-Regular, Menlo, monospace; }}
    a {{ color: inherit; text-underline-offset: .2em; }}
    .skip {{ position: absolute; left: 1rem; top: -4rem; background: var(--ink); color: white; padding: .7rem; }}
    .skip:focus {{ top: 1rem; }}
    header, main {{ width: min(74rem, calc(100% - 2rem)); margin: 0 auto; }}
    header {{ padding: 5rem 0 2rem; border-bottom: 1px solid var(--line); }}
    h1 {{ max-width: 18ch; font: 700 clamp(2.5rem, 8vw, 5.5rem)/.96 Georgia, serif; margin: .2rem 0 1.5rem; letter-spacing: -.04em; }}
    h2 {{ margin-top: 3.5rem; font: 700 2rem/1.1 Georgia, serif; }}
    h3 {{ margin-top: 0; }}
    .eyebrow, .digest {{ color: var(--muted); text-transform: uppercase; letter-spacing: .08em; font-size: .78rem; }}
    .digest {{ overflow-wrap: anywhere; }}
    .states {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1rem; }}
    .state {{ border-top: .45rem solid var(--line); background: white; padding: 1.1rem; min-width: 0; }}
    .state.before {{ border-color: var(--good); }} .state.drift {{ border-color: var(--bad); }} .state.repaired {{ border-color: var(--repair); }}
    code, pre {{ font: .88rem/1.45 ui-monospace, SFMono-Regular, Menlo, monospace; }}
    pre {{ overflow: auto; padding: .9rem; background: #101512; color: #edf2ed; white-space: pre-wrap; }}
    .step span {{ float: right; color: var(--muted); }}
    .next {{ display: inline-block; margin: 0 0 5rem; padding: .8rem 1rem; border: 2px solid var(--ink); text-decoration: none; }}
    @media (max-width: 760px) {{ .states {{ grid-template-columns: 1fr; }} header {{ padding-top: 3.5rem; }} }}
    @media (prefers-reduced-motion: reduce) {{ *, *::before, *::after {{ scroll-behavior: auto !important; }} }}
  </style>
</head>
<body>
  <a class="skip" href="#main">Skip to demonstration</a>
  <header>
    <p class="eyebrow">Recorded local evidence</p>
    <h1>{esc(evidence.title)}</h1>
    <p>{esc(evidence.value)}</p>
    <p class="digest">Evidence sha256: {evidence.digest}</p>
  </header>
  <main id="main">
    <section aria-labelledby="intended-reader"><h2 id="intended-reader">Intended reader</h2><p>{esc(evidence.intended_reader)}</p></section>
    <section aria-labelledby="prerequisites"><h2 id="prerequisites">Prerequisites</h2><ul>{prerequisite_items}</ul></section>
    <section aria-labelledby="procedure"><h2 id="procedure">Procedure</h2><div class="states">{''.join(state_cards)}</div></section>
    <section aria-labelledby="limits"><h2 id="limits">Limits</h2><ul>{limit_items}</ul></section>
    <section aria-labelledby="next-step"><h2 id="next-step">Next step</h2><a class="next" href="{esc(next_href)}">{esc(evidence.next_step_label)}</a></section>
  </main>
</body>
</html>
"""
    validate_static_html(content)
    return content
