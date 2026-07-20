#!/usr/bin/env python3
"""Render the repository social preview from its own stable design tokens."""

from __future__ import annotations

import argparse
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path

from clean_docs.regions import atomic_write


ROOT = Path(__file__).resolve().parents[1]
SVG_OUTPUT = ROOT / "docs/assets/sourcebound-social.svg"
PNG_OUTPUT = ROOT / "docs/assets/sourcebound-social.png"
WIDTH = 1280
HEIGHT = 640


def _design_tokens() -> dict[str, str]:
    return {
        "background": "#edf6ff",
        "ink": "#15143b",
        "line": "#25225f",
        "border": "#302d78",
        "accent": "#4541a2",
        "Repository sources": "Repository sources",
        "Source bindings": "Source bindings",
        "Reject stale changes": "Reject stale changes",
    }


def render_svg() -> str:
    token = _design_tokens()
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title desc">
  <title id="title">Sourcebound: docs that answer to code</title>
  <desc id="desc">A three-step source-bound documentation flow. Repository sources own facts, bindings connect facts to prose, and a deterministic check rejects stale changes.</desc>
  <defs>
    <pattern id="grid" width="32" height="32" patternUnits="userSpaceOnUse">
      <circle cx="2" cy="2" r="1.5" fill="#a9bfda"/>
    </pattern>
    <filter id="shadow" x="-10%" y="-10%" width="120%" height="135%">
      <feDropShadow dx="0" dy="7" stdDeviation="8" flood-color="#26355e" flood-opacity="0.13"/>
    </filter>
    <marker id="arrow" markerWidth="12" markerHeight="12" refX="10" refY="6" orient="auto">
      <path d="M0 0L12 6L0 12Z" fill="{token['line']}"/>
    </marker>
    <style>
      .brand {{ font: 800 24px ui-sans-serif, system-ui, sans-serif; fill: {token['ink']}; }}
      .eyebrow {{ font: 750 15px ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: .14em; fill: {token['accent']}; }}
      .headline {{ font: 800 62px ui-sans-serif, system-ui, sans-serif; letter-spacing: -.035em; fill: {token['ink']}; }}
      .subhead {{ font: 540 22px ui-sans-serif, system-ui, sans-serif; fill: #41415f; }}
      .step {{ font: 750 14px ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: .12em; fill: {token['accent']}; }}
      .card-title {{ font: 790 27px ui-sans-serif, system-ui, sans-serif; fill: {token['ink']}; }}
      .card-body {{ font: 540 18px ui-sans-serif, system-ui, sans-serif; fill: #41415f; }}
      .outcome {{ font: 720 15px ui-sans-serif, system-ui, sans-serif; fill: {token['line']}; }}
    </style>
  </defs>
  <rect width="1280" height="640" fill="{token['background']}"/>
  <rect width="1280" height="640" fill="url(#grid)"/>
  <rect x="34" y="34" width="1212" height="572" rx="22" fill="{token['background']}" fill-opacity=".91" stroke="{token['line']}" stroke-width="3"/>

  <g transform="translate(70 64)">
    <rect width="48" height="48" rx="10" fill="{token['line']}"/>
    <path d="M14 14h20v20H14zM20 9v30M28 9v30" fill="none" stroke="#fff" stroke-width="3"/>
    <text x="64" y="33" class="brand">Sourcebound</text>
  </g>
  <text x="70" y="154" class="eyebrow">SOURCE-BOUND DOCUMENTATION ENGINE</text>
  <text x="70" y="225" class="headline">Docs that answer to code.</text>
  <text x="70" y="270" class="subhead">When source moves, stale prose fails loudly.</text>

  <path d="M370 424H481M772 424H883" fill="none" stroke="{token['line']}" stroke-width="5" stroke-linecap="round" marker-end="url(#arrow)"/>

  <g transform="translate(70 336)" filter="url(#shadow)">
    <rect width="300" height="176" rx="16" fill="#fff" stroke="{token['border']}" stroke-width="3"/>
    <text x="26" y="38" class="step">01 · SOURCE</text>
    <text x="26" y="82" class="card-title">{token['Repository sources']}</text>
    <text x="26" y="116" class="card-body">Code owns the fact.</text>
    <rect x="26" y="140" width="118" height="26" rx="13" fill="#dbe8ff"/>
    <text x="43" y="159" class="outcome">static evidence</text>
    <circle cx="300" cy="88" r="8" fill="#fff" stroke="{token['line']}" stroke-width="4"/>
  </g>

  <g transform="translate(472 336)" filter="url(#shadow)">
    <rect width="300" height="176" rx="16" fill="#fff" stroke="{token['border']}" stroke-width="3"/>
    <text x="26" y="38" class="step">02 · BIND</text>
    <text x="26" y="82" class="card-title">{token['Source bindings']}</text>
    <text x="26" y="116" class="card-body">Prose names its owner.</text>
    <rect x="26" y="140" width="154" height="26" rx="13" fill="#dff4ed"/>
    <text x="43" y="159" class="outcome">region · command pin · symbol</text>
    <circle cx="0" cy="88" r="8" fill="#fff" stroke="{token['line']}" stroke-width="4"/>
    <circle cx="300" cy="88" r="8" fill="#fff" stroke="{token['line']}" stroke-width="4"/>
  </g>

  <g transform="translate(874 336)" filter="url(#shadow)">
    <rect width="300" height="176" rx="16" fill="{token['line']}" stroke="#15143b" stroke-width="3"/>
    <text x="26" y="38" class="step" style="fill:#c9c7ff">03 · PROVE</text>
    <text x="26" y="82" class="card-title" style="fill:#fff">Deterministic check</text>
    <text x="26" y="116" class="card-body" style="fill:#eef0ff">Drift fails before merge.</text>
    <rect x="26" y="140" width="194" height="26" rx="13" fill="#fff"/>
    <text x="43" y="159" class="outcome">repair · reject · project</text>
    <circle cx="0" cy="88" r="8" fill="#fff" stroke="{token['line']}" stroke-width="4"/>
  </g>

  <path d="M70 558H1174" stroke="{token['accent']}" stroke-width="3" stroke-linecap="round"/>
  <text x="70" y="586" class="step">THE CHECKABLE SPINE STAYS ATTACHED</text>
</svg>
'''


def _png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()[:24]
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise RuntimeError(f"not a PNG: {path}")
    return struct.unpack(">II", data[16:24])


def _chrome() -> str:
    candidates = (
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    )
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise RuntimeError("Chrome or Chromium is required to render the social preview PNG")


def render_png(svg: str, output: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="sourcebound-social-") as temporary:
        html = Path(temporary) / "preview.html"
        html.write_text(
            '<!doctype html><html><head><meta charset="utf-8"><style>'
            'html,body{margin:0;width:1280px;height:640px;overflow:hidden}'
            'svg{display:block}</style></head><body>' + svg + "</body></html>",
            encoding="utf-8",
        )
        subprocess.run(
            [
                _chrome(),
                "--headless=new",
                "--hide-scrollbars",
                "--disable-gpu",
                "--force-device-scale-factor=1",
                "--window-size=1280,640",
                f"--screenshot={output.resolve()}",
                html.resolve().as_uri(),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
    if _png_dimensions(output) != (WIDTH, HEIGHT):
        raise RuntimeError(f"social preview has unexpected dimensions: {_png_dimensions(output)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    svg = render_svg()
    if args.check:
        if SVG_OUTPUT.read_text(encoding="utf-8") != svg:
            raise SystemExit("social preview SVG is stale")
        if _png_dimensions(PNG_OUTPUT) != (WIDTH, HEIGHT):
            raise SystemExit("social preview PNG is missing or has the wrong dimensions")
        return 0
    atomic_write(SVG_OUTPUT, svg)
    render_png(svg, PNG_OUTPUT)
    print(PNG_OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
