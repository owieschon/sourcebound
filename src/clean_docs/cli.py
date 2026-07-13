from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from clean_docs import __version__
from clean_docs.engine import evaluate, write_results
from clean_docs.errors import CleanDocsError
from clean_docs.models import BindingResult


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="clean-docs")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="repository root")
    parser.add_argument(
        "--manifest", type=Path, default=Path(".clean-docs.yml"), help="manifest path"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    derive = sub.add_parser("derive", help="preview or write generated documentation regions")
    derive.add_argument("--write", action="store_true", help="write derived regions atomically")
    derive.add_argument("--check", action="store_true", help="exit 1 when a region would change")
    derive.add_argument("--binding", help="evaluate one binding id")
    derive.add_argument("--ref", help="read bound sources from an immutable git ref")
    derive.add_argument("--format", choices=("text", "json"), default="text")
    check = sub.add_parser("check", help="fail when generated documentation has drifted")
    check.add_argument("--binding", help="evaluate one binding id")
    check.add_argument("--ref", help="read bound sources from an immutable git ref")
    check.add_argument("--format", choices=("text", "json"), default="text")
    return parser


def _json(results: list[BindingResult]) -> str:
    return json.dumps({
        "ok": not any(result.changed for result in results),
        "results": [
            {
                "binding": result.binding_id,
                "doc": result.doc,
                "status": "drift" if result.changed else "current",
                "diff": result.diff,
                "provenance": {
                    "ref": result.provenance.ref,
                    "path": result.provenance.path,
                    "locator": result.provenance.locator,
                    "extractor": result.provenance.extractor,
                    "digest": result.provenance.digest,
                },
            }
            for result in results
        ],
    }, indent=2) + "\n"


def _text(results: list[BindingResult]) -> str:
    lines: list[str] = []
    for result in results:
        status = "drift" if result.changed else "current"
        lines.append(f"[{status}] {result.binding_id}: {result.doc}")
        if result.diff:
            lines.append(result.diff.rstrip())
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = args.root.resolve()
    manifest = args.manifest
    if not manifest.is_absolute():
        manifest = root / manifest
    try:
        results = evaluate(
            root,
            manifest,
            ref=args.ref,
            binding_id=args.binding,
        )
        output = _json(results) if args.format == "json" else _text(results)
        sys.stdout.write(output)
        drift = any(result.changed for result in results)
        if args.command == "derive" and args.write and drift:
            write_results(root, results)
            sys.stdout.write(f"wrote {sum(result.changed for result in results)} document(s)\n")
        if args.command == "check" or getattr(args, "check", False):
            return 1 if drift else 0
        return 0
    except CleanDocsError as exc:
        print(f"clean-docs: {exc}", file=sys.stderr)
        return exc.exit_code
