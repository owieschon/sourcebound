from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from clean_docs import __version__
from clean_docs.applicability import ROLE_DESCRIPTIONS
from clean_docs.audit import AUDIT_BASELINE_PATH, audit, write_audit_baseline
from clean_docs.bootstrap import apply_bootstrap_plan, build_bootstrap_plan
from clean_docs.capabilities import CLI_REFERENCE
from clean_docs.changed import check_changed, render_sarif
from clean_docs.claims import claim_binding_results, scan_source_claims
from clean_docs.context import compile_context
from clean_docs.doctor import build_diagnostic_bundle
from clean_docs.emit import emit_llms_txt, emit_stepwise_skill
from clean_docs.engine import drive, evaluate, write_results
from clean_docs.evaluation import run_evaluation, write_evaluation_history
from clean_docs.errors import CleanDocsError, ConfigurationError
from clean_docs.execution import ExecutionPolicy
from clean_docs.explain import explain
from clean_docs.feedback import (
    disable_feedback,
    enable_feedback,
    enqueue_feedback,
    flush_feedback,
    ingest_behavior_signal,
    load_behavior_signal,
    load_feedback_config,
    preview_feedback,
    prepare_behavior_signal,
    purge_feedback,
    rotate_feedback_identity,
    transition_improvement_case,
)
from clean_docs.impact import build_impact_plan, render_impact_plan
from clean_docs.improvements import (
    LIFECYCLE_EVIDENCE_KINDS,
    LIFECYCLE_STATES,
    LifecycleEvidence,
    initialize_candidate_lifecycle,
    load_candidate_lifecycle,
    load_review_candidates,
    transition_candidate_lifecycle,
    write_candidate_lifecycle,
    write_improvement_candidates,
)
from clean_docs.inventory import scan_inventory
from clean_docs.plugins import scan_extended_inventory
from clean_docs.manifest import load_manifest
from clean_docs.models import BindingResult
from clean_docs.migration import apply_migration, build_migration_plan, rollback_migration
from clean_docs.outcomes import build_outcome_receipt
from clean_docs.performance import benchmark_changed_check
from clean_docs.phrasing import RecordedProvider
from clean_docs.projections import evaluate_projections, write_projections
from clean_docs.release import (
    build_release_report,
    render_release_markdown,
    validate_release_narrative,
)
from clean_docs.regions import atomic_write
from clean_docs.residue import LOCAL_CONFIG_NAME, load_local_residue_rules
from clean_docs.sensitivity import (
    decode_json_object,
    evaluate_binding_sensitivity,
    load_json_object,
)
from clean_docs.standard import compile_standard, pack_matches_standard, write_pack
from clean_docs.snapshot import RepositorySnapshot
from clean_docs.verdict import (
    VERDICT_SCHEMA,
    build_pr_verdict,
    render_verdict_sarif,
)


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
    audit_parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="replace the exact existing-debt baseline with current findings",
    )
    audit_parser.add_argument(
        "--preview-policy",
        action="store_true",
        help="report compatible house-policy candidates without accepting them as gates",
    )
    residue = sub.add_parser("residue", help="manage private residue matching")
    residue_sub = residue.add_subparsers(dest="residue_command", required=True)
    residue_sub.add_parser("status", help="report whether private matching is active")
    residue_sub.add_parser("init-local", help="create a permission-restricted local rule template")
    inventory_parser = sub.add_parser("inventory", help=_command_help("inventory"))
    inventory_parser.add_argument("--format", choices=("text", "json"), default="text")
    inventory_parser.add_argument(
        "--no-exec",
        action="store_true",
        help="skip repository-declared discoverer plugins",
    )
    claims_parser = sub.add_parser("claims", help=_command_help("claims"))
    claims_parser.add_argument("--format", choices=("text", "json"), default="text")
    binding_parser = sub.add_parser("binding", help=_command_help("binding"))
    binding_sub = binding_parser.add_subparsers(
        dest="binding_command",
        required=True,
    )
    binding_sensitivity = binding_sub.add_parser(
        "sensitivity",
        help=_command_help("binding sensitivity"),
    )
    binding_sensitivity.add_argument(
        "--proposal",
        type=Path,
        required=True,
        help="proposal JSON path, or - for standard input",
    )
    binding_sensitivity.add_argument(
        "--fact",
        type=Path,
        required=True,
        help="independently frozen mutation-target JSON",
    )
    binding_sensitivity.add_argument(
        "--fact-sha256",
        required=True,
        help="expected SHA-256 of the complete mutation-target file",
    )
    binding_sensitivity.add_argument(
        "--format",
        choices=("text", "json"),
        default="json",
    )
    context_parser = sub.add_parser("context")
    context_sub = context_parser.add_subparsers(dest="context_command", required=True)
    context_compile = context_sub.add_parser(
        "compile", help=_command_help("context compile")
    )
    context_compile.add_argument("--request", type=Path, required=True)
    context_compile.add_argument("--format", choices=("text", "json"), default="json")
    review_parser = sub.add_parser("review", help=_command_help("review"))
    review_sub = review_parser.add_subparsers(dest="review_command", required=True)
    review_candidates = review_sub.add_parser(
        "candidates",
        help=_command_help("review candidates"),
    )
    review_candidates.add_argument("--input", type=Path, required=True)
    review_candidates.add_argument("--out", type=Path)
    review_candidates.add_argument(
        "--check",
        action="store_true",
        help="exit 1 instead of rewriting a stale --out candidate set",
    )
    review_candidates.add_argument(
        "--format",
        choices=("text", "json"),
        default="json",
    )
    review_lifecycle = review_sub.add_parser(
        "lifecycle",
        help=_command_help("review lifecycle"),
    )
    review_lifecycle_sub = review_lifecycle.add_subparsers(
        dest="review_lifecycle_command",
        required=True,
    )
    lifecycle_init = review_lifecycle_sub.add_parser(
        "init",
        help=_command_help("review lifecycle init"),
    )
    lifecycle_init.add_argument("--input", type=Path, required=True)
    lifecycle_init.add_argument("--out", type=Path, required=True)
    lifecycle_init.add_argument(
        "--force",
        action="store_true",
        help="replace an existing lifecycle record",
    )
    lifecycle_init.add_argument("--format", choices=("text", "json"), default="json")
    lifecycle_transition = review_lifecycle_sub.add_parser(
        "transition",
        help=_command_help("review lifecycle transition"),
    )
    lifecycle_transition.add_argument("--input", type=Path, required=True)
    lifecycle_transition.add_argument("--state", type=Path, required=True)
    lifecycle_transition.add_argument("--observation", required=True)
    lifecycle_transition.add_argument("--to", choices=tuple(sorted(LIFECYCLE_STATES)), required=True)
    lifecycle_transition.add_argument(
        "--evidence-kind",
        choices=tuple(sorted(LIFECYCLE_EVIDENCE_KINDS)),
        required=True,
    )
    lifecycle_transition.add_argument("--reference", required=True)
    lifecycle_transition.add_argument("--detail", required=True)
    lifecycle_transition.add_argument(
        "--format", choices=("text", "json"), default="json"
    )
    lifecycle_check = review_lifecycle_sub.add_parser(
        "check",
        help=_command_help("review lifecycle check"),
    )
    lifecycle_check.add_argument("--input", type=Path, required=True)
    lifecycle_check.add_argument("--state", type=Path, required=True)
    lifecycle_check.add_argument("--format", choices=("text", "json"), default="json")
    init_parser = sub.add_parser("init", help=_command_help("init"))
    model_mode = init_parser.add_mutually_exclusive_group()
    model_mode.add_argument(
        "--no-model", action="store_true", help="use deterministic adapters only"
    )
    model_mode.add_argument(
        "--recorded-model-response",
        type=Path,
        help="replay a grounded JSON provider response",
    )
    init_parser.add_argument(
        "--dry-run", action="store_true", help="print the content plan without writing"
    )
    init_parser.add_argument(
        "--accept-hygiene-baseline",
        action="store_true",
        help="record exact existing findings so mature repositories can adopt the gate",
    )
    init_parser.add_argument("--format", choices=("text", "json"), default="text")
    explain_parser = sub.add_parser("explain", help=_command_help("explain"))
    explain_parser.add_argument("identifier", help="policy rule or inventory id")
    explain_parser.add_argument("--format", choices=("text", "json"), default="text")
    doctor_parser = sub.add_parser("doctor", help=_command_help("doctor"))
    doctor_parser.add_argument("--format", choices=("text", "json"), default="text")
    doctor_parser.add_argument("--bundle", type=Path)
    verify = sub.add_parser("verify", help=_command_help("verify"))
    verify.add_argument("--base")
    verify.add_argument("--head")
    verify.add_argument("--project", type=Path, default=Path("."))
    verify.add_argument("--out", type=Path)
    verify.add_argument(
        "--no-exec",
        action="store_true",
        help="skip repository-declared commands and plugins",
    )
    benchmark = sub.add_parser("benchmark", help=_command_help("benchmark"))
    benchmark.add_argument("--base", required=True)
    benchmark.add_argument("--head", required=True)
    benchmark.add_argument("--project", type=Path, default=Path("."))
    benchmark.add_argument("--iterations", type=int, default=7)
    benchmark.add_argument("--out", type=Path)
    derive = sub.add_parser("derive", help=_command_help("derive"))
    derive_mode = derive.add_mutually_exclusive_group()
    derive_mode.add_argument(
        "--write", action="store_true", help="write derived regions atomically"
    )
    derive_mode.add_argument(
        "--check", action="store_true", help="exit 1 when a region would change"
    )
    derive.add_argument("--binding", help="evaluate one binding id")
    derive.add_argument("--ref", help="read bound sources from an immutable git ref")
    derive.add_argument("--format", choices=("text", "json"), default="text")
    drive_parser = sub.add_parser("drive", help=_command_help("drive"))
    drive_parser.add_argument("--binding", help="repair one binding id")
    drive_parser.add_argument("--ref", help="read bound sources from an immutable git ref")
    drive_parser.add_argument("--format", choices=("text", "json"), default="text")
    plan = sub.add_parser("plan", help=_command_help("plan"))
    plan.add_argument("--base", required=True, help="target branch or base git ref")
    plan.add_argument("--head", required=True, help="change head git ref")
    plan.add_argument(
        "--project", type=Path, default=Path("."), help="monorepo project path"
    )
    plan.add_argument("--no-cache", action="store_true", help="bypass immutable-ref cache")
    plan.add_argument("--format", choices=("text", "json"), default="text")
    plan.add_argument(
        "--no-exec",
        action="store_true",
        help="skip repository-declared commands and plugins",
    )
    verdict = sub.add_parser("verdict", help=_command_help("verdict"))
    verdict.add_argument("--base", required=True, help="target branch or base git ref")
    verdict.add_argument("--head", required=True, help="checked-out change head git ref")
    verdict.add_argument(
        "--mutation-receipt",
        type=Path,
        action="append",
        default=[],
        help="optional binding-sensitivity receipt to summarize",
    )
    verdict.add_argument("--format", choices=("json", "sarif"), default="json")
    check = sub.add_parser("check", help=_command_help("check"))
    check.add_argument("--binding", help="evaluate one binding id")
    check.add_argument("--ref", help="read bound sources from an immutable git ref")
    check.add_argument("--changed", action="store_true", help="check base-to-head impact")
    check.add_argument("--base", help="base git ref for --changed")
    check.add_argument("--head", help="head git ref for --changed")
    check.add_argument("--project", type=Path, default=Path("."), help="monorepo project path")
    check.add_argument("--no-cache", action="store_true", help="bypass immutable-ref cache")
    check.add_argument("--format", choices=("text", "json", "sarif"), default="text")
    check.add_argument(
        "--no-exec",
        action="store_true",
        help="skip repository-declared commands and plugins",
    )
    project = sub.add_parser("project", help=_command_help("project"))
    project.add_argument(
        "--check", action="store_true", help="exit 1 instead of writing stale projections"
    )
    project.add_argument("--format", choices=("text", "json"), default="text")
    evaluate_tasks = sub.add_parser("eval", help=_command_help("eval"))
    evaluate_tasks.add_argument(
        "--fixtures", type=Path, default=Path(".clean-docs/eval.yml")
    )
    evaluate_tasks.add_argument("--mode", choices=("replay", "live"), default="replay")
    evaluate_tasks.add_argument("--record-dir", type=Path)
    evaluate_tasks.add_argument("--history", type=Path)
    evaluate_tasks.add_argument("--format", choices=("text", "json"), default="text")
    release = sub.add_parser("release", help=_command_help("release"))
    release.add_argument("--from", dest="from_ref", required=True, help="base git ref")
    release.add_argument("--to", dest="to_ref", required=True, help="target git ref")
    release.add_argument("--recorded-model-response", type=Path)
    release.add_argument("--format", choices=("markdown", "json"), default="markdown")
    migrate = sub.add_parser("migrate", help=_command_help("migrate"))
    migration_mode = migrate.add_mutually_exclusive_group()
    migration_mode.add_argument("--write", action="store_true")
    migration_mode.add_argument("--rollback", action="store_true")
    migrate.add_argument("--format", choices=("text", "json"), default="text")
    feedback = sub.add_parser("feedback", help=_command_help("feedback"))
    feedback_sub = feedback.add_subparsers(dest="feedback_command", required=True)
    feedback_enable = feedback_sub.add_parser(
        "enable",
        help="enable feedback with a visible sink configuration",
    )
    feedback_enable.add_argument("--sink", choices=("local", "connected"), required=True)
    feedback_enable.add_argument("--target")
    feedback_enable.add_argument("--endpoint")
    feedback_enable.add_argument("--token-env")
    feedback_sub.add_parser("status", help="show feedback configuration and queue counts")
    feedback_sub.add_parser("preview", help="write exact pending envelope bytes")
    feedback_sub.add_parser("flush", help="deliver pending envelopes explicitly")
    feedback_sub.add_parser("disable", help="remove delivery authority immediately")
    feedback_sub.add_parser("rotate", help="replace the pseudonymous installation identifier")
    feedback_sub.add_parser("purge", help="delete queued, delivered, and signal state")
    feedback_signal = feedback_sub.add_parser(
        "signal",
        help="validate or ingest aggregate behavior signals",
    )
    feedback_signal_sub = feedback_signal.add_subparsers(
        dest="feedback_signal_command",
        required=True,
    )
    for signal_command in ("prepare", "validate", "ingest"):
        signal_parser = feedback_signal_sub.add_parser(signal_command)
        signal_parser.add_argument("--input", type=Path, required=True)
    feedback_case = feedback_sub.add_parser(
        "case",
        help="advance a verified improvement case",
    )
    feedback_case_sub = feedback_case.add_subparsers(
        dest="feedback_case_command",
        required=True,
    )
    feedback_transition = feedback_case_sub.add_parser("transition")
    feedback_transition.add_argument("--case", required=True)
    feedback_transition.add_argument(
        "--to",
        required=True,
        choices=(
            "reproduced",
            "root-cause-classified",
            "evaluation-proposed",
            "regression-added",
            "shadow-measured",
            "candidate-change",
            "ordinary-verified-pr",
        ),
    )
    feedback_transition.add_argument("--receipt", type=Path, required=True)
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


