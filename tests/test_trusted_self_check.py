from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from scripts.trusted_self_check import verify


ROOT = Path(__file__).parents[1]


def test_trusted_and_candidate_verifiers_accept_current_tree() -> None:
    report = verify(ROOT)
    assert report["ok"] is True
    assert {(item["authority"], item["check"]) for item in report["results"]} == {
        ("trusted", "standard"),
        ("trusted", "bindings"),
        ("candidate", "standard"),
        ("candidate", "bindings"),
    }


def test_candidate_checker_bypass_cannot_override_trusted_failure(tmp_path: Path) -> None:
    clone = tmp_path / "candidate"
    subprocess.run(
        ["git", "clone", "-q", "--no-hardlinks", str(ROOT), str(clone)], check=True
    )
    shutil.copyfile(ROOT / ".sourcebound-trust.json", clone / ".sourcebound-trust.json")
    capabilities = clone / "src/clean_docs/capabilities.py"
    source = capabilities.read_text()
    marker = "SUPPORTED_BINDINGS = {"
    assert source.count(marker) == 1
    capabilities.write_text(source.replace(marker, """\
SUPPORTED_BINDINGS = {
    "tampered": {
        "binding": "tampered",
        "source": "Changed source surface",
        "output": "Changed output",
        "check": "Changed check",
    },""", 1))
    (clone / "src/clean_docs/cli.py").write_text(
        "def main(argv=None):\n    return 0\n"
    )

    report = verify(clone)

    assert report["ok"] is False
    by_authority = {
        (item["authority"], item["check"]): item for item in report["results"]
    }
    assert by_authority[("candidate", "bindings")]["ok"] is True
    assert by_authority[("trusted", "bindings")]["ok"] is False
    assert "Changed source surface" in by_authority[("trusted", "bindings")]["stdout"]
