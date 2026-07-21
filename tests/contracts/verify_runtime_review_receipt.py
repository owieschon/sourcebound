from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_manifest_sha256(path: Path) -> str:
    payload = json.loads(path.read_text())
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--tree", required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--runtime-receipt", type=Path, required=True)
    args = parser.parse_args()
    review = json.loads(args.receipt.read_text())
    required = {"schema", "status", "reviewer_identity", "reviewer_session_id", "commit", "tree", "manifest_sha256", "runtime_receipt_sha256", "input_allowlist", "attestation"}
    if not required <= set(review):
        raise SystemExit("runtime review receipt is incomplete")
    if review["schema"] != "sourcebound.runtime-review.v1" or review["status"] != "pass":
        raise SystemExit("runtime review did not pass")
    if not review["reviewer_identity"] or not review["reviewer_session_id"]:
        raise SystemExit("runtime reviewer lacks provenance")
    if review["commit"] != args.commit or review["tree"] != args.tree:
        raise SystemExit("runtime review is not commit-bound")
    if review["manifest_sha256"] != canonical_manifest_sha256(args.manifest):
        raise SystemExit("runtime review has wrong manifest identity")
    if review["runtime_receipt_sha256"] != sha256(args.runtime_receipt):
        raise SystemExit("runtime review has wrong receipt identity")
    expected_inputs = {str(args.manifest), str(args.runtime_receipt), args.commit, args.tree}
    if set(review["input_allowlist"]) != expected_inputs:
        raise SystemExit("runtime review input boundary differs")
    attestation = review["attestation"]
    if attestation != {"read_only": True, "published_docs_only": True, "implementation_context": False}:
        raise SystemExit("runtime review lacks read-only attestation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