def _validate_arguments(args: argparse.Namespace) -> None:
    if (
        args.command == "review"
        and args.review_command == "candidates"
        and args.check
        and args.out is None
    ):
        raise ConfigurationError("review candidates --check requires --out")
    if args.command != "check":
        return
    changed_only = (
        args.base is not None
        or args.head is not None
        or args.project != Path(".")
        or args.no_cache
    )
    if changed_only and not args.changed:
        raise ConfigurationError(
            "--base, --head, --project, and --no-cache require check --changed"
        )
    if args.changed and (args.base is None or args.head is None):
        raise ConfigurationError("check --changed requires both --base and --head")


def _json(results: list[BindingResult], *, repaired: bool = False) -> str:
    assurance = {
        "region": {
            "source_evidence_checked": True,
            "document_bytes_checked": True,
        },
        "command-pin": {
            "command_output_checked": True,
            "anchor_exists": True,
            "anchored_prose_checked": False,
        },
        "symbol": {
            "source_locator_exists": True,
            "anchored_prose_checked": False,
        },
        "source-claim": {
            "document_value_checked": True,
            "source_value_checked": True,
        },
        "plugin": {
            "plugin_executed": False,
            "result_checked": False,
        },
        "projection": {
            "configured_output_checked": True,
            "source_document_prose_certified": False,
        },
    }
    return json.dumps({
        "ok": not any(
            result.changed
            and result.state != "skipped-untrusted-execution"
            and not (repaired and result.binding_type == "region")
            for result in results
        ),
        "complete": not any(
            result.state == "skipped-untrusted-execution" for result in results
        ),
        "results": [
            {
                "binding": result.binding_id,
                "mechanism": result.binding_type,
                "doc": result.doc,
                "status": result.state or (
                    "repaired" if repaired and result.changed
                and result.binding_type == "region" else (
                    "drift" if result.changed else "current"
                )),
                "diff": result.diff,
                "provenance": {
                    "ref": result.provenance.ref,
                    "path": result.provenance.path,
                    "locator": result.provenance.locator,
                    "extractor": result.provenance.extractor,
                    "digest": result.provenance.digest,
                },
                "assurance": assurance[result.binding_type],
            }
            for result in results
        ],
    }, indent=2) + "\n"


