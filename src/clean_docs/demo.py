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
    if root["schema"] != "sourcebound.demo-evidence.v1":
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
    state_explanations = {
        "before": "Source and README agree. The gate has nothing to repair.",
        "drift": "The source changed; the README did not. The gate names the stale binding.",
        "repaired": "The declared region is regenerated, then the same check passes.",
    }
    state_cards: list[str] = []
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
            f'<div class="state-heading"><span class="state-index">0{len(state_cards) + 1}</span>'
            f'<h3 id="state-{esc(state.id)}">{esc(state.label.split(". ", 1)[-1])}</h3></div>'
            f'<p class="state-explanation">{esc(state_explanations[state.id])}</p>'
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
    :root {{ color-scheme: light; --ink: #20242c; --muted: #667085; --paper: #f7f8fa; --panel: #ffffff; --line: #d9dde5; --binding: #6558d3; --binding-soft: #eeecff; --bad: #c9342f; --bad-soft: #fff0ef; --good: #22734b; --good-soft: #eaf7f0; --code: #171a21; }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{ margin: 0; background: var(--paper); color: var(--ink); font: 16px/1.55 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    a {{ color: inherit; text-underline-offset: .22em; }}
    .skip {{ position: absolute; left: 1rem; top: -5rem; z-index: 5; background: var(--ink); color: white; padding: .7rem 1rem; }}
    .skip:focus {{ top: 1rem; }}
    .wrap, main {{ width: min(72rem, calc(100% - 2.5rem)); margin: 0 auto; }}
    header {{ background: var(--panel); border-bottom: 1px solid var(--line); }}
    .hero {{ display: grid; grid-template-columns: minmax(0, .9fr) minmax(28rem, 1.1fr); gap: clamp(2rem, 5vw, 4.5rem); align-items: center; padding: 3.25rem 0; }}
    h1 {{ max-width: 14ch; margin: .45rem 0 1rem; font-size: clamp(2.5rem, 5vw, 4.5rem); line-height: .98; letter-spacing: -.055em; }}
    h2 {{ margin: 0 0 .75rem; font-size: clamp(1.65rem, 3vw, 2.45rem); line-height: 1.08; letter-spacing: -.035em; }}
    h3 {{ margin: 0; font-size: 1.05rem; letter-spacing: -.015em; }}
    .eyebrow, .digest, .state-index, .node-label {{ font: 700 .75rem/1.2 ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: .1em; text-transform: uppercase; }}
    .eyebrow {{ color: var(--binding); }}
    .hero-copy {{ min-width: 0; }}
    .hero-copy > p:not(.eyebrow):not(.digest) {{ max-width: 34rem; color: var(--muted); font-size: 1.02rem; overflow-wrap: anywhere; }}
    .digest {{ margin-top: 1.35rem; color: #8b93a3; overflow-wrap: anywhere; word-break: break-all; text-transform: none; letter-spacing: .01em; font-size: .67rem; }}
    .binding {{ position: relative; padding: 1rem; border: 1px solid var(--line); border-radius: .65rem; background: #fafaff; }}
    .binding-title {{ margin: 0 0 .75rem; color: var(--muted); font-size: .8rem; }}
    .node {{ padding: .8rem .9rem; border: 1px solid #d5d1fb; border-radius: .4rem; background: var(--panel); }}
    .node-label {{ display: block; margin-bottom: .4rem; color: var(--binding); }}
    .node code {{ display: block; overflow-x: auto; color: var(--ink); font-size: .84rem; }}
    .tether {{ display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; gap: .6rem; margin: .55rem 0; color: var(--bad); }}
    .tether::before, .tether::after {{ content: ""; border-top: 2px dashed currentColor; }}
    .tether span {{ padding: .25rem .5rem; border: 1px solid currentColor; border-radius: 999px; background: var(--bad-soft); font: 700 .67rem/1 ui-monospace, monospace; text-transform: uppercase; letter-spacing: .06em; }}
    .mismatch {{ color: var(--bad); }}
    main {{ padding: 2.5rem 0 2rem; }}
    .intro-grid {{ display: grid; grid-template-columns: 1.2fr .8fr; gap: 3rem; padding-bottom: 2.5rem; border-bottom: 1px solid var(--line); }}
    .intro-grid p {{ max-width: 44rem; font-size: 1.15rem; }}
    .prerequisites {{ margin: 0; padding: 1rem 1rem 1rem 2.2rem; border: 1px solid var(--line); border-radius: .5rem; background: var(--panel); }}
    .section-kicker {{ margin: 0 0 .55rem; color: var(--binding); font: 700 .72rem/1.2 ui-monospace, monospace; letter-spacing: .08em; text-transform: uppercase; }}
    .procedure {{ padding: 2.75rem 0; }}
    .procedure-lead {{ max-width: 43rem; margin: 0 0 1.35rem; color: var(--muted); }}
    .states {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); border: 1px solid var(--line); background: var(--line); gap: 1px; }}
    .state {{ position: relative; background: var(--panel); padding: 1.2rem; min-width: 0; }}
    .state::before {{ content: ""; position: absolute; inset: 0 auto auto 0; width: 100%; height: .25rem; background: var(--binding); }}
    .state.drift::before {{ background: var(--bad); }} .state.repaired::before {{ background: var(--good); }}
    .state-heading {{ display: flex; align-items: baseline; gap: .65rem; margin-bottom: .65rem; }}
    .state-index {{ color: var(--muted); }}
    .state-explanation {{ min-height: 4.65rem; margin: 0; color: var(--muted); font-size: .9rem; }}
    .step {{ margin-top: .85rem; }}
    .step > p {{ margin: 0; padding: .55rem .7rem; border: 1px solid var(--line); border-bottom: 0; background: #f5f6f8; }}
    .step span {{ float: right; color: var(--muted); font: 700 .75rem/1.8 ui-monospace, monospace; text-transform: uppercase; }}
    code, pre {{ font: .84rem/1.5 ui-monospace, SFMono-Regular, Menlo, monospace; }}
    pre {{ min-height: 7rem; margin: 0; overflow: auto; padding: .8rem; background: var(--code); color: #e8eaf0; white-space: pre-wrap; }}
    .proof {{ display: grid; grid-template-columns: .75fr 1.25fr; gap: 3rem; padding: 2.75rem 0; border-top: 1px solid var(--line); }}
    .proof ul {{ margin: 0; padding-left: 1.2rem; }}
    .proof li + li {{ margin-top: .8rem; }}
    .next-section {{ display: flex; justify-content: space-between; align-items: center; gap: 2rem; margin-top: 1rem; padding: 1.5rem; border: 1px solid #d5d1fb; border-radius: .65rem; background: var(--binding-soft); }}
    .next-section h2 {{ max-width: 15ch; font-size: 2rem; }}
    .next {{ flex: none; display: inline-block; padding: .75rem 1rem; border: 1px solid var(--binding); border-radius: .4rem; background: var(--binding); color: white; font-weight: 700; text-decoration: none; }}
    .next:hover {{ background: #5145bd; }}
    @media (max-width: 900px) {{ .hero {{ grid-template-columns: 1fr; }} .binding {{ max-width: 38rem; }} .states {{ grid-template-columns: 1fr; }} .state-explanation {{ min-height: 0; }} .intro-grid, .proof {{ grid-template-columns: 1fr; gap: 1.5rem; }} }}
    @media (max-width: 560px) {{ .wrap, main {{ width: min(100% - 2rem, 72rem); }} .hero {{ padding: 2.25rem 0; }} h1 {{ font-size: 2.65rem; }} .binding {{ padding: .75rem; }} .next-section {{ align-items: flex-start; flex-direction: column; }} }}
    @media (prefers-reduced-motion: reduce) {{ *, *::before, *::after {{ scroll-behavior: auto !important; }} }}
  </style>
</head>
<body>
  <a class="skip" href="#main">Skip to demonstration</a>
  <header>
    <div class="wrap hero">
      <div class="hero-copy">
        <p class="eyebrow">Recorded, deterministic proof</p>
        <h1>{esc(evidence.title)}</h1>
        <p>{esc(evidence.value)}</p>
        <p class="digest">Evidence sha256: {evidence.digest}</p>
      </div>
      <div class="binding" aria-label="A source command no longer matches its README claim">
        <p class="binding-title">Binding: <code>public-command</code></p>
        <div class="node"><span class="node-label">Source · command.txt</span><code>sourcebound check --changed</code></div>
        <div class="tether mismatch"><span>mismatch</span></div>
        <div class="node"><span class="node-label">Document · README.md</span><code>sourcebound check</code></div>
      </div>
    </div>
  </header>
  <main id="main">
    <section class="procedure" aria-labelledby="procedure"><p class="section-kicker">The complete loop</p><h2 id="procedure">One binding. Three observable states.</h2><p class="procedure-lead">The source changes in state two. The document is left untouched until the declared repair runs in state three.</p><div class="states">{''.join(state_cards)}</div></section>
    <section class="intro-grid" aria-labelledby="intended-reader">
      <div><p class="section-kicker">Why this demonstration exists</p><h2 id="intended-reader">See the failure before adding the gate.</h2><p>{esc(evidence.intended_reader)}</p></div>
      <div><p class="section-kicker" id="prerequisites">What is running</p><ul class="prerequisites" aria-labelledby="prerequisites">{prerequisite_items}</ul></div>
    </section>
    <section class="proof" aria-labelledby="limits"><div><p class="section-kicker">Evidence boundary</p><h2 id="limits">What this proves.</h2></div><ul>{limit_items}</ul></section>
    <section class="next-section" aria-labelledby="next-step"><h2 id="next-step">Try the same loop in a repository.</h2><a class="next" href="{esc(next_href)}">{esc(evidence.next_step_label)}</a></section>
  </main>
</body>
</html>
"""
    validate_static_html(content)
    return content
