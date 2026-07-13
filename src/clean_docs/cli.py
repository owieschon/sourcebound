from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from clean_docs import __version__
from clean_docs.audit import audit
from clean_docs.capabilities import CLI_REFERENCE
from clean_docs.doctor import diagnose
from clean_docs.emit import emit_llms_txt, emit_stepwise_skill
from clean_docs.engine import drive, evaluate, write_results
from clean_docs.errors import CleanDocsError
from clean_docs.inventory import scan_inventory
from clean_docs.manifest import load_manifest
from clean_docs.models import BindingResult
from clean_docs.standard import compile_standard, pack_matches_standard, write_pack


def _command_help(command: str) -> str:
    return next(item["job"] for item in CLI_REFERENCE if item["command"] == command)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="clean-docs")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="repository root")
    parser.add_argument(
        "--manifest", type=Path, default=Path(".clean-docs.yml"), help="manifest path"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    audit_parser = sub.add_parser("audit", help=_command_help("audit"))
    audit_parser.add_argument("--format", choices=("text", "json"), default="text")
    inventory_parser = sub.add_parser("inventory", help=_command_help("inventory"))
    inventory_parser.add_argument("--format", choices=("text", "json"), default="text")
    doctor_parser = sub.add_parser("doctor", help=_command_help("doctor"))
    doctor_parser.add_argument("--format", choices=("text", "json"), default="text")
    derive = sub.add_parser("derive", help=_command_help("derive"))
    derive.add_argument("--write", action="store_true", help="write derived regions atomically")
    derive.add_argument("--check", action="store_true", help="exit 1 when a region would change")
    derive.add_argument("--binding", help="evaluate one binding id")
    derive.add_argument("--ref", help="read bound sources from an immutable git ref")
    derive.add_argument("--format", choices=("text", "json"), default="text")
    drive_parser = sub.add_parser("drive", help=_command_help("drive"))
    drive_parser.add_argument("--binding", help="repair one binding id")
    drive_parser.add_argument("--ref", help="read bound sources from an immutable git ref")
    drive_parser.add_argument("--format", choices=("text", "json"), default="text")
    check = sub.add_parser("check", help=_command_help("check"))
    check.add_argument("--binding", help="evaluate one binding id")
    check.add_argument("--ref", help="read bound sources from an immutable git ref")
    check.add_argument("--format", choices=("text", "json"), default="text")
    emit = sub.add_parser("emit", help=_command_help("emit"))
    emit_sub = emit.add_subparsers(dest="target", required=True)
    stepwise = emit_sub.add_parser(
        "stepwise-skill", help=_command_help("emit stepwise-skill")
    )
    stepwise.add_argument("--out", type=Path, default=Path("dist/stepwise-skill"))
    stepwise.add_argument("--display-name", default="Keep documentation true")
    stepwise.add_argument("--role", choices=("skill", "command"), default="skill")
    stepwise.add_argument("--parent-command")
    stepwise.add_argument("--command", dest="command_name")
    llms = emit_sub.add_parser(
        "llms-txt", help=_command_help("emit llms-txt")
    )
    llms.add_argument("--out", type=Path, default=Path("llms.txt"))
    llms.add_argument("--title", default="Repository documentation")
    llms.add_argument("--summary")
    standard = sub.add_parser("standard", help=_command_help("standard"))
    standard_sub = standard.add_subparsers(dest="standard_command", required=True)
    for command in ("build", "check"):
        item = standard_sub.add_parser(command, help=_command_help(f"standard {command}"))
        item.add_argument("--source", type=Path, default=Path("STANDARD.md"))
        item.add_argument(
            "--output", type=Path, default=Path("src/clean_docs/standards/default.json")
        )
    return parser


def _json(results: list[BindingResult], *, repaired: bool = False) -> str:
    return json.dumps({
        "ok": not any(
            result.changed and not (repaired and result.binding_type == "region")
            for result in results
        ),
        "results": [
            {
                "binding": result.binding_id,
                "doc": result.doc,
                "status": "repaired" if repaired and result.changed
                and result.binding_type == "region" else (
                    "drift" if result.changed else "current"
                ),
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


def _text(results: list[BindingResult], *, repaired: bool = False) -> str:
    lines: list[str] = []
    for result in results:
        was_repaired = repaired and result.changed and result.binding_type == "region"
        status = "repaired" if was_repaired else (
            "drift" if result.changed else "current"
        )
        lines.append(f"[{status}] {result.binding_id}: {result.doc}")
        if result.diff:
            lines.append(result.diff.rstrip())
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = args.root.resolve()
    if args.command == "audit":
        try:
            report = audit(root)
        except CleanDocsError as exc:
            print(f"clean-docs: {exc}", file=sys.stderr)
            return exc.exit_code
        if args.format == "json":
            print(json.dumps({
                "ok": not report.findings,
                "documents": list(report.documents),
                "ignored_documents": list(report.ignored_documents),
                "findings": [asdict(finding) for finding in report.findings],
            }, indent=2))
        else:
            for audit_finding in report.findings:
                print(
                    f"[{audit_finding.rule}] {audit_finding.path}:{audit_finding.line} "
                    f"{audit_finding.detail}"
                )
            print(
                f"audit: {len(report.documents)} active document(s), "
                f"{len(report.ignored_documents)} archived, {len(report.findings)} finding(s)"
            )
        return 1 if report.findings else 0
    if args.command == "inventory":
        inventory_report = scan_inventory(root)
        if args.format == "json":
            print(json.dumps(inventory_report.as_dict(), indent=2))
        else:
            for item in inventory_report.items:
                print(f"[{item.coverage}] {item.kind} {item.name}: {item.source}#{item.locator}")
            print(
                f"inventory: {len(inventory_report.items)} surface(s); "
                f"{len(inventory_report.languages)} language(s)"
            )
        return 0
    if args.command == "doctor":
        manifest = args.manifest if args.manifest.is_absolute() else root / args.manifest
        checks = diagnose(root, manifest)
        if args.format == "json":
            print(json.dumps({
                "ok": all(check.ok for check in checks),
                "checks": [asdict(check) for check in checks],
            }, indent=2))
        else:
            for check in checks:
                print(f"[{'ok' if check.ok else 'fail'}] {check.name}: {check.detail}")
        return 0 if all(check.ok for check in checks) else 1
    if args.command == "standard":
        source = args.source if args.source.is_absolute() else root / args.source
        output = args.output if args.output.is_absolute() else root / args.output
        try:
            if args.standard_command == "build":
                write_pack(compile_standard(source), output)
                print(f"wrote {output}")
                return 0
            if pack_matches_standard(source, output):
                print(f"[current] {output}")
                return 0
            print(f"clean-docs: policy pack is stale: {output}", file=sys.stderr)
            return 1
        except CleanDocsError as exc:
            print(f"clean-docs: {exc}", file=sys.stderr)
            return exc.exit_code
    manifest = args.manifest
    if not manifest.is_absolute():
        manifest = root / manifest
    try:
        if args.command == "emit":
            loaded = load_manifest(manifest)
            out = args.out if args.out.is_absolute() else root / args.out

            def _shown(path: Path) -> Path:
                return path.relative_to(root) if path.is_relative_to(root) else path

            if args.target == "llms-txt":
                written_path = emit_llms_txt(
                    loaded, out, title=args.title, summary=args.summary
                )
                print(_shown(written_path))
                return 0
            written = emit_stepwise_skill(
                loaded,
                out,
                display_name=args.display_name,
                role=args.role,
                parent_command=args.parent_command,
                command=args.command_name,
            )
            for path in written:
                print(_shown(path))
            print(f"emit: wrote {len(written)} file(s) to {_shown(out)}")
            return 0
        if args.command == "drive":
            results, findings = drive(
                root,
                manifest,
                ref=args.ref,
                binding_id=args.binding,
            )
            output = (
                _json(results, repaired=not findings)
                if args.format == "json"
                else _text(results, repaired=not findings)
            )
            sys.stdout.write(output)
            if findings:
                for policy_finding in findings:
                    print(
                        f"[policy] {policy_finding.doc}:{policy_finding.line} "
                        f"{policy_finding.rule}: {policy_finding.detail}",
                        file=sys.stderr,
                    )
                return 1
            print(
                f"drive: repaired {sum(result.changed for result in results if result.binding_type == 'region')} document(s); "
                "implemented policy checks passed"
            )
            return 1 if any(
                result.changed and result.binding_type != "region" for result in results
            ) else 0
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