def _text(results: list[BindingResult], *, repaired: bool = False) -> str:
    lines: list[str] = []
    for result in results:
        was_repaired = repaired and result.changed and result.binding_type == "region"
        status = result.state or ("repaired" if was_repaired else (
            "drift" if result.changed else "current"
        ))
        lines.append(f"[{status}] {result.binding_id}: {result.doc}")
        if result.diff:
            lines.append(result.diff.rstrip())
    return "\n".join(lines) + "\n"


def _main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        _validate_arguments(args)
    except CleanDocsError as exc:
        print(f"clean-docs: {exc}", file=sys.stderr)
        return exc.exit_code
    root = args.root.resolve()
    if args.command == "residue":
        local = root / LOCAL_CONFIG_NAME
        try:
            if args.residue_command == "init-local":
                if local.exists():
                    raise ConfigurationError("local residue config already exists")
                atomic_write(local, "version: 1\nrules: []\n")
                local.chmod(0o600)
                print(f"residue: initialized {LOCAL_CONFIG_NAME}")
                return 0
            active = bool(load_local_residue_rules(local))
        except CleanDocsError as exc:
            print(f"clean-docs: {exc}", file=sys.stderr)
            return exc.exit_code
        print(f"residue: private matching {'active' if active else 'inactive'}")
        return 0
    if args.command == "review":
        try:
            source = args.input if args.input.is_absolute() else root / args.input
            candidates = load_review_candidates(source)
            if args.review_command == "candidates":
                rendered = json.dumps(
                    candidates.as_dict(),
                    indent=2,
                    ensure_ascii=False,
                ) + "\n"
                if args.out is None:
                    print(rendered, end="")
                    return 0
                output = args.out if args.out.is_absolute() else root / args.out
                try:
                    relative_output = output.resolve().relative_to(root)
                except ValueError as exc:
                    raise ConfigurationError(
                        "review candidates --out must stay inside the repository"
                    ) from exc
                if args.check:
                    try:
                        observed = output.read_text(encoding="utf-8")
                    except FileNotFoundError:
                        observed = ""
                    except OSError as exc:
                        raise ConfigurationError(
                            f"cannot read improvement candidates {output}: {exc}"
                        ) from exc
                    current = observed == rendered
                    if args.format == "json":
                        print(json.dumps({
                            "schema": "clean-docs.improvement-candidate-check.v1",
                            "ok": current,
                            "output": relative_output.as_posix(),
                            "candidate_digest": candidates.digest,
                        }, indent=2))
                    else:
                        print(
                            f"[{'current' if current else 'drift'}] "
                            f"{relative_output.as_posix()}"
                        )
                    return 0 if current else 1
                write_improvement_candidates(candidates, output)
                if args.format == "json":
                    print(rendered, end="")
                else:
                    print(
                        f"[written] {relative_output.as_posix()}: "
                        f"{len(candidates.candidates)} candidate(s)"
                    )
                return 0

            state_argument = args.out if args.review_lifecycle_command == "init" else args.state
            state_path = (
                state_argument if state_argument.is_absolute() else root / state_argument
            )
            try:
                relative_state = state_path.resolve().relative_to(root)
            except ValueError as exc:
                raise ConfigurationError(
                    "review lifecycle state must stay inside the repository"
                ) from exc
            if args.review_lifecycle_command == "init":
                if state_path.exists() and not args.force:
                    raise ConfigurationError(
                        "review lifecycle init refuses to replace an existing state; use --force"
                    )
                lifecycle = initialize_candidate_lifecycle(candidates)
                write_candidate_lifecycle(lifecycle, state_path)
                if args.format == "json":
                    print(json.dumps(lifecycle.as_dict(), indent=2))
                else:
                    print(
                        f"[written] {relative_state.as_posix()}: "
                        f"{len(lifecycle.candidates)} candidate(s)"
                    )
                return 0
            if args.review_lifecycle_command == "check":
                lifecycle = load_candidate_lifecycle(state_path, candidates)
                if args.format == "json":
                    print(json.dumps({
                        "schema": "clean-docs.improvement-candidate-lifecycle-check.v1",
                        "ok": True,
                        "state": relative_state.as_posix(),
                        "candidate_digest": lifecycle.candidate_digest,
                        "lifecycle_digest": lifecycle.digest,
                    }, indent=2))
                else:
                    print(f"[current] {relative_state.as_posix()}")
                return 0
            lifecycle = load_candidate_lifecycle(state_path, candidates)
            lifecycle = transition_candidate_lifecycle(
                lifecycle,
                observation_id=args.observation,
                to_state=args.to,
                evidence=LifecycleEvidence(
                    kind=args.evidence_kind,
                    reference=args.reference,
                    detail=args.detail,
                ),
            )
            write_candidate_lifecycle(lifecycle, state_path)
            if args.format == "json":
                print(json.dumps(lifecycle.as_dict(), indent=2))
            else:
                print(
                    f"[transitioned] {args.observation}: {args.to} "
                    f"in {relative_state.as_posix()}"
                )
            return 0
        except CleanDocsError as exc:
            print(f"clean-docs: {exc}", file=sys.stderr)
            return exc.exit_code
    if args.command == "feedback":
        try:
            if args.feedback_command == "enable":
                config = enable_feedback(
                    root,
                    sink=args.sink,
                    target=args.target,
                    endpoint=args.endpoint,
                    token_env=args.token_env,
                )
                print(json.dumps(config.as_dict(), indent=2))
                return 0
            if args.feedback_command == "status":
                status_config = load_feedback_config(root)
                pending = preview_feedback(root)
                print(json.dumps({
                    "schema": "clean-docs.feedback-status.v1",
                    "configured": status_config is not None,
                    "enabled": (
                        status_config.enabled if status_config is not None else False
                    ),
                    "sink": (
                        dict(status_config.sink)
                        if status_config is not None
                        else None
                    ),
                    "pending_bytes": len(pending),
                    "pending_records": pending.count(b"\n"),
                }, indent=2))
                return 0
            if args.feedback_command == "preview":
                sys.stdout.buffer.write(preview_feedback(root))
                return 0
            if args.feedback_command == "flush":
                flush_result = flush_feedback(root)
                print(json.dumps({
                    "schema": "clean-docs.feedback-flush.v1",
                    **flush_result,
                }, indent=2))
                return 0 if flush_result["failed"] == 0 else 1
            if args.feedback_command == "disable":
                config = disable_feedback(root)
                print(json.dumps(config.as_dict(), indent=2))
                return 0
            if args.feedback_command == "rotate":
                config = rotate_feedback_identity(root)
                print(json.dumps(config.as_dict(), indent=2))
                return 0
            if args.feedback_command == "signal":
                signal_path = (
                    args.input if args.input.is_absolute() else root / args.input
                )
                if args.feedback_signal_command == "prepare":
                    try:
                        signal_body_raw = json.loads(
                            signal_path.read_text(encoding="utf-8")
                        )
                    except (OSError, json.JSONDecodeError) as exc:
                        raise ConfigurationError(
                            f"cannot read behavior signal body {signal_path}"
                        ) from exc
                    if not isinstance(signal_body_raw, dict):
                        raise ConfigurationError(
                            "behavior signal body must be an object"
                        )
                    signal = prepare_behavior_signal(signal_body_raw)
                    print(json.dumps(signal, indent=2))
                elif args.feedback_signal_command == "validate":
                    signal, _source = load_behavior_signal(signal_path)
                    print(json.dumps(signal, indent=2))
                else:
                    case = ingest_behavior_signal(root, signal_path)
                    print(json.dumps(case, indent=2))
                return 0
            if args.feedback_command == "case":
                receipt_path = (
                    args.receipt
                    if args.receipt.is_absolute()
                    else root / args.receipt
                )
                case = transition_improvement_case(
                    root,
                    case_id=args.case,
                    target_state=args.to,
                    receipt_path=receipt_path,
                )
                print(json.dumps(case, indent=2))
                return 0
            purge_feedback(root)
            print("feedback: local state purged")
            return 0
        except CleanDocsError as exc:
            print(f"clean-docs: {exc}", file=sys.stderr)
            return exc.exit_code
    if args.command == "audit":
        try:
            if args.update_baseline:
                write_audit_baseline(root)
            report = audit(root, preview_policy=args.preview_policy)
        except CleanDocsError as exc:
            print(f"clean-docs: {exc}", file=sys.stderr)
            return exc.exit_code
        if args.format == "json":
            print(json.dumps({
                "schema": "clean-docs.audit.v1",
                "ok": report.ok,
                "documents": list(report.documents),
                "ignored_documents": list(report.ignored_documents),
                "unsupported_documents": list(report.unsupported_documents),
                "document_profiles": {
                    profile.path: profile.role
                    for profile in report.document_profiles
                },
                "registered_documents": [
                    profile.path
                    for profile in report.document_profiles
                    if profile.registered
                ],
                "enforcement": {
                    "repository_integrity": report.repository_integrity_enforced,
                    "policy_documents": [
                        profile.path
                        for profile in report.document_profiles
                        if profile.registered
                    ],
                },
                "policy_preview": report.policy_preview,
                "role_definitions": ROLE_DESCRIPTIONS,
                "findings": [asdict(finding) for finding in report.findings],
                "advisories": [asdict(finding) for finding in report.advisories],
                "advisory_totals": dict(report.advisory_totals),
                "baselined_findings": [
                    asdict(finding) for finding in report.baselined_findings
                ],
                "stale_baseline": [
                    asdict(finding) for finding in report.stale_baseline
                ],
            }, indent=2))
        else:
            document_roles = {
                profile.path: profile.role
                for profile in report.document_profiles
            }
            for audit_finding in report.findings:
                print(
                    f"[{audit_finding.rule}] {audit_finding.path}:{audit_finding.line} "
                    f"{audit_finding.detail}"
                )
            for advisory in report.advisories:
                print(
                    f"[advisory:{advisory.rule} "
                    f"role={document_roles.get(advisory.path, 'unknown')}] "
                    f"{advisory.path}:{advisory.line} "
                    f"{advisory.detail}"
                )
            for stale_finding in report.stale_baseline:
                print(
                    f"[stale-baseline] {stale_finding.path}:{stale_finding.line} "
                    f"{stale_finding.rule}: finding was resolved; update the baseline"
                )
            if args.update_baseline:
                print(f"[updated] {AUDIT_BASELINE_PATH}")
            print(
                f"audit: {len(report.documents)} active document(s), "
                f"{len(report.ignored_documents)} archived, "
                f"{len(report.findings)} finding(s); "
                f"{sum(count for _rule, count in report.advisory_totals)} "
                f"advisory candidate(s), {len(report.advisories)} shown; "
                f"{len(report.baselined_findings)} baselined; "
                f"{len(report.stale_baseline)} stale; "
                f"{len(report.unsupported_documents)} unsupported; "
                "integrity "
                f"{'enforced' if report.repository_integrity_enforced else 'assessment-only'}"
            )
        return 0 if report.ok else 1
    if args.command == "inventory":
        try:
            manifest_path = root / args.manifest
            manifest = load_manifest(manifest_path) if manifest_path.is_file() else None
            discoverer_ids = (
                sorted(
                    plugin.id
                    for plugin in manifest.plugins
                    if "discoverer" in plugin.interfaces
                )
                if manifest is not None
                else []
            )
            inventory_report = (
                scan_inventory(root)
                if args.no_exec
                else scan_extended_inventory(root)
            )
        except CleanDocsError as exc:
            print(f"clean-docs: {exc}", file=sys.stderr)
            return exc.exit_code
        if args.format == "json":
            payload = inventory_report.as_dict()
            payload["execution"] = {
                "mode": (
                    ExecutionPolicy.STATIC_ONLY.value
                    if args.no_exec
                    else ExecutionPolicy.TRUSTED.value
                ),
                "skipped_plugin_ids": discoverer_ids if args.no_exec else [],
            }
            print(json.dumps(payload, indent=2))
        else:
            for item in inventory_report.items:
                print(f"[{item.coverage}] {item.kind} {item.name}: {item.source}#{item.locator}")
            print(
                f"inventory: {len(inventory_report.items)} surface(s); "
                f"{len(inventory_report.languages)} language(s)"
            )
        return 0
    if args.command == "claims":
        manifest = args.manifest if args.manifest.is_absolute() else root / args.manifest
        try:
            source_claim_checks = (
                load_manifest(manifest).source_claim_checks
                if manifest.is_file()
                else ()
            )
            claim_report = scan_source_claims(root, source_claim_checks)
        except CleanDocsError as exc:
            print(f"clean-docs: {exc}", file=sys.stderr)
            return exc.exit_code
        if args.format == "json":
            print(json.dumps(claim_report.as_dict(), indent=2))
        else:
            for missing in claim_report.missing:
                print(
                    f"[required:missing] {missing.id} {missing.doc}#{missing.anchor}: "
                    f"{missing.detail}"
                )
            for claim_result in claim_report.results:
                print(
                    f"[{'required' if claim_result.status == 'drift' else 'current'}:"
                    f"{claim_result.kind}] {claim_result.id} "
                    f"{claim_result.doc}:{claim_result.line} "
                    f"<- {claim_result.source}#{claim_result.locator}: "
                    f"{claim_result.detail}"
                )
            for claim_candidate in claim_report.candidates:
                print(
                    f"[advisory:{claim_candidate.status}:{claim_candidate.kind}] "
                    f"{claim_candidate.id} "
                    f"{claim_candidate.doc}:{claim_candidate.line} "
                    f"<- {claim_candidate.source}#{claim_candidate.locator}: "
                    f"{claim_candidate.detail}"
                )
            print(
                f"claims: {len(claim_report.results)} enforced relationship(s), "
                f"{sum(count for _status, count in claim_report.candidate_totals)} "
                f"ranked candidate(s); {claim_report.authority}"
            )
        return 0 if claim_report.ok else 1
    if args.command == "binding":
        fact_path = args.fact if args.fact.is_absolute() else root / args.fact
        try:
            if args.proposal == Path("-"):
                proposal_bytes = sys.stdin.read().encode()
                proposal = decode_json_object(proposal_bytes, "proposal")
            else:
                proposal_path = (
                    args.proposal
                    if args.proposal.is_absolute()
                    else root / args.proposal
                )
                proposal, proposal_bytes = load_json_object(
                    proposal_path,
                    "proposal",
                )
            fact, fact_bytes = load_json_object(fact_path, "fact")
            receipt = evaluate_binding_sensitivity(
                root,
                proposal,
                fact,
                proposal_bytes=proposal_bytes,
                fact_bytes=fact_bytes,
                expected_fact_file_sha256=args.fact_sha256,
            )
        except CleanDocsError as exc:
            print(f"clean-docs: {exc}", file=sys.stderr)
            return exc.exit_code
        if args.format == "json":
            print(json.dumps(receipt, indent=2))
        else:
            inputs = receipt["inputs"]
            assert isinstance(inputs, dict)
            relationship = inputs["relationship"]
            assert isinstance(relationship, dict)
            print(
                f"[{receipt['state']}] {relationship['id']}: "
                f"{receipt['detail']}"
            )
            print(
                "semantic relationship authorized: "
                f"{str(receipt['semantic_relationship_authorized']).lower()}"
            )
        return {
            "sensitive": 0,
            "insensitive": 1,
            "invalid": 2,
            "unsupported": 3,
        }[str(receipt["state"])]
    if args.command == "context":
        request = args.request if args.request.is_absolute() else root / args.request
        try:
            context_bundle = compile_context(root, request)
        except CleanDocsError as exc:
            print(f"clean-docs: {exc}", file=sys.stderr)
            return exc.exit_code
        if args.format == "json":
            print(json.dumps(context_bundle.as_dict(), indent=2))
        else:
            for context_item in context_bundle.items:
                print(
                    f"[included:{context_item.authority}] {context_item.id} "
                    f"{context_item.path}#{context_item.locator}: "
                    f"{context_item.inclusion_reason}"
                )
            for excluded_context in context_bundle.excluded:
                print(
                    f"[excluded:{excluded_context.reason}] "
                    f"{excluded_context.id}: {excluded_context.path}"
                )
            print(
                f"context: {context_bundle.status}; "
                f"{context_bundle.used_bytes}/"
                f"{context_bundle.budget_bytes} bytes"
            )
        return 0 if context_bundle.ok else 2
    if args.command == "release":
        try:
            release_report = build_release_report(root, args.from_ref, args.to_ref)
            narrative = None
            if args.recorded_model_response is not None:
                response_path = args.recorded_model_response
                if not response_path.is_absolute():
                    response_path = root / response_path
                try:
                    response = response_path.read_text(encoding="utf-8")
                except OSError as exc:
                    raise ConfigurationError(
                        f"cannot read recorded release narrative {response_path}"
                    ) from exc
                narrative = validate_release_narrative(release_report, response)
        except CleanDocsError as exc:
            print(f"clean-docs: {exc}", file=sys.stderr)
            return exc.exit_code
        if args.format == "json":
            payload = release_report.as_dict()
            if narrative is not None:
                payload["narrative"] = narrative.as_dict()
            print(json.dumps(payload, indent=2))
        else:
            sys.stdout.write(render_release_markdown(release_report, narrative))
        return 0 if narrative is None or narrative.ok else 1
    if args.command == "migrate":
        manifest = args.manifest if args.manifest.is_absolute() else root / args.manifest
        try:
            if args.rollback:
                rollback_migration(manifest)
                print(f"migrate: restored {manifest}")
                return 0
            migration = build_migration_plan(manifest)
            if args.write:
                backup = apply_migration(manifest, migration)
            else:
                backup = None
        except CleanDocsError as exc:
            print(f"clean-docs: {exc}", file=sys.stderr)
            return exc.exit_code
        if args.format == "json":
            payload = migration.as_dict()
            payload["applied"] = args.write
            print(json.dumps(payload, indent=2))
        else:
            sys.stdout.write(migration.diff)
            state = "applied" if args.write else "planned"
            suffix = f"; backup {backup}" if backup is not None else ""
            print(f"migrate: {state} version 0 to 1{suffix}")
        return 0
    if args.command == "explain":
        try:
            explanation = explain(root, args.identifier)
        except CleanDocsError as exc:
            print(f"clean-docs: {exc}", file=sys.stderr)
            return exc.exit_code
        if args.format == "json":
            print(json.dumps(explanation.as_dict(), indent=2))
        else:
            print(f"[{explanation.state}] {explanation.id}: {explanation.summary}")
            if explanation.evidence:
                print(
                    "evidence: "
                    f"{explanation.evidence['source']}#{explanation.evidence['locator']} "
                    f"via {explanation.evidence['adapter']} "
                    f"sha256:{explanation.evidence['sha256']}"
                )
            print(f"repair: {explanation.repair}")
        return 0
    if args.command == "init":
        try:
            provider = None
            if args.recorded_model_response:
                response_path = args.recorded_model_response
                if not response_path.is_absolute():
                    response_path = root / response_path
                try:
                    provider = RecordedProvider(response_path.read_text(encoding="utf-8"))
                except OSError as exc:
                    raise ConfigurationError(
                        f"cannot read recorded model response {response_path}"
                    ) from exc
            plan = build_bootstrap_plan(
                root,
                provider,
                accept_hygiene_baseline=args.accept_hygiene_baseline,
            )
            if not args.dry_run:
                apply_bootstrap_plan(root, plan)
        except CleanDocsError as exc:
            print(f"clean-docs: {exc}", file=sys.stderr)
            return exc.exit_code
        if args.format == "json":
            print(json.dumps(plan.as_dict(), indent=2))
        else:
            state = "planned" if args.dry_run else "applied"
            for write in plan.writes:
                print(f"[{state}] write {write.path}: {write.reason}")
            for move in plan.moves:
                print(f"[{state}] move {move.source} -> {move.path}: {move.reason}")
            if plan.accept_hygiene_baseline:
                print(
                    f"[{state}] write {AUDIT_BASELINE_PATH}: "
                    "record exact existing documentation debt after bootstrap"
                )
            for gap in plan.gaps:
                print(f"[gap] {gap}")
            print(
                f"init: {state} "
                f"{len(plan.writes) + len(plan.moves) + int(plan.accept_hygiene_baseline)} "
                "operation(s); "
                f"{len(plan.facts)} grounded fact(s)"
            )
        return 2 if plan.gaps else 0
    if args.command == "doctor":
        manifest = args.manifest if args.manifest.is_absolute() else root / args.manifest
        bundle = build_diagnostic_bundle(root, manifest)
        checks = bundle.checks
        if args.bundle is not None:
            bundle_path = args.bundle if args.bundle.is_absolute() else root / args.bundle
            atomic_write(bundle_path, json.dumps(bundle.as_dict(), indent=2) + "\n")
        if args.format == "json":
            print(json.dumps(bundle.as_dict(), indent=2))
        else:
            for check in checks:
                print(f"[{'ok' if check.ok else 'fail'}] {check.name}: {check.detail}")
        return 0 if all(check.ok for check in checks) else 1
    if args.command in {"verify", "benchmark"}:
        manifest = args.manifest if args.manifest.is_absolute() else root / args.manifest
        try:
            if args.command == "verify":
                outcome_report = build_outcome_receipt(
                    root,
                    manifest,
                    base=args.base,
                    head=args.head,
                    project=args.project,
                    execution_policy=(
                        ExecutionPolicy.STATIC_ONLY
                        if args.no_exec
                        else ExecutionPolicy.TRUSTED
                    ),
                )
                payload = outcome_report.as_dict()
                ok = outcome_report.ok
            else:
                performance_report = benchmark_changed_check(
                    root,
                    manifest,
                    base=args.base,
                    head=args.head,
                    project=args.project,
                    iterations=args.iterations,
                )
                payload = performance_report.as_dict()
                ok = performance_report.ok
        except CleanDocsError as exc:
            print(f"clean-docs: {exc}", file=sys.stderr)
            return exc.exit_code
        rendered = json.dumps(payload, indent=2) + "\n"
        if args.out is not None:
            output = args.out if args.out.is_absolute() else root / args.out
            atomic_write(output, rendered)
        sys.stdout.write(rendered)
        return 0 if ok else 1
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
        if args.command == "eval":
            fixtures = args.fixtures if args.fixtures.is_absolute() else root / args.fixtures
            record_dir = args.record_dir
            if record_dir is not None and not record_dir.is_absolute():
                record_dir = root / record_dir
            evaluation_report = run_evaluation(
                root,
                manifest,
                fixtures,
                mode=args.mode,
                record_dir=record_dir,
            )
            if args.history:
                history = args.history if args.history.is_absolute() else root / args.history
                write_evaluation_history(history, evaluation_report)
            if args.format == "json":
                print(json.dumps(evaluation_report.as_dict(), indent=2))
            else:
                for audience, task_results in (
                    ("human", evaluation_report.human_tasks),
                    ("agent", evaluation_report.agent_tasks),
                ):
                    passed = sum(result.ok for result in task_results)
                    print(f"{audience}: {passed}/{len(task_results)} task(s) passed")
                    for result in task_results:
                        state = "pass" if result.ok else "fail"
                        print(f"[{state}] {result.id} ({result.scorer}): {result.detail}")
                print(
                    f"hygiene: {len(evaluation_report.hygiene_findings)} finding(s)"
                )
            return 0 if evaluation_report.ok else 1
        if args.command == "project":
            loaded = load_manifest(manifest)
            projection_results = evaluate_projections(root, loaded)
            if args.check:
                output = (
                    _json(projection_results)
                    if args.format == "json"
                    else _text(projection_results)
                )
                sys.stdout.write(output)
                return 1 if any(result.changed for result in projection_results) else 0
            written = write_projections(root, loaded)
            if args.format == "json":
                print(json.dumps({
                    "ok": True,
                    "written": [path.as_posix() for path in written],
                }, indent=2))
            else:
                for path in written:
                    print(f"[projected] {path}")
                print(f"project: wrote {len(written)} file(s)")
            return 0
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
        if args.command == "plan":
            plan_manifest = manifest
            if args.project != Path(".") and args.manifest == Path(".clean-docs.yml"):
                plan_manifest = root / args.project / args.manifest
            impact_plan = build_impact_plan(
                root,
                plan_manifest,
                base=args.base,
                head=args.head,
                use_cache=not args.no_cache,
                project=args.project,
                execution_policy=(
                    ExecutionPolicy.STATIC_ONLY
                    if args.no_exec
                    else ExecutionPolicy.TRUSTED
                ),
            )
            if args.format == "json":
                print(json.dumps(impact_plan.as_dict(), indent=2))
            else:
                sys.stdout.write(render_impact_plan(impact_plan))
            return 0
        if args.command == "verdict":
            mutation_receipts = tuple(
                path if path.is_absolute() else root / path
                for path in args.mutation_receipt
            )
            try:
                pr_verdict = build_pr_verdict(
                    root,
                    manifest,
                    base=args.base,
                    head=args.head,
                    mutation_receipt_paths=mutation_receipts,
                )
            except CleanDocsError as exc:
                if args.format == "json":
                    print(
                        json.dumps(
                            {
                                "schema": VERDICT_SCHEMA,
                                "state": "invalid",
                                "ready": False,
                                "error": {
                                    "class": (
                                        "configuration"
                                        if isinstance(exc, ConfigurationError)
                                        else "extraction"
                                    ),
                                    "detail": str(exc),
                                },
                            },
                            indent=2,
                        )
                    )
                else:
                    print(f"clean-docs: {exc}", file=sys.stderr)
                return exc.exit_code
            if args.format == "sarif":
                sys.stdout.write(render_verdict_sarif(pr_verdict))
            else:
                print(json.dumps(pr_verdict.as_dict(), indent=2))
            return 0 if pr_verdict.ok else 1
        if args.command == "check" and args.changed:
            if args.binding or args.ref:
                raise ConfigurationError(
                    "check --changed cannot be combined with --binding or --ref"
                )
            changed_manifest = manifest
            if args.project != Path(".") and args.manifest == Path(".clean-docs.yml"):
                changed_manifest = root / args.project / args.manifest
            changed_report = check_changed(
                root,
                changed_manifest,
                base=args.base,
                head=args.head,
                use_cache=not args.no_cache,
                project=args.project,
                execution_policy=(
                    ExecutionPolicy.STATIC_ONLY
                    if args.no_exec
                    else ExecutionPolicy.TRUSTED
                ),
            )
            if args.format == "json":
                print(json.dumps(changed_report.as_dict(), indent=2))
            elif args.format == "sarif":
                sys.stdout.write(render_sarif(changed_report))
            else:
                print(f"changed: {changed_report.base}..{changed_report.head}")
                for section, section_findings in (
                    ("required", changed_report.required),
                    ("gap", changed_report.gaps),
                    ("ignored", changed_report.ignored),
                ):
                    for finding in section_findings:
                        print(f"[{section}] {finding.id} {finding.message}")
                        print(f"repair: {finding.repair}")
            return 0 if changed_report.ok else 1
        results = evaluate(
            root,
            manifest,
            ref=args.ref,
            binding_id=args.binding,
            execution_policy=(
                ExecutionPolicy.STATIC_ONLY
                if args.command == "check" and args.no_exec
                else ExecutionPolicy.TRUSTED
            ),
        )
        if (
            args.command == "check"
            and args.binding is None
            and args.ref is None
        ):
            loaded = load_manifest(manifest)
            if loaded.projections is not None:
                results.extend(evaluate_projections(root, loaded))
            if loaded.source_claim_checks:
                results.extend(
                    claim_binding_results(
                        scan_source_claims(
                            root,
                            loaded.source_claim_checks,
                            discover=False,
                        ),
                        # Required checks read only accepted document/source pairs.
                        # Candidate discovery remains an explicit `claims` operation.
                        ref=RepositorySnapshot(root).label,
                    )
                )
        output = _json(results) if args.format == "json" else _text(results)
        sys.stdout.write(output)
        drift = any(
            result.changed and result.state != "skipped-untrusted-execution"
            for result in results
        )
        if args.command == "derive" and args.write and drift:
            write_results(root, results)
            sys.stdout.write(f"wrote {sum(result.changed for result in results)} document(s)\n")
        if args.command == "check" or getattr(args, "check", False):
            return 1 if drift else 0
        return 0
    except CleanDocsError as exc:
        print(f"clean-docs: {exc}", file=sys.stderr)
        return exc.exit_code


def main(argv: list[str] | None = None) -> int:
    effective_argv = argv if argv is not None else sys.argv[1:]
    exit_code = _main(effective_argv)
    try:
        args = _parser().parse_args(effective_argv)
        if args.command != "feedback":
            enqueue_feedback(
                args.root.resolve(),
                command=args.command,
                exit_code=exit_code,
                execution_policy=(
                    ExecutionPolicy.STATIC_ONLY.value
                    if getattr(args, "no_exec", False)
                    else ExecutionPolicy.TRUSTED.value
                ),
            )
    except (CleanDocsError, OSError, ValueError):
        # Feedback is an opt-in observation plane. It cannot alter gate behavior.
        pass
    return exit_code
